"""Implementação auditável do modelo CreditRisk+ (CSFB, 1997)."""

from .model import CreditRiskPlus
from .simple_model import (
    LossDistributionResult,
    SectorParameters,
    analytic_loss_moments,
    calculate_loss_distribution,
    calculate_loss_distribution_detailed,
    loss_quantile,
)
from . import data
from . import plots

__version__ = "2.0.0"
__all__ = [
    "CreditRiskPlus",
    "LossDistributionResult",
    "SectorParameters",
    "analytic_loss_moments",
    "calculate_loss_distribution",
    "calculate_loss_distribution_detailed",
    "loss_quantile",
    "data",
    "plots",
]
