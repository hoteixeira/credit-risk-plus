"""Modelo assintótico de um fator de Vasicek e especialização IRB de varejo.

O módulo separa deliberadamente três objetos que têm interpretações distintas:

* a probabilidade de default condicionada a um cenário macroeconômico;
* a perda esperada condicional no cenário adverso associado a um quantil; e
* o capital inesperado ASRF/IRB, definido como perda adversa menos perda esperada.

As linhas de entrada podem representar contratos ou pools homogêneos. Para um
pool, ``obligor_count`` é a multiplicidade. Como a aproximação ASRF é linear na
EAD quando PD, LGD e correlação são mantidas fixas, a contribuição Euler de
cada contrato é exata e a contribuição do pool é apenas sua multiplicidade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import ndtr, ndtri


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class VasicekIRBResult:
    """Resultado detalhado do cálculo ASRF/IRB para contratos ou pools.

    Todos os campos vetoriais têm uma posição por linha de entrada. Valores
    ``per_obligor`` são por contrato representativo; valores ``pool`` já
    incorporam ``obligor_count``. Montantes estão na unidade monetária da EAD.
    """

    confidence: float
    adverse_systematic_factor: float
    pd: FloatArray
    ead_per_obligor: FloatArray
    lgd: FloatArray
    asset_correlation: FloatArray
    obligor_count: NDArray[np.int64]
    downturn_pd: FloatArray
    expected_loss_per_obligor: FloatArray
    adverse_loss_per_obligor: FloatArray
    marginal_capital_per_ead: FloatArray
    capital_per_obligor: FloatArray
    expected_loss_pool: FloatArray
    adverse_loss_pool: FloatArray
    capital_pool: FloatArray
    rwa_pool: FloatArray

    @property
    def total_ead(self) -> float:
        """EAD agregada, já considerando a multiplicidade dos pools."""

        return float(np.dot(self.ead_per_obligor, self.obligor_count))

    @property
    def total_expected_loss(self) -> float:
        """Perda esperada incondicional ``sum(EAD * LGD * PD)``."""

        return float(self.expected_loss_pool.sum())

    @property
    def total_adverse_loss(self) -> float:
        """Perda condicional no cenário sistemático do quantil escolhido."""

        return float(self.adverse_loss_pool.sum())

    @property
    def total_capital(self) -> float:
        """Perda inesperada ASRF: perda adversa menos perda esperada."""

        return float(self.capital_pool.sum())

    @property
    def total_rwa(self) -> float:
        """Ativos ponderados pelo risco: ``12,5 * capital``."""

        return float(self.rwa_pool.sum())


def _float_array(values: ArrayLike, name: str) -> FloatArray:
    """Converte uma entrada numérica em vetor 1-D finito de ``float64``."""

    array = np.atleast_1d(np.asarray(values, dtype=float))
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} deve ser um vetor unidimensional não vazio.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} deve conter apenas valores finitos.")
    return array


def _broadcast_inputs(*arrays: FloatArray) -> tuple[FloatArray, ...]:
    """Aplica broadcasting e materializa vetores independentes e graváveis."""

    try:
        broadcast = np.broadcast_arrays(*arrays)
    except ValueError as error:
        raise ValueError("PD, EAD, LGD, R e contagens devem ser compatíveis.") from error
    return tuple(np.asarray(value, dtype=float).copy() for value in broadcast)


def retail_asset_correlation(
    pd: ArrayLike,
    subcategory: str | Sequence[str] = "other_retail",
) -> FloatArray:
    r"""Calcula a correlação de ativos regulatória para varejo.

    As categorias aceitas são ``"qrre"`` (rotativo de varejo qualificado),
    ``"other_retail"`` (demais exposições de varejo) e ``"residential"``.
    Para demais varejo, a função da Resolução BCB 303, art. 46, é

    .. math::

       R(PD)=0{,}03\,w(PD)+0{,}16[1-w(PD)],\qquad
       w(PD)=\frac{1-e^{-35PD}}{1-e^{-35}}.

    Assim, ``R`` cai suavemente de 16% para 3% à medida que a PD cresce.
    """

    pd_array = _float_array(pd, "PD")
    if ((pd_array <= 0.0) | (pd_array >= 1.0)).any():
        raise ValueError("PD deve estar estritamente entre zero e um.")

    categories = np.asarray(subcategory, dtype=object)
    if categories.ndim == 0:
        categories = np.full(pd_array.shape, categories.item(), dtype=object)
    try:
        pd_array, categories = np.broadcast_arrays(pd_array, categories)
    except ValueError as error:
        raise ValueError("subcategory deve ser compatível com PD.") from error

    allowed = {"qrre", "other_retail", "residential"}
    unknown = sorted(set(categories.tolist()) - allowed)
    if unknown:
        raise ValueError(f"Subcategorias de varejo desconhecidas: {unknown}.")

    weight = -np.expm1(-35.0 * pd_array) / -np.expm1(-35.0)
    other_retail = 0.03 * weight + 0.16 * (1.0 - weight)
    correlation = np.where(
        categories == "qrre",
        0.04,
        np.where(categories == "residential", 0.15, other_retail),
    )
    return np.asarray(correlation, dtype=float)


def conditional_default_probability(
    pd: ArrayLike,
    asset_correlation: ArrayLike,
    systematic_factor: ArrayLike,
) -> FloatArray:
    r"""Retorna ``P(default | W=w)`` no modelo gaussiano de um fator.

    A variável latente é

    .. math:: A_i=\sqrt{R_i}W+\sqrt{1-R_i}\varepsilon_i,

    com ``W`` e ``epsilon`` normais-padrão independentes. O default ocorre se
    ``A_i <= Phi^-1(PD_i)``. Logo,

    .. math::

       p_i(w)=\Phi\!\left(
       \frac{\Phi^{-1}(PD_i)-\sqrt{R_i}w}{\sqrt{1-R_i}}
       \right).

    Nesta convenção, ``W`` negativo representa deterioração macroeconômica.
    """

    pd_array = _float_array(pd, "PD")
    correlation = _float_array(asset_correlation, "R")
    factor = _float_array(systematic_factor, "fator sistemático")
    pd_array, correlation, factor = _broadcast_inputs(pd_array, correlation, factor)

    if ((pd_array <= 0.0) | (pd_array >= 1.0)).any():
        raise ValueError("PD deve estar estritamente entre zero e um.")
    if ((correlation < 0.0) | (correlation >= 1.0)).any():
        raise ValueError("R deve estar no intervalo [0, 1).")

    threshold = ndtri(pd_array)
    conditional_z = (
        threshold - np.sqrt(correlation) * factor
    ) / np.sqrt(1.0 - correlation)
    return np.asarray(ndtr(conditional_z), dtype=float)


def downturn_default_probability(
    pd: ArrayLike,
    asset_correlation: ArrayLike,
    confidence: float = 0.999,
) -> FloatArray:
    """PD condicional no cenário adverso associado ao quantil de perda.

    Como a perda diminui quando o fator ``W`` aumenta, o quantil ``q`` da perda
    corresponde a ``W = Phi^-1(1-q) = -Phi^-1(q)``.
    """

    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence deve estar estritamente entre 0,5 e 1.")
    adverse_factor = float(ndtri(1.0 - confidence))
    return conditional_default_probability(pd, asset_correlation, adverse_factor)


def calculate_vasicek_irb(
    pd: ArrayLike,
    ead_per_obligor: ArrayLike,
    lgd: ArrayLike,
    asset_correlation: ArrayLike,
    obligor_count: ArrayLike | None = None,
    confidence: float = 0.999,
) -> VasicekIRBResult:
    r"""Calcula capital, RWA e contribuições marginais ASRF/IRB.

    Para cada contrato performando,

    .. math::

       K_i=LGD_i[p_i(w_q)-PD_i],\qquad
       C_i=EAD_iK_i,\qquad RWA_i=12{,}5C_i.

    ``K_i`` é simultaneamente a taxa de capital e a derivada do capital total
    em relação à EAD do contrato, mantendo PD, LGD e R fixos. Portanto ``C_i``
    é sua contribuição Euler. Não há ajuste de maturidade para varejo.
    """

    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence deve estar estritamente entre 0,5 e 1.")

    pd_array = _float_array(pd, "PD")
    ead_array = _float_array(ead_per_obligor, "EAD")
    lgd_array = _float_array(lgd, "LGD")
    correlation = _float_array(asset_correlation, "R")
    if obligor_count is None:
        count_array = np.ones(1, dtype=float)
    else:
        count_array = _float_array(obligor_count, "obligor_count")

    pd_array, ead_array, lgd_array, correlation, count_float = _broadcast_inputs(
        pd_array, ead_array, lgd_array, correlation, count_array
    )
    if ((pd_array <= 0.0) | (pd_array >= 1.0)).any():
        raise ValueError("PD deve estar estritamente entre zero e um.")
    if (ead_array < 0.0).any():
        raise ValueError("EAD não pode ser negativa.")
    if ((lgd_array < 0.0) | (lgd_array > 1.0)).any():
        raise ValueError("LGD deve estar no intervalo [0, 1].")
    if ((correlation < 0.0) | (correlation >= 1.0)).any():
        raise ValueError("R deve estar no intervalo [0, 1).")
    if (count_float <= 0.0).any() or not np.equal(count_float, np.floor(count_float)).all():
        raise ValueError("obligor_count deve conter inteiros estritamente positivos.")
    counts = count_float.astype(np.int64)

    downturn_pd = downturn_default_probability(pd_array, correlation, confidence)
    expected_loss = ead_array * lgd_array * pd_array
    adverse_loss = ead_array * lgd_array * downturn_pd
    marginal_rate = lgd_array * (downturn_pd - pd_array)
    capital = ead_array * marginal_rate

    expected_loss_pool = expected_loss * counts
    adverse_loss_pool = adverse_loss * counts
    capital_pool = capital * counts

    return VasicekIRBResult(
        confidence=float(confidence),
        adverse_systematic_factor=float(ndtri(1.0 - confidence)),
        pd=pd_array,
        ead_per_obligor=ead_array,
        lgd=lgd_array,
        asset_correlation=correlation,
        obligor_count=counts,
        downturn_pd=downturn_pd,
        expected_loss_per_obligor=expected_loss,
        adverse_loss_per_obligor=adverse_loss,
        marginal_capital_per_ead=marginal_rate,
        capital_per_obligor=capital,
        expected_loss_pool=expected_loss_pool,
        adverse_loss_pool=adverse_loss_pool,
        capital_pool=capital_pool,
        rwa_pool=12.5 * capital_pool,
    )


def conditional_portfolio_loss(
    pd: ArrayLike,
    ead_per_obligor: ArrayLike,
    lgd: ArrayLike,
    asset_correlation: ArrayLike,
    systematic_factor: float,
    obligor_count: ArrayLike | None = None,
) -> float:
    """Soma a perda esperada da carteira condicionada a um valor de ``W``."""

    pd_array = _float_array(pd, "PD")
    ead_array = _float_array(ead_per_obligor, "EAD")
    lgd_array = _float_array(lgd, "LGD")
    correlation = _float_array(asset_correlation, "R")
    counts = (
        np.ones(1, dtype=float)
        if obligor_count is None
        else _float_array(obligor_count, "obligor_count")
    )
    pd_array, ead_array, lgd_array, correlation, counts = _broadcast_inputs(
        pd_array, ead_array, lgd_array, correlation, counts
    )
    if (ead_array < 0.0).any():
        raise ValueError("EAD não pode ser negativa.")
    if ((lgd_array < 0.0) | (lgd_array > 1.0)).any():
        raise ValueError("LGD deve estar no intervalo [0, 1].")
    if (counts <= 0.0).any() or not np.equal(counts, np.floor(counts)).all():
        raise ValueError("obligor_count deve conter inteiros estritamente positivos.")
    conditional_pd = conditional_default_probability(
        pd_array, correlation, systematic_factor
    )
    return float(np.sum(counts * ead_array * lgd_array * conditional_pd))
