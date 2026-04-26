"""
Módulo de visualizações para o Credit Risk+.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional


def plot_loss_distribution(model, figsize=(12, 5)):
    """
    Plota a distribuição de perdas (PMF e CDF).

    Parâmetros:
    -----------
    model : CreditRiskPlus
        Modelo calculado
    figsize : tuple
        Tamanho da figura
    """
    if model.loss_pmf is None:
        raise ValueError("Modelo não foi calculado. Use calculate_loss_distribution() primeiro.")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    # PMF (função de massa de probabilidade)
    loss_values = np.arange(len(model.loss_pmf)) * model.unit_size / 1e6  # em milhões
    pmf_values = model.loss_pmf

    ax1.bar(loss_values, pmf_values, width=0.5, alpha=0.7, color='steelblue', edgecolor='black')
    ax1.set_xlabel('Perda (milhões)', fontsize=11)
    ax1.set_ylabel('Probabilidade', fontsize=11)
    ax1.set_title('Função de Massa de Probabilidade (PMF)', fontsize=12, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    ax1.set_xlim(left=0)

    # CDF (função de distribuição cumulativa)
    cdf_values = model.loss_cdf

    ax2.plot(loss_values, cdf_values, linewidth=2, color='darkblue', marker='o', markersize=3, alpha=0.7)
    ax2.axhline(y=0.99, color='red', linestyle='--', linewidth=1.5, label='99º percentil')
    ax2.axhline(y=0.975, color='orange', linestyle='--', linewidth=1.5, label='97.5º percentil')
    ax2.set_xlabel('Perda (milhões)', fontsize=11)
    ax2.set_ylabel('Probabilidade Acumulada', fontsize=11)
    ax2.set_title('Função de Distribuição Cumulativa (CDF)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower right')
    ax2.set_xlim(left=0)
    ax2.set_ylim([0, 1])

    plt.tight_layout()
    return fig


def plot_percentile_losses(percentiles: Dict[float, float], title: str = "Perdas por Percentil"):
    """
    Plota as perdas em diferentes percentis.

    Parâmetros:
    -----------
    percentiles : Dict[float, float]
        Mapeamento {percentil: perda}
    title : str
        Título do gráfico
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    pcts = sorted(percentiles.keys())
    losses = [percentiles[p] / 1e6 for p in pcts]  # em milhões

    bars = ax.bar(range(len(pcts)), losses, color='steelblue', edgecolor='black', alpha=0.7)

    # Adiciona labels com valores
    for bar, loss in zip(bars, losses):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                f'{loss:.1f}M',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_xlabel('Percentil', fontsize=11)
    ax.set_ylabel('Perda (milhões)', fontsize=11)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xticks(range(len(pcts)))
    ax.set_xticklabels([f'{p:.1f}%' for p in pcts], rotation=45)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    return fig


def plot_risk_contributions(rc_df: pd.DataFrame, top_n: int = 10, figsize=(12, 6)):
    """
    Plota as contribuições de risco dos obrigadores.

    Parâmetros:
    -----------
    rc_df : pd.DataFrame
        DataFrame com risk_contribution_99pct
    top_n : int
        Número de obrigadores top a plotar
    figsize : tuple
        Tamanho da figura
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Ordena por risk contribution
    df_sorted = rc_df.nlargest(top_n, 'risk_contribution_99pct')

    obligor_labels = [f"Obl. {oid}\n({rating})" for oid, rating in
                      zip(df_sorted['obligor_id'], df_sorted['rating'])]
    rc_values = df_sorted['risk_contribution_99pct'].values / 1e6  # em milhões

    bars = ax.barh(range(len(df_sorted)), rc_values, color='coral', edgecolor='black', alpha=0.7)

    # Adiciona labels com valores
    for i, (bar, rc) in enumerate(zip(bars, rc_values)):
        ax.text(rc, i, f' {rc:.1f}M', va='center', fontsize=9, fontweight='bold')

    ax.set_yticks(range(len(df_sorted)))
    ax.set_yticklabels(obligor_labels)
    ax.set_xlabel('Contribuição de Risco @ 99º Percentil (milhões)', fontsize=11)
    ax.set_title(f'Top {top_n} Obrigadores por Contribuição de Risco', fontsize=12, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    return fig


def plot_comparison(examples: Dict[str, Dict], metric: str = 'percentile_loss_99pct'):
    """
    Compara métricas entre múltiplos exemplos.

    Parâmetros:
    -----------
    examples : Dict[str, Dict]
        Mapeamento {nome_exemplo: {'expected_loss': ..., 'percentile_loss_99pct': ..., ...}}
    metric : str
        Métrica a comparar
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    names = list(examples.keys())
    values = [examples[name][metric] / 1e6 for name in names]  # em milhões

    bars = ax.bar(range(len(names)), values, color='steelblue', edgecolor='black', alpha=0.7)

    # Adiciona labels com valores
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                f'{value:.1f}M',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Valor (milhões)', fontsize=11)
    ax.set_title(f'Comparação: {metric.replace("_", " ").title()}', fontsize=12, fontweight='bold')
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha='right')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    return fig


def create_summary_table(model, percentiles: Optional[List[float]] = None) -> pd.DataFrame:
    """
    Cria uma tabela de sumário com estatísticas principais.

    Parâmetros:
    -----------
    model : CreditRiskPlus
        Modelo calculado
    percentiles : List[float], optional
        Percentis a incluir (default: [50, 75, 95, 99])

    Retorna:
    --------
    pd.DataFrame
        Tabela de sumário
    """
    if percentiles is None:
        percentiles = [50, 75, 95, 97.5, 99, 99.5, 99.9]

    data = {
        'Métrica': [
            'Exposição Total',
            'Num. Obrigadores',
            'Num. Setores',
            'Perda Esperada',
            'Volatilidade (σ)',
            'Variância',
        ] + [f'{p:.1f}º Percentil' for p in percentiles],

        'Valor': [
            f'{model.obligors["exposure"].sum():,.0f}',
            f'{model.num_obligors}',
            f'{model.num_sectors}',
            f'{model.expected_loss:,.0f}',
            f'{model.loss_std:,.0f}',
            f'{model.loss_variance:,.0f}',
        ] + [f'{model.get_percentile_loss(p):,.0f}' for p in percentiles]
    }

    return pd.DataFrame(data)
