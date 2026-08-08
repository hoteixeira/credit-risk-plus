"""Teste de integração: executa todos os notebooks sem alterar os arquivos."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor


ROOT = Path(__file__).resolve().parent
NOTEBOOK_DIR = ROOT / "notebooks"


def execute_notebook(path: Path) -> None:
    """Executa uma cópia em memória com a raiz de imports esperada pelo notebook."""

    with path.open(encoding="utf-8") as stream:
        notebook = nbformat.read(stream, as_version=4)
    executor = ExecutePreprocessor(timeout=600, kernel_name="python3")
    executor.preprocess(notebook, {"metadata": {"path": str(NOTEBOOK_DIR)}})


if __name__ == "__main__":
    failures: list[tuple[str, str]] = []
    paths = sorted(NOTEBOOK_DIR.glob("*.ipynb"))
    for notebook_path in paths:
        print(f"Executando {notebook_path.name} ...", flush=True)
        try:
            execute_notebook(notebook_path)
        except Exception as error:  # a mensagem completa do nbclient já inclui a célula
            failures.append((notebook_path.name, str(error)))

    if failures:
        for name, message in failures:
            print(f"\nFALHA — {name}\n{message}")
        raise SystemExit(1)
    print(f"OK: {len(paths)} notebooks executados sem erro.")
