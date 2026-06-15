# Implementação Python

Este capítulo documenta a implementação do Credit Risk+ em Python disponível no repositório. O código foi escrito para ser educacional, reprodutível e alinhado ao paper oficial e à planilha `CreditRisk+.xls`.

---

## 1. Estrutura do Pacote

O pacote principal é `creditriskplus/`:

```
creditriskplus/
├── __init__.py
├── simple_model.py       # Implementação principal (recursão NB)
├── data.py               # Dados dos exemplos e tabelas de rating
├── plots.py              # Utilitários de visualização
├── model.py              # Modelo alternativo
└── variable_model.py     # Extensões variáveis
```

### 1.1 `simple_model.py`

Contém a função principal `calculate_loss_distribution` e funções auxiliares para:

- Cálculo da unidade de perda $L$.
- Distribuição de um setor sistemático (fator Gama compartilhado).
- Distribuição do setor idiossincrático (convolução de NBs individuais).
- Convolução de setores.

### 1.2 `data.py`

Fornece:

- Tabela de ratings (`RATING_TABLE`).
- Tabela multi-ano (`MULTI_YEAR_RATING_TABLE`).
- Funções para criar os portfólios dos Exemplos 1A, 1B, 1C, 2 e 3.
- Carregamento de dados da planilha Excel original.

### 1.3 `plots.py`

Utilitários para visualização da distribuição de perdas, CDF, contribuições de risco e evolução temporal.

---

## 2. API Principal

### 2.1 `calculate_loss_distribution`

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

#### Parâmetros

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `exposures` | array [N] | Exposições brutas em dólares |
| `mean_default_rates` | array [N] | Probabilidades médias de default |
| `std_default_rates` | array [N] | Desvios-padrão das PDs |
| `recovery_rates` | array [N] | Taxas de recuperação [0,1] |
| `sector_weights_matrix` | array [N × K] ou None | Pesos setoriais; None = 1 setor |
| `idiosyncratic_sector_indices` | list[int] ou None | Índices de setores idiossincráticos |
| `unit_size` | float ou None | Unidade de perda L |
| `max_loss_dollars` | float | Perda máxima a calcular |

#### Retornos

| Retorno | Tipo | Descrição |
|---------|------|-----------|
| `pmf` | np.ndarray | $A[n] = \mathbb{P}(\text{perda total} = n \cdot L)$ |
| `el` | float | Perda esperada em dólares |

### 2.2 Exemplo de uso básico

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

print(f"E[Loss]  = ${el:,.0f}")
print(f"VaR(99%) = ${var_99:,.0f}")
```

---

## 3. Algoritmos Implementados

### 3.1 Setor sistemático

A função `_sector_distribution` implementa a recursão NB geral:

```python
A[0] = (1 - p_k) ** alpha_k
for n in range(1, max_n + 1):
    s_val = 0.0
    for vj, ej in zip(bands, epsilons):
        if vj <= n:
            s_val += ej * (alpha_k - 1.0 + n / vj) * A[n - vj]
    A[n] = (p_k / (n * mu_k)) * s_val
```

### 3.2 Setor idiossincrático

A função `_idiosyncratic_sector_distribution` implementa a convolução de NBs individuais com $\alpha_A = 4$:

```python
beta_a = 0.25 * mu_a
p_a = beta_a / (1.0 + beta_a)

A_indiv[0] = (1.0 - p_a) ** 4
for kk in range(1, max_n // v_a + 1):
    n_idx = kk * v_a
    A_indiv[n_idx] = p_a * (3 + kk) / kk * A_indiv[n_idx - v_a]

conv = np.convolve(A, A_indiv)
A = conv[:max_n + 1]
```

### 3.3 Multi-setor

A convolução de setores é feita iterativamente:

```python
A = np.array([1.0])
for k in range(n_sectors):
    w_k = sector_weights_matrix[:, k]
    if k in idio_set:
        A_k = _idiosyncratic_sector_distribution(...)
    else:
        A_k = _sector_distribution(...)
    conv = np.convolve(A, A_k)
    A = conv[:max_n + 1]
```

---

## 4. Notebooks Educacionais

A pasta `notebooks/` contém 10 notebooks que cobrem o modelo passo a passo:

| Notebook | Conteúdo |
|----------|----------|
| `01_introducao.ipynb` | Contexto histórico, pressupostos e componentes |
| `02_modelo_fixo.ipynb` | Derivação do caso Poisson e recursão de perdas |
| `03_modelo_variavel.ipynb` | Mistura Poisson-Gama, NB, recursão geral |
| `04_exemplo_1A.ipynb` | Reprodução do Exemplo 1A (25 contrapartes, 1 setor) |
| `05_exemplo_1B.ipynb` | Gestão de portfólio: remoção das maiores exposições |
| `06_exemplo_1C_multi_ano.ipynb` | Horizonte de 3 anos com contrapartes virtuais |
| `07_exemplo_2_setores_geo.ipynb` | 3 setores geográficos exclusivos |
| `08_exemplo_3_setores_fracionarios.ipynb` | 4 setores com pesos fracionários + setor específico |
| `09_aplicacoes.ipynb` | ACP, ICR, limites, stress testing, RARoC |
| `10_simulacao_portfolio_varejo.ipynb` | 1M clientes × 24 meses com Markov e choque macro |

---

## 5. Testes

O repositório inclui scripts de teste:

- `run_tests.py`: executa testes de validação dos exemplos contra a planilha.
- `test_notebooks.py`: verifica a execução dos notebooks.
- `extract_expected.py`: extrai valores esperados da planilha Excel.

Para executar:

```bash
source venv/bin/activate
python run_tests.py
```

---

## 6. Dependências

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

## 7. Início Rápido

```bash
source venv/bin/activate
pip install -r requirements.txt
jupyter notebook
```

Abrir o notebook `notebooks/04_exemplo_1A.ipynb` para verificar a reprodução dos resultados oficiais.

---

## 8. Diferenças em Relação ao Paper

A implementação segue fielmente o paper, com as seguintes observações:

- A banda $\nu_A$ é calculada com a exposição total, mesmo em setores fracionários, conforme o Apêndice A9.
- O setor idiossincrático é implementado por convolução de NBs individuais com $\alpha_A = 4$, conforme a Seção A12.
- O truncamento em `max_loss_dollars` é uma necessidade computacional; o paper não discute truncamento explicitamente.

---

## 9. Extensões Possíveis

Possíveis melhorias e extensões da implementação:

- Incorporação estocástica das taxas de recuperação.
- Modelagem de migração de ratings endógena.
- Cálculo de Expected Shortfall (CVaR) além do VaR.
- Paralelização para carteiras muito grandes.
- Integração com dados de mercado (spreads, CDS).
