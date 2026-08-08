"""Simulação reprodutível de uma carteira PF brasileira por safras.

O módulo produz dados sintéticos, não dados de clientes reais. Cartão de crédito
e crédito pessoal parcelado têm curvas distintas de utilização, amortização,
saída e risco. As linhas são *pools* homogêneos; ``obligor_count`` informa sua
multiplicidade. No núcleo CreditRisk+, essa representação é matematicamente
equivalente a repetir cada contrato do pool, sem o custo de memória da expansão.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .simple_model import (
    analytic_loss_moments,
    calculate_loss_distribution_detailed,
)


PRODUCTS = ("Cartão de crédito", "Crédito pessoal parcelado")
RISK_BANDS = ("A", "B", "C", "D")
SECTOR_COLUMNS = (
    "sector_weight_specific",
    "sector_weight_macro",
    "sector_weight_card",
    "sector_weight_installment",
)

BASE_PD_12M = {
    "Cartão de crédito": np.array([0.012, 0.035, 0.080, 0.180]),
    "Crédito pessoal parcelado": np.array([0.018, 0.045, 0.100, 0.220]),
}
BASE_MIX = {
    "Cartão de crédito": np.array([0.36, 0.34, 0.22, 0.08]),
    "Crédito pessoal parcelado": np.array([0.30, 0.35, 0.25, 0.10]),
}
ANNUAL_CLOSURE = {
    "Cartão de crédito": np.array([0.10, 0.11, 0.13, 0.16]),
    "Crédito pessoal parcelado": np.array([0.12, 0.13, 0.15, 0.18]),
}
RECOVERY = {"Cartão de crédito": 0.15, "Crédito pessoal parcelado": 0.22}
PD_CV = {"Cartão de crédito": 0.65, "Crédito pessoal parcelado": 0.55}


@dataclass(frozen=True)
class RetailSimulationConfig:
    """Controles do cenário longitudinal; valores monetários estão em reais.

    O backbook histórico cria a distribuição de idades de uma carteira madura.
    Depois dele, ``burn_in_months`` permite verificar a estabilidade antes dos
    ``reporting_months`` divulgados. Crescimento e choque são ancorados na data
    de início do reporte e, portanto, não mudam quando o backbook é ampliado.
    """

    reporting_start: str = "2023-01-01"
    reporting_months: int = 24
    vintage_performance_months: int = 60
    backbook_months: int = 180
    burn_in_months: int = 12
    seed: int = 20260808
    average_monthly_card_originations: int = 150
    average_monthly_installment_originations: int = 110
    annual_origination_growth: float = 0.05
    shock_start_month: int = 6
    unit_size: float = 250.0
    tail_tolerance: float = 1e-8
    max_pre_report_level_change: float = 0.08
    max_pre_report_el_rate_change: float = 0.003
    max_pre_report_mix_change: float = 0.03
    max_pre_report_age_tv: float = 0.04

    @property
    def simulation_start(self) -> pd.Timestamp:
        """Primeiro fechamento do burn-in, anterior ao início do reporte."""

        return pd.Timestamp(self.reporting_start) - pd.DateOffset(months=self.burn_in_months)

    @property
    def n_months(self) -> int:
        """Fechamentos necessários para maturar a última safra reportada."""

        return (
            self.burn_in_months
            + self.reporting_months
            + self.vintage_performance_months
        )


def _macro_multiplier(
    month: pd.Timestamp,
    months_from_reporting_start: int,
    config: RetailSimulationConfig,
) -> float:
    """Ciclo sintético ancorado no reporte, sem contaminar o backbook.

    A sazonalidade depende do mês civil. O choque começa somente depois do
    início do reporte; aumentar o histórico não desloca o cenário econômico.
    """

    seasonal = 1.0 + 0.05 * np.sin(2.0 * np.pi * (month.month - 1) / 12.0)
    shock_offset = months_from_reporting_start - config.shock_start_month
    if 0 <= shock_offset <= 4:
        shock = [1.15, 1.35, 1.65, 1.45, 1.25][shock_offset]
    elif 5 <= shock_offset <= 9:
        shock = 1.0 + 0.18 * (10 - shock_offset) / 5.0
    else:
        shock = 1.0
    return float(seasonal * shock)


def _seasoning_multiplier(mob: int, product: str) -> float:
    """Modela o amadurecimento do risco após a originação (months on book)."""

    if product == "Cartão de crédito":
        # A utilização e a seleção adversa aparecem gradualmente até cerca de 1 ano.
        return float(0.65 + 0.70 * (1.0 - np.exp(-mob / 6.0)))
    # Parcelados têm risco baixo nos primeiros pagamentos e pico intermediário.
    return float(0.55 + 0.75 * (1.0 - np.exp(-mob / 5.0)))


def _ead_per_obligor(product: str, risk_index: int, mob: int, macro: float) -> float:
    """Calcula EAD média: utilização rotativa no cartão e saldo amortizado no parcelado."""

    if product == "Cartão de crédito":
        base = [2_400.0, 3_300.0, 4_300.0, 5_200.0][risk_index]
        ramp = 0.72 + 0.28 * (1.0 - np.exp(-mob / 4.0))
        utilization_stress = 1.0 + 0.10 * max(macro - 1.0, 0.0)
        return float(base * ramp * utilization_stress)

    original_balance = [7_500.0, 9_000.0, 10_500.0, 12_000.0][risk_index]
    contractual_term = [30, 30, 27, 24][risk_index]
    remaining_fraction = max(0.0, 1.0 - mob / contractual_term)
    return float(original_balance * remaining_fraction)


def _sector_weights(product: str) -> tuple[float, float, float, float]:
    """Decompõe a variância entre risco específico, macro e fator do produto."""

    if product == "Cartão de crédito":
        return 0.15, 0.45, 0.40, 0.0
    return 0.15, 0.45, 0.0, 0.40


def _monthly_retention(product: str, risk_index: int, mob: int) -> float:
    """Sobrevivência mensal neutra usada para reconstruir o backbook maduro."""

    pd_12m = min(
        BASE_PD_12M[product][risk_index] * _seasoning_multiplier(mob, product),
        0.45,
    )
    monthly_pd = 1.0 - (1.0 - pd_12m) ** (1.0 / 12.0)
    monthly_exit = 1.0 - (1.0 - ANNUAL_CLOSURE[product][risk_index]) ** (1.0 / 12.0)
    return float((1.0 - monthly_pd) * (1.0 - monthly_exit))


def _survival_probabilities(product: str, risk_index: int, max_age: int) -> np.ndarray:
    """Retorna S[a], probabilidade de um contrato chegar ativo ao MOB ``a``."""

    survival = np.ones(max_age + 1, dtype=float)
    for age in range(1, max_age + 1):
        survival[age] = survival[age - 1] * _monthly_retention(
            product, risk_index, age - 1
        )
    return survival


def _calendar_month_distance(month: pd.Timestamp, origin: pd.Timestamp) -> int:
    """Diferença inteira em meses, sem depender do número de dias."""

    return (month.year - origin.year) * 12 + month.month - origin.month


def simulate_retail_portfolio(config: RetailSimulationConfig) -> pd.DataFrame:
    """Gera painel mensal a partir de uma carteira inicial madura.

    O estoque inicial contém safras históricas sobreviventes. Para cartão, a
    parcela anterior ao histórico explícito é mantida em um pool de cauda já
    plenamente maturado. Depois da abertura, defaults e saídas são simulados
    sequencialmente. A PD do CreditRisk+ é prospectiva de 12 meses; eventos
    realizados usam a probabilidade mensal equivalente.
    """

    reporting_start = pd.Timestamp(config.reporting_start)
    if not reporting_start.is_month_start:
        raise ValueError("reporting_start deve ser o primeiro dia de um mês.")
    if config.reporting_months < 24:
        raise ValueError("reporting_months deve ser pelo menos 24.")
    if config.vintage_performance_months < 12:
        raise ValueError("vintage_performance_months deve ser pelo menos 12.")
    if config.backbook_months < 36:
        raise ValueError("backbook_months deve ser pelo menos 36.")
    if config.burn_in_months < 12:
        raise ValueError("burn_in_months deve ser pelo menos 12.")
    if config.annual_origination_growth <= -1.0:
        raise ValueError("annual_origination_growth deve ser maior que -100%.")
    if min(
        config.average_monthly_card_originations,
        config.average_monthly_installment_originations,
    ) <= 0:
        raise ValueError("As originações médias devem ser positivas.")
    if config.unit_size <= 0.0 or not 0.0 < config.tail_tolerance < 1.0:
        raise ValueError("unit_size e tail_tolerance devem ter domínios válidos.")

    # Fluxos independentes garantem que ampliar apenas o horizonte de vintage
    # não reescreva defaults já realizados na janela reportada.
    population_seed, event_seed = np.random.SeedSequence(config.seed).spawn(2)
    population_rng = np.random.default_rng(population_seed)
    event_rng = np.random.default_rng(event_seed)
    months = pd.date_range(config.simulation_start, periods=config.n_months, freq="MS")
    average_originations = {
        "Cartão de crédito": config.average_monthly_card_originations,
        "Crédito pessoal parcelado": config.average_monthly_installment_originations,
    }

    # Reconstrói as safras anteriores à abertura. S[a] incorpora defaults e
    # encerramentos neutros até o MOB a, preservando uma pirâmide de idades.
    maximum_survival_age = max(config.backbook_months + 1, 1_200)
    survival = {
        (product, risk_index): _survival_probabilities(
            product, risk_index, maximum_survival_age
        )
        for product in PRODUCTS
        for risk_index in range(len(RISK_BANDS))
    }
    pools: list[dict] = []
    for age in range(1, config.backbook_months + 1):
        cohort_month = config.simulation_start - pd.DateOffset(months=age)
        seasonal = 1.12 if cohort_month.month in (11, 12) else 1.0
        for product in PRODUCTS:
            total = int(population_rng.poisson(average_originations[product] * seasonal))
            originated = population_rng.multinomial(
                total, BASE_MIX[product] / BASE_MIX[product].sum()
            )
            for risk_index, count in enumerate(originated):
                active = int(
                    population_rng.binomial(
                        int(count), survival[(product, risk_index)][age]
                    )
                )
                if active and _ead_per_obligor(product, risk_index, age, 1.0) > 0.0:
                    pools.append(
                        {
                            "cohort_index": -age,
                            "cohort_month": cohort_month,
                            "product": product,
                            "risk_band": RISK_BANDS[risk_index],
                            "risk_index": risk_index,
                            "originated_count": int(count),
                            "active_count": active,
                            "opening_backbook": True,
                            "backbook_tail": False,
                        }
                    )

    # Cartões anteriores ao histórico explícito não são descartados. Como EAD
    # e seasoning já convergiram no MOB 180, a soma das sobrevivências antigas
    # é um único pool homogêneo, sem aproximação adicional na PGF CreditRisk+.
    for risk_index, risk_band in enumerate(RISK_BANDS):
        mean_band_originations = (
            average_originations["Cartão de crédito"]
            * 1.02  # média anual da sazonalidade de novembro/dezembro
            * BASE_MIX["Cartão de crédito"][risk_index]
        )
        tail_survival = survival[("Cartão de crédito", risk_index)][
            config.backbook_months + 1 :
        ].sum()
        tail_active = int(round(mean_band_originations * tail_survival))
        if tail_active:
            tail_age = config.backbook_months + 1
            pools.append(
                {
                    "cohort_index": -tail_age,
                    "cohort_month": config.simulation_start
                    - pd.DateOffset(months=tail_age),
                    "product": "Cartão de crédito",
                    "risk_band": risk_band,
                    "risk_index": risk_index,
                    "originated_count": tail_active,
                    "active_count": tail_active,
                    "opening_backbook": True,
                    "backbook_tail": True,
                }
            )

    # O burn-in usa volume estável. O crescimento comercial começa no reporte;
    # alterar o tamanho do backbook não muda originação nem cenário macro.
    for cohort_index, cohort_month in enumerate(months):
        report_offset = _calendar_month_distance(cohort_month, reporting_start)
        macro_at_origination = _macro_multiplier(cohort_month, report_offset, config)
        for product in PRODUCTS:
            growth_months = max(report_offset, 0)
            growth = (1.0 + config.annual_origination_growth) ** (growth_months / 12.0)
            supply = 1.0 / (1.0 + 0.35 * max(macro_at_origination - 1.0, 0.0))
            seasonal = 1.12 if cohort_month.month in (11, 12) else 1.0
            total = int(
                population_rng.poisson(
                    average_originations[product] * growth * supply * seasonal
                )
            )

            # Underwriting mais restritivo reduz D e eleva A durante o choque.
            mix = BASE_MIX[product].copy()
            tightening = min(
                0.035 * max(macro_at_origination - 1.0, 0.0) / 0.65, 0.035
            )
            mix[0] += tightening
            mix[3] -= tightening
            originated = population_rng.multinomial(total, mix / mix.sum())
            for risk_index, count in enumerate(originated):
                if count:
                    pools.append(
                        {
                            "cohort_index": cohort_index,
                            "cohort_month": cohort_month,
                            "product": product,
                            "risk_band": RISK_BANDS[risk_index],
                            "risk_index": risk_index,
                            "originated_count": int(count),
                            "active_count": int(count),
                            "opening_backbook": False,
                            "backbook_tail": False,
                        }
                    )

    rows: list[dict] = []
    for observation_index, observation_month in enumerate(months):
        report_offset = _calendar_month_distance(observation_month, reporting_start)
        macro = _macro_multiplier(observation_month, report_offset, config)
        for pool in pools:
            if pool["cohort_index"] > observation_index or pool["active_count"] <= 0:
                continue
            mob = observation_index - pool["cohort_index"]
            product = pool["product"]
            risk_index = pool["risk_index"]
            ead = _ead_per_obligor(product, risk_index, mob, macro)
            if ead <= 0:
                pool["active_count"] = 0
                continue

            pd_12m = min(
                BASE_PD_12M[product][risk_index]
                * _seasoning_multiplier(mob, product)
                * macro,
                0.45,
            )
            monthly_pd = 1.0 - (1.0 - pd_12m) ** (1.0 / 12.0)
            active = pool["active_count"]
            defaults = int(event_rng.binomial(active, monthly_pd))
            remaining = active - defaults
            monthly_exit = 1.0 - (
                1.0 - ANNUAL_CLOSURE[product][risk_index]
            ) ** (1.0 / 12.0)
            exits = int(event_rng.binomial(remaining, monthly_exit))

            weight_specific, weight_macro, weight_card, weight_installment = (
                _sector_weights(product)
            )
            rows.append(
                {
                    "observation_month": observation_month,
                    "cohort_month": pool["cohort_month"],
                    "mob": mob,
                    "product": product,
                    "risk_band": pool["risk_band"],
                    "originated_count": pool["originated_count"],
                    "obligor_count": active,
                    "ead_per_obligor": ead,
                    "pd_12m": pd_12m,
                    "std_pd_12m": pd_12m * PD_CV[product],
                    "recovery_rate": RECOVERY[product],
                    "realized_defaults": defaults,
                    "realized_exits": exits,
                    "macro_multiplier": macro,
                    "opening_backbook": pool["opening_backbook"],
                    "backbook_tail": pool["backbook_tail"],
                    "sector_weight_specific": weight_specific,
                    "sector_weight_macro": weight_macro,
                    "sector_weight_card": weight_card,
                    "sector_weight_installment": weight_installment,
                }
            )
            pool["active_count"] = remaining - exits

    return pd.DataFrame(rows)


def _run_snapshot(snapshot: pd.DataFrame, config: RetailSimulationConfig):
    """Executa o modelo e amplia a cauda até atender à tolerância configurada."""

    exposures = snapshot["ead_per_obligor"].to_numpy()
    mean_rates = snapshot["pd_12m"].to_numpy()
    std_rates = snapshot["std_pd_12m"].to_numpy()
    recoveries = snapshot["recovery_rate"].to_numpy()
    weights = snapshot[list(SECTOR_COLUMNS)].to_numpy()
    counts = snapshot["obligor_count"].to_numpy()

    expected_loss, variance = analytic_loss_moments(
        exposures,
        mean_rates,
        std_rates,
        recoveries,
        sector_weights_matrix=weights,
        idiosyncratic_sector_indices=[0],
        unit_size=config.unit_size,
        obligor_counts=counts,
    )
    standard_deviation = float(np.sqrt(variance))
    max_loss = max(expected_loss + 10.0 * standard_deviation, 500 * config.unit_size)

    for _ in range(4):
        result = calculate_loss_distribution_detailed(
            exposures,
            mean_rates,
            std_rates,
            recoveries,
            sector_weights_matrix=weights,
            idiosyncratic_sector_indices=[0],
            unit_size=config.unit_size,
            max_loss_dollars=max_loss,
            obligor_counts=counts,
        )
        if result.tail_mass_upper_bound <= config.tail_tolerance and result.cdf[-1] >= 0.999:
            break
        max_loss *= 1.8
    else:
        raise RuntimeError("A distribuição não convergiu dentro das quatro ampliações de cauda.")

    return result, variance


def portfolio_regime_diagnostics(
    panel: pd.DataFrame,
    config: RetailSimulationConfig,
) -> pd.Series:
    """Compara dois fechamentos sazonais equivalentes antes do reporte.

    A comparação usa o início do burn-in e o início do reporte, separados por
    12 meses. Além de nível, controla mix de produto, intensidade de risco e a
    distribuição de EAD por idade. Assim, crescimento de estoque não pode ser
    confundido silenciosamente com uma carteira madura.
    """

    report_month = pd.Timestamp(config.reporting_start)
    baseline_month = report_month - pd.DateOffset(months=12)
    baseline = panel[panel["observation_month"] == baseline_month].copy()
    report = panel[panel["observation_month"] == report_month].copy()
    if baseline.empty or report.empty:
        raise ValueError("O painel não contém 12 meses completos antes do reporte.")

    def summarize(snapshot: pd.DataFrame) -> dict:
        gross_ead_pool = snapshot["obligor_count"] * snapshot["ead_per_obligor"]
        el_pool = (
            gross_ead_pool
            * (1.0 - snapshot["recovery_rate"])
            * snapshot["pd_12m"]
        )
        product_share = gross_ead_pool.groupby(snapshot["product"]).sum()
        product_share = product_share / product_share.sum()
        age_bucket = pd.cut(
            snapshot["mob"],
            bins=[-1, 5, 11, 23, 59, np.inf],
            labels=["0–5", "6–11", "12–23", "24–59", "60+"],
        )
        age_share = gross_ead_pool.groupby(age_bucket, observed=False).sum()
        age_share = age_share / age_share.sum()
        return {
            "gross_ead": float(gross_ead_pool.sum()),
            "active": float(snapshot["obligor_count"].sum()),
            "el_rate": float(el_pool.sum() / gross_ead_pool.sum()),
            "product_share": product_share,
            "age_share": age_share,
        }

    base_summary = summarize(baseline)
    report_summary = summarize(report)
    product_change = report_summary["product_share"].subtract(
        base_summary["product_share"], fill_value=0.0
    )
    age_change = report_summary["age_share"].subtract(
        base_summary["age_share"], fill_value=0.0
    )
    diagnostics = pd.Series(
        {
            "annual_ead_change": report_summary["gross_ead"]
            / base_summary["gross_ead"]
            - 1.0,
            "annual_active_change": report_summary["active"] / base_summary["active"]
            - 1.0,
            "el_rate_change": report_summary["el_rate"] - base_summary["el_rate"],
            "max_product_share_change": float(product_change.abs().max()),
            "age_distribution_tv": float(0.5 * age_change.abs().sum()),
        },
        name="value",
    )
    diagnostics["passed"] = bool(
        abs(diagnostics["annual_ead_change"])
        <= config.max_pre_report_level_change
        and abs(diagnostics["annual_active_change"])
        <= config.max_pre_report_level_change
        and abs(diagnostics["el_rate_change"])
        <= config.max_pre_report_el_rate_change
        and diagnostics["max_product_share_change"]
        <= config.max_pre_report_mix_change
        and diagnostics["age_distribution_tv"] <= config.max_pre_report_age_tv
    )
    return diagnostics


def validate_portfolio_regime(
    panel: pd.DataFrame,
    config: RetailSimulationConfig,
) -> pd.Series:
    """Retorna os diagnósticos ou interrompe a análise se o regime não convergiu."""

    diagnostics = portfolio_regime_diagnostics(panel, config)
    if not bool(diagnostics["passed"]):
        raise RuntimeError(
            "A carteira não passou nos controles de regime; amplie ou recalibre o backbook."
        )
    return diagnostics


def run_creditriskplus_over_time(
    panel: pd.DataFrame,
    config: RetailSimulationConfig,
) -> pd.DataFrame:
    """Aplica CreditRisk+ aos fechamentos reportados após validar o regime."""

    validate_portfolio_regime(panel, config)
    reporting_start = pd.Timestamp(config.reporting_start)
    months = sorted(panel["observation_month"].unique())
    reported_months = [month for month in months if month >= reporting_start][
        : config.reporting_months
    ]
    metrics: list[dict] = []
    for month in reported_months:
        snapshot = panel[panel["observation_month"] == month]
        result, variance = _run_snapshot(snapshot, config)
        net_ead = np.sum(
            snapshot["obligor_count"]
            * snapshot["ead_per_obligor"]
            * (1.0 - snapshot["recovery_rate"])
        )
        var_95 = result.quantile(0.95)
        var_99 = result.quantile(0.99)
        var_999 = result.quantile(0.999)
        metrics.append(
            {
                "observation_month": month,
                "active_obligors": int(snapshot["obligor_count"].sum()),
                "gross_ead": float(np.sum(snapshot["obligor_count"] * snapshot["ead_per_obligor"])),
                "net_ead": float(net_ead),
                "expected_loss": result.expected_loss,
                "loss_std": float(np.sqrt(variance)),
                "var_95": var_95,
                "var_99": var_99,
                "var_999": var_999,
                "economic_capital_99": var_99 - result.expected_loss,
                "economic_capital_999": var_999 - result.expected_loss,
                "tail_mass": result.tail_mass_upper_bound,
                "macro_multiplier": float(snapshot["macro_multiplier"].iloc[0]),
            }
        )
    return pd.DataFrame(metrics)


def run_creditriskplus_by_cohort(
    panel: pd.DataFrame,
    config: RetailSimulationConfig,
) -> pd.DataFrame:
    """Aplica CreditRisk+ na fotografia de originação das 24 safras reportadas."""

    reporting_start = pd.Timestamp(config.reporting_start)
    origin = panel[(panel["mob"] == 0) & (~panel["opening_backbook"])].copy()
    cohorts = [
        cohort
        for cohort in sorted(origin["cohort_month"].unique())
        if cohort >= reporting_start
    ][: config.reporting_months]
    metrics: list[dict] = []
    for cohort in cohorts:
        snapshot = origin[origin["cohort_month"] == cohort]
        result, variance = _run_snapshot(snapshot, config)
        var_99 = result.quantile(0.99)
        metrics.append(
            {
                "cohort_month": cohort,
                "originated_obligors": int(snapshot["obligor_count"].sum()),
                "origination_ead": float(
                    np.sum(snapshot["obligor_count"] * snapshot["ead_per_obligor"])
                ),
                "expected_loss": result.expected_loss,
                "loss_std": float(np.sqrt(variance)),
                "var_99": var_99,
                "economic_capital_99": var_99 - result.expected_loss,
                "tail_mass": result.tail_mass_upper_bound,
                "macro_multiplier": float(snapshot["macro_multiplier"].iloc[0]),
            }
        )
    return pd.DataFrame(metrics)


def vintage_default_curves(panel: pd.DataFrame, config: RetailSimulationConfig) -> pd.DataFrame:
    """Constrói curvas até um MOB comum para todas as safras reportadas."""

    reporting_start = pd.Timestamp(config.reporting_start)
    cohorts = [
        cohort
        for cohort in sorted(panel.loc[~panel["opening_backbook"], "cohort_month"].unique())
        if cohort >= reporting_start
    ][: config.reporting_months]
    selected = panel[
        panel["cohort_month"].isin(cohorts)
        & (panel["mob"] <= config.vintage_performance_months)
    ]
    grouped = (
        selected.groupby(["cohort_month", "mob"], as_index=False)
        .agg(
            defaults=("realized_defaults", "sum"),
            originated=("originated_count", "sum"),
        )
        .sort_values(["cohort_month", "mob"])
    )
    # originated aparece em todos os MOBs; max recupera o denominador único da safra.
    grouped["cumulative_defaults"] = grouped.groupby("cohort_month")["defaults"].cumsum()
    # O denominador correto está na fotografia MOB 0; somar o painel repetiria
    # o mesmo pool em todas as idades observadas.
    denominators = (
        selected[selected["mob"] == 0].groupby("cohort_month")["originated_count"].sum()
    )
    grouped["cumulative_default_rate"] = (
        grouped["cumulative_defaults"] / grouped["cohort_month"].map(denominators)
    )
    return grouped
