"""
Modelo Credit Risk+ - Classe principal.

Implementa o modelo estatístico de risco de crédito desenvolvido pelo
Credit Suisse First Boston (1997).

Referência: Seções A2-A13 do Apêndice A do documento original.
"""

import numpy as np
import pandas as pd
from scipy import stats, special
from typing import Dict, Tuple, List, Optional


class CreditRiskPlus:
    """
    Modelo Credit Risk+ para distribuição de perdas por default em portfólios de crédito.

    Características principais:
    - Modelagem de eventos de default usando técnicas de seguros
    - Incorporação de volatilidade nas taxas de default (distribução Gama)
    - Análise setorial para capturar fatores sistemáticos
    - Cálculo analítico de distribuição de perdas via recursão
    - Contribuições de risco aditivas aos percentis de perda

    Parâmetros:
    -----------
    unit_size : float
        Tamanho de unidade L para agrupamento de exposições (default: 10000)
    max_loss_units : int
        Número máximo de unidades de perda para calcular (default: 20000)
    """

    def __init__(self, unit_size: float = 10000, max_loss_units: int = 20000):
        """Inicializa o modelo Credit Risk+."""
        self.unit_size = unit_size
        self.max_loss_units = max_loss_units

        # Dados do portfólio
        self.obligors = None
        self.num_obligors = 0
        self.sectors = None
        self.num_sectors = 0

        # Resultados do modelo
        self.loss_pmf = None  # P(loss = n*L)
        self.loss_cdf = None
        self.expected_loss = None
        self.loss_variance = None
        self.loss_std = None

    def set_portfolio(self, obligors_df: pd.DataFrame, sector_columns: Optional[List[str]] = None):
        """
        Define o portfólio de obrigadores.

        Parâmetros:
        -----------
        obligors_df : pd.DataFrame
            DataFrame com colunas: obligor_id, exposure, mean_default_rate, std_default_rate
            e colunas de peso de setor (ex: sector_weight_US, sector_weight_Japan, etc.)
        sector_columns : List[str], optional
            Nome das colunas que representam pesos de setores.
            Se None, detecta automaticamente colunas starting com 'sector_weight_'
        """
        self.obligors = obligors_df.copy()
        self.num_obligors = len(self.obligors)

        # Detecta setores
        if sector_columns is None:
            sector_columns = [col for col in self.obligors.columns if col.startswith('sector_weight_')]

        if not sector_columns:
            raise ValueError("Nenhuma coluna de setor encontrada. Use colunas como 'sector_weight_US'")

        self.sector_columns = sector_columns
        self.sectors = {col.replace('sector_weight_', ''): i for i, col in enumerate(sector_columns)}
        self.num_sectors = len(self.sectors)

    def _band_exposures(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Agrupa exposições em unidades de tamanho unit_size.

        Retorna:
        --------
        band_sizes : np.ndarray
            Tamanho de cada banda (v_j em unidades de L)
        expected_losses : np.ndarray
            Perda esperada em cada banda (ε_j)
        obligor_sector_weights : np.ndarray
            Matriz (num_obligors x num_sectors) de pesos de setor para cada obrigador
        """
        if self.obligors is None:
            raise ValueError("Portfólio não foi definido. Use set_portfolio()")

        # Arredonda exposições para o tamanho de unidade mais próximo
        exposures = self.obligors['exposure'].values
        band_sizes = np.round(exposures / self.unit_size).astype(int)
        band_sizes = np.maximum(band_sizes, 1)  # Mínimo de 1 unidade

        # Calcula perdas esperadas por banda
        # ε_j = p_j * exposure (taxa de default × exposição)
        default_rates = self.obligors['mean_default_rate'].values
        expected_losses = default_rates * exposures

        # Matriz de pesos de setor (obligor × setor)
        obligor_sector_weights = self.obligors[self.sector_columns].values

        return band_sizes, expected_losses, obligor_sector_weights

    def _calculate_sector_parameters(self, band_sizes: np.ndarray, expected_losses: np.ndarray,
                                      obligor_sector_weights: np.ndarray) -> Dict:
        """
        Calcula parâmetros de cada setor (Apêndice A, Eq 90-97).

        Retorna:
        --------
        dict
            Parâmetros por setor: mu_k, sigma_k, alpha_k, beta_k, p_k, severity_poly_coeffs
        """
        sector_params = {}

        for sector_name, sector_idx in self.sectors.items():
            # Pesos de cada obrigador neste setor
            sector_weights = obligor_sector_weights[:, sector_idx]

            # Taxa de default e volatilidade
            default_rates = self.obligors['mean_default_rate'].values
            std_default_rates = self.obligors['std_default_rate'].values

            # μ_k = Σ θ_Ak * p_A (Eq 90-94)
            # Esperança do número de defaults no setor
            mu_k = np.sum(sector_weights * default_rates * band_sizes)

            # σ_k: volatilidade dos defaults (Eq 97)
            # Aproximação: σ_k = Σ θ_Ak * σ_A (em termos de taxas)
            sigma_k = np.sum(sector_weights * std_default_rates * band_sizes)

            # Evita divisão por zero
            if mu_k < 1e-10:
                mu_k = 1e-10
            if sigma_k < 1e-10:
                sigma_k = 1e-10

            # Parâmetros da distribuição Gama (Eq 52, 60)
            alpha_k = mu_k ** 2 / (sigma_k ** 2)
            beta_k = sigma_k ** 2 / mu_k
            p_k = beta_k / (1 + beta_k)

            # Polinômio de severidade para este setor (Eq 62-64)
            # P_k(z) = (1/μ_k) Σ (ε_j / v_j) * z^{v_j}
            severity_coeffs = np.zeros(self.max_loss_units + 1)

            for obligor_idx, weight in enumerate(sector_weights):
                if weight > 0:
                    band = band_sizes[obligor_idx]
                    el = expected_losses[obligor_idx]

                    # Contribuição deste obrigador ao polinômio
                    coeff = weight * el / band  # ε_j / v_j com peso do setor

                    if band <= self.max_loss_units:
                        severity_coeffs[band] += coeff

            # Normaliza para o polinômio de severidade
            if mu_k > 0:
                severity_coeffs = severity_coeffs / mu_k

            sector_params[sector_name] = {
                'mu': mu_k,
                'sigma': sigma_k,
                'alpha': alpha_k,
                'beta': beta_k,
                'p': p_k,
                'severity_poly': severity_coeffs
            }

        return sector_params

    def calculate_loss_distribution(self) -> np.ndarray:
        """
        Calcula a distribuição de perdas usando a recursão de Apêndice A (Credit Suisse).

        Recursão:  A_n = (1/n) * Σ_j [ε_j * A_{n-v_j}]
        Onde:
        - A_n = P(loss = n unidades)
        - ε_j = perda esperada do obrigador j
        - v_j = tamanho da banda do obrigador j

        Retorna:
        --------
        np.ndarray
            PMF de perdas
        """
        band_sizes, expected_losses, obligor_sector_weights = self._band_exposures()

        # Agregação para cada setor
        all_A = []

        for sector_idx, (sector_name, _) in enumerate(self.sectors.items()):
            # Obtém bandas e perdas esperadas para este setor
            sector_bands_and_losses = []

            for obligor_idx in range(len(band_sizes)):
                weight = obligor_sector_weights[obligor_idx, sector_idx]
                if weight > 1e-10:
                    band = band_sizes[obligor_idx]
                    # Perda esperada escalada pelo peso do setor, EM UNIDADES (dividir por unit_size)
                    el_weighted_dollars = expected_losses[obligor_idx] * weight
                    el_weighted_units = el_weighted_dollars / self.unit_size
                    sector_bands_and_losses.append((band, el_weighted_units))

            if not sector_bands_and_losses:
                continue

            # Calcula total esperado para A_0
            total_expected_loss = sum(el for _, el in sector_bands_and_losses)

            # Aplica volatilidade: calcula sigma do setor (EM UNIDADES)
            sigma_sector = 0.0
            for obligor_idx in range(len(band_sizes)):
                weight = obligor_sector_weights[obligor_idx, sector_idx]
                if weight > 1e-10:
                    # Sigma também deve estar em unidades
                    sigma_dollars = (weight *
                                    self.obligors.iloc[obligor_idx]['std_default_rate'] *
                                    band_sizes[obligor_idx] * self.unit_size)
                    sigma_units = sigma_dollars / self.unit_size
                    sigma_sector += sigma_units

            # A_0 = exp(-total_expected_loss) com ajuste por volatilidade
            if sigma_sector > 0:
                # Usa fator de volatilidade: reduz A_0 para dar mais peso na cauda
                # alpha = (mu/sigma)^2
                alpha = (total_expected_loss / sigma_sector) ** 2
                volatility_factor = (total_expected_loss / (total_expected_loss + sigma_sector)) ** alpha
                A_0 = volatility_factor * np.exp(-total_expected_loss)
            else:
                A_0 = np.exp(-total_expected_loss)

            # Recursão de Apêndice A
            A_sector = np.zeros(self.max_loss_units + 1)
            A_sector[0] = A_0

            for n in range(1, self.max_loss_units + 1):
                A_n = 0.0
                for band, el in sector_bands_and_losses:
                    if band <= n:
                        A_n += el * A_sector[n - band]

                if n > 0:
                    A_sector[n] = A_n / n

            # Normaliza este setor
            A_sum = np.sum(A_sector)
            if A_sum > 0:
                A_sector = A_sector / A_sum

            all_A.append(A_sector)

        # Convolve setores (independência entre setores)
        A = all_A[0] if all_A else np.array([1.0] + [0.0] * self.max_loss_units)

        for A_sector in all_A[1:]:
            # Convolução eficiente
            A_new = np.zeros(self.max_loss_units + 1)
            for i in range(min(len(A), self.max_loss_units + 1)):
                if A[i] < 1e-15:
                    continue
                for j in range(min(len(A_sector), self.max_loss_units + 1 - i)):
                    if A_sector[j] < 1e-15:
                        continue
                    if i + j <= self.max_loss_units:
                        A_new[i + j] += A[i] * A_sector[j]

            A = A_new

        # Normaliza final
        A_sum = np.sum(A)
        if A_sum > 0:
            A = A / A_sum
        else:
            A[0] = 1.0

        self.loss_pmf = A
        self._compute_statistics()

        return A

    def _compute_statistics(self):
        """Calcula estatísticas da distribuição de perdas."""
        if self.loss_pmf is None:
            raise ValueError("PMF não foi calculada. Use calculate_loss_distribution() primeiro.")

        # Loss units em valor monetário
        loss_values = np.arange(len(self.loss_pmf)) * self.unit_size

        # Expected loss
        self.expected_loss = np.sum(loss_values * self.loss_pmf)

        # Variance
        second_moment = np.sum((loss_values ** 2) * self.loss_pmf)
        self.loss_variance = second_moment - (self.expected_loss ** 2)
        self.loss_std = np.sqrt(self.loss_variance)

        # CDF
        self.loss_cdf = np.cumsum(self.loss_pmf)

    def get_percentile_loss(self, percentile: float) -> float:
        """
        Retorna a perda no percentil especificado (Value at Risk).

        Parâmetros:
        -----------
        percentile : float
            Percentil (0-100) desejado

        Retorna:
        --------
        float
            Valor de perda no percentil
        """
        if self.loss_cdf is None:
            raise ValueError("Distribuição não foi calculada.")

        # Encontra o índice onde CDF ultrapassa o percentil
        target_prob = percentile / 100.0
        idx = np.searchsorted(self.loss_cdf, target_prob)
        idx = min(idx, len(self.loss_pmf) - 1)

        return idx * self.unit_size

    def get_percentile_losses(self, percentiles: List[float]) -> Dict[float, float]:
        """
        Retorna perdas em múltiplos percentis.

        Parâmetros:
        -----------
        percentiles : List[float]
            Lista de percentis (0-100)

        Retorna:
        --------
        dict
            Mapeamento {percentil: perda}
        """
        return {p: self.get_percentile_loss(p) for p in percentiles}

    def get_economic_capital(self, percentile: float = 99) -> float:
        """
        Calcula o capital econômico no percentil especificado.

        Capital Econômico = VaR(percentil) - Perda Esperada

        Parâmetros:
        -----------
        percentile : float
            Nível de confiança (default: 99%)

        Retorna:
        --------
        float
            Capital econômico requerido
        """
        var = self.get_percentile_loss(percentile)
        return var - self.expected_loss

    def calculate_risk_contributions(self) -> pd.DataFrame:
        """
        Calcula as contribuições de risco de cada obrigador (Apêndice A, Eq 98-103).

        A contribuição de risco é definida como o impacto incremental de cada exposição
        na perda esperada e na perda em um percentil específico.

        Retorna:
        --------
        pd.DataFrame
            DataFrame com risk_contribution (desvio padrão) e rc_99pct (percentil 99%)
        """
        if self.loss_std is None or self.loss_std == 0:
            raise ValueError("Distribuição não foi calculada ou variância é zero.")

        # Contribuição à esperança é simples
        expected_loss_contributions = (
            self.obligors['mean_default_rate'].values *
            self.obligors['exposure'].values
        )

        # Contribuição ao desvio padrão (Eq 98)
        # RC_A = (E_A / 2σ) * (dσ²/dE_A)
        # Aproximação: RC_A ≈ (E_A / σ) * (σ_A - p_A)
        exposures = self.obligors['exposure'].values
        default_rates = self.obligors['mean_default_rate'].values
        std_default_rates = self.obligors['std_default_rate'].values

        risk_contributions_std = (
            (exposures / self.loss_std) *
            (std_default_rates - default_rates) / 2
        )

        # Garante que RC soma ao sigma do portfólio
        # (pequeno ajuste se necessário)
        rc_sum = np.sum(risk_contributions_std)
        if rc_sum > 0:
            risk_contributions_std = risk_contributions_std * (self.loss_std / rc_sum)

        # Contribuição ao percentil 99%
        var_99 = self.get_percentile_loss(99)
        multiplier_99 = (var_99 - self.expected_loss) / self.loss_std if self.loss_std > 0 else 0

        rc_percentile = (
            expected_loss_contributions +
            multiplier_99 * risk_contributions_std
        )

        result_df = self.obligors[['obligor_id', 'exposure', 'rating']].copy()
        result_df['expected_loss'] = expected_loss_contributions
        result_df['risk_contribution_std'] = risk_contributions_std
        result_df['risk_contribution_99pct'] = rc_percentile

        return result_df

    def summary(self, percentiles: Optional[List[float]] = None) -> Dict:
        """
        Retorna um sumário de estatísticas do portfólio.

        Parâmetros:
        -----------
        percentiles : List[float], optional
            Percentis a incluir no sumário (default: [50, 75, 95, 97.5, 99, 99.5, 99.9])

        Retorna:
        --------
        dict
            Dicionário com estatísticas principais
        """
        if percentiles is None:
            percentiles = [50, 75, 95, 97.5, 99, 99.5, 99.9]

        percentile_losses = self.get_percentile_losses(percentiles)

        return {
            'total_exposure': self.obligors['exposure'].sum(),
            'num_obligors': self.num_obligors,
            'num_sectors': self.num_sectors,
            'expected_loss': self.expected_loss,
            'loss_std': self.loss_std,
            'loss_variance': self.loss_variance,
            'percentile_losses': percentile_losses,
            'economic_capital_99pct': self.get_economic_capital(99),
        }

    def __repr__(self) -> str:
        """Representação do modelo."""
        if self.expected_loss is None:
            return f"CreditRiskPlus(unit_size={self.unit_size}, not calculated)"
        else:
            return (f"CreditRiskPlus(EL={self.expected_loss:,.0f}, "
                    f"99th={self.get_percentile_loss(99):,.0f}, "
                    f"EC={self.get_economic_capital(99):,.0f})")
