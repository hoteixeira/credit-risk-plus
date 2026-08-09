"""Interface orientada a objetos para o núcleo matemático do CreditRisk+.

A classe deste módulo não mantém uma segunda implementação das equações. Ela
delega o cálculo a :mod:`creditriskplus.simple_model`, evitando que as APIs
funcional e orientada a objetos produzam distribuições diferentes.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .simple_model import (
    LossDistributionResult,
    _compute_unit_size,
    analytic_loss_moments,
    calculate_loss_distribution_detailed,
    loss_quantile,
    systematic_risk_term,
)


class CreditRiskPlus:
    """Modelo CreditRisk+ para perdas por default de uma carteira de crédito.

    Parameters
    ----------
    unit_size:
        Unidade monetária ``L`` usada no banding. Se ``None``, adota a regra da
        planilha oficial: ``ceil(max(exposição líquida) / 100)``.
    max_loss_units:
        Quantidade de pontos da distribuição calculada após o zero.
    """

    def __init__(self, unit_size: float | None = None, max_loss_units: int = 20_000):
        """Inicializa parâmetros numéricos sem calcular ou carregar uma carteira."""

        if unit_size is not None and unit_size <= 0:
            raise ValueError("unit_size deve ser positivo ou None.")
        if max_loss_units < 1:
            raise ValueError("max_loss_units deve ser positivo.")

        self.unit_size = unit_size
        self.max_loss_units = int(max_loss_units)
        self.obligors: pd.DataFrame | None = None
        self.num_obligors = 0
        self.sectors: dict[str, int] = {}
        self.num_sectors = 0
        self.sector_columns: list[str] = []
        self.idiosyncratic_sector_indices: list[int] = []

        # Atributos preenchidos somente após calculate_loss_distribution().
        self.result: LossDistributionResult | None = None
        self.loss_pmf: np.ndarray | None = None
        self.loss_cdf: np.ndarray | None = None
        self.expected_loss: float | None = None
        self.loss_variance: float | None = None
        self.loss_std: float | None = None
        self.tail_mass_upper_bound: float | None = None

    def set_portfolio(
        self,
        obligors_df: pd.DataFrame,
        sector_columns: Optional[List[str]] = None,
        idiosyncratic_sector_columns: Optional[List[str]] = None,
    ) -> None:
        """Registra os contratos e identifica suas colunas de alocação setorial.

        São obrigatórias as colunas ``exposure``, ``mean_default_rate`` e
        ``std_default_rate``. ``recovery_rate`` é opcional e vale zero quando
        ausente. Colunas de setor começam, por convenção, com
        ``sector_weight_`` e os pesos de cada linha devem somar um.
        """

        required = {"exposure", "mean_default_rate", "std_default_rate"}
        missing = required.difference(obligors_df.columns)
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes: {sorted(missing)}")

        portfolio = obligors_df.copy()
        if "recovery_rate" not in portfolio:
            portfolio["recovery_rate"] = 0.0
        if "obligor_id" not in portfolio:
            portfolio["obligor_id"] = np.arange(1, len(portfolio) + 1)
        if "rating" not in portfolio:
            portfolio["rating"] = "N/A"

        if sector_columns is None:
            sector_columns = [
                column for column in portfolio.columns if column.startswith("sector_weight_")
            ]
        if not sector_columns:
            # Um único fator econômico é a hipótese padrão mais conservadora.
            portfolio["sector_weight_general_economy"] = 1.0
            sector_columns = ["sector_weight_general_economy"]
        unknown = set(sector_columns).difference(portfolio.columns)
        if unknown:
            raise ValueError(f"Colunas setoriais ausentes: {sorted(unknown)}")

        idiosyncratic_sector_columns = idiosyncratic_sector_columns or []
        unknown_idio = set(idiosyncratic_sector_columns).difference(sector_columns)
        if unknown_idio:
            raise ValueError(f"Setores específicos desconhecidos: {sorted(unknown_idio)}")

        self.obligors = portfolio
        self.num_obligors = len(portfolio)
        self.sector_columns = list(sector_columns)
        self.sectors = {
            column.removeprefix("sector_weight_"): index
            for index, column in enumerate(self.sector_columns)
        }
        self.num_sectors = len(self.sector_columns)
        self.idiosyncratic_sector_indices = [
            self.sector_columns.index(column) for column in idiosyncratic_sector_columns
        ]

        # Trocar a carteira invalida resultados anteriores.
        self.result = None
        self.loss_pmf = None
        self.loss_cdf = None
        self.expected_loss = None
        self.loss_variance = None
        self.loss_std = None
        self.tail_mass_upper_bound = None

    def _portfolio_arrays(self):
        """Centraliza a tradução do DataFrame para a API funcional validada."""

        if self.obligors is None:
            raise ValueError("Portfólio não definido. Use set_portfolio() primeiro.")
        return (
            self.obligors["exposure"].to_numpy(dtype=float),
            self.obligors["mean_default_rate"].to_numpy(dtype=float),
            self.obligors["std_default_rate"].to_numpy(dtype=float),
            self.obligors["recovery_rate"].to_numpy(dtype=float),
            self.obligors[self.sector_columns].to_numpy(dtype=float),
        )

    def calculate_loss_distribution(self) -> np.ndarray:
        """Calcula a PMF, os momentos analíticos e a massa de cauda truncada."""

        exposures, mean_rates, std_rates, recoveries, weights = self._portfolio_arrays()
        effective_unit = self.unit_size
        if effective_unit is None:
            # Mesma regra do XLS oficial, com a guarda de exposição positiva.
            effective_unit = _compute_unit_size(exposures * (1.0 - recoveries))

        result = calculate_loss_distribution_detailed(
            exposures,
            mean_rates,
            std_rates,
            recoveries,
            sector_weights_matrix=weights,
            idiosyncratic_sector_indices=self.idiosyncratic_sector_indices,
            unit_size=effective_unit,
            max_loss_dollars=self.max_loss_units * effective_unit,
        )
        expected_loss, variance = analytic_loss_moments(
            exposures,
            mean_rates,
            std_rates,
            recoveries,
            sector_weights_matrix=weights,
            idiosyncratic_sector_indices=self.idiosyncratic_sector_indices,
            unit_size=effective_unit,
        )

        self.unit_size = effective_unit
        self.result = result
        self.loss_pmf = result.pmf
        self.loss_cdf = result.cdf
        self.expected_loss = expected_loss
        self.loss_variance = variance
        self.loss_std = float(np.sqrt(variance))
        self.tail_mass_upper_bound = result.tail_mass_upper_bound
        return self.loss_pmf

    def _require_result(self) -> None:
        """Produz mensagem uniforme quando uma métrica é pedida cedo demais."""

        if self.result is None:
            raise ValueError("Distribuição não calculada. Use calculate_loss_distribution().")

    def get_percentile_loss(self, percentile: float, *, interpolate: bool = False) -> float:
        """Retorna o VaR discreto; interpolação é opcional para comparar com o XLS."""

        self._require_result()
        return loss_quantile(
            self.loss_pmf,
            percentile / 100.0,
            self.unit_size,
            interpolate=interpolate,
        )

    def get_percentile_losses(
        self,
        percentiles: List[float],
        *,
        interpolate: bool = False,
    ) -> Dict[float, float]:
        """Calcula vários percentis sob a mesma convenção de reporte."""

        return {
            percentile: self.get_percentile_loss(percentile, interpolate=interpolate)
            for percentile in percentiles
        }

    def get_economic_capital(self, percentile: float = 99.0) -> float:
        """Calcula ``EC = VaR - EL`` sem interpolar a distribuição discreta."""

        self._require_result()
        return self.get_percentile_loss(percentile) - self.expected_loss

    def calculate_risk_contributions(
        self,
        percentile: float = 99.0,
        *,
        convention: str = "manual",
    ) -> pd.DataFrame:
        """Calcula contribuições de risco das equações 121 e 102.

        A contribuição ao desvio padrão responde "quanto do risco total desta
        carteira vem desta contraparte". A contribuição ao percentil responde a
        mesma pergunta para o capital, usando a aproximação aditiva da equação
        102: ``RC_A = EL_A + xi * RC_sigma_A``, com ``xi = (VaR - EL)/sigma``.

        Existem duas convenções porque a planilha oficial e o texto do manual
        divergem em um ponto: qual PD entra na equação 121.

        ``"manual"`` (padrão) usa a PD compensada pelo banding, ``epsilon_A/nu_A``,
        que é o ``mu_A`` definido em A3.3 depois do arredondamento das bandas. Com
        ela a identidade da equação 123 vale exatamente e as contribuições somam ao
        desvio padrão sem nenhuma correção.

        ``"spreadsheet"`` reproduz o arquivo `CreditRisk+.xls`, que usa a PD bruta
        do rating e depois reescala o vetor para somar ao desvio padrão correto.
        Essa convenção reproduz a coluna publicada com erro inferior a 0,001%, ou
        seja, dentro do arredondamento dos inteiros impressos na planilha. Ela
        existe para auditoria e regressão; nenhuma das duas é um erro da outra, e a
        diferença por contraparte chega a 5% justamente onde o arredondamento de
        banda é maior.
        """

        if convention not in {"manual", "spreadsheet"}:
            raise ValueError("convention deve ser 'manual' ou 'spreadsheet'.")

        self._require_result()
        exposures, mean_rates, _, recoveries, weights = self._portfolio_arrays()
        net = exposures * (1.0 - recoveries)
        exact_bands = net / self.unit_size
        bands = np.maximum(np.ceil(exact_bands).astype(int), 1)
        systematic = systematic_risk_term(self.result.sector_parameters, weights)
        expected_loss_contribution = net * mean_rates

        if convention == "manual":
            # mu_A compensado: nu_A * mu_A = epsilon_A, o que faz a soma das
            # contribuições fechar exatamente em sigma pela equação 123.
            adjusted_pd = (mean_rates * exact_bands) / bands
            rc_std = (
                bands * adjusted_pd * (bands + systematic)
                / (self.loss_std / self.unit_size)
                * self.unit_size
            )
            var_loss = self.get_percentile_loss(percentile)
        else:
            # A planilha aplica a equação 121 com a PD bruta do rating. O vetor
            # resultante não soma a sigma, e ela o reescala para que some.
            unscaled = bands * mean_rates * (bands + systematic)
            rc_std = self.loss_std * unscaled / unscaled.sum()
            # A planilha também usa o VaR interpolado da própria grade em xi.
            var_loss = self.get_percentile_loss(percentile, interpolate=True)

        multiplier = (var_loss - self.expected_loss) / self.loss_std
        rc_percentile = expected_loss_contribution + multiplier * rc_std

        result = self.obligors[["obligor_id", "exposure", "rating"]].copy()
        result["expected_loss"] = expected_loss_contribution
        result["risk_contribution_std"] = rc_std
        result[f"risk_contribution_{percentile:g}pct"] = rc_percentile
        return result

    def summary(self, percentiles: Optional[List[float]] = None) -> Dict:
        """Reúne exposição, momentos, percentis e diagnóstico de truncamento."""

        self._require_result()
        percentiles = percentiles or [50, 75, 95, 97.5, 99, 99.5, 99.9]
        return {
            "total_exposure": float(self.obligors["exposure"].sum()),
            "num_obligors": self.num_obligors,
            "num_sectors": self.num_sectors,
            "expected_loss": self.expected_loss,
            "loss_std": self.loss_std,
            "loss_variance": self.loss_variance,
            "percentile_losses": self.get_percentile_losses(percentiles),
            "economic_capital_99pct": self.get_economic_capital(99),
            "tail_mass_upper_bound": self.tail_mass_upper_bound,
        }

    def __repr__(self) -> str:
        """Representação curta, útil em notebooks."""

        if self.result is None:
            return f"CreditRiskPlus(unit_size={self.unit_size}, not calculated)"
        return (
            f"CreditRiskPlus(EL={self.expected_loss:,.0f}, "
            f"VaR99={self.get_percentile_loss(99):,.0f}, "
            f"EC99={self.get_economic_capital(99):,.0f})"
        )
