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


@dataclass(frozen=True)
class RetailSimulationConfig:
    """Controles do cenário longitudinal; valores monetários estão em reais."""

    start: str = "2022-01-01"
    n_months: int = 36
    warmup_months: int = 12
    seed: int = 20260808
    average_monthly_card_originations: int = 150
    average_monthly_installment_originations: int = 110
    unit_size: float = 250.0
    tail_tolerance: float = 1e-8


def _macro_multiplier(month_index: int) -> float:
    """Ciclo sintético: sazonalidade, choque transitório e recuperação gradual."""

    seasonal = 1.0 + 0.05 * np.sin(2.0 * np.pi * month_index / 12.0)
    if 18 <= month_index <= 22:
        shock = [1.15, 1.35, 1.65, 1.45, 1.25][month_index - 18]
    elif 23 <= month_index <= 27:
        shock = 1.0 + 0.18 * (28 - month_index) / 5.0
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


def simulate_retail_portfolio(config: RetailSimulationConfig) -> pd.DataFrame:
    """Gera o painel mensal de pools por safra, produto e faixa de risco.

    Defaults e saídas são simulados sequencialmente com uma semente fixa. A PD
    usada pelo CreditRisk+ é prospectiva de 12 meses; os defaults realizados
    usam a probabilidade mensal equivalente, o que evita confundir horizontes.
    """

    if config.n_months <= config.warmup_months:
        raise ValueError("n_months deve ser maior que warmup_months.")
    rng = np.random.default_rng(config.seed)
    months = pd.date_range(config.start, periods=config.n_months, freq="MS")

    base_pd_12m = {
        "Cartão de crédito": np.array([0.012, 0.035, 0.080, 0.180]),
        "Crédito pessoal parcelado": np.array([0.018, 0.045, 0.100, 0.220]),
    }
    base_mix = {
        "Cartão de crédito": np.array([0.36, 0.34, 0.22, 0.08]),
        "Crédito pessoal parcelado": np.array([0.30, 0.35, 0.25, 0.10]),
    }
    average_originations = {
        "Cartão de crédito": config.average_monthly_card_originations,
        "Crédito pessoal parcelado": config.average_monthly_installment_originations,
    }
    annual_closure = {
        "Cartão de crédito": np.array([0.10, 0.11, 0.13, 0.16]),
        "Crédito pessoal parcelado": np.array([0.12, 0.13, 0.15, 0.18]),
    }
    recovery = {"Cartão de crédito": 0.15, "Crédito pessoal parcelado": 0.22}
    pd_cv = {"Cartão de crédito": 0.65, "Crédito pessoal parcelado": 0.55}

    # Cada item acompanha um pool do nascimento até seu esgotamento.
    pools: list[dict] = []
    for cohort_index, cohort_month in enumerate(months):
        macro_at_origination = _macro_multiplier(cohort_index)
        for product in PRODUCTS:
            # A oferta contrai durante o choque e cresce suavemente fora dele.
            growth = 1.0 + 0.006 * cohort_index
            supply = 1.0 / (1.0 + 0.35 * max(macro_at_origination - 1.0, 0.0))
            seasonal = 1.0 + (0.12 if cohort_month.month in (11, 12) else 0.0)
            total = int(rng.poisson(average_originations[product] * growth * supply * seasonal))

            # Underwriting mais restritivo reduz D e eleva A durante o choque.
            mix = base_mix[product].copy()
            tightening = min(0.035 * max(macro_at_origination - 1.0, 0.0) / 0.65, 0.035)
            mix[0] += tightening
            mix[3] -= tightening
            originated = rng.multinomial(total, mix / mix.sum())

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
                        }
                    )

    rows: list[dict] = []
    for observation_index, observation_month in enumerate(months):
        macro = _macro_multiplier(observation_index)
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
                base_pd_12m[product][risk_index]
                * _seasoning_multiplier(mob, product)
                * macro,
                0.45,
            )
            monthly_pd = 1.0 - (1.0 - pd_12m) ** (1.0 / 12.0)
            active = pool["active_count"]
            defaults = int(rng.binomial(active, monthly_pd))
            remaining = active - defaults
            monthly_exit = 1.0 - (1.0 - annual_closure[product][risk_index]) ** (1.0 / 12.0)
            exits = int(rng.binomial(remaining, monthly_exit))

            weight_specific, weight_macro, weight_card, weight_installment = _sector_weights(product)
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
                    "std_pd_12m": pd_12m * pd_cv[product],
                    "recovery_rate": recovery[product],
                    "realized_defaults": defaults,
                    "realized_exits": exits,
                    "macro_multiplier": macro,
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


def run_creditriskplus_over_time(
    panel: pd.DataFrame,
    config: RetailSimulationConfig,
) -> pd.DataFrame:
    """Aplica CreditRisk+ a cada fechamento mensal após o ramp-up."""

    months = sorted(panel["observation_month"].unique())
    reported_months = months[config.warmup_months :]
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

    origin = panel[panel["mob"] == 0].copy()
    cohorts = sorted(origin["cohort_month"].unique())[config.warmup_months :]
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
    """Constrói curvas acumuladas observadas por MOB para as safras reportadas."""

    cohorts = sorted(panel["cohort_month"].unique())[config.warmup_months :]
    selected = panel[panel["cohort_month"].isin(cohorts)]
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
