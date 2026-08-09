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
from .vasicek_irb import (
    VasicekIRBResult,
    calculate_vasicek_irb,
    conditional_default_probability,
    conditional_portfolio_loss,
    downturn_default_probability,
    retail_asset_correlation,
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
    "VasicekIRBResult",
    "calculate_vasicek_irb",
    "conditional_default_probability",
    "conditional_portfolio_loss",
    "downturn_default_probability",
    "retail_asset_correlation",
    "data",
    "plots",
]
