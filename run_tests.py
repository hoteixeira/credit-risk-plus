"""Suíte rápida de regressão matemática e validação contra o XLS oficial."""

from __future__ import annotations

import unittest

import numpy as np

from creditriskplus import CreditRiskPlus, data
from creditriskplus.simple_model import (
    analytic_loss_moments,
    calculate_loss_distribution_detailed,
)
from extract_expected import extract_kpis


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


class SpreadsheetRegressionTests(unittest.TestCase):
    """Compara os quatro exemplos de um ano com os outputs do XLS oficial."""

    @classmethod
    def setUpClass(cls):
        """Lê uma vez os KPIs gravados no arquivo de referência."""

        cls.references = extract_kpis()

    def _assert_example(self, sheet, portfolio, weights=None, idiosyncratic=None):
        """Executa uma regressão de EL, VaR interpolado e massa de cauda."""

        result = calculate_loss_distribution_detailed(
            portfolio.exposure,
            portfolio.mean_default_rate,
            portfolio.std_default_rate,
            np.zeros(len(portfolio)),
            sector_weights_matrix=weights,
            idiosyncratic_sector_indices=idiosyncratic,
            max_loss_dollars=250_000_000,
        )
        reference = self.references[sheet]
        self.assertAlmostEqual(result.expected_loss, reference["EL"], delta=0.51)
        self.assertAlmostEqual(
            result.quantile(0.99, interpolate=True),
            reference["VaR99"],
            delta=1.0,
        )
        self.assertLess(result.tail_mass_upper_bound, 3e-7)

    def test_example_1a(self):
        """Valida a carteira de 25 contrapartes e um fator."""

        self._assert_example("Example1A", data.create_example_1a_portfolio())

    def test_example_1b(self):
        """Valida a retirada das duas maiores exposições."""

        self._assert_example("Example1B", data.create_example_1a_23_obligor_portfolio())

    def test_example_1c(self):
        """Valida o perfil virtual de três anos da planilha."""

        self._assert_example("Example1C", data.create_example_1c_portfolio())

    def test_example_2(self):
        """Valida três setores geográficos exclusivos."""

        portfolio = data.create_example_2_3sector_portfolio()
        columns = [column for column in portfolio if column.startswith("sector_weight_")]
        self._assert_example("Example2", portfolio, portfolio[columns].to_numpy())

    def test_example_3_specific_sector(self):
        """Valida pesos fracionários e o limite Poisson do setor específico."""

        portfolio = data.create_example_3_4sector_portfolio()
        columns = [column for column in portfolio if column.startswith("sector_weight_")]
        self._assert_example(
            "Example3",
            portfolio,
            portfolio[columns].to_numpy(),
            [columns.index("sector_weight_Specific")],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
