"""Suíte rápida de regressão matemática e validação contra o XLS oficial."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from creditriskplus import CreditRiskPlus, data
from creditriskplus.simple_model import (
    analytic_loss_moments,
    calculate_loss_distribution_detailed,
)
from creditriskplus.retail import (
    RetailSimulationConfig,
    portfolio_regime_diagnostics,
    simulate_retail_portfolio,
    validate_portfolio_regime,
)
from extract_expected import PMF_PRINT_TOLERANCE, extract_references


class CreditRiskPlusMathematicalTests(unittest.TestCase):
    """Testa identidades que independem dos exemplos da planilha."""

    def test_poisson_limit_matches_closed_form(self):
        """Com severidade unitária, compara a recursão à PMF Poisson fechada."""

        # Com severidade de uma unidade, a perda em unidades é Poisson(mu).
        exposures = np.ones(3) * 100.0
        pd_mean = np.array([0.02, 0.03, 0.05])
        result = calculate_loss_distribution_detailed(
            exposures,
            pd_mean,
            np.zeros(3),
            np.zeros(3),
            unit_size=100.0,
            max_loss_dollars=2_000.0,
        )
        mu = pd_mean.sum()
        expected = np.empty_like(result.pmf)
        expected[0] = np.exp(-mu)
        for n in range(1, len(expected)):
            expected[n] = expected[n - 1] * mu / n
        np.testing.assert_allclose(result.pmf, expected, rtol=2e-14, atol=1e-16)

    def test_pmf_moments_match_analytic_formula(self):
        """Compara momentos somados da PMF às equações analíticas 115--118."""

        portfolio = data.create_example_1a_portfolio()
        result = calculate_loss_distribution_detailed(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
            max_loss_dollars=400_000_000,
        )
        mean, variance = analytic_loss_moments(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
            unit_size=result.unit_size,
        )
        losses = np.arange(len(result.pmf)) * result.unit_size
        pmf_mean = np.dot(losses, result.pmf)
        pmf_variance = np.dot((losses - mean) ** 2, result.pmf)
        self.assertLess(result.tail_mass_upper_bound, 1e-12)
        self.assertAlmostEqual(pmf_mean / mean, 1.0, places=10)
        self.assertAlmostEqual(pmf_variance / variance, 1.0, places=8)

    def test_log_recursion_survives_underflow_of_zero_loss_probability(self):
        """Mantém a massa perto do modo quando exp(-mu) não cabe em float64."""

        result = calculate_loss_distribution_detailed(
            [1.0],
            [0.01],
            [0.0],
            [0.0],
            unit_size=1.0,
            max_loss_dollars=1_400.0,
            obligor_counts=[80_000],  # mu = 800 e exp(-mu) subflui
        )
        losses = np.arange(len(result.pmf))
        self.assertAlmostEqual(result.pmf.sum(), 1.0, places=12)
        self.assertAlmostEqual(np.dot(losses, result.pmf), 800.0, places=8)

    def test_input_expected_loss_is_preserved_by_banding(self):
        """Garante que o ajuste de PD compense o arredondamento das bandas."""

        exposures = np.array([101.0, 249.0, 907.0])
        pd_mean = np.array([0.01, 0.08, 0.23])
        recovery = np.array([0.1, 0.4, 0.2])
        result = calculate_loss_distribution_detailed(
            exposures,
            pd_mean,
            pd_mean * 0.5,
            recovery,
            unit_size=100.0,
            max_loss_dollars=20_000.0,
        )
        exact = np.dot(exposures * (1.0 - recovery), pd_mean)
        self.assertAlmostEqual(result.expected_loss, exact, places=12)

    def test_invalid_sector_weights_are_rejected(self):
        """Rejeita uma decomposição que viole a equação 90."""

        with self.assertRaisesRegex(ValueError, "devem somar 1"):
            calculate_loss_distribution_detailed(
                [100, 200],
                [0.01, 0.02],
                [0.005, 0.01],
                [0, 0],
                sector_weights_matrix=[[0.4, 0.4], [0.5, 0.5]],
            )

    def test_group_multiplicity_equals_literal_expansion(self):
        """Demonstra que multiplicidades são compressão exata de pools iguais."""

        # Pools homogêneos são uma compressão exata, usada no notebook de safras.
        exposures = np.array([100.0, 250.0])
        pd_mean = np.array([0.02, 0.08])
        pd_std = pd_mean * 0.5
        counts = np.array([3, 4])
        grouped = calculate_loss_distribution_detailed(
            exposures,
            pd_mean,
            pd_std,
            np.zeros(2),
            unit_size=50.0,
            max_loss_dollars=5_000.0,
            obligor_counts=counts,
        )
        expanded = calculate_loss_distribution_detailed(
            np.repeat(exposures, counts),
            np.repeat(pd_mean, counts),
            np.repeat(pd_std, counts),
            np.zeros(counts.sum()),
            unit_size=50.0,
            max_loss_dollars=5_000.0,
        )
        np.testing.assert_allclose(grouped.pmf, expanded.pmf, rtol=0, atol=2e-16)
        self.assertEqual(grouped.expected_loss, expanded.expected_loss)

    def test_class_and_function_share_the_same_core(self):
        """Evita regressão para duas implementações matemáticas divergentes."""

        portfolio = data.create_example_3_4sector_portfolio()
        sector_columns = [column for column in portfolio if column.startswith("sector_weight_")]
        model = CreditRiskPlus(max_loss_units=800)
        model.set_portfolio(
            portfolio,
            sector_columns=sector_columns,
            idiosyncratic_sector_columns=["sector_weight_Specific"],
        )
        model.calculate_loss_distribution()
        direct = calculate_loss_distribution_detailed(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
            portfolio[sector_columns].to_numpy(),
            [sector_columns.index("sector_weight_Specific")],
            unit_size=model.unit_size,
            max_loss_dollars=model.max_loss_units * model.unit_size,
        )
        np.testing.assert_allclose(model.loss_pmf, direct.pmf, rtol=0, atol=0)
        contributions = model.calculate_risk_contributions()
        self.assertAlmostEqual(
            contributions["risk_contribution_std"].sum() / model.loss_std,
            1.0,
            places=12,
        )


def _example_portfolios():
    """Descreve cada aba do XLS: carteira, setores e setor específico."""

    example_2 = data.create_example_2_3sector_portfolio()
    example_3 = data.create_example_3_4sector_portfolio()
    return {
        "Example1A": (data.create_example_1a_portfolio(), None, None),
        "Example1B": (data.create_example_1a_23_obligor_portfolio(), None, None),
        "Example1C": (data.create_example_1c_portfolio(), None, None),
        "Example2": (example_2, _sector_columns(example_2), None),
        "Example3": (example_3, _sector_columns(example_3), "sector_weight_Specific"),
    }


def _sector_columns(portfolio):
    """Lista, em ordem, as colunas de alocação setorial de uma carteira."""

    return [column for column in portfolio if column.startswith("sector_weight_")]


class SpreadsheetRegressionTests(unittest.TestCase):
    """Compara os cinco exemplos com tudo o que o XLS oficial publica."""

    @classmethod
    def setUpClass(cls):
        """Lê uma vez os valores gravados no arquivo de referência."""

        cls.references = extract_references()
        cls.examples = _example_portfolios()

    def _distribution(self, sheet):
        """Calcula a distribuição do exemplo com folga de cauda suficiente."""

        portfolio, columns, specific = self.examples[sheet]
        return calculate_loss_distribution_detailed(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
            sector_weights_matrix=portfolio[columns].to_numpy() if columns else None,
            idiosyncratic_sector_indices=[columns.index(specific)] if specific else None,
            max_loss_dollars=250_000_000,
        )

    def test_expected_loss_matches_every_example(self):
        """A perda esperada é aditiva e deve bater à unidade monetária."""

        for sheet in self.examples:
            with self.subTest(sheet=sheet):
                result = self._distribution(sheet)
                self.assertAlmostEqual(
                    result.expected_loss,
                    self.references[sheet].expected_loss,
                    delta=0.51,
                )
                self.assertLess(result.tail_mass_upper_bound, 3e-7)

    def test_published_loss_distribution_matches_point_by_point(self):
        """Confere a PMF inteira, e não apenas alguns quantis dela.

        A planilha publica a distribuição ponto a ponto na grade ``n * L``. Bater
        em todos os pontos é a validação mais forte disponível: qualquer erro na
        recursão, no banding ou na convolução setorial apareceria aqui antes de
        aparecer em um percentil isolado.
        """

        for sheet, reference in self.references.items():
            with self.subTest(sheet=sheet):
                result = self._distribution(sheet)
                # A grade publicada é exatamente a grade do modelo.
                spacing = np.diff(reference.loss_amounts)
                np.testing.assert_allclose(spacing, result.unit_size)
                index = np.round(reference.loss_amounts / result.unit_size).astype(int)
                np.testing.assert_allclose(
                    result.pmf[index],
                    reference.loss_probabilities,
                    rtol=0.0,
                    atol=PMF_PRINT_TOLERANCE,
                )

    def test_every_published_percentile_matches(self):
        """Valida os oito percentis de cada exemplo, não apenas o de 99%.

        A comparação usa a interpolação linear da própria planilha. O quantil
        discreto continua sendo o padrão da API e cai no ponto adjacente da grade.
        """

        for sheet, reference in self.references.items():
            with self.subTest(sheet=sheet):
                result = self._distribution(sheet)
                for level, expected in reference.percentiles.items():
                    with self.subTest(percentile=level):
                        self.assertAlmostEqual(
                            result.quantile(level / 100.0, interpolate=True),
                            expected,
                            delta=1.0,
                        )

    def test_standard_deviation_matches_the_manual(self):
        """Confere o desvio padrão publicado no Apêndice B do manual."""

        # Manual CSFB 1997, seção B3.4: 12.668.742 para o Exemplo 1A.
        portfolio = data.create_example_1a_portfolio()
        _, variance = analytic_loss_moments(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
        )
        self.assertAlmostEqual(float(np.sqrt(variance)), 12_668_742.0, delta=1.0)

    def test_risk_contributions_reproduce_the_spreadsheet(self):
        """Reproduz a coluna de contribuições publicada em cada exemplo anual.

        A tolerância de 0,001% é o arredondamento dos próprios inteiros impressos
        na planilha: um erro de uma unidade sobre uma contribuição de 200 mil já
        vale 0,0005%.
        """

        for sheet in ("Example1A", "Example1B", "Example2", "Example3"):
            with self.subTest(sheet=sheet):
                portfolio, columns, specific = self.examples[sheet]
                model = CreditRiskPlus(max_loss_units=20_000)
                model.set_portfolio(
                    portfolio,
                    sector_columns=columns,
                    idiosyncratic_sector_columns=[specific] if specific else None,
                )
                model.calculate_loss_distribution()
                contributions = model.calculate_risk_contributions(
                    99, convention="spreadsheet"
                )["risk_contribution_99pct"].to_numpy()
                expected = self.references[sheet].obligor_risk_contributions
                np.testing.assert_allclose(
                    contributions, expected[: len(contributions)], rtol=1e-5
                )

    def test_manual_convention_stays_additive_and_differs_knowingly(self):
        """A convenção do manual soma a sigma e não deve virar a da planilha."""

        portfolio, _, _ = self.examples["Example1A"]
        model = CreditRiskPlus(max_loss_units=20_000)
        model.set_portfolio(portfolio)
        model.calculate_loss_distribution()
        manual = model.calculate_risk_contributions(99)
        spreadsheet = model.calculate_risk_contributions(99, convention="spreadsheet")

        # Equação 123: a decomposição do manual fecha exatamente em sigma.
        self.assertAlmostEqual(
            manual["risk_contribution_std"].sum() / model.loss_std, 1.0, places=12
        )
        # A da planilha fecha por construção, porque é reescalada.
        self.assertAlmostEqual(
            spreadsheet["risk_contribution_std"].sum() / model.loss_std, 1.0, places=12
        )
        # As duas divergem por contraparte onde o arredondamento de banda é maior.
        divergence = (
            manual["risk_contribution_99pct"] / spreadsheet["risk_contribution_99pct"]
            - 1.0
        ).abs().max()
        self.assertGreater(divergence, 0.01)

    def test_unknown_risk_contribution_convention_is_rejected(self):
        """Um nome de convenção inválido deve falhar em vez de escolher um padrão."""

        portfolio, _, _ = self.examples["Example1A"]
        model = CreditRiskPlus(max_loss_units=20_000)
        model.set_portfolio(portfolio)
        model.calculate_loss_distribution()
        with self.assertRaisesRegex(ValueError, "convention"):
            model.calculate_risk_contributions(99, convention="excel")


class MatureRetailPortfolioTests(unittest.TestCase):
    """Valida a formação do backbook anterior aos 24 meses reportados."""

    @classmethod
    def setUpClass(cls):
        """Simula uma única vez o cenário longitudinal determinístico."""

        cls.config = RetailSimulationConfig()
        cls.panel = simulate_retail_portfolio(cls.config)

    def test_opening_backbook_contains_explicit_history_and_card_tail(self):
        """Evita regressão para uma carteira iniciada vazia."""

        opening = self.panel[
            self.panel["observation_month"] == self.config.simulation_start
        ]
        self.assertTrue(opening["opening_backbook"].any())
        self.assertTrue(opening["backbook_tail"].any())
        self.assertGreaterEqual(opening.loc[opening.opening_backbook, "mob"].max(), 181)

    def test_portfolio_passes_pre_reporting_regime_gate(self):
        """Controla nível, mix, EL/EAD e distribuição etária antes do reporte."""

        diagnostics = validate_portfolio_regime(self.panel, self.config)
        self.assertTrue(diagnostics["passed"])
        self.assertLess(abs(diagnostics["annual_ead_change"]), 0.08)
        self.assertLess(diagnostics["age_distribution_tv"], 0.04)

    def test_reporting_window_is_independent_from_backbook_length(self):
        """Ancora o cenário macro no reporte, não no tamanho do histórico."""

        short_config = RetailSimulationConfig(backbook_months=60)
        short_panel = simulate_retail_portfolio(short_config)
        start = np.datetime64(self.config.reporting_start)
        long_macro = (
            self.panel[self.panel.observation_month >= start]
            .groupby("observation_month")["macro_multiplier"]
            .first()
            .iloc[: self.config.reporting_months]
        )
        short_macro = (
            short_panel[short_panel.observation_month >= start]
            .groupby("observation_month")["macro_multiplier"]
            .first()
            .iloc[: short_config.reporting_months]
        )
        np.testing.assert_allclose(long_macro.to_numpy(), short_macro.to_numpy())
        self.assertEqual(len(long_macro), self.config.reporting_months)

    def test_all_reported_cohorts_reach_the_same_vintage_horizon(self):
        """Evita comparar safras maduras com safras censuradas em MOBs menores."""

        from creditriskplus.retail import vintage_default_curves

        curves = vintage_default_curves(self.panel, self.config)
        maximum_mob = curves.groupby("cohort_month")["mob"].max()
        self.assertEqual(len(maximum_mob), self.config.reporting_months)
        self.assertTrue(
            (maximum_mob == self.config.vintage_performance_months).all()
        )

    def test_longer_vintage_does_not_rewrite_reported_events(self):
        """Separa a aleatoriedade do futuro dos defaults já reportados."""

        short_config = RetailSimulationConfig(vintage_performance_months=12)
        short_panel = simulate_retail_portfolio(short_config)
        report_end = pd.Timestamp(self.config.reporting_start) + pd.DateOffset(
            months=self.config.reporting_months - 1
        )
        keys = [
            "observation_month",
            "cohort_month",
            "product",
            "risk_band",
            "obligor_count",
            "realized_defaults",
            "realized_exits",
        ]
        long_report = self.panel[self.panel.observation_month <= report_end][keys]
        short_report = short_panel[short_panel.observation_month <= report_end][keys]
        pd.testing.assert_frame_equal(
            long_report.reset_index(drop=True),
            short_report.reset_index(drop=True),
        )

    def test_diagnostic_detects_an_immature_portfolio(self):
        """Demonstra que o controle rejeita uma perda material de estoque."""

        altered = self.panel.copy()
        report_month = np.datetime64(self.config.reporting_start)
        mask = altered.observation_month == report_month
        altered.loc[mask, "obligor_count"] //= 2
        diagnostics = portfolio_regime_diagnostics(altered, self.config)
        self.assertFalse(diagnostics["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
