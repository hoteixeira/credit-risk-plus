"""
CreditRisk+ - Um modelo estatístico para risco de crédito em portfólios.

Desenvolvido por Credit Suisse First Boston (1997).
Implementação em Python com suporte a:
- Taxas de default fixas e variáveis
- Análise setorial (fatores sistemáticos)
- Distribuição de perdas (modelo recursivo)
- Capital econômico
- Contribuições de risco

Componentes principais:
- model.CreditRiskPlus: classe central do modelo
- data: carregamento de dados e tabelas de referência
- plots: visualizações de distribuições e análises
"""

from .model import CreditRiskPlus
from . import data
from . import plots

__version__ = "1.0.0"
__all__ = ["CreditRiskPlus", "data", "plots"]
