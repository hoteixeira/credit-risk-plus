"""
Credit Risk+ — Distribuição de perdas por defaults de crédito.

Implementa a recursão exata da Seção A10 do Apêndice A (Credit Suisse, 1997):

MODELO COM TAXA VARIÁVEL (Binomial Negativa) — Equações 79-80
--------------------------------------------------------------
PGF: G(z) = ((1-p) / (1 - p·P(z)))^α

Recursão derivada da derivada logarítmica (eq. 72/77):
    A_n = (p / (n·μ)) · Σ_j ε_j · (α - 1 + n/v_j) · A_{n-v_j}

Onde:
    L   = ceil(max_exposure / 100)  (tamanho da unidade de perda)
    v_j = ceil(E_A / L)             (banda de exposição — arredondamento para cima)
    ε_j = p_A · E_A / L             (perda esperada da contraparte j em unidades L)
    μ   = Σ_A ε_A / v_A             (número esperado de defaults, eq. 38/96)
    σ   = Σ_A σ_A · (E_A/L) / v_A  (desvio padrão efetivo do setor)
    α   = μ² / σ²                   (parâmetro de forma BN; = 4 quando CV = 0,5)
    β   = σ² / μ                    (parâmetro de escala BN)
    p   = β / (1 + β)               (probabilidade BN)
    A_0 = (1 − p)^α                 (prob. de perda zero)

MODELO MULTI-SETOR (Seções A7–A9):
    G_total(z) = ∏_k G_k(z)  — PGF total = produto das PGFs setoriais
    Cada setor k usa apenas as contrapartes com peso θ_Ak > 0,
    com exposições baseadas na exposição TOTAL (banda v_A = ceil(E_A/L)).

SETOR IDIOSSINCRÁTICO (Seção A12 — Specific sector):
    Para o setor específico (risco individual), cada contraparte possui
    seu próprio fator Gamma independente. A PMF do setor é a convolução
    de 25 distribuições NB individuais, uma por contraparte.

CONVERGÊNCIA PARA POISSON (seção A11):
    Quando σ → 0: A_n → (1/n) · Σ_j ε_j · A_{n-v_j}  (Poisson)
"""

import numpy as np


def _compute_unit_size(net_exposures: np.ndarray) -> float:
    """Unidade de perda L = ceil(max_exposure / 100), conforme planilha Excel."""
    return float(np.ceil(net_exposures.max() / 100.0))


def _sector_distribution(
    net_exposures: np.ndarray,
    mean_default_rates: np.ndarray,
    std_default_rates: np.ndarray,
    sector_weights: np.ndarray,
    unit_size: float,
    max_n: int,
) -> np.ndarray:
    """
    Calcula a PMF de perdas para um único setor sistemático (fator compartilhado).

    Parâmetros
    ----------
    net_exposures : array (N,)
        Exposições líquidas (descontada recuperação) do portfólio inteiro.
    mean_default_rates : array (N,)
        Taxa média de default por contraparte.
    std_default_rates : array (N,)
        Desvio padrão da taxa de default por contraparte.
    sector_weights : array (N,)
        Peso de cada contraparte neste setor (θ_Ak ∈ [0,1]).
    unit_size : float
        Tamanho da unidade L de perda.
    max_n : int
        Número máximo de unidades L a calcular.

    Retorna
    -------
    A : np.ndarray de tamanho (max_n+1,)
        A[n] = P(perda do setor = n · L).
    """
    mask = sector_weights > 0
    if not mask.any():
        A = np.zeros(max_n + 1)
        A[0] = 1.0
        return A

    w = sector_weights[mask]
    net_e = net_exposures[mask]       # exposição TOTAL (não escalada pelo peso)
    p = mean_default_rates[mask]
    s = std_default_rates[mask]

    # Banda: ceil(E_A / L) — baseada na exposição TOTAL (não no peso setorial)
    # Todas as contrapartes usam a mesma banda independentemente do setor (Apêndice A9)
    exact_bands = net_e / unit_size
    bands = np.maximum(np.ceil(exact_bands).astype(int), 1)

    # ε_A^k = θ_Ak · p_A · E_A / L  (épsilon escalado pelo peso setorial)
    epsilons = net_e * p * w / unit_size

    # μ_k = Σ θ_Ak · ε_A / v_A  (eq. 38/96)
    mu_k = (epsilons / bands).sum()
    if mu_k <= 0:
        A = np.zeros(max_n + 1)
        A[0] = 1.0
        return A

    # σ_k efetivo = Σ θ_Ak · σ_A · (E_A/L) / v_A  (preserva CV por contraparte)
    sigma_k = (s * w * exact_bands / bands).sum()

    if sigma_k > 0:
        alpha_k = mu_k ** 2 / sigma_k ** 2
        beta_k  = sigma_k ** 2 / mu_k
        p_k     = beta_k / (1.0 + beta_k)
    else:
        alpha_k = np.inf
        p_k     = 0.0

    A = np.zeros(max_n + 1, dtype=np.float64)

    if p_k > 0:
        A[0] = (1.0 - p_k) ** alpha_k
        for n in range(1, max_n + 1):
            s_val = 0.0
            for vj, ej in zip(bands, epsilons):
                if vj <= n:
                    s_val += ej * (alpha_k - 1.0 + n / vj) * A[n - vj]
            A[n] = (p_k / (n * mu_k)) * s_val
    else:
        # Poisson puro (fallback σ = 0)
        total_eps = epsilons.sum()
        A[0] = np.exp(-total_eps) if total_eps < 700 else 0.0
        for n in range(1, max_n + 1):
            s_val = 0.0
            for vj, ej in zip(bands, epsilons):
                if vj <= n:
                    s_val += ej * A[n - vj]
            A[n] = s_val / n

    total = A.sum()
    if total > 0:
        A /= total
    return A


def _idiosyncratic_sector_distribution(
    net_exposures: np.ndarray,
    mean_default_rates: np.ndarray,
    sector_weights: np.ndarray,
    unit_size: float,
    max_n: int,
) -> np.ndarray:
    """
    Calcula a PMF de perdas para o setor idiossincrático (Specific sector).

    No setor específico, cada contraparte possui seu próprio fator Gamma
    independente (α_A = 4 para CV = 0,5). A PMF do setor é a convolução
    das 25 distribuições NB individuais (Seção A12 do Apêndice A).

    Diferença do setor sistemático: não há fator compartilhado; cada
    contraparte contribui de forma independente.

    Parâmetros
    ----------
    net_exposures : array (N,)
        Exposições líquidas do portfólio inteiro.
    mean_default_rates : array (N,)
        Taxa média de default por contraparte.
    sector_weights : array (N,)
        Peso de cada contraparte neste setor (θ_Ak ∈ [0,1]).
    unit_size : float
        Tamanho da unidade L de perda.
    max_n : int
        Número máximo de unidades L a calcular.

    Retorna
    -------
    A : np.ndarray de tamanho (max_n+1,)
        A[n] = P(perda do setor = n · L).
    """
    mask = sector_weights > 0
    if not mask.any():
        A = np.zeros(max_n + 1)
        A[0] = 1.0
        return A

    w = sector_weights[mask]
    net_e = net_exposures[mask]
    p = mean_default_rates[mask]

    exact_bands = net_e / unit_size
    bands = np.maximum(np.ceil(exact_bands).astype(int), 1)
    epsilons = net_e * p * w / unit_size
    mus = epsilons / bands  # μ_A = θ_A · p_A · (E_A/L) / ceil(E_A/L)

    # Começa com distribuição degenerada em 0 e convolui contraparte por contraparte
    A = np.zeros(max_n + 1, dtype=np.float64)
    A[0] = 1.0

    for mu_a, v_a in zip(mus, bands):
        if mu_a <= 0:
            continue
        # NB individual com α=4: p_a = 0,25·μ / (1 + 0,25·μ), β = 0,25·μ
        beta_a = 0.25 * mu_a
        p_a = beta_a / (1.0 + beta_a)

        # PMF NB para esta contraparte: suporte em {0, v_a, 2·v_a, ...}
        # Recursão: A[k·v_a] = p_a · (3+k)/k · A[(k-1)·v_a]
        A_indiv = np.zeros(max_n + 1, dtype=np.float64)
        A_indiv[0] = (1.0 - p_a) ** 4
        for kk in range(1, max_n // v_a + 1):
            n_idx = kk * v_a
            if n_idx > max_n:
                break
            A_indiv[n_idx] = p_a * (3 + kk) / kk * A_indiv[n_idx - v_a]

        # Normaliza antes de convolucionar para evitar acúmulo de erros de truncamento
        t = A_indiv.sum()
        if t > 0:
            A_indiv /= t

        conv = np.convolve(A, A_indiv)
        A = conv[:max_n + 1]

    total = A.sum()
    if total > 0:
        A /= total
    return A


def calculate_loss_distribution(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix=None,
    idiosyncratic_sector_indices=None,
    unit_size: float = None,
    max_loss_dollars: float = 150_000_000,
) -> tuple[np.ndarray, float]:
    """
    Calcula a distribuição de perdas pelo modelo Credit Risk+ (Binomial Negativa).

    Parâmetros
    ----------
    exposures : array_like
        Exposições brutas em dólares.
    mean_default_rates : array_like
        Taxa média de default por contraparte (0–1).
    std_default_rates : array_like
        Desvio padrão da taxa de default por contraparte (0–1).
    recovery_rates : array_like
        Taxa de recuperação por contraparte (0–1).
    sector_weights_matrix : array_like (N, K) ou None
        Matriz de pesos setoriais θ_Ak. Cada linha soma a 1.
        None = portfólio com setor único (todos os pesos = 1).
    idiosyncratic_sector_indices : list[int] ou None
        Índices de colunas em sector_weights_matrix que representam setores
        idiossincráticos (e.g., [0] para o setor "Specific" do Exemplo 3).
        Esses setores usam convolução de NB individuais por contraparte
        em vez do NB de fator compartilhado.
    unit_size : float ou None
        Tamanho da unidade L de perda. None = ceil(max_exposure / 100).
    max_loss_dollars : float
        Perda máxima a calcular.

    Retorna
    -------
    pmf : np.ndarray
        A[n] = P(perda total = n · L) para n = 0, 1, …
    el : float
        Perda esperada em dólares (= Σ n·L·A[n]).
    """
    exposures          = np.asarray(exposures,          dtype=float)
    mean_default_rates = np.asarray(mean_default_rates, dtype=float)
    std_default_rates  = np.asarray(std_default_rates,  dtype=float)
    recovery_rates     = np.asarray(recovery_rates,     dtype=float)

    net_exposures = exposures * (1.0 - recovery_rates)

    if unit_size is None:
        unit_size = _compute_unit_size(net_exposures)

    max_n = int(max_loss_dollars / unit_size)

    idio_set = set(idiosyncratic_sector_indices or [])

    if sector_weights_matrix is None:
        weights_single = np.ones(len(exposures))
        A = _sector_distribution(
            net_exposures, mean_default_rates, std_default_rates,
            weights_single, unit_size, max_n,
        )
    else:
        sector_weights_matrix = np.asarray(sector_weights_matrix, dtype=float)
        n_sectors = sector_weights_matrix.shape[1]

        A = np.array([1.0])
        for k in range(n_sectors):
            w_k = sector_weights_matrix[:, k]
            if k in idio_set:
                A_k = _idiosyncratic_sector_distribution(
                    net_exposures, mean_default_rates, w_k, unit_size, max_n,
                )
            else:
                A_k = _sector_distribution(
                    net_exposures, mean_default_rates, std_default_rates,
                    w_k, unit_size, max_n,
                )
            conv = np.convolve(A, A_k)
            A = conv[:max_n + 1]

        total = A.sum()
        if total > 0:
            A /= total

    loss_values = np.arange(len(A)) * unit_size
    el = (loss_values * A).sum()

    return A, el


def calculate_loss_distribution_simple(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    unit_size: float = None,
    max_units: int = None,
) -> tuple[np.ndarray, float]:
    """Alias para calculate_loss_distribution (retrocompatibilidade)."""
    if max_units is not None and unit_size is not None:
        max_loss_dollars = max_units * unit_size
    else:
        max_loss_dollars = 150_000_000
    return calculate_loss_distribution(
        exposures=exposures,
        mean_default_rates=mean_default_rates,
        std_default_rates=std_default_rates,
        recovery_rates=recovery_rates,
        unit_size=unit_size,
        max_loss_dollars=max_loss_dollars,
    )


# ── Teste básico ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    from data import create_example_1a_portfolio

    portfolio = create_example_1a_portfolio()
    A, el = calculate_loss_distribution(
        exposures=portfolio["exposure"].values,
        mean_default_rates=portfolio["mean_default_rate"].values,
        std_default_rates=portfolio["std_default_rate"].values,
        recovery_rates=np.zeros(len(portfolio)),
    )

    net_e = portfolio["exposure"].values
    L = float(np.ceil(net_e.max() / 100))
    cdf = np.cumsum(A)

    def var_interp(cdf, pct, L):
        idx = np.searchsorted(cdf, pct / 100)
        if idx == 0: return 0.0
        p_lo, p_hi = cdf[idx - 1], cdf[idx]
        frac = (pct / 100 - p_lo) / (p_hi - p_lo) if p_hi > p_lo else 0.0
        return (idx - 1 + frac) * L

    print(f"E[Loss] = ${el:,.0f}  (ref: $14,221,863)")
    for pct, ref in [(99, 55_311_503), (99.5, 62_033_181)]:
        val = var_interp(cdf, pct, L)
        err = (val - ref) / ref * 100
        print(f"  VaR({pct}%) = ${val:,.0f}  ref=${ref:,.0f}  err={err:+.3f}%")
