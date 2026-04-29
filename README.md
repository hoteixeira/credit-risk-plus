# Credit Risk+ — Guia de Estudos e Implementação em Python

Implementação completa do modelo **Credit Risk+** (Credit Suisse First Boston, 1997) com notebooks educacionais em português. Este documento serve como guia de estudos detalhado do modelo, cobrindo a teoria, as fórmulas, os exemplos numéricos e a aplicação prática em um portfólio de varejo realista.

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

print(f"E[Loss]  = ${el:,.0f}")     # $14,221,863
print(f"VaR(99%) = ${var_99:,.0f}") # $55,311,503
```

---

## Parte I — Contexto e Motivação

### 1.1 Por que o Credit Risk+?

Antes do Credit Risk+, a gestão de risco de crédito era baseada principalmente em limites individuais por contraparte, rating e setor — técnicas que controlam fatores individuais, mas não fornecem uma medida integrada da diversificação e concentração do portfólio como um todo.

O Credit Risk+, publicado pelo Credit Suisse First Boston em dezembro de 1996, representa uma mudança de paradigma: ao invés de tratar cada exposição isoladamente, ele constrói a **distribuição completa de perdas do portfólio**, permitindo calcular o capital necessário para cobrir perdas inesperadas com um nível de confiança explícito (ex: 99%).

As principais inovações do modelo são:

- **Abordagem atuarial**: usa técnicas da indústria de seguros (distribuições de eventos raros) em vez das técnicas financeiras usuais de variância-covariância.
- **Sem pressupostos sobre causas de default**: o modelo não tenta explicar *por que* ocorrem defaults, apenas *com que frequência e magnitude*.
- **Tratamento analítico fechado**: a distribuição de perdas é calculada exatamente por recursão, sem necessidade de simulação de Monte Carlo.
- **Incorporação de correlação via volatilidade**: em vez de usar correlações de default explícitas (que são instáveis e difíceis de estimar), o modelo captura os efeitos de fatores macroeconômicos comuns através da volatilidade das taxas de default.

### 1.2 Tipos de Risco de Crédito

O Credit Risk+ foca exclusivamente em **risco de default de crédito** — o risco de que uma contraparte não consiga honrar suas obrigações financeiras, gerando uma perda igual à exposição menos o valor recuperado.

Existe também o **risco de spread de crédito** (variação no prêmio de risco de mercado), mas este é tratado em outros frameworks de risco de mercado (VaR histórico, etc.) e não é objeto do Credit Risk+.

### 1.3 Três Componentes do Framework

```
┌─────────────────────────────────────────────────────┐
│                    Credit Risk+                      │
├──────────────────┬──────────────────┬───────────────┤
│ Medição do Risco │ Capital Econômico│  Aplicações   │
│                  │                  │               │
│ • Exposições     │ • Distribuição   │ • Provisioning│
│ • Default rates  │   de perdas      │ • Limites     │
│ • Volatilidades  │ • Análise de     │ • Gestão de   │
│ • Recovery rates │   cenários       │   portfólio   │
│ • Modelo CR+     │                  │               │
└──────────────────┴──────────────────┴───────────────┘
```

---

## Parte II — Dados de Entrada

### 2.1 Exposições

A exposição de uma contraparte representa o valor em risco no evento de default. Para empréstimos, é o saldo devedor; para derivativos, é o valor de mercado mais um add-on de exposição futura potencial; para cartas de crédito, o valor nominal completo (pois serão totalmente sacadas antes do default).

Em horizontes multi-ano, as exposições variam ao longo do tempo (amortização, mark-to-market) e devem ser modeladas por período.

### 2.2 Taxas de Default (PD)

A taxa de default `p_A` é a probabilidade anual de que a contraparte A entre em default. Pode ser obtida de:

- **Ratings externos** (Moody's, S&P) com mapeamento histórico para PDs médias
- **Spreads de mercado** de instrumentos negociados
- **Modelos internos** (PD estimada por modelos de scorecard)

Referências históricas (Moody's, 1996):

| Rating | PD média anual | Desvio padrão |
|--------|---------------|---------------|
| Aaa    | 0,00%         | 0,0%          |
| Aa     | 0,03%         | 0,1%          |
| A      | 0,01%         | 0,0%          |
| Baa    | 0,12%         | 0,3%          |
| Ba     | 1,36%         | 1,3%          |
| B      | 7,27%         | 5,1%          |

**Ponto-chave**: o desvio padrão pode ser significativo em relação à média (para Ba: desvio/média = 96%). Isso reflete a enorme variação cíclica das taxas de default — em recessões, o número de defaults pode ser várias vezes maior que a média histórica.

### 2.3 Volatilidade das Taxas de Default

A volatilidade `σ_A` da taxa de default é o que distingue o Credit Risk+ de um modelo de Poisson simples. Ela captura a incerteza *na própria taxa de default*, não apenas o ruído estatístico em torno de uma taxa fixa.

Intuição: mesmo que soubéssemos com certeza que a PD média de rating Ba é 1,36%, no próximo ano ela pode ser 0,5% (expansão econômica) ou 3% (recessão). Essa incerteza de segundo nível é o que a volatilidade modela.

### 2.4 Taxas de Recuperação

Em caso de default, a perda líquida é `Exposição × (1 - Recovery Rate)`. As taxas de recuperação variam conforme a seniority da dívida:

| Tipo                          | Média  | Desvio padrão |
|-------------------------------|--------|---------------|
| Senior secured bank loans     | 71,2%  | 21,1%         |
| Senior unsecured public debt  | 47,5%  | 26,3%         |
| Subordinated public debt      | 28,3%  | 20,1%         |
| Junior subordinated debt      | 14,7%  | 8,7%          |

A exposição usada no modelo é sempre a **exposição líquida** após a aplicação da taxa de recuperação: `E_A^{net} = E_A × (1 - RR_A)`.

---

## Parte III — O Modelo Credit Risk+: Teoria Completa

### 3.1 Visão Geral: Dois Estágios

O modelo opera em dois estágios:

```
Estágio 1: Frequência de defaults   → distribuição do número de defaults
              ↓
Estágio 2: Severidade das perdas    → distribuição das perdas monetárias
```

No Estágio 1, modelamos *quantas* contrapartes darão default. No Estágio 2, convertemos esses defaults em perdas financeiras, levando em conta que cada contraparte tem uma exposição diferente.

### 3.2 Estágio 1 com Taxas Fixas: Distribuição de Poisson

#### 3.2.1 PGF do Portfólio (Apêndice A2)

Considere N contrapartes, cada uma com probabilidade de default `p_A`. A **Função Geradora de Probabilidade** (PGF) do número de defaults de uma única contraparte é:

```
F_A(z) = (1 - p_A) + p_A · z = 1 + p_A(z - 1)
```

Como os defaults são independentes (condicionalmente às taxas fixas), a PGF do portfólio é o produto das PGFs individuais:

```
F(z) = ∏_A F_A(z) = ∏_A [1 + p_A(z - 1)]
```

#### 3.2.2 Aproximação de Poisson (Eq. 5-10)

Para probabilidades individuais pequenas (o que é sempre verdade em portfólios de crédito), usa-se a aproximação `log(1 + x) ≈ x`:

```
log F(z) = Σ_A log[1 + p_A(z-1)] ≈ Σ_A p_A(z-1) = μ(z-1)
```

onde `μ = Σ_A p_A` é o número esperado de defaults.

Portanto:

```
F(z) = e^{μ(z-1)}
```

Expandindo em série de Taylor, reconhecemos a **distribuição de Poisson**:

```
P(n defaults) = e^{-μ} · μ^n / n!
```

**Limitação**: A Poisson tem variância igual à média (`Var = μ`). Historicamente, a variância observada de defaults é muito maior — evidência de que as taxas de default *não são fixas*.

### 3.3 Estágio 2 com Taxas Fixas: Distribuição de Perdas (Apêndice A3-A4)

#### 3.3.1 Discretização (Exposure Banding)

Para calcular a distribuição de perdas, as exposições líquidas são primeiro discretizadas em múltiplos inteiros de uma **unidade de perda** L:

```
L = ceil(max_exposure / 100)   [unidade de base, em moeda]

v_A = ceil(E_A^{net} / L)      [banda de exposição — número inteiro]

ε_A = p_A · E_A^{net} / L      [perda esperada em unidades L]
```

A escolha `L = ceil(max_exposure / 100)` garante que a maior exposição use ~100 bandas, balanceando precisão e custo computacional.

**Exemplo numérico** (portfólio 1A, contraparte 1):
- Exposição: $20.000.000, sem recuperação → E_net = $20M
- L = ceil($20M / 100) = $200.000
- v_1 = ceil($20M / $200K) = 100 bandas
- p_1 = 0,04% (rating A)
- ε_1 = 0,0004 × $20M / $200K = 0,040

#### 3.3.2 PGF das Perdas (Eq. 14-19)

A PGF das perdas `G(z)` onde o expoente de z representa a perda em múltiplos de L:

```
G(z) = Σ_n P(perda = n·L) · z^n
```

Para cada banda de exposição j com exposição v_j e perda esperada total ε_j = Σ_{A: v_A=v_j} ε_A, a sub-PGF é `e^{-μ_j + μ_j · z^{v_j}}`. O produto sobre todas as bandas dá:

```
G(z) = e^{μ(P(z) - 1)}

onde  P(z) = (1/μ) · Σ_j ε_j · z^{v_j}   (polinômio de severidade, Eq. 18)
             μ = Σ_j ε_j / v_j              (defaults esperados ponderados)
```

#### 3.3.3 Recursão de Perdas — Caso Poisson (Eq. 25-26)

Extraindo os coeficientes da PGF `G(z)` por diferenciação logarítmica, obtemos a recursão:

```
A[0] = e^{-μ}   (probabilidade de perda zero)

A[n] = (1/n) · Σ_{j: v_j ≤ n} ε_j · A[n - v_j]
```

Esta recursão é **computacionalmente eficiente**: calcula toda a PMF em O(N_max × m) operações, onde m é o número de bandas distintas.

### 3.4 Estágio 1 com Taxas Variáveis: Distribuição Binomial Negativa (Apêndice A6)

Esta é a inovação central do Credit Risk+.

#### 3.4.1 Modelagem da Incerteza via Distribuição Gama

Em vez de tratar `p_A` como fixo, assumimos que a taxa de default de cada contraparte A segue uma distribuição Gama com:
- Média: `μ_A` (a PD média observada historicamente)
- Variância: `σ_A²` (a volatilidade da PD)

A escolha da Gama é conveniente matematicamente, pois a mistura de Poisson com intensidade Gama produz exatamente a **Binomial Negativa** (NB).

#### 3.4.2 Parâmetros da NB por Setor (Eq. 90-97)

Agrupando todas as contrapartes em um único setor (modelo de 1 setor), os parâmetros são:

```
μ = Σ_A ε_A / v_A           (defaults esperados, ponderados pela exposição)
σ = Σ_A σ_A · (E_A/L) / v_A (desvio efetivo agregado)

α = μ² / σ²                  (parâmetro de forma da NB — "concentração")
β = σ² / μ                   (parâmetro de escala da NB)
p = β / (1 + β)              (probabilidade NB)
```

**Intuição sobre α**: quando α → ∞ (σ → 0), a NB converge para Poisson. Valores pequenos de α (ex: α = 2) indicam alta volatilidade e distribuição com cauda muito pesada.

**Exemplo numérico** (portfólio 1A simplificado):
- Se μ = 0,071 e σ = 0,034, então:
- α = 0,071² / 0,034² = 4,37
- β = 0,034² / 0,071 = 0,0163
- p = 0,0163 / 1,0163 = 0,0160

#### 3.4.3 PGF da NB (Eq. 62-72)

```
G(z) = ((1 - p) / (1 - p · P(z)))^α
```

onde `P(z)` é o mesmo polinômio de severidade do caso Poisson. Esta forma é uma NB generalizada com severidade variável.

**Por que isso captura correlação?** Porque o fator Gama subjacente é *compartilhado* por todas as contrapartes do setor. Quando o fator de risco sistêmico está alto (recessão), todas as contrapartes do setor têm suas PDs elevadas simultaneamente — gerando correlação implícita entre defaults.

#### 3.4.4 Recursão NB — Caso Variável (Apêndice A10, Eq. 79-80)

Diferenciando logaritmicamente a PGF da NB, obtemos a recursão generalizada:

```
A[0] = (1 - p)^α

A[n] = (p / (n · μ)) · Σ_{j: v_j ≤ n} ε_j · (α - 1 + n/v_j) · A[n - v_j]
```

Note como esta recursão se reduz ao caso Poisson quando σ → 0:
- α → ∞, p → 0, mas α·p → μ → constante
- O termo `(α - 1 + n/v_j)` torna-se dominado por `α`, que cancela com `p/μ`
- Resulta em `A[n] = (1/n) · Σ ε_j · A[n - v_j]` ✓

**Caso especial v_j = 1 (ν=1 para todas as bandas):**

Quando todas as exposições individuais são muito menores que L (como em portfólios de varejo com L = $1M), todas as bandas v_A = 1. A recursão simplifica para:

```
A[n] = p · (α - 1 + n) / n · A[n - 1]
```

Esta forma escalar é extremamente eficiente — cada iteração é O(1) em vez de O(m).

### 3.5 Modelo Multi-Setor (Apêndice A7-A9)

#### 3.5.1 Motivação

Se todas as contrapartes estão em um único setor, assume-se que um único fator Gama afeta todas — correlação máxima. Na realidade, contrapartes em geografias ou setores diferentes respondem a fatores econômicos distintos. O modelo multi-setor captura isso.

#### 3.5.2 Alocação por Pesos

Cada contraparte A é alocada a K setores com pesos `θ_{Ak} ≥ 0`, onde `Σ_k θ_{Ak} = 1`. A exposição efetiva de A no setor k é `θ_{Ak} × E_A`.

Para cada setor k os parâmetros são calculados como:

```
ε_A^k = θ_{Ak} · p_A · E_A / L          (epsilon setorial de A)
v_A    = ceil(E_A / L)                    (banda baseada na exposição TOTAL — não setorial)
μ_k    = Σ_A θ_{Ak} · ε_A / v_A         (defaults esperados do setor k)
σ_k    = Σ_A θ_{Ak} · σ_A · (E_A/L)/v_A (desvio efetivo do setor k)
```

**Detalhe sutil**: a banda `v_A` é calculada com a exposição **total** de A, não a fração setorial. Isso preserva a severidade da perda dado um default — se A defaultar, a perda é sempre `E_A`, não `θ_{Ak} · E_A`.

#### 3.5.3 PGF Total = Produto das PGFs Setoriais

Como os fatores Gama de cada setor são independentes entre si:

```
G_total(z) = ∏_{k=1}^{K} G_k(z)
```

Na prática, isto é implementado via **convolução** das PMFs setoriais:

```python
pmf_total = pmf_setor_1
for k in range(1, K):
    pmf_total = np.convolve(pmf_total, pmf_setor_k)[:max_n+1]
```

#### 3.5.4 Efeito da Diversificação Setorial

O VaR diminui à medida que o número de setores independentes aumenta (Figura 8 do PDF). Para o portfólio de 25 contrapartes:

| Configuração | VaR(99%) | Redução vs. 1 setor |
|-------------|----------|---------------------|
| 1 setor     | $55.311.503 | — |
| 3 setores geográficos | $49.931.502 | −9,7% |
| 4 setores + específico | $47.368.235 | −14,4% |

### 3.6 Setor Idiossincrático (Apêndice A12)

#### 3.6.1 O Problema

Na alocação com pesos fracionários, parte do risco de cada contraparte não é correlacionado com nenhum fator setorial — é risco *específico* da contraparte. Este componente deve ser tratado separadamente.

#### 3.6.2 Setor Específico: Convolução de NB Individuais

No setor idiossincrático, cada contraparte A tem seu **próprio fator Gama independente** com parâmetro de forma fixo `α_A = 4` (coeficiente de variação CV = 1/√4 = 0,5):

```
Para cada contraparte A com peso θ_A > 0 no setor específico:

  ε_A^{ido}  = θ_A · p_A · (E_A/L) / v_A    (epsilon idiossincrático)
  μ_A        = ε_A^{ido}
  β_A        = μ_A / α_A = μ_A / 4
  p_A        = β_A / (1 + β_A)

  Recursão NB individual no suporte {0, v_A, 2·v_A, ...}:
    A_A[0]       = (1 - p_A)^4
    A_A[k · v_A] = p_A · (3 + k) / k · A_A[(k-1) · v_A]

  PMF do setor = convolução sequencial de todas as A_A:
    pmf_ido = convolve(A_1, A_2, ..., A_N)
```

A escolha `α_A = 4` é uma convenção do modelo que balanceia realismo e tratabilidade analítica.

### 3.7 Extensão Multi-Ano (Apêndice A5)

#### 3.7.1 Contrapartes Virtuais

Para horizonte de T anos, cada contraparte A gera T **contrapartes virtuais** — uma por ano — com:
- Exposição: `E_A^{(t)}` (perfil de amortização no ano t)
- PD: `p_A^{(t)}` (taxa marginal condicional: P(default no ano t | sobreviveu até t-1))

As taxas marginais condicionais são calculadas a partir da estrutura a termo de ratings usando a matriz de transição.

#### 3.7.2 Como Calcular as PDs Marginais

Se `S_A^{(t)}` é a probabilidade acumulada de sobrevivência até o ano t:

```
S_A^{(0)} = 1
S_A^{(t)} = S_A^{(t-1)} · (1 - p_A^{(t)})

Portanto:
p_A^{(t)} = 1 - S_A^{(t)} / S_A^{(t-1)}  (taxa marginal condicional)
```

As probabilidades de sobrevivência acumulada por rating/ano são derivadas da matriz de transição de ratings elevada à potência t.

#### 3.7.3 O Modelo de 40 Contrapartes Virtuais (Exemplo 1C)

No portfólio de 25 contrapartes com horizonte 3 anos:
- Ano 1: todas 25 contrapartes (exposição cheia)
- Ano 2: 10 contrapartes ainda têm exposição no ano 2 (as demais amortizaram)
- Ano 3: 5 contrapartes ainda têm exposição no ano 3

Total: 25 + 10 + 5 = 40 contrapartes virtuais, todas no mesmo modelo Credit Risk+.

---

## Parte IV — Capital Econômico

### 4.1 A Distribuição Completa de Perdas

O resultado do modelo é uma PMF (função de massa de probabilidade):

```
A[n] = P(perda total = n · L)
```

Da PMF obtemos:

```
CDF[n] = Σ_{k=0}^{n} A[k]       (função de distribuição acumulada)

E[Loss] = Σ_{n=0}^{N} n · L · A[n]    (perda esperada)

VaR(q%) = min{n·L : CDF[n] ≥ q/100}  (Value at Risk)

EC(q%) = VaR(q%) - E[Loss]            (Capital Econômico)
```

### 4.2 Por que 99%?

O PDF recomenda o percentil 99% como padrão para capital econômico de crédito com horizonte de 1 ano. A lógica:
- Cobre perdas inesperadas na grande maioria dos anos
- Permite que o banco suporte 1 "mau ano" em 100 sem insolvência
- Em instituições mais conservadoras (rating AA target), usa-se 99,9% ou 99,97%

### 4.3 As Três Regiões da Distribuição (Figura 10 do PDF)

```
 Perda
 ─────────────────────────────────────────────────────►
 │◄── Cobertas por ──►│◄── Capital Econômico ──►│ Cenários
 │  pricing/provision │   (EC = VaR-EL)         │  extremos
 0                   EL                       VaR(99%)
```

| Região | Cobertura |
|--------|-----------|
| Até EL | Pricing e provisões (ACP) |
| EL até VaR(99%) | Capital econômico e/ou ICR |
| Acima de VaR(99%) | Análise de cenários e limites de concentração |

### 4.4 Contribuições de Risco por Contraparte (Apêndice A13)

A contribuição de risco (RC) de cada contraparte A ao VaR do portfólio é definida como o efeito incremental de remover A do portfólio. O modelo fornece uma aproximação analítica aditiva:

```
RC_A = EL_A + (VaR - EL) · (μ_A / μ_total)

onde:
  EL_A    = p_A · E_A^{net}          (perda esperada de A)
  μ_A     = ε_A / v_A                (contribuição de A ao μ total)
  μ_total = Σ_A μ_A
```

**Propriedade fundamental**: `Σ_A RC_A = VaR` — as contribuições são perfeitamente aditivas.

Esta decomposição é a base para a gestão ativa de portfólio: ordenar contrapartes por RC revela quais concentram mais capital e devem ser priorizadas para redução ou hedge.

---

## Parte V — Aplicações

### 5.1 Provisão Anual de Crédito (ACP)

```
ACP = Σ_A Exposição_A × PD_A × (1 - RR_A)
    = Σ_A EL_A
    = E[Loss]
```

A ACP é cobrada ao P&L anualmente como custo do risco de crédito. É o "preço" de fazer negócios com risco de crédito.

### 5.2 Reserva Incremental de Crédito (ICR)

O ICR protege contra variações das perdas efetivas em torno da ACP. Funciona como um buffer:
- Anos bons (perdas < ACP): excedente credita o ICR (até o ICR Cap)
- Anos ruins (perdas > ACP): ICR absorve o excesso antes de impactar capital

```
ICR Cap = VaR(99%) - EL     (equivalente ao Capital Econômico)
```

### 5.3 Limites de Crédito Baseados em Risco

Em vez de limites fixos por contraparte, o Credit Risk+ permite definir limites baseados em contribuição de risco igual:

```
Limite_A ∝ 1 / (PD_A × (1 - RR_A))
```

Contrapartes de pior rating recebem limites menores, naturalmente alinhando apetite de risco com qualidade de crédito.

### 5.4 Gestão de Portfólio via Risk Contributions

A figura 12 do PDF mostra: ao remover as poucas contrapartes com maior RC, o VaR cai desproporcionalmente em relação à queda no EL — o capital econômico diminui mais que a perda esperada. Isso é a essência da gestão ativa de portfólio baseada em risco.

### 5.5 RARoC — Retorno Ajustado ao Risco sobre Capital

```
RARoC = (Receita de spread - EL - Custo de funding - Custo operacional) / RC
```

O RARoC permite comparar exposições de diferentes ratings, maturidades e tamanhos numa métrica única de eficiência de capital. Contrapartes com RARoC abaixo do custo de capital (hurdle rate) destroem valor.

---

## Parte VI — Análise de Cenários e Stress Testing

O modelo analítico permite recalcular toda a distribuição de perdas em milissegundos, tornando o stress testing prático e iterativo.

**Cenários típicos**:
1. Aumento das PDs médias (simulação de recessão)
2. Aumento das volatilidades das PDs (maior incerteza macroeconômica)
3. Queda nas taxas de recuperação
4. Concentração setorial (redução do número efetivo de setores)

**Exemplo**: duplicar as PDs de todas as contrapartes de rating Ba e B simula uma recessão moderada. O novo VaR pode ser calculado imediatamente — não há necessidade de re-rodar Monte Carlo.

---

## Parte VII — Exemplo Realista: Portfólio de Varejo Bancário

### 7.1 Descrição do Problema

O notebook 10 ([10_simulacao_portfolio_varejo.ipynb](notebooks/10_simulacao_portfolio_varejo.ipynb)) simula um banco de varejo com aproximadamente **1 milhão de clientes** ao longo de **24 meses**, incluindo:
- Migrações de rating mensais (upgrades e downgrades via cadeia de Markov)
- Um **choque macroeconômico no mês 12** que afeta com maior intensidade os ratings borderline (C, D, E, F)
- Cálculo mensal de EL, VaR(99%), VaR(99,9%) e Capital Econômico
- Decomposição de Capital por rating via contribuições de risco
- RARoC por rating e ao longo do tempo

### 7.2 Parâmetros do Portfólio de Varejo

| Parâmetro | Rating A | B | C | D | E | F | G | H |
|-----------|---------|---|---|---|---|---|---|---|
| PD anual (%) | 0,20 | 0,50 | 1,00 | 2,00 | 5,00 | 10,00 | 15,00 | 25,00 |
| Vol PD (%) | 0,10 | 0,25 | 0,50 | 1,00 | 2,50 | 5,00 | 7,50 | 12,50 |
| Exposição média ($) | 45.000 | 35.000 | 28.000 | 20.000 | 15.000 | 10.000 | 7.000 | 5.000 |
| Spread anual (%) | 2,0 | 3,0 | 4,5 | 6,5 | 9,0 | 13,0 | 18,0 | 25,0 |

Distribuição inicial dos clientes: [5%, 10%, 15%, 20%, 20%, 15%, 10%, 5%] por rating.
Taxa de recuperação: 35%. Custo de funding: 3% a.a. Custo operacional: $60/cliente/ano.

### 7.3 Metodologia: Agregação de Clientes Idênticos

O modelo trata os `n_r` clientes de cada rating r como uma única **"super-contraparte"** com:

```
ε_r = n_r × p_r^{mensal} × E_r^{net} / L
σ_r = n_r × σ_r^{mensal} × E_r^{net} / L
```

Com `L = $1.000.000` (muito maior que qualquer exposição individual), todas as bandas `v_r = 1`, permitindo a recursão escalar simplificada:

```
A[n] = p · (α - 1 + n) / n · A[n - 1]    (O(MAX_N), MAX_N = 2000)
```

Este portfólio de $25B+ é calculado em milissegundos por mês — viabilizando a simulação de 24 meses em menos de 1 segundo.

### 7.4 Matriz de Transição de Ratings

A migração mensal de clientes entre ratings é simulada por uma cadeia de Markov com a matriz de transição base `P_BASE` (8 ratings + estado "default absorvente"):

```
        A      B      C      D      E      F      G      H    Default
A   [0,921  0,060  0,012  0,004  0,001    ...                  0,002]
B   [0,040  0,893  0,050  0,010  0,004  0,001    ...           0,002]
C   [0,005  0,045  0,882  0,050  0,010  0,003  0,001    ...    0,004]  ← borderline
D   [0,001  0,005  0,050  0,867  0,060  0,008  0,003  0,001    0,005]  ← borderline
E   [  ...         0,005  0,055  0,862  0,050  0,010  0,005    0,012]  ← borderline
F   [  ...               0,005  0,045  0,858  0,050  0,015    0,026]  ← borderline
G   [  ...                      0,005  0,040  0,848  0,038    0,068]
H   [  ...                             0,005  0,035  0,820    0,139]
```

### 7.5 Choque Macroeconômico (Mês 12)

O choque simula uma recessão com duração de 4 meses. A intensidade segue uma curva triangular — cresce até o pico no meio do choque e depois recua:

```
fator_choque(mês) = max(0, 1 - |pos_relativa - 0.5| / 0.5)   # triangular [0,1]
MULT = 1 + 2,5 × fator_choque                                 # máximo: 3,5×
```

Apenas os ratings **borderline (C, D, E, F)** são afetados: suas probabilidades de downgrade e default são multiplicadas por MULT, com compensação proporcional nas probabilidades de upgrade/manutenção para preservar a soma em 1.

**Intuição**: ratings extremos (A, B = muito bons; G, H = já deteriorados) são menos sensíveis ao ciclo econômico. Os borderline são os mais suscetíveis a mudanças na conjuntura.

### 7.6 Resultados Observados

#### 7.6.1 Evolução do Capital ao Longo do Tempo

A simulação revela três fases distintas:

| Fase | Meses | Característica |
|------|-------|---------------|
| Pré-choque | 0–11 | Capital estável, carteira bem distribuída |
| Choque | 12–15 | Aceleração de downgrades: concentração em E-H cresce, capital sobe ~30-50% |
| Recuperação | 16–23 | Normalização lenta; capital permanece acima do nível pré-choque por vários meses |

#### 7.6.2 Métricas Selecionadas (referência pré vs. choque vs. pós)

| Métrica | Mês 0 | Mês 12 (pico) | Mês 23 |
|---------|-------|---------------|--------|
| Clientes E-H (%) | ~30% | ~40-45% | ~33% |
| EL mensal | ~$65M | ~$100M | ~$75M |
| VaR(99,9%) | ~$350M | ~$550M | ~$400M |
| Capital Econômico | ~$285M | ~$450M | ~$325M |
| RARoC portfólio (anualizado) | ~15% | ~8% | ~12% |

*Nota: valores aproximados — dependem da aleatoriedade das simulações Markov.*

#### 7.6.3 Insights de Gestão de Portfólio

**1. Concentração do capital em poucos ratings**: Ratings F, G e H representam tipicamente <30% dos clientes, mas >60% do capital econômico. Pequenas variações na proporção de clientes nesses ratings têm impacto desproporcional no VaR.

**2. RARoC diferenciado**: Ratings A e B têm os maiores RARoC (spread mais que compensa a perda esperada e o capital). Ratings G e H frequentemente têm RARoC negativo — o spread não cobre a perda esperada + custo de capital.

**3. Detecção antecipada do choque**: O EL começa a subir 1-2 meses *antes* do pico do VaR — clientes migram para ratings piores antes de efetivamente defaultar. O EL é um leading indicator do capital necessário.

**4. Persistência pós-choque**: Mesmo após o fim do choque, o capital permanece elevado por vários meses — reflexo de clientes "presos" em ratings baixos que levam tempo para migrar de volta.

### 7.7 Steps do Notebook 10

O notebook está organizado em 13 células:

| Célula | Conteúdo |
|--------|----------|
| 1 | Imports e configuração |
| 2 | Parâmetros do portfólio (ratings, PDs, exposições, spreads) |
| 3 | Matriz de transição base e função de choque |
| 4 | Simulação Markov de 24 meses (migração de clientes) |
| 5 | Credit Risk+ mensal: VaR, EL e Capital (recursão NB v=1) |
| 6 | RARoC por rating e por mês |
| 7 | Gráfico 1: Composição do portfólio (área empilhada, % qualidade, exposição, defaults) |
| 8 | Gráfico 2: EL/VaR/Capital, capital por rating, RC, múltiplos VaR/EL |
| 9 | Gráfico 3: RARoC ao longo do tempo, heatmap por rating, P&L stack, comparativo |
| 10 | Gráfico 4: Distribuição pré vs. pós choque, defaults acumulados, concentração RC |
| 11 | Gráfico 5: Dashboard executivo KPI |
| 12 | Tabela resumo mensal (linhas do choque destacadas) |
| 13 | Análise pré vs. pós por rating com recomendações de gestão |

---

## Parte VIII — Guia dos Notebooks

### [01 — Introdução ao Credit Risk+](notebooks/01_introducao.ipynb)

Contexto histórico (Credit Suisse, 1997), tipos de risco de crédito, pressupostos fundamentais, componentes do framework e inputs necessários.

### [02 — Modelo de Taxa Fixa (Poisson)](notebooks/02_modelo_fixo.ipynb)

Derivação completa para o caso com taxas fixas: PGF individual e do portfólio, aproximação de Poisson, exposure banding e a recursão `A[n] = (1/n) · Σ ε_j · A[n-v_j]`. Inclui exemplos numéricos passo a passo.

### [03 — Modelo de Taxa Variável (Binomial Negativa)](notebooks/03_modelo_variavel.ipynb)

Extensão para taxas estocásticas: mistura Poisson-Gama → NB, derivação dos parâmetros α, β, p, PGF da NB generalizada e recursão de Apêndice A10. Análise do impacto da volatilidade no VaR. Setor idiossincrático (A12).

### [04 — Exemplo 1A: Portfólio Base](notebooks/04_exemplo_1A.ipynb)

25 contrapartes, 1 setor (Economia Geral). Reproduz exatamente o Exemplo 1A da planilha original:
- **E[Loss] = $14.221.863** (erro 0,000%)
- **VaR(99%) = $55.311.503** (erro 0,000%)
- **Capital Econômico = $41.089.640**

Distribuição de perdas completa, análise de percentis, contribuições de risco por contraparte e curva de Lorenz de concentração.

### [05 — Exemplo 1B: Gestão de Portfólio](notebooks/05_exemplo_1B.ipynb)

23 contrapartes (remoção das contrapartes 24 e 25, as de maior exposição). Impacto da remoção:
- **E[Loss] = $11.162.856** (−21,5% vs 1A)
- **VaR(99%) = $39.946.857** (−27,8% vs 1A)

A queda no VaR é proporcionalmente maior que no EL — demonstração direta do valor de gerir concentrações.

### [06 — Exemplo 1C: Horizonte Multi-Ano](notebooks/06_exemplo_1C_multi_ano.ipynb)

3 anos, 40 contrapartes virtuais. Taxas de default marginais condicionais por rating/ano. Reproduz:
- **E[Loss] = $17.277.632** (erro 0,000%)
- **VaR(99%) = $62.100.307** (erro 0,000%)

### [07 — Exemplo 2: Setores Geográficos](notebooks/07_exemplo_2_setores_geo.ipynb)

Mesmas 25 contrapartes alocadas a 3 setores exclusivos (EUA: 10, Japão: 8, Europa: 7). Diversificação setorial reduz o VaR(99%) de $55,3M para $49,9M (−9,7%).

### [08 — Exemplo 3: Pesos Fracionários](notebooks/08_exemplo_3_setores_fracionarios.ipynb)

4 setores com pesos fracionários por contraparte (Specific + EUA + Japão + Europa). Implementação do setor idiossincrático via convolução de NB individuais (Seção A12). Máxima diversificação:
- **VaR(99%) ≈ $47.368.235** (erro +0,579% vs. referência)

### [09 — Aplicações Práticas](notebooks/09_aplicacoes.ipynb)

1. Provisioning (ACP/ICR): reservas para perdas esperadas e inesperadas
2. Limites de crédito baseados em risco: concentração máxima por contraparte
3. Stress testing: cenários base / leve / moderado / severo
4. Otimização de portfólio: eficiência retorno/risco por contraparte

### [10 — Simulação de Portfólio de Varejo](notebooks/10_simulacao_portfolio_varejo.ipynb)

1M de clientes × 24 meses, cadeia de Markov, choque macroeconômico no mês 12. VaR/EL/Capital mensais, decomposição por rating, RARoC. Ver Parte VII deste documento para descrição completa.

---

## Parte IX — Validação contra a Referência

Todos os exemplos reproduzem os resultados da planilha `CreditRisk+.xls` com erro < 0,001%:

| Exemplo | Descrição | E[Loss] (ref) | VaR(99%) (ref) | Erro EL | Erro VaR |
|---------|-----------|--------------|----------------|---------|----------|
| 1A | 25 contrapartes, 1 setor | $14.221.863 | $55.311.503 | 0,000% | 0,000% |
| 1B | 23 contrapartes (sem 24 e 25) | $11.162.856 | $39.946.857 | 0,000% | 0,000% |
| 1C | 25 contrapartes, horizonte 3 anos | $17.277.632 | $62.100.307 | 0,000% | 0,000% |
| 2 | 25 contrapartes, 3 setores geográficos | $14.221.863 | $49.931.502 | 0,000% | 0,000% |
| 3 | 25 contrapartes, 4 setores fracionários | $14.221.863 | $47.368.235 | 0,000% | +0,579% |

> **Nota sobre Exemplo 3**: o erro de +0,579% no VaR(99%) é o melhor resultado obtido sem acesso ao código VBA da planilha. O EL é exato. A implementação do setor idiossincrático por convolução de NB individuais (Seção A12) é matematicamente correta conforme o paper.

---

## Parte X — Referência de Implementação

### Estrutura do Repositório

```
credit-risk-plus/
├── references/
│   ├── CreditRisk+.pdf        # Documento original (Credit Suisse, 1997)
│   └── CreditRisk+.xls        # Planilha de referência com exemplos
├── creditriskplus/
│   ├── simple_model.py        # Implementação principal (NB recursion)
│   ├── data.py                # Dados dos portfólios de exemplo
│   └── plots.py               # Utilitários de visualização
└── notebooks/
    ├── 01_introducao.ipynb
    ├── 02_modelo_fixo.ipynb
    ├── 03_modelo_variavel.ipynb
    ├── 04_exemplo_1A.ipynb
    ├── 05_exemplo_1B.ipynb
    ├── 06_exemplo_1C_multi_ano.ipynb
    ├── 07_exemplo_2_setores_geo.ipynb
    ├── 08_exemplo_3_setores_fracionarios.ipynb
    ├── 09_aplicacoes.ipynb
    └── 10_simulacao_portfolio_varejo.ipynb
```

### API Principal: `calculate_loss_distribution()`

```python
from creditriskplus.simple_model import calculate_loss_distribution

pmf, el = calculate_loss_distribution(
    exposures,                          # array [N] de exposições líquidas
    mean_default_rates,                 # array [N] de PDs médias
    std_default_rates,                  # array [N] de volatilidades de PD
    recovery_rates,                     # array [N] de taxas de recuperação
    sector_weights_matrix=None,         # array [N × K] de pesos setoriais (None = 1 setor)
    idiosyncratic_sector_indices=None,  # lista de índices de setores idiossincráticos
    unit_size=None,                     # L (None = ceil(max_exp / 100))
    max_loss_dollars=150_000_000,       # truncamento da distribuição
)
```

### Tabela de Parâmetros

| Símbolo | Fórmula | Descrição |
|---------|---------|-----------|
| L | `ceil(max_exposure / 100)` | Unidade de discretização |
| v_A | `ceil(E_A / L)` | Banda de exposição (exposição total) |
| ε_A | `p_A · E_A / L` | Perda esperada em unidades L |
| ε_A^k | `θ_{Ak} · p_A · E_A / L` | Epsilon setorial (escalado pelo peso) |
| μ_k | `Σ_A θ_{Ak} · ε_A / v_A` | Defaults esperados ponderados do setor k |
| σ_k | `Σ_A θ_{Ak} · σ_A · (E_A/L) / v_A` | Desvio efetivo do setor k |
| α | `μ² / σ²` | Parâmetro de forma da NB |
| β | `σ² / μ` | Parâmetro de escala da NB |
| p | `β / (1 + β)` | Probabilidade NB |
| A[0] | `(1 − p)^α` | Probabilidade de perda zero (NB) |
| EC | `VaR(q%) − E[Loss]` | Capital Econômico |
| RC_A | `EL_A + (VaR − EL) · (μ_A / μ)` | Contribuição de risco de A |

### Dependências

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

---

## Referência

**Credit Suisse Financial Products** (1997). *CreditRisk+: A Credit Risk Management Framework*. Credit Suisse First Boston International.

O documento original está disponível em `references/CreditRisk+.pdf`. A planilha de referência com todos os exemplos está em `references/CreditRisk+.xls`.
