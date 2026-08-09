"""Visualizações do CreditRisk+.

As funções deste módulo não calculam nada: elas apenas apresentam o que o núcleo
já produziu. Duas decisões de apresentação merecem destaque porque afetam a
leitura dos resultados.

Primeira: a distribuição de perdas é uma série infinita truncada em
``max_loss_dollars``, e quase toda a massa fica concentrada num intervalo muito
menor do que o domínio calculado. Desenhar o suporte inteiro produz um gráfico
onde a região de interesse ocupa menos de 2% do eixo. Por isso os gráficos
recortam o eixo em torno de um quantil alto.

Segunda: percentis podem ser lidos de duas formas — o quantil discreto, que é o
VaR matemático da distribuição, e a interpolação linear usada pela planilha
oficial. As tabelas deste módulo declaram explicitamente qual convenção usam.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional


# Quantil usado para recortar o eixo de perdas, com folga, nos gráficos.
_DISPLAY_QUANTILE = 0.999
_DISPLAY_MARGIN = 1.15


def _display_limit(model) -> float:
    """Escolhe até onde desenhar o eixo de perdas, em milhões.

    O domínio calculado costuma ser dezenas de vezes mais largo do que a região
    onde a probabilidade é visível. O corte usa um quantil alto com folga, de modo
    que a cauda relevante para capital econômico continue inteiramente no gráfico.
    """

    cdf = np.cumsum(model.loss_pmf)
    reachable = min(_DISPLAY_QUANTILE, float(cdf[-1]) - 1e-12)
    index = int(np.searchsorted(cdf, reachable, side="left"))
    return max(index * model.unit_size * _DISPLAY_MARGIN, model.unit_size) / 1e6


def _contribution_column(rc_df: pd.DataFrame) -> str:
    """Descobre a coluna de contribuição ao percentil dentro do DataFrame.

    O nome depende do percentil pedido em ``calculate_risk_contributions``
    (``risk_contribution_99pct``, ``risk_contribution_99.9pct`` e assim por
    diante), então ele é detectado em vez de assumido.
    """

    candidates = [
        column
        for column in rc_df.columns
        if column.startswith("risk_contribution_") and column.endswith("pct")
    ]
    if not candidates:
        raise ValueError(
            "DataFrame sem coluna de contribuição ao percentil. "
            "Use CreditRiskPlus.calculate_risk_contributions()."
        )
    return candidates[0]


def plot_loss_distribution(model, figsize=(12, 5)):
    """Plota a distribuição de perdas (PMF e CDF).

    Parâmetros:
    -----------
    model : CreditRiskPlus
        Modelo já calculado.
    figsize : tuple
        Tamanho da figura.

    A PMF mostra a probabilidade de cada nível discreto de perda; a CDF acumula
    essas probabilidades e é onde os percentis são lidos.
    """
    if model.loss_pmf is None:
        raise ValueError("Modelo não foi calculado. Use calculate_loss_distribution() primeiro.")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    loss_values = np.arange(len(model.loss_pmf)) * model.unit_size / 1e6  # em milhões
    limit = _display_limit(model)

    # PMF (função de massa de probabilidade). A perda vive numa grade discreta de
    # múltiplos de L, então a curva é uma sequência de pontos, não um contínuo.
    ax1.plot(loss_values, model.loss_pmf, linewidth=1.2, color='steelblue')
    ax1.set_xlabel('Perda (milhões)', fontsize=11)
    ax1.set_ylabel('Probabilidade', fontsize=11)
    ax1.set_title('Função de Massa de Probabilidade (PMF)', fontsize=12, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    ax1.set_xlim(0, limit)

    # CDF (função de distribuição cumulativa).
    ax2.plot(loss_values, model.loss_cdf, linewidth=2, color='darkblue')
    ax2.axhline(y=0.99, color='red', linestyle='--', linewidth=1.5, label='99º percentil')
    ax2.axhline(y=0.975, color='orange', linestyle='--', linewidth=1.5, label='97.5º percentil')
    ax2.set_xlabel('Perda (milhões)', fontsize=11)
    ax2.set_ylabel('Probabilidade Acumulada', fontsize=11)
    ax2.set_title('Função de Distribuição Cumulativa (CDF)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower right')
    ax2.set_xlim(0, limit)
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
    Plota as contribuições de risco das contrapartes.

    Parâmetros:
    -----------
    rc_df : pd.DataFrame
        Saída de ``CreditRiskPlus.calculate_risk_contributions()``, qualquer que
        seja o percentil escolhido.
    top_n : int
        Número de contrapartes a plotar.
    figsize : tuple
        Tamanho da figura.

    A contribuição responde quanto do capital da carteira é atribuível a cada
    contraparte. Ela não é a perda que a contraparte causaria sozinha, e sim sua
    parcela do risco conjunto (equações 121 e 102 do manual).
    """
    fig, ax = plt.subplots(figsize=figsize)

    column = _contribution_column(rc_df)
    df_sorted = rc_df.nlargest(top_n, column)

    obligor_labels = [f"Obl. {oid}\n({rating})" for oid, rating in
                      zip(df_sorted['obligor_id'], df_sorted['rating'])]
    rc_values = df_sorted[column].values / 1e6  # em milhões

    bars = ax.barh(range(len(df_sorted)), rc_values, color='coral', edgecolor='black', alpha=0.7)

    # Adiciona labels com valores
    for i, (bar, rc) in enumerate(zip(bars, rc_values)):
        ax.text(rc, i, f' {rc:.1f}M', va='center', fontsize=9, fontweight='bold')

    # O rótulo do percentil vem do próprio nome da coluna.
    level = column.removeprefix('risk_contribution_').removesuffix('pct')
    ax.set_yticks(range(len(df_sorted)))
    ax.set_yticklabels(obligor_labels)
    ax.set_xlabel(f'Contribuição de Risco @ {level}º Percentil (milhões)', fontsize=11)
    ax.set_title(f'Top {top_n} Contrapartes por Contribuição de Risco', fontsize=12, fontweight='bold')
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


def create_summary_table(
    model,
    percentiles: Optional[List[float]] = None,
    *,
    interpolate: bool = False,
) -> pd.DataFrame:
    """
    Cria uma tabela de sumário com estatísticas principais.

    Parâmetros:
    -----------
    model : CreditRiskPlus
        Modelo calculado.
    percentiles : List[float], optional
        Percentis a incluir.
    interpolate : bool
        ``False`` (padrão) reporta o quantil discreto, que é o VaR da distribuição.
        ``True`` reporta a interpolação linear da planilha oficial, útil apenas
        para comparar linha a linha com o XLS. Os dois diferem por menos de uma
        unidade ``L``, mas a diferença é visível ao confrontar valores publicados.

    Retorna:
    --------
    pd.DataFrame
        Tabela de sumário, com a convenção de quantil indicada em cada linha.
    """
    if percentiles is None:
        percentiles = [50, 75, 95, 97.5, 99, 99.5, 99.9]

    convention = 'interpolado' if interpolate else 'discreto'
    data = {
        'Métrica': [
            'Exposição Total',
            'Num. Contrapartes',
            'Num. Setores',
            'Perda Esperada',
            'Volatilidade (σ)',
            'Variância',
        ] + [f'{p:.1f}º Percentil ({convention})' for p in percentiles],

        'Valor': [
            f'{model.obligors["exposure"].sum():,.0f}',
            f'{model.num_obligors}',
            f'{model.num_sectors}',
            f'{model.expected_loss:,.0f}',
            f'{model.loss_std:,.0f}',
            f'{model.loss_variance:,.0f}',
        ] + [
            f'{model.get_percentile_loss(p, interpolate=interpolate):,.0f}'
            for p in percentiles
        ]
    }

    return pd.DataFrame(data)
