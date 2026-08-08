"""Camada de compatibilidade para a antiga API de taxa variável.

Historicamente este arquivo continha uma segunda recursão, que tratava apenas o
primeiro setor e calculava ``mu`` com dimensões incorretas. Manter uma única
fonte matemática evita divergência entre APIs; novos projetos devem importar
diretamente :func:`creditriskplus.calculate_loss_distribution`.
"""

from __future__ import annotations

import warnings

import numpy as np

from .simple_model import calculate_loss_distribution


def calculate_loss_distribution_variable(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_allocations=None,
    unit_size: float = 10_000,
    max_units: int = 15_000,
):
    """Delega a chamada legada ao núcleo validado do CreditRisk+.

    ``sector_allocations`` continua aceitando um dicionário ``nome -> pesos``.
    A ordem de inserção do dicionário define a ordem das colunas setoriais.
    """

    warnings.warn(
        "creditriskplus.variable_model é legado; use "
        "creditriskplus.calculate_loss_distribution.",
        DeprecationWarning,
        stacklevel=2,
    )

    weights = None
    if sector_allocations is not None:
        if not sector_allocations:
            raise ValueError("sector_allocations não pode ser um dicionário vazio.")
        weights = np.column_stack(
            [np.asarray(values, dtype=float) for values in sector_allocations.values()]
        )

    return calculate_loss_distribution(
        exposures=exposures,
        mean_default_rates=mean_default_rates,
        std_default_rates=std_default_rates,
        recovery_rates=recovery_rates,
        sector_weights_matrix=weights,
        unit_size=unit_size,
        max_loss_dollars=float(unit_size) * int(max_units),
    )
