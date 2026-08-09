"""Núcleo matemático do modelo CreditRisk+.

Este módulo implementa as equações do Apêndice A do manual do Credit Suisse
First Boston (1997). A implementação preserva três propriedades importantes:

* a exposição é arredondada para cima em bandas, como na planilha de referência;
* a probabilidade de default é compensada para que a perda esperada original
  não seja alterada pelo arredondamento (equações 11--13);
* a massa além do limite calculado não é renormalizada. Assim, um truncamento
  insuficiente fica visível em vez de contaminar silenciosamente os percentis.

O modelo é analítico. A aleatoriedade aparece na distribuição que ele descreve,
mas o algoritmo em si é determinístico e, portanto, inteiramente reprodutível.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.signal import fftconvolve
from scipy.special import logsumexp


@dataclass(frozen=True)
class SectorParameters:
    """Parâmetros do fator Gama associado a um setor (equações 52 e 60)."""

    mean_defaults: float
    std_defaults: float
    expected_loss_units: float
    alpha: float
    beta: float
    negative_binomial_p: float


@dataclass(frozen=True)
class LossDistributionResult:
    """Resultado completo, incluindo diagnósticos que a API histórica omitia."""

    pmf: np.ndarray
    unit_size: float
    expected_loss: float
    pmf_expected_loss: float
    tail_mass_upper_bound: float
    sector_parameters: tuple[SectorParameters, ...]

    @property
    def cdf(self) -> np.ndarray:
        """Distribuição acumulada no suporte discreto ``n * unit_size``."""

        return np.cumsum(self.pmf)

    def quantile(self, confidence: float, *, interpolate: bool = False) -> float:
        """Retorna o quantil de perda, verificando antes a massa truncada.

        ``interpolate=False`` devolve o VaR matemático da distribuição discreta.
        A interpolação existe apenas para reproduzir a convenção da planilha XLS;
        ela não transforma a distribuição em contínua.
        """

        return loss_quantile(
            self.pmf,
            confidence,
            self.unit_size,
            interpolate=interpolate,
        )


def _as_float_vector(values, name: str) -> np.ndarray:
    """Converte um input unidimensional e rejeita NaN ou infinito cedo."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} deve ser um vetor unidimensional.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contém NaN ou infinito.")
    return array


def _validate_inputs(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix,
    idiosyncratic_sector_indices,
    obligor_counts=None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    set[int],
    np.ndarray,
]:
    """Valida as hipóteses de domínio das equações 90, 95 e 97."""

    exposures = _as_float_vector(exposures, "exposures")
    mean_rates = _as_float_vector(mean_default_rates, "mean_default_rates")
    std_rates = _as_float_vector(std_default_rates, "std_default_rates")
    recoveries = _as_float_vector(recovery_rates, "recovery_rates")

    lengths = {len(exposures), len(mean_rates), len(std_rates), len(recoveries)}
    if len(lengths) != 1 or not len(exposures):
        raise ValueError("Os quatro vetores devem ter o mesmo tamanho positivo.")
    if np.any(exposures < 0):
        raise ValueError("Exposições não podem ser negativas.")
    if np.any((mean_rates < 0) | (mean_rates > 1)):
        raise ValueError("As PDs médias devem pertencer ao intervalo [0, 1].")
    if np.any(std_rates < 0):
        raise ValueError("Desvios padrão de PD não podem ser negativos.")
    if np.any((recoveries < 0) | (recoveries > 1)):
        raise ValueError("Taxas de recuperação devem pertencer a [0, 1].")

    if sector_weights_matrix is None:
        weights = np.ones((len(exposures), 1), dtype=np.float64)
    else:
        weights = np.asarray(sector_weights_matrix, dtype=np.float64)
        if weights.ndim != 2 or weights.shape[0] != len(exposures) or not weights.shape[1]:
            raise ValueError("sector_weights_matrix deve ter formato (N, K), com K >= 1.")
        if not np.all(np.isfinite(weights)) or np.any(weights < 0):
            raise ValueError("Pesos setoriais devem ser finitos e não negativos.")
        # A tolerância cobre apenas ruído de ponto flutuante; não corrige alocações.
        if not np.allclose(weights.sum(axis=1), 1.0, rtol=0.0, atol=1e-10):
            raise ValueError("Os pesos setoriais de cada contraparte devem somar 1.")

    idiosyncratic = {int(index) for index in (idiosyncratic_sector_indices or [])}
    if any(index < 0 or index >= weights.shape[1] for index in idiosyncratic):
        raise ValueError("Índice de setor específico fora dos limites da matriz.")

    if obligor_counts is None:
        counts = np.ones(len(exposures), dtype=np.float64)
    else:
        counts = _as_float_vector(obligor_counts, "obligor_counts")
        if len(counts) != len(exposures):
            raise ValueError("obligor_counts deve ter o mesmo tamanho das exposições.")
        if np.any(counts < 0) or not np.allclose(counts, np.round(counts), atol=1e-10):
            raise ValueError("obligor_counts deve conter inteiros não negativos.")

    return exposures, mean_rates, std_rates, recoveries, weights, idiosyncratic, counts


def _compute_unit_size(net_exposures: np.ndarray) -> float:
    """Calcula ``L = ceil(max(L_A) / 100)``, convenção do XLS oficial."""

    maximum = float(np.max(net_exposures))
    if maximum <= 0:
        raise ValueError("Ao menos uma exposição líquida deve ser positiva.")
    return float(np.ceil(maximum / 100.0))


def _band_portfolio(net_exposures: np.ndarray, unit_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Retorna bandas inteiras e razões exatas ``L_A/L`` antes do arredondamento."""

    exact_bands = net_exposures / unit_size
    # Exposições líquidas nulas não geram perda. O valor 1 evita divisão por zero;
    # seus epsilons também serão zero e, portanto, não afetam nenhuma equação.
    bands = np.maximum(np.ceil(exact_bands).astype(np.int64), 1)
    return bands, exact_bands


def _sector_parameters(
    exact_bands: np.ndarray,
    bands: np.ndarray,
    mean_rates: np.ndarray,
    std_rates: np.ndarray,
    weights: np.ndarray,
    counts: np.ndarray,
) -> tuple[SectorParameters, np.ndarray]:
    """Calcula ``mu_k``, ``sigma_k`` e os epsilons das equações 94, 96 e 97."""

    # epsilon_Ak = theta_Ak * p_A * L_A/L. A divisão posterior por nu_A
    # é o ajuste de PD que preserva a perda esperada após o banding.
    epsilons = counts * weights * mean_rates * exact_bands
    mean_defaults = float(np.sum(epsilons / bands))
    expected_loss_units = float(np.sum(epsilons))

    # sigma_A também recebe o ajuste de banding aplicado à PD média. Esta é a
    # versão por contraparte de sigma_k = sum(theta_Ak * sigma_A), eq. 97.
    std_defaults = float(np.sum(counts * weights * std_rates * exact_bands / bands))

    if mean_defaults <= 0:
        alpha = np.inf
        beta = 0.0
        nb_p = 0.0
    elif std_defaults == 0:
        alpha = np.inf
        beta = 0.0
        nb_p = 0.0
    else:
        beta = std_defaults**2 / mean_defaults
        alpha = mean_defaults / beta  # algebricamente igual a mu^2/sigma^2
        nb_p = beta / (1.0 + beta)

    params = SectorParameters(
        mean_defaults=mean_defaults,
        std_defaults=std_defaults,
        expected_loss_units=expected_loss_units,
        alpha=alpha,
        beta=beta,
        negative_binomial_p=nb_p,
    )
    return params, epsilons


def _aggregate_epsilon_by_band(
    bands: np.ndarray,
    epsilons: np.ndarray,
    max_n: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Agrupa contratos de mesma severidade sem alterar a PGF do portfólio."""

    relevant = (epsilons > 0) & (bands <= max_n)
    if not np.any(relevant):
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    totals = np.bincount(bands[relevant], weights=epsilons[relevant], minlength=max_n + 1)
    nonzero_bands = np.flatnonzero(totals)
    return nonzero_bands, totals[nonzero_bands]


def _sector_distribution_from_bands(
    bands: np.ndarray,
    epsilons: np.ndarray,
    params: SectorParameters,
    max_n: int,
) -> np.ndarray:
    """Aplica a recursão NB (A10) ou seu limite Poisson (A11)."""

    distribution = np.zeros(max_n + 1, dtype=np.float64)
    if params.mean_defaults <= 0:
        distribution[0] = 1.0
        return distribution

    severity_bands, epsilon_by_band = _aggregate_epsilon_by_band(bands, epsilons, max_n)
    mu = params.mean_defaults

    if params.std_defaults == 0:
        # Da eq. 81: G(0)=exp(-mu). Usar sum(epsilon) aqui seria dimensionalmente
        # errado e faria A_0 depender do tamanho arbitrário da unidade monetária.
        log_a0 = -mu
        if log_a0 < -700.0:
            # Para carteiras muito grandes, A0 pode subfluir embora a massa ao
            # redor do modo seja material. A mesma recursão em log preserva essa massa.
            log_distribution = np.full(max_n + 1, -np.inf, dtype=np.float64)
            log_distribution[0] = log_a0
            log_epsilon = np.log(epsilon_by_band)
            for n in range(1, max_n + 1):
                eligible = severity_bands <= n
                v = severity_bands[eligible]
                previous = log_distribution[n - v]
                finite = np.isfinite(previous)
                if np.any(finite):
                    log_distribution[n] = (
                        logsumexp(log_epsilon[eligible][finite] + previous[finite])
                        - np.log(n)
                    )
            return np.exp(log_distribution)

        distribution[0] = np.exp(log_a0)
        for n in range(1, max_n + 1):
            eligible = severity_bands <= n
            v = severity_bands[eligible]
            if v.size:
                distribution[n] = np.dot(epsilon_by_band[eligible], distribution[n - v]) / n
        return distribution

    beta = params.beta
    # Forma numericamente estável da recursão da eq. 79. Ela evita multiplicar
    # alpha -> infinito por p -> 0 quando a volatilidade é muito pequena.
    shared_factor = 1.0 / (1.0 + beta)  # alpha*p/mu
    residual_factor = beta / (mu * (1.0 + beta))  # p/mu
    log_a0 = -(mu / beta) * np.log1p(beta)
    if log_a0 < -700.0:
        log_distribution = np.full(max_n + 1, -np.inf, dtype=np.float64)
        log_distribution[0] = log_a0
        for n in range(1, max_n + 1):
            eligible = severity_bands <= n
            v = severity_bands[eligible]
            if v.size:
                coefficient = epsilon_by_band[eligible] * (
                    shared_factor + residual_factor * (n / v - 1.0)
                )
                previous = log_distribution[n - v]
                finite = np.isfinite(previous) & (coefficient > 0)
                if np.any(finite):
                    log_distribution[n] = (
                        logsumexp(np.log(coefficient[finite]) + previous[finite])
                        - np.log(n)
                    )
        return np.exp(log_distribution)

    distribution[0] = np.exp(log_a0)

    for n in range(1, max_n + 1):
        eligible = severity_bands <= n
        v = severity_bands[eligible]
        if v.size:
            coefficient = epsilon_by_band[eligible] * (
                shared_factor + residual_factor * (n / v - 1.0)
            )
            distribution[n] = np.dot(coefficient, distribution[n - v]) / n
    return distribution


def _sector_distribution(
    net_exposures: np.ndarray,
    mean_default_rates: np.ndarray,
    std_default_rates: np.ndarray,
    sector_weights: np.ndarray,
    unit_size: float,
    max_n: int,
) -> np.ndarray:
    """Compatibilidade interna: calcula a PMF de um único fator sistemático."""

    bands, exact_bands = _band_portfolio(net_exposures, unit_size)
    params, epsilons = _sector_parameters(
        exact_bands,
        bands,
        mean_default_rates,
        std_default_rates,
        sector_weights,
        np.ones(len(net_exposures), dtype=np.float64),
    )
    return _sector_distribution_from_bands(bands, epsilons, params, max_n)


def _convolve_truncated(left: np.ndarray, right: np.ndarray, max_n: int) -> np.ndarray:
    """Multiplica PGFs por FFT e conserva apenas o suporte solicitado."""

    convolution = fftconvolve(left, right)[: max_n + 1]
    # FFT pode gerar resíduos negativos da ordem de 1e-17. Eles não representam
    # probabilidades e são removidos sem renormalizar a massa de cauda.
    convolution[np.abs(convolution) < 1e-15] = 0.0
    if np.any(convolution < -1e-12):
        raise FloatingPointError("A convolução gerou probabilidade negativa material.")
    return np.maximum(convolution, 0.0)


def calculate_loss_distribution_detailed(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix=None,
    idiosyncratic_sector_indices: Sequence[int] | None = None,
    unit_size: float | None = None,
    max_loss_dollars: float = 150_000_000,
    obligor_counts=None,
) -> LossDistributionResult:
    """Calcula a distribuição e expõe seus diagnósticos numéricos.

    Setores listados em ``idiosyncratic_sector_indices`` seguem A12.3: sua
    variância de fator é fixada em zero. Isso representa o limite de muitos
    fatores específicos independentes, exatamente como prescrito no manual.
    ``obligor_counts`` comprime grupos de contratos com parâmetros idênticos e
    é algebricamente equivalente a repetir cada linha o número indicado.
    """

    (
        exposures,
        mean_rates,
        std_rates,
        recoveries,
        weights,
        idiosyncratic,
        counts,
    ) = _validate_inputs(
        exposures,
        mean_default_rates,
        std_default_rates,
        recovery_rates,
        sector_weights_matrix,
        idiosyncratic_sector_indices,
        obligor_counts,
    )

    net_exposures = exposures * (1.0 - recoveries)
    positive_loss = net_exposures > 0
    if not np.any(positive_loss):
        raise ValueError("Ao menos uma exposição após recuperação deve ser positiva.")

    if unit_size is None:
        unit_size = _compute_unit_size(net_exposures)
    unit_size = float(unit_size)
    if not np.isfinite(unit_size) or unit_size <= 0:
        raise ValueError("unit_size deve ser finito e positivo.")
    if not np.isfinite(max_loss_dollars) or max_loss_dollars <= 0:
        raise ValueError("max_loss_dollars deve ser finito e positivo.")

    max_n = int(np.floor(max_loss_dollars / unit_size))
    if max_n < 1:
        raise ValueError("max_loss_dollars deve comportar ao menos uma unidade de perda.")

    bands, exact_bands = _band_portfolio(net_exposures, unit_size)
    total = np.array([1.0], dtype=np.float64)
    sector_parameters: list[SectorParameters] = []

    for sector_index in range(weights.shape[1]):
        sector_std = std_rates.copy()
        if sector_index in idiosyncratic:
            # A12.3: o setor específico perde sua volatilidade sistemática.
            sector_std.fill(0.0)
        params, epsilons = _sector_parameters(
            exact_bands,
            bands,
            mean_rates,
            sector_std,
            weights[:, sector_index],
            counts,
        )
        sector_parameters.append(params)
        sector_pmf = _sector_distribution_from_bands(bands, epsilons, params, max_n)
        total = _convolve_truncated(total, sector_pmf, max_n)

    mass = float(np.sum(total))
    if mass > 1.0 and mass - 1.0 < 1e-11:
        # Corrige somente erro de soma no último bit; não redistribui a cauda.
        total[0] -= mass - 1.0
        mass = float(np.sum(total))
    if mass > 1.0 + 1e-11:
        raise FloatingPointError(f"A PMF soma {mass:.12f}, acima de 1.")

    losses = np.arange(total.size, dtype=np.float64) * unit_size
    exact_el = float(np.dot(net_exposures * mean_rates, counts))
    truncated_el = float(np.dot(losses, total))

    return LossDistributionResult(
        pmf=total,
        unit_size=unit_size,
        expected_loss=exact_el,
        pmf_expected_loss=truncated_el,
        tail_mass_upper_bound=max(0.0, 1.0 - mass),
        sector_parameters=tuple(sector_parameters),
    )


def calculate_loss_distribution(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix=None,
    idiosyncratic_sector_indices: Sequence[int] | None = None,
    unit_size: float | None = None,
    max_loss_dollars: float = 150_000_000,
    obligor_counts=None,
) -> tuple[np.ndarray, float]:
    """API histórica: retorna ``(pmf, perda_esperada_exata)``.

    Para auditoria de truncamento e parâmetros setoriais, prefira
    :func:`calculate_loss_distribution_detailed`.
    """

    result = calculate_loss_distribution_detailed(
        exposures=exposures,
        mean_default_rates=mean_default_rates,
        std_default_rates=std_default_rates,
        recovery_rates=recovery_rates,
        sector_weights_matrix=sector_weights_matrix,
        idiosyncratic_sector_indices=idiosyncratic_sector_indices,
        unit_size=unit_size,
        max_loss_dollars=max_loss_dollars,
        obligor_counts=obligor_counts,
    )
    return result.pmf, result.expected_loss


def calculate_loss_distribution_simple(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    unit_size: float | None = None,
    max_units: int | None = None,
) -> tuple[np.ndarray, float]:
    """Alias retrocompatível para portfólios de um único setor."""

    if max_units is None:
        max_loss = 150_000_000
    else:
        effective_unit = unit_size
        if effective_unit is None:
            gross = _as_float_vector(exposures, "exposures")
            recoveries = _as_float_vector(recovery_rates, "recovery_rates")
            effective_unit = _compute_unit_size(gross * (1.0 - recoveries))
        max_loss = float(max_units) * float(effective_unit)
    return calculate_loss_distribution(
        exposures,
        mean_default_rates,
        std_default_rates,
        recovery_rates,
        unit_size=unit_size,
        max_loss_dollars=max_loss,
    )


def loss_quantile(
    pmf: Iterable[float],
    confidence: float,
    unit_size: float,
    *,
    interpolate: bool = False,
) -> float:
    """Calcula um quantil discreto ou a interpolação usada pelo XLS oficial."""

    probabilities = _as_float_vector(pmf, "pmf")
    if np.any(probabilities < -1e-14):
        raise ValueError("A PMF contém probabilidades negativas.")
    if not 0 < confidence < 1:
        raise ValueError("confidence deve pertencer ao intervalo aberto (0, 1).")
    if unit_size <= 0:
        raise ValueError("unit_size deve ser positivo.")

    cdf = np.cumsum(np.maximum(probabilities, 0.0))
    if cdf[-1] + 1e-12 < confidence:
        raise ValueError(
            f"Domínio truncado: a CDF termina em {cdf[-1]:.8f}, abaixo de {confidence:.8f}."
        )
    index = int(np.searchsorted(cdf, confidence, side="left"))
    if not interpolate or index == 0:
        return index * float(unit_size)

    lower_probability = cdf[index - 1]
    upper_probability = cdf[index]
    if upper_probability <= lower_probability:
        return index * float(unit_size)
    fraction = (confidence - lower_probability) / (upper_probability - lower_probability)
    return (index - 1 + fraction) * float(unit_size)


def systematic_risk_term(
    sector_parameters: Sequence[SectorParameters],
    sector_weights: np.ndarray,
) -> np.ndarray:
    """Calcula ``S_A = sum_k (sigma_k/mu_k)^2 * epsilon_k * theta_Ak`` da equação 121.

    Este é o termo que distingue a contribuição de risco da simples perda esperada:
    ele mede o quanto a contraparte ``A`` é exposta à variação conjunta dos fatores
    sistemáticos. Uma carteira sem volatilidade de fator tem ``S_A = 0`` e a
    contribuição colapsa no termo de severidade individual.

    ``sector_weights`` tem formato ``(N, K)`` e o retorno tem tamanho ``N``, ambos
    expressos em unidades de perda ``L``.
    """

    systematic = np.zeros(sector_weights.shape[0], dtype=np.float64)
    for sector_index, parameters in enumerate(sector_parameters):
        if parameters.mean_defaults <= 0:
            continue
        # (sigma_k/mu_k)^2 é o quadrado do coeficiente de variação do fator k.
        cv_squared = (parameters.std_defaults / parameters.mean_defaults) ** 2
        systematic += (
            cv_squared
            * parameters.expected_loss_units
            * sector_weights[:, sector_index]
        )
    return systematic


def analytic_loss_moments(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix=None,
    idiosyncratic_sector_indices: Sequence[int] | None = None,
    unit_size: float | None = None,
    obligor_counts=None,
) -> tuple[float, float]:
    """Retorna média e variância analíticas das equações 115--118, em moeda."""

    (
        exposures,
        mean_rates,
        std_rates,
        recoveries,
        weights,
        idiosyncratic,
        counts,
    ) = _validate_inputs(
        exposures,
        mean_default_rates,
        std_default_rates,
        recovery_rates,
        sector_weights_matrix,
        idiosyncratic_sector_indices,
        obligor_counts,
    )
    net = exposures * (1.0 - recoveries)
    if unit_size is None:
        unit_size = _compute_unit_size(net)
    bands, exact_bands = _band_portfolio(net, float(unit_size))

    epsilon_obligor = counts * mean_rates * exact_bands
    variance_units = float(np.dot(epsilon_obligor, bands))
    for sector_index in range(weights.shape[1]):
        sector_std = std_rates.copy()
        if sector_index in idiosyncratic:
            sector_std.fill(0.0)
        params, _ = _sector_parameters(
            exact_bands,
            bands,
            mean_rates,
            sector_std,
            weights[:, sector_index],
            counts,
        )
        if params.mean_defaults > 0:
            ratio = params.std_defaults / params.mean_defaults
            variance_units += params.expected_loss_units**2 * ratio**2

    expected_loss = float(np.dot(net * mean_rates, counts))
    return expected_loss, variance_units * float(unit_size) ** 2
