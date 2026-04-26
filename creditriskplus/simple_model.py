"""
Implementação simples e literal do Credit Risk+ (Apêndice A, Eq 25-26).

Esta é uma versão de referência que implementa exatamente:
A_n = (1/n) * Σ_j [ε_j * A_{n-v_j}]
A_0 = exp(-Σ ε_j)

Onde:
- ε_j = perda esperada do obrigador j (em unidades de L)
- v_j = tamanho da banda (em unidades)
"""

import numpy as np
import pandas as pd


def calculate_loss_distribution_simple(exposures, mean_default_rates, std_default_rates, recovery_rates, unit_size=10000, max_units=15000):
    """
    Calcula distribuição de perdas usando recursão literal do Apêndice A.

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
    # Cálculos preparatórios
    exposures = np.array(exposures, dtype=float)
    mean_default_rates = np.array(mean_default_rates, dtype=float)
    std_default_rates = np.array(std_default_rates, dtype=float)
    recovery_rates = np.array(recovery_rates, dtype=float)

    # Perdas esperadas em dólares
    expected_losses_dollars = exposures * mean_default_rates * (1 - recovery_rates)

    # Agrupa por tamanho de banda
    # v_j = tamanho da banda em unidades
    bands = np.round(exposures / unit_size).astype(int)
    bands = np.maximum(bands, 1)  # Mínimo 1 unidade

    # ε_j = perda esperada em unidades
    epsilons = expected_losses_dollars / unit_size

    print(f"Obrigadores: {len(exposures)}")
    print(f"Bandas: {bands[:5]}")
    print(f"Epsilons (unidades): {epsilons[:5]}")
    print(f"Soma total ε: {np.sum(epsilons):.2f} unidades")

    # Agrupa epsilons por banda (pode haver múltiplos obrigadores na mesma banda)
    epsilon_by_band = {}
    for band, eps in zip(bands, epsilons):
        if band not in epsilon_by_band:
            epsilon_by_band[band] = 0
        epsilon_by_band[band] += eps

    print(f"Bandas únicas: {sorted(epsilon_by_band.keys())[:10]}")

    # Calcula A_0
    total_epsilon = np.sum(epsilons)
    # Para evitar underflow: use log-space internamente, mas trabalhe em space normal
    log_A_0 = -total_epsilon
    A_0 = np.exp(log_A_0)

    print(f"Total epsilon: {total_epsilon:.2f}")
    print(f"log(A_0) = {log_A_0:.2f}")
    print(f"A_0 = exp({log_A_0:.2f}) = {A_0:.2e}")

    # Recursão: A_n = (1/n) * Σ_j [ε_j * A_{n-v_j}]
    # Trabalha completamente em log-space até a normalização final
    log_A = np.full(max_units + 1, -np.inf)
    log_A[0] = log_A_0

    for n in range(1, max_units + 1):
        log_contributions = []

        for band, epsilon in epsilon_by_band.items():
            if band <= n and log_A[n - band] > -np.inf:
                # log(epsilon * A[n-band]) = log(epsilon) + log(A[n-band])
                log_contrib = np.log(epsilon) + log_A[n - band]
                log_contributions.append(log_contrib)

        if log_contributions:
            # LogSumExp trick para evitar overflow/underflow
            max_log_contrib = max(log_contributions)
            sum_exp = sum(np.exp(lc - max_log_contrib) for lc in log_contributions)
            log_A_n = max_log_contrib + np.log(sum_exp) - np.log(n)
            log_A[n] = log_A_n
        else:
            log_A[n] = -np.inf

    # Normaliza em log-space
    # log(sum(A)) usando LogSumExp
    valid_indices = log_A > -np.inf
    if not np.any(valid_indices):
        print("ERRO: nenhum A_n válido!")
        return None, None

    log_A_valid = log_A[valid_indices]
    max_log_A = np.max(log_A_valid)
    sum_exp_A = np.sum(np.exp(log_A_valid - max_log_A))
    log_A_sum = max_log_A + np.log(sum_exp_A)

    print(f"\nlog(sum(A)) = {log_A_sum:.2f}")
    print(f"sum(A) ≈ exp({log_A_sum:.2f})")

    # Converte para linear-space normalizando via log-space
    # A_normalized[n] = exp(log_A[n] - log_A_sum)
    A = np.zeros(max_units + 1)
    for n in range(max_units + 1):
        if log_A[n] > -np.inf:
            A[n] = np.exp(log_A[n] - log_A_sum)

    print(f"Após normalizar: sum(A) = {np.sum(A):.6f}")

    # Calcula EL e estatísticas
    loss_values = np.arange(len(A)) * unit_size
    el = np.sum(loss_values * A)

    return A, el


# Teste
if __name__ == "__main__":
    from data import create_example_1a_portfolio

    portfolio = create_example_1a_portfolio()

    A, el = calculate_loss_distribution_simple(
        exposures=portfolio['exposure'].values,
        mean_default_rates=portfolio['mean_default_rate'].values,
        std_default_rates=portfolio['std_default_rate'].values,
        recovery_rates=np.zeros(len(portfolio)),
        unit_size=10000,
        max_units=15000
    )

    if A is not None:
        print(f"\nExpected Loss: ${el:,.0f}")
        print(f"Expected (from Excel): $14,221,863")
        print(f"Erro: {abs(el - 14_221_863) / 14_221_863 * 100:.4f}%")
