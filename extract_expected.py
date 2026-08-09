"""Extrai todos os valores de referência gravados no arquivo XLS oficial.

A planilha `references/CreditRisk+.xls` não guarda apenas os dois KPIs que a
suíte antiga lia. Ela publica, para cada exemplo:

* a perda esperada e a tabela completa de percentis;
* a perda esperada e a contribuição de risco de cada contraparte;
* a função de massa de probabilidade inteira, ponto a ponto na grade ``n * L``.

Esses números são o padrão-ouro do projeto: foram produzidos pelo add-in
original do Credit Suisse, que não acompanha o repositório (o arquivo não contém
VBA nem XLM). Lê-los da planilha, em vez de recalculá-los, é o que permite que os
testes sejam uma regressão de verdade e não uma tautologia.

Os KPIs devem sair da tabela de percentis, e não de um momento recalculado sobre
a coluna da PMF: a planilha imprime apenas uma cauda finita, então a média da
coluna visível subestima a perda esperada em cerca de 0,3%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


SHEETS = ("Example1A", "Example1B", "Example1C", "Example2", "Example3")

# Precisão de impressão da planilha: as probabilidades têm seis casas decimais,
# logo dois valores só são distinguíveis acima de meia unidade da última casa.
PMF_PRINT_TOLERANCE = 5e-7


@dataclass(frozen=True)
class SheetReference:
    """Todos os valores publicados em uma aba de exemplo do XLS."""

    expected_loss: float
    percentiles: dict[float, float]
    loss_amounts: np.ndarray
    loss_probabilities: np.ndarray
    obligor_expected_losses: np.ndarray = field(default_factory=lambda: np.empty(0))
    obligor_risk_contributions: np.ndarray = field(default_factory=lambda: np.empty(0))

    @property
    def var_99(self) -> float:
        """Atalho para o percentil de 99%, usado na regressão histórica."""

        return self.percentiles[99.0]


def _find_label(frame: pd.DataFrame, label: str) -> tuple[int, int] | None:
    """Localiza a primeira célula cujo texto seja exatamente ``label``.

    A busca é por rótulo porque o layout muda entre as abas: o Example1C começa
    dezenas de linhas abaixo dos demais e cada exemplo desloca as colunas de
    saída conforme o número de setores.
    """

    for row in range(frame.shape[0]):
        for column in range(frame.shape[1]):
            if str(frame.iat[row, column]).strip() == label:
                return row, column
    return None


def _numeric_column(frame: pd.DataFrame, first_row: int, column: int) -> np.ndarray:
    """Lê uma coluna numérica contígua, parando na primeira célula não numérica."""

    values: list[float] = []
    for row in range(first_row, frame.shape[0]):
        value = pd.to_numeric(frame.iat[row, column], errors="coerce")
        if pd.isna(value):
            break
        values.append(float(value))
    return np.asarray(values, dtype=float)


def extract_sheet(frame: pd.DataFrame) -> SheetReference:
    """Lê perda esperada, percentis, contribuições e PMF de uma aba."""

    percentile_cell = _find_label(frame, "Percentile")
    if percentile_cell is None:
        raise ValueError("Tabela de percentis não encontrada.")
    row, column = percentile_cell

    expected_loss = None
    percentiles: dict[float, float] = {}
    for offset in range(1, 15):
        label = frame.iat[row + offset, column]
        value = pd.to_numeric(frame.iat[row + offset, column + 1], errors="coerce")
        if pd.isna(value):
            continue
        if str(label).strip() == "Mean":
            expected_loss = float(value)
            continue
        level = pd.to_numeric(label, errors="coerce")
        if not pd.isna(level):
            percentiles[float(level)] = float(value)
    if expected_loss is None or not percentiles:
        raise ValueError("Perda esperada ou percentis ausentes na aba.")

    # A PMF é o único par de colunas rotulado "Amount" seguido de "Probability".
    amounts = probabilities = np.empty(0)
    for search_row in range(frame.shape[0]):
        for search_column in range(frame.shape[1] - 1):
            here = str(frame.iat[search_row, search_column]).strip()
            right = str(frame.iat[search_row, search_column + 1]).strip()
            if here == "Amount" and right == "Probability":
                amounts = _numeric_column(frame, search_row + 1, search_column)
                probabilities = _numeric_column(frame, search_row + 1, search_column + 1)
                break
        if amounts.size:
            break
    if not amounts.size:
        raise ValueError("Distribuição de perdas não encontrada na aba.")

    # As contribuições ficam à direita da coluna de perda esperada por contraparte.
    expected_losses = contributions = np.empty(0)
    contribution_cell = _find_label(frame, "Contribution")
    if contribution_cell is not None:
        contribution_row, contribution_column = contribution_cell
        contributions = _numeric_column(frame, contribution_row + 1, contribution_column)
        expected_losses = _numeric_column(frame, contribution_row + 1, contribution_column - 1)

    return SheetReference(
        expected_loss=expected_loss,
        percentiles=percentiles,
        loss_amounts=amounts,
        loss_probabilities=probabilities,
        obligor_expected_losses=expected_losses,
        obligor_risk_contributions=contributions,
    )


def extract_references(
    path: str = "references/CreditRisk+.xls",
) -> dict[str, SheetReference]:
    """Lê os cinco exemplos oficiais em uma única abertura do arquivo."""

    with pd.ExcelFile(path) as workbook:
        return {
            sheet: extract_sheet(pd.read_excel(workbook, sheet_name=sheet, header=None))
            for sheet in SHEETS
        }


def extract_kpis(
    path: str = "references/CreditRisk+.xls",
) -> dict[str, dict[str, float]]:
    """API histórica: devolve apenas ``{"EL": ..., "VaR99": ...}`` por aba."""

    return {
        sheet: {"EL": reference.expected_loss, "VaR99": reference.var_99}
        for sheet, reference in extract_references(path).items()
    }


if __name__ == "__main__":
    print("Valores publicados na planilha oficial:")
    for sheet, reference in extract_references().items():
        print(
            f"{sheet}: EL = {reference.expected_loss:,.0f}, "
            f"VaR99 = {reference.var_99:,.0f}, "
            f"{len(reference.percentiles)} percentis, "
            f"{reference.loss_amounts.size} pontos de PMF, "
            f"{reference.obligor_risk_contributions.size} contribuições"
        )
