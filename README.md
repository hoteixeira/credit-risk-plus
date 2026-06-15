# Credit Risk+ — Guia de Estudos e Implementação em Python

Implementação completa do modelo **Credit Risk+** (Credit Suisse First Boston, 1997) com notebooks educacionais em português. Este repositório serve como guia de estudos e ferramenta prática para modelagem de risco de crédito de portfólio.

> **Documentação completa**: consulte a [Wiki do projeto](wiki/Home) para uma referência técnica detalhada, demonstrações matemáticas e discussão aprofundada do arcabouço teórico.

---

## Início Rápido

```bash
source venv/bin/activate
pip install -r requirements.txt
jupyter notebook
```

```python
import numpy as np
from creditriskplus.simple_model import calculate_loss_distribution
from creditriskplus import data

portfolio = data.create_example_1a_portfolio()

pmf, el = calculate_loss_distribution(
    exposures=portfolio['exposure'].values,
    mean_default_rates=portfolio['mean_default_rate'].values,
    std_default_rates=portfolio['std_default_rate'].values,
    recovery_rates=np.zeros(len(portfolio)),
)

cdf = np.cumsum(pmf)
unit_size = float(np.ceil(portfolio['exposure'].max() / 100))
idx_99 = np.searchsorted(cdf, 0.99)
var_99 = idx_99 * unit_size

print(f"E[Loss]  = ${el:,.0f}")      # $14,221,863
print(f"VaR(99%) = ${var_99:,.0f}")  # $55,311,503
```

---

## Visão Geral do Modelo

O Credit Risk+ constrói a **distribuição completa de perdas** de uma carteira de crédito, permitindo calcular o capital necessário para cobrir perdas inesperadas com um nível de confiança explícito (ex: 99%).

### Inputs principais

- Exposições líquidas $E_A^{\text{net}} = E_A(1 - RR_A)$.
- Probabilidades médias de default $p_A$.
- Volatilidades das taxas de default $\sigma_A$.
- Pesos setoriais $\theta_{Ak}$ com $\sum_k \theta_{Ak} = 1$.

### Discretização

As exposições são agrupadas em bandas de tamanho $L$:

$$
L = \left\lceil \frac{\max_A E_A^{\text{net}}}{100} \right\rceil, \qquad
\nu_A = \left\lceil \frac{E_A^{\text{net}}}{L} \right\rceil, \qquad
\varepsilon_A = \frac{p_A E_A^{\text{net}}}{L}
$$

### Caso de taxa variável (modelo completo)

A probability generating function (PGF) das perdas agregadas é:

$$
G(z) = \prod_{k=1}^{K} \left( \frac{1 - p_k}{1 - p_k P_k(z)} \right)^{\alpha_k}
$$

onde, para cada setor $k$:

$$
\mu_k = \sum_A \theta_{Ak} \frac{\varepsilon_A}{\nu_A}, \qquad
\sigma_k = \sum_A \theta_{Ak} \sigma_A \frac{E_A / L}{\nu_A}
$$

$$
\alpha_k = \frac{\mu_k^2}{\sigma_k^2}, \qquad
\beta_k = \frac{\sigma_k^2}{\mu_k}, \qquad
p_k = \frac{\beta_k}{1 + \beta_k}
$$

A recursão para a PMF $A_n = \mathbb{P}(\text{perda} = nL)$ é:

$$
A_0 = (1 - p)^{\alpha}
$$

$$
A_n = \frac{p}{n \mu} \sum_{j: \nu_j \le n} \varepsilon_j \left( \alpha - 1 + \frac{n}{\nu_j} \right) A_{n - \nu_j}
$$

O caso Poisson de taxa fixa é recuperado quando $\sigma_k \to 0$.

### Capital econômico

$$
EL = \sum_{n} n L \, A_n
$$

$$
VaR(q) = \min\{ nL : \sum_{i=0}^{n} A_i \ge q \}
$$

$$
EC(q) = VaR(q) - EL
$$

---

## Estrutura do Repositório

```
credit-risk-plus/
├── references/
│   ├── CreditRisk+.pdf        # Documento original (Credit Suisse, 1997)
│   └── CreditRisk+.xls        # Planilha de referência com exemplos
├── creditriskplus/
│   ├── simple_model.py        # Implementação principal (NB recursion)
│   ├── data.py                # Dados dos portfólios de exemplo
│   ├── plots.py               # Utilitários de visualização
│   ├── model.py               # Modelo alternativo
│   └── variable_model.py      # Extensões variáveis
├── notebooks/
│   ├── 01_introducao.ipynb
│   ├── 02_modelo_fixo.ipynb
│   ├── 03_modelo_variavel.ipynb
│   ├── 04_exemplo_1A.ipynb
│   ├── 05_exemplo_1B.ipynb
│   ├── 06_exemplo_1C_multi_ano.ipynb
│   ├── 07_exemplo_2_setores_geo.ipynb
│   ├── 08_exemplo_3_setores_fracionarios.ipynb
│   ├── 09_aplicacoes.ipynb
│   └── 10_simulacao_portfolio_varejo.ipynb
├── wiki/                      # Documentação técnica completa
├── run_tests.py               # Testes de validação
├── test_notebooks.py          # Testes dos notebooks
├── extract_expected.py        # Extrai valores esperados do XLS
└── requirements.txt           # Dependências
```

---

## API Principal

```python
from creditriskplus.simple_model import calculate_loss_distribution

pmf, el = calculate_loss_distribution(
    exposures,                          # array [N] de exposições brutas
    mean_default_rates,                 # array [N] de PDs médias
    std_default_rates,                  # array [N] de volatilidades de PD
    recovery_rates,                     # array [N] de taxas de recuperação
    sector_weights_matrix=None,         # array [N × K] de pesos setoriais
    idiosyncratic_sector_indices=None,  # lista de índices de setores idiossincráticos
    unit_size=None,                     # L (None = ceil(max_exp / 100))
    max_loss_dollars=150_000_000,       # truncamento da distribuição
)
```

| Parâmetro | Descrição |
|-----------|-----------|
| `exposures` | Exposições brutas em dólares |
| `mean_default_rates` | PDs médias por contraparte |
| `std_default_rates` | Volatilidades das PDs |
| `recovery_rates` | Taxas de recuperação [0,1] |
| `sector_weights_matrix` | Pesos setoriais $\theta_{Ak}$; `None` = 1 setor |
| `idiosyncratic_sector_indices` | Índices de setores idiossincráticos |
| `unit_size` | Unidade de perda $L$ |
| `max_loss_dollars` | Perda máxima a calcular |

**Retornos**:

- `pmf`: array $A[n] = \mathbb{P}(\text{perda} = n \cdot L)$.
- `el`: perda esperada em dólares.

---

## Guia dos Notebooks

| Notebook | Conteúdo |
|----------|----------|
| [01_introducao.ipynb](notebooks/01_introducao.ipynb) | Contexto histórico, tipos de risco e componentes |
| [02_modelo_fixo.ipynb](notebooks/02_modelo_fixo.ipynb) | Caso Poisson: PGF, bandas e recursão |
| [03_modelo_variavel.ipynb](notebooks/03_modelo_variavel.ipynb) | Mistura Poisson-Gama, NB e recursão geral |
| [04_exemplo_1A.ipynb](notebooks/04_exemplo_1A.ipynb) | Reprodução do Exemplo 1A (1 setor) |
| [05_exemplo_1B.ipynb](notebooks/05_exemplo_1B.ipynb) | Gestão de portfólio e redução de concentração |
| [06_exemplo_1C_multi_ano.ipynb](notebooks/06_exemplo_1C_multi_ano.ipynb) | Horizonte de 3 anos |
| [07_exemplo_2_setores_geo.ipynb](notebooks/07_exemplo_2_setores_geo.ipynb) | 3 setores geográficos |
| [08_exemplo_3_setores_fracionarios.ipynb](notebooks/08_exemplo_3_setores_fracionarios.ipynb) | Pesos fracionários + setor específico |
| [09_aplicacoes.ipynb](notebooks/09_aplicacoes.ipynb) | ACP, ICR, limites, stress testing e RARoC |
| [10_simulacao_portfolio_varejo.ipynb](notebooks/10_simulacao_portfolio_varejo.ipynb) | 1M clientes × 24 meses com Markov e choque macro |

---

## Validação

Todos os exemplos reproduzem os resultados da planilha `CreditRisk+.xls` com erro < 0,001%, exceto o Exemplo 3 (setor específico), que apresenta erro de +0,579% no VaR(99%) devido à ausência do código VBA original.

| Exemplo | E[Loss] (ref) | VaR(99%) (ref) | Erro EL | Erro VaR |
|---------|--------------:|---------------:|:-------:|:--------:|
| 1A | \$14.221.863 | \$55.311.503 | 0,000% | 0,000% |
| 1B | \$11.162.856 | \$39.946.857 | 0,000% | 0,000% |
| 1C | \$17.277.632 | \$62.100.307 | 0,000% | 0,000% |
| 2 | \$14.221.863 | \$49.931.502 | 0,000% | 0,000% |
| 3 | \$14.221.863 | \$47.368.235 | 0,000% | +0,579% |

---

## Dependências

```
numpy
pandas
matplotlib
scipy
xlrd
openpyxl
jupyter
notebook
```

Instalação:

```bash
pip install -r requirements.txt
```

---

## Testes

```bash
python run_tests.py
```

---

## Documentação Técnica Completa

Para uma referência completa com demonstrações matemáticas rigorosas, consulte a [Wiki](wiki/Home), que cobre:

- [Visão Geral](wiki/01-Visao-Geral)
- [Dados de Entrada](wiki/02-Dados-de-Entrada)
- [Modelo de Taxa Fixa (Poisson)](wiki/03-Modelo-Taxa-Fixa-Poisson)
- [Modelo de Taxa Variável (NB)](wiki/04-Modelo-Taxa-Variavel-NB)
- [Setores e Correlação](wiki/05-Setores-e-Correlacao)
- [Extensão Multi-Ano](wiki/06-Multi-Ano)
- [Capital Econômico](wiki/07-Capital-Economico)
- [Aplicações Práticas](wiki/08-Aplicacoes)
- [Implementação Python](wiki/09-Implementacao-Python)
- [Validação](wiki/10-Validacao)
- [Referências](wiki/11-Referencias)

---

## Referência

**Credit Suisse Financial Products** (1997). *CreditRisk+: A Credit Risk Management Framework*. Credit Suisse First Boston International.

O documento original está disponível em `references/CreditRisk+.pdf`. A planilha de referência com todos os exemplos está em `references/CreditRisk+.xls`.
