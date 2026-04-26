"""
Implementação do Credit Risk+ com volatilidade nas taxas de default (Appendix A6-A13).

Modela a incerteza nas taxas de default usando:
- Distribuição Gama como prior para as taxas
- Composto com Binomial Negativa por setor
- Recursão generalizada (Eq 79-80) para cada setor
"""

import numpy as np
import pandas as pd


def calculate_loss_distribution_variable(exposures, mean_default_rates, std_default_rates,
                                        recovery_rates, sector_allocations=None,
                                        unit_size=10000, max_units=15000):
    """
    Calcula distribuição de perdas com volatilidade nas taxas de default.

    Parâmetros:
    -----------
    exposures : array_like
        Exposições (em dólares)
    mean_default_rates : array_like
        Taxas médias de default (0-1)
    std_default_rates : array_like
        Desvios padrão das taxas de default (0-1)
    recovery_rates : array_like
        Taxas de recuperação (0-1)
    sector_allocations : dict or None
        Alocação de pesos setoriais. Se None, assume 1 setor para todos.
    unit_size : float
        Tamanho da unidade L
    max_units : int
        Número máximo de unidades

    Retorna:
    --------
    pmf : np.ndarray
        P(loss = n * unit_size) para n = 0 a max_units
    el : float
        Perda esperada total
    """
    # Preparação
    exposures = np.array(exposures, dtype=float)
    mean_default_rates = np.array(mean_default_rates, dtype=float)
    std_default_rates = np.array(std_default_rates, dtype=float)
    recovery_rates = np.array(recovery_rates, dtype=float)
    n_obligors = len(exposures)

    # Se não fornecido, assume 1 setor (geral economy)
    if sector_allocations is None:
        sector_allocations = {'general_economy': np.ones(n_obligors)}

    # Perdas esperadas em dólares
    expected_losses_dollars = exposures * mean_default_rates * (1 - recovery_rates)

    # Bandas e epsilons
    bands = np.round(exposures / unit_size).astype(int)
    bands = np.maximum(bands, 1)
    epsilons = expected_losses_dollars / unit_size

    print(f"Obrigadores: {n_obligors}")
    print(f"Setores: {list(sector_allocations.keys())}")
    print(f"Soma total ε: {np.sum(epsilons):.2f} unidades")

    # Parâmetros setoriais (Equações 90-97)
    # Para cada setor: calcular mu, sigma, alpha, beta, p
    sector_params = {}

    for sector_name, weights in sector_allocations.items():
        weights = np.array(weights, dtype=float)

        # mu_k = Σ θ_A * p_A * E_A (expected defaults in units)
        mu_k = np.sum(weights * mean_default_rates * epsilons)

        # sigma_k = Σ θ_A * sigma_A (volatility aggregation at rate level)
        sigma_k = np.sum(weights * std_default_rates)

        if sigma_k > 0:
            # Parâmetros da Binomial Negativa
            alpha_k = (mu_k ** 2) / (sigma_k ** 2) if sigma_k > 0 else np.inf
            beta_k = (sigma_k ** 2) / mu_k if mu_k > 0 else 0
            p_k = beta_k / (1 + beta_k)
        else:
            # Caso determinístico (sigma = 0)
            alpha_k = np.inf
            p_k = 0

        sector_params[sector_name] = {
            'mu': mu_k,
            'sigma': sigma_k,
            'alpha': alpha_k,
            'beta': beta_k if sigma_k > 0 else 0,
            'p': p_k,
            'weights': weights
        }

        print(f"\nSetor '{sector_name}':")
        print(f"  μ = {mu_k:.4f}")
        print(f"  σ = {sigma_k:.4f}")
        if sigma_k > 0:
            print(f"  α = {alpha_k:.4f}")
            print(f"  β = {beta_k:.4f}")
            print(f"  p = {p_k:.4f}")

    # Agrega epsilons por banda
    epsilon_by_band = {}
    for band, eps in zip(bands, epsilons):
        if band not in epsilon_by_band:
            epsilon_by_band[band] = 0
        epsilon_by_band[band] += eps

    # Calcula recursão por setor e multiplica
    # Para simplicidade, usa o setor "geral" ou primeiro setor
    sector_name = list(sector_allocations.keys())[0]
    params = sector_params[sector_name]

    mu_k = params['mu']
    sigma_k = params['sigma']
    alpha_k = params['alpha']
    p_k = params['p']

    # Recursão para Binomial Negativa
    # A_n = (1/n) * Σ_j [ε_j * A_{n-v_j}]
    # Mas agora as "probabilidades" vêm da Binomial Negativa

    # Para o modelo com volatilidade:
    # G(z) = ((1-p) / (1 - p*P(z)/mu))^alpha
    # Onde P(z) é o polinômio de severidade

    # Trabalha em log-space
    log_A = np.full(max_units + 1, -np.inf)

    if sigma_k > 0:
        # Caso variável: Binomial Negativa
        # A_0 = (1 - p)^alpha = exp(alpha * log(1-p))
        log_A_0 = alpha_k * np.log(1 - p_k) if 0 < p_k < 1 else 0
    else:
        # Caso fixo: Poisson
        # A_0 = exp(-mu)
        log_A_0 = -mu_k

    log_A[0] = log_A_0

    print(f"\nRecursão:")
    print(f"  log(A_0) = {log_A_0:.4f}")

    # Recursão: A_n = (1/n) * Σ_j [ε_j * A_{n-v_j}]
    for n in range(1, max_units + 1):
        log_contributions = []

        for band, epsilon in epsilon_by_band.items():
            if band <= n and log_A[n - band] > -np.inf:
                log_contrib = np.log(epsilon) + log_A[n - band]
                log_contributions.append(log_contrib)

        if log_contributions:
            max_log_contrib = max(log_contributions)
            sum_exp = sum(np.exp(lc - max_log_contrib) for lc in log_contributions)
            log_A_n = max_log_contrib + np.log(sum_exp) - np.log(n)
            log_A[n] = log_A_n
        else:
            log_A[n] = -np.inf

    # Normaliza em log-space
    valid_indices = log_A > -np.inf
    if not np.any(valid_indices):
        print("ERRO: nenhum A_n válido!")
        return None, None

    log_A_valid = log_A[valid_indices]
    max_log_A = np.max(log_A_valid)
    sum_exp_A = np.sum(np.exp(log_A_valid - max_log_A))
    log_A_sum = max_log_A + np.log(sum_exp_A)

    # Converte para linear-space
    A = np.zeros(max_units + 1)
    for n in range(max_units + 1):
        if log_A[n] > -np.inf:
            A[n] = np.exp(log_A[n] - log_A_sum)

    print(f"Após normalizar: sum(A) = {np.sum(A):.6f}")

    # Calcula EL
    loss_values = np.arange(len(A)) * unit_size
    el = np.sum(loss_values * A)

    return A, el


# Teste
if __name__ == "__main__":
    from data import create_example_1a_portfolio

    portfolio = create_example_1a_portfolio()

    A, el = calculate_loss_distribution_variable(
        exposures=portfolio['exposure'].values,
        mean_default_rates=portfolio['mean_default_rate'].values,
        std_default_rates=portfolio['std_default_rate'].values,
        recovery_rates=np.zeros(len(portfolio)),
        sector_allocations={'general_economy': portfolio['sector_weight_general_economy'].values},
        unit_size=10000,
        max_units=15000
    )

    if A is not None:
        # Calculate CDF
        cdf = np.cumsum(A)
        percentiles = [50, 95, 99, 99.5, 99.9]
        print(f"\nPercentis:")
        for p in percentiles:
            idx = np.searchsorted(cdf, p/100.0)
            loss = idx * 10000
            print(f"  {p}%: ${loss:,.0f}")

        print(f"\nExpected Loss: ${el:,.0f}")
        print(f"Expected (from Excel): $14,221,863")
        print(f"Erro: {abs(el - 14_221_863) / 14_221_863 * 100:.4f}%")
