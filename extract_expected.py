"""Extrai os KPIs publicados no arquivo XLS oficial do CreditRisk+.

Os valores devem ser lidos da tabela de percentis, e não recalculados a partir
da PMF exibida: a planilha mostra apenas uma cauda finita e, portanto, o momento
da coluna visível subestima a perda esperada.
"""

from __future__ import annotations

import pandas as pd


def extract_kpis(path: str = "references/CreditRisk+.xls") -> dict[str, dict[str, float]]:
    """Localiza, por rótulo, a média e o percentil de 99% em cada exemplo."""

    results: dict[str, dict[str, float]] = {}
    with pd.ExcelFile(path) as workbook:
        for sheet_name in ["Example1A", "Example1B", "Example1C", "Example2", "Example3"]:
            frame = pd.read_excel(workbook, sheet_name=sheet_name, header=None)
            expected_loss = None
            var_99 = None

            for row in range(len(frame)):
                for column in range(frame.shape[1] - 1):
                    label = frame.iat[row, column]
                    value = frame.iat[row, column + 1]
                    try:
                        numeric_value = float(value)
                    except (TypeError, ValueError):
                        numeric_value = None
                    if (
                        expected_loss is None
                        and str(label).strip() == "Mean"
                        and numeric_value is not None
                    ):
                        expected_loss = numeric_value
                    try:
                        is_99 = float(label) == 99.0
                    except (TypeError, ValueError):
                        is_99 = False
                    if var_99 is None and is_99 and numeric_value is not None:
                        var_99 = numeric_value

            if expected_loss is None or var_99 is None:
                raise ValueError(f"KPIs não encontrados na aba {sheet_name}.")
            results[sheet_name] = {"EL": expected_loss, "VaR99": var_99}
    return results


if __name__ == "__main__":
    print("Valores publicados na planilha oficial:")
    for sheet, metrics in extract_kpis().items():
        print(f"{sheet}: EL = {metrics['EL']:.0f}, VaR99 = {metrics['VaR99']:.0f}")
