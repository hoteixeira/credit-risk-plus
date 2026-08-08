# CreditRisk+ em Python — modelo, validação e estudos

Implementação auditável do **CreditRisk+**, publicado pelo Credit Suisse First Boston em 1997, acompanhada de notebooks educacionais em português e regressões contra os artefatos oficiais do modelo.

O projeto calcula analiticamente a distribuição de perdas por default de uma carteira. Ele cobre o limite Poisson de taxa fixa, a mistura Poisson–Gama de taxas variáveis, múltiplos fatores setoriais, alocações fracionárias, setor específico, momentos analíticos, capital econômico e contribuições de risco. Inclui ainda um estudo longitudinal de carteira PF brasileira sintética com cartão de crédito e crédito pessoal parcelado.

Este repositório é adequado para estudo, reprodução metodológica e prototipação controlada. O notebook PF não é uma calibração de mercado nem um modelo aprovado para decisão, provisionamento ou capital regulatório.

## Estado da implementação

- Um único núcleo matemático em `creditriskplus/simple_model.py`.
- API funcional e classe orientada a objetos produzindo os mesmos resultados.
- Cinco exemplos oficiais reproduzidos contra `references/CreditRisk+.xls`.
- Quantil discreto separado da interpolação usada pela planilha legada.
- Massa de cauda truncada exposta e nunca renormalizada silenciosamente.
- Nove notebooks executáveis e comentados.
- Carteira PF inicializada com backbook maduro e gate de convergência.
- 18 testes matemáticos e regressivos automatizados.

O parecer completo da revisão está em [AUDITORIA_TECNICA.md](AUDITORIA_TECNICA.md). A matriz de validação dos notebooks está em [notebooks/README.md](notebooks/README.md).

## Referências oficiais incluídas

O diretório `references/` contém:

- `CreditRisk+.pdf`: manual *CreditRisk+ — A Credit Risk Management Framework*;
- `CreditRisk+.xls`: planilha oficial com os Exemplos 1A–1C, 2 e 3.

A implementação foi confrontada principalmente com as Seções A3–A5, A7–A13 e com os cinco exemplos da planilha.

## O que o CreditRisk+ modela

O CreditRisk+ descreve perdas decorrentes de default em um horizonte definido, normalmente um ano. Seus inputs fundamentais são:

- exposição no default, ou EAD;
- probabilidade média de default, ou PD;
- volatilidade da PD ou da intensidade de default;
- recuperação determinística, convertida em LGD;
- participação de cada contraparte nos fatores setoriais.

O resultado é uma distribuição discreta de perdas. A partir dela são calculados perda esperada, desvio padrão, quantis e capital econômico.

O modelo não explica a causa econômica do default e não modela diretamente migração de rating, spreads de mercado, cura, pré-pagamento ou LGD estocástica. Esses fenômenos precisam produzir ou complementar os inputs do CreditRisk+.

## Hipóteses estruturais

1. Defaults condicionais são aproximados por processos de Poisson.
2. As intensidades setoriais variáveis seguem distribuições Gama.
3. Fatores setoriais distintos são independentes na formulação original.
4. Contrapartes que compartilham um fator tornam-se dependentes incondicionalmente.
5. EAD e recuperação são pontuais dentro do horizonte.
6. Severidades são discretizadas em múltiplos inteiros de uma unidade monetária.

Essas hipóteses pertencem ao próprio CreditRisk+. A implementação procura não acrescentar aproximações ocultas além delas.

## Construção matemática

### 1. Exposição líquida de recuperação

Para a contraparte \(A\), a severidade líquida é:

$$
L_A = EAD_A(1-RR_A),
$$

onde \(RR_A\) é a taxa de recuperação. A LGD é, portanto, \(1-RR_A\).

### 2. Banding e preservação da perda esperada

Escolhida a unidade monetária \(L\), cada severidade é associada à banda inteira:

$$
\nu_A = \left\lceil\frac{L_A}{L}\right\rceil.
$$

A perda esperada da contraparte em unidades de \(L\) é:

$$
\varepsilon_A = p_A\frac{L_A}{L}.
$$

Como \(\nu_A\) foi arredondado, a frequência usada na distribuição é ajustada para:

$$
\mu_A = \frac{\varepsilon_A}{\nu_A}.
$$

Assim,

$$
\mu_A\nu_A L = p_A L_A,
$$

e a perda esperada original é preservada exatamente apesar do arredondamento. Quando `unit_size=None`, o código segue a convenção da planilha:

$$
L=\left\lceil\frac{\max_A L_A}{100}\right\rceil.
$$

Reduzir \(L\) diminui o efeito do banding sobre a variância, mas aumenta o número de estados calculados.

### 3. Modelo de taxa fixa — limite Poisson

No limite sem volatilidade sistemática, a PGF de perdas da contraparte é:

$$
G_A(z)=\exp\left[\mu_A(z^{\nu_A}-1)\right].
$$

Para a carteira:

$$
G(z)=\exp\left[\sum_A\mu_A(z^{\nu_A}-1)\right].
$$

A probabilidade de perda zero é:

$$
A_0=\exp\left(-\sum_A\mu_A\right),
$$

e não `exp(-sum(epsilon))`. Para \(n>0\), a recursão composta usa as contribuições \(\varepsilon_A\) das bandas elegíveis:

$$
A_n=\frac{1}{n}\sum_{A:\nu_A\le n}\varepsilon_A A_{n-\nu_A}.
$$

### 4. Modelo de taxas variáveis — mistura Poisson–Gama

A variável Gama representa a intensidade agregada do setor, não uma PD Gama independente para cada contrato. Para o setor \(k\), com pesos \(\theta_{Ak}\):

$$
\varepsilon_{Ak}=\theta_{Ak}p_A\frac{L_A}{L},
$$

$$
\mu_k=\sum_A\frac{\varepsilon_{Ak}}{\nu_A},
$$

$$
\sigma_k=\sum_A\theta_{Ak}\sigma_A
\frac{L_A/L}{\nu_A}.
$$

Os parâmetros da Gama, na parametrização forma–escala, são:

$$
\alpha_k=\frac{\mu_k^2}{\sigma_k^2},
\qquad
\beta_k=\frac{\sigma_k^2}{\mu_k},
\qquad
q_k=\frac{\beta_k}{1+\beta_k}.
$$

Definindo a PGF normalizada das severidades do setor como

$$
P_k(z)=\frac{1}{\mu_k}
\sum_A\frac{\varepsilon_{Ak}}{\nu_A}z^{\nu_A},
$$

a PGF setorial é:

$$
G_k(z)=
\left(\frac{1-q_k}{1-q_kP_k(z)}\right)^{\alpha_k}.
$$

Quando \(\sigma_k=0\), essa expressão converge para o limite Poisson. A implementação usa uma forma algébrica estável da recursão A79/A80 e evita produtos indeterminados quando a volatilidade é muito pequena.

### 5. Setores, correlação e setor específico

Cada linha da matriz `sector_weights_matrix` deve conter pesos não negativos que somem um:

$$
\sum_k\theta_{Ak}=1.
$$

As distribuições dos setores independentes são combinadas multiplicando suas PGFs, o que no código corresponde a uma convolução por FFT.

O setor específico da Seção A12.3 mantém sua contribuição média, mas possui volatilidade de fator igual a zero. Por isso ele deve ser informado em `idiosyncratic_sector_indices`; tratá-lo como uma Binomial Negativa individual introduziria correlação e variância inexistentes no manual.

### 6. Momentos analíticos

A perda esperada em moeda é calculada diretamente dos inputs:

$$
EL=\sum_A m_Ap_AL_A,
$$

onde \(m_A\) é a multiplicidade do pool. Em unidades de perda, a variância implementa A115–A118:

$$
\operatorname{Var}(X)=
\sum_A m_A\varepsilon_A\nu_A
+\sum_k
\left(\sum_A m_A\varepsilon_{Ak}\right)^2
\left(\frac{\sigma_k}{\mu_k}\right)^2.
$$

O resultado monetário é obtido multiplicando a expressão por \(L^2\).

### 7. VaR e capital econômico

A PMF calculada é:

$$
A_n=P(X=nL).
$$

O quantil matemático da distribuição discreta é:

$$
VaR_q=\min\left\{nL:\sum_{i=0}^{n}A_i\ge q\right\}.
$$

O capital econômico adotado no projeto é:

$$
EC_q=VaR_q-EL.
$$

`quantile(..., interpolate=False)` retorna o VaR discreto. A opção `interpolate=True` existe exclusivamente para reproduzir a convenção linear do XLS oficial; ela não transforma a variável em contínua.

### 8. Contribuições de risco

A classe `CreditRiskPlus` implementa:

- contribuição analítica ao desvio padrão conforme A121, aditiva até precisão numérica;
- aproximação de contribuição ao percentil conforme A102.

A diferença de VaR depois da remoção finita de contratos não é uma contribuição Euler e não deve ser dividida ou somada como se fosse uma alocação marginal.

## Controles numéricos

### Truncamento

A distribuição possui suporte potencialmente infinito. `max_loss_dollars` limita apenas o domínio calculado. O código retorna:

- `tail_mass_upper_bound = 1 - sum(pmf)`;
- `pmf_expected_loss`, a EL capturada no domínio truncado;
- `expected_loss`, a EL exata dos inputs.

A PMF não é renormalizada. Se a CDF truncada não alcançar a confiança solicitada, o cálculo do quantil lança erro.

### FFT

A FFT é usada somente para convoluir distribuições setoriais. Resíduos negativos inferiores a `1e-15` são tratados como ruído numérico. Probabilidades negativas materiais geram exceção, e nenhuma reescala posterior é aplicada.

### Underflow

Quando a probabilidade de perda zero não cabe em `float64`, a recursão é executada em log-espaço. Isso preserva a massa em torno do modo em carteiras com frequência agregada elevada.

### Pools homogêneos

`obligor_counts=m_A` comprime contratos com EAD, PD, volatilidade, recuperação e pesos setoriais idênticos. Multiplicar suas contribuições por \(m_A\) é algebricamente equivalente a repetir as linhas. A homogeneidade dentro do pool, contudo, é uma decisão de segmentação que precisa ser validada em uso real.

## Instalação

Requer Python 3.10 ou superior.

```bash
git clone <endereco-do-repositorio>
cd credit-risk-plus
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No Windows PowerShell, a ativação equivalente é:

```powershell
venv\Scripts\Activate.ps1
```

## Uso rápido da API funcional

Para aplicações novas, prefira a API detalhada:

```python
import numpy as np

from creditriskplus import data
from creditriskplus.simple_model import calculate_loss_distribution_detailed

portfolio = data.create_example_1a_portfolio()

result = calculate_loss_distribution_detailed(
    exposures=portfolio["exposure"].to_numpy(),
    mean_default_rates=portfolio["mean_default_rate"].to_numpy(),
    std_default_rates=portfolio["std_default_rate"].to_numpy(),
    recovery_rates=np.zeros(len(portfolio)),
    max_loss_dollars=250_000_000,
)

print(f"Unidade: {result.unit_size:,.0f}")
print(f"EL: {result.expected_loss:,.2f}")
print(f"VaR99 discreto: {result.quantile(0.99):,.2f}")
print(f"VaR99 interpolado como XLS: {result.quantile(0.99, interpolate=True):,.2f}")
print(f"Massa truncada: {result.tail_mass_upper_bound:.3e}")
```

Resultado esperado para o Exemplo 1A:

```text
Unidade: 202.389
EL: 14.221.863,48
VaR99 discreto: 55.454.586,00
VaR99 interpolado como XLS: 55.311.503,38
Massa truncada: aproximadamente 1,1e-12
```

A função histórica `calculate_loss_distribution` continua disponível e retorna apenas `(pmf, expected_loss)`.

## Parâmetros da API principal

```python
result = calculate_loss_distribution_detailed(
    exposures,
    mean_default_rates,
    std_default_rates,
    recovery_rates,
    sector_weights_matrix=None,
    idiosyncratic_sector_indices=None,
    unit_size=None,
    max_loss_dollars=150_000_000,
    obligor_counts=None,
)
```

| Parâmetro | Significado |
|---|---|
| `exposures` | EAD bruta por contraparte ou pool, em uma única moeda |
| `mean_default_rates` | PD média no horizonte, entre zero e um |
| `std_default_rates` | Desvio padrão da PD ou intensidade de default, não negativo |
| `recovery_rates` | Taxa de recuperação determinística, entre zero e um |
| `sector_weights_matrix` | Matriz `N × K`; cada linha deve somar um |
| `idiosyncratic_sector_indices` | Índices dos setores específicos sujeitos ao limite Poisson de A12.3 |
| `unit_size` | Unidade monetária do banding; `None` aplica a convenção do XLS |
| `max_loss_dollars` | Maior perda monetária incluída no domínio computado |
| `obligor_counts` | Multiplicidade inteira não negativa de cada pool homogêneo |

## Uso da classe orientada a objetos

```python
from creditriskplus import CreditRiskPlus, data

portfolio = data.create_example_3_4sector_portfolio()
sector_columns = [
    column for column in portfolio.columns
    if column.startswith("sector_weight_")
]

model = CreditRiskPlus(max_loss_units=2_000)
model.set_portfolio(
    portfolio,
    sector_columns=sector_columns,
    idiosyncratic_sector_columns=["sector_weight_Specific"],
)
model.calculate_loss_distribution()

print(model.summary())
contributions = model.calculate_risk_contributions(percentile=99)
```

`model.py` é uma fachada sobre `simple_model.py`; não existe uma segunda recursão matemática independente.

## Estrutura do repositório

```text
credit-risk-plus/
├── creditriskplus/
│   ├── simple_model.py       # núcleo matemático canônico
│   ├── model.py              # fachada orientada a objetos
│   ├── variable_model.py     # compatibilidade legada com aviso de depreciação
│   ├── retail.py             # simulação longitudinal da carteira PF
│   ├── data.py               # portfólios dos exemplos oficiais
│   └── plots.py              # funções auxiliares de visualização
├── notebooks/
│   ├── 01_introducao.ipynb
│   ├── 02_modelo_fixo.ipynb
│   ├── 03_modelo_variavel.ipynb
│   ├── 04_exemplo_1A.ipynb
│   ├── 05_exemplo_1B.ipynb
│   ├── 06_exemplo_1C_multi_ano.ipynb
│   ├── 07_exemplo_2_setores_geo.ipynb
│   ├── 08_exemplo_3_setores_fracionarios.ipynb
│   ├── 11_safras_pf_brasil_creditriskplus.ipynb
│   └── README.md             # parecer individual dos notebooks
├── references/
│   ├── CreditRisk+.pdf
│   └── CreditRisk+.xls
├── wiki/                     # documentação temática complementar
├── AUDITORIA_TECNICA.md
├── extract_expected.py
├── run_tests.py
├── test_notebooks.py
└── requirements.txt
```

## Roteiro dos notebooks

Os notebooks 01–03 apresentam a teoria, 04–08 reproduzem os exemplos oficiais e o notebook 11 aplica o modelo a uma carteira PF longitudinal.

### 01 — Introdução

[Abrir notebook](notebooks/01_introducao.ipynb)

Explica a natureza paramétrica e analítica do CreditRisk+, suas hipóteses, a PGF de perdas, a dependência setorial e as diferenças entre EL, VaR e capital econômico. Também separa aproximações estruturais de erros de implementação.

### 02 — Modelo de taxa fixa

[Abrir notebook](notebooks/02_modelo_fixo.ipynb)

Deriva o limite Poisson, o banding, a preservação da EL e a recursão composta. A implementação é confrontada com massa, média e variância analíticas.

### 03 — Modelo de taxas variáveis

[Abrir notebook](notebooks/03_modelo_variavel.ipynb)

Mostra a mistura Poisson–Gama e a Binomial Negativa setorial. Destaca que a variável Gama pertence à intensidade comum do setor, não a PDs individuais independentes, e compara os limites fixo e variável.

### 04 — Exemplo oficial 1A

[Abrir notebook](notebooks/04_exemplo_1A.ipynb)

Reproduz a carteira oficial de 25 contrapartes e um fator. Valida EL, VaR99 interpolado, quantil discreto, momentos e contribuições de risco A121/A102.

### 05 — Exemplo oficial 1B

[Abrir notebook](notebooks/05_exemplo_1B.ipynb)

Remove as duas maiores exposições da carteira 1A e reproduz o XLS. O estudo distingue redução finita do risco de contribuições marginais ou Euler.

### 06 — Exemplo oficial 1C multi-ano

[Abrir notebook](notebooks/06_exemplo_1C_multi_ano.ipynb)

Reproduz a construção de contrapartes virtuais do exemplo de três anos. O notebook documenta por que essa construção não substitui um modelo completo de migração e dependência temporal.

### 07 — Exemplo oficial 2

[Abrir notebook](notebooks/07_exemplo_2_setores_geo.ipynb)

Aplica três setores geográficos exclusivos — Estados Unidos, Japão e Europa — e demonstra a combinação das distribuições setoriais independentes.

### 08 — Exemplo oficial 3

[Abrir notebook](notebooks/08_exemplo_3_setores_fracionarios.ipynb)

Aplica pesos fracionários em quatro setores e o setor específico de A12.3. A variância do fator específico é zerada literalmente, eliminando a divergência que existia em versões anteriores.

### 11 — Safras PF brasileiras

[Abrir notebook](notebooks/11_safras_pf_brasil_creditriskplus.ipynb)

Estudo sintético de cartão de crédito e crédito pessoal parcelado com:

- backbook inicial com 180 safras históricas explícitas;
- pool de cauda para cartões anteriores ao histórico explícito;
- 12 meses de burn-in;
- 24 safras e 24 fechamentos CreditRisk+ reportados;
- acompanhamento homogêneo das 24 safras até MOB 60;
- quatro faixas de risco e fatores específico, macro, cartão e parcelado;
- seasoning, utilização, amortização, defaults, saídas e originação;
- choque macroeconômico, contração de oferta e tightening de underwriting;
- EL, desvio padrão, VaR95/99/99,9, capital econômico e massa truncada;
- tabelas executivas, séries temporais, heatmap e curvas de vintage.

O estoque não começa vazio. Antes do reporte, um gate compara dois fechamentos sazonais equivalentes em:

- EAD e clientes ativos;
- EL/EAD;
- participação de produto;
- distribuição de EAD por faixas de MOB.

Se os limites configurados não forem atendidos, `run_creditriskplus_over_time` interrompe a execução. O cenário validado apresentou EAD pré-reporte de `+0,31%`, clientes de `+0,48%`, EL/EAD de `+0,11 p.p.`, mudança máxima de mix de `0,29 p.p.` e distância etária de `0,36%`, eliminando o crescimento artificial de aproximadamente 90% da versão iniciada sem backbook.

Originação e eventos de performance usam fluxos pseudoaleatórios independentes. Assim, ampliar o horizonte de vintage não altera defaults já realizados nos 24 meses reportados. Todas as curvas chegam ao mesmo MOB 60; as antigas aparecem mais transparentes e as recentes mais opacas.

O cartão não possui vencimento contratual e pode continuar acumulando defaults depois do MOB 60. O horizonte comum remove censura desigual, mas não impõe artificialmente um platô.

## Notebooks excluídos

Dois notebooks antigos foram removidos durante a auditoria:

- `09_aplicacoes.ipynb`: misturava outputs do CreditRisk+ com regras não calibradas de provisão, limite, preço e RARoC;
- `10_simulacao_portfolio_varejo.ipynb`: era apenas um aviso de substituição, sem análise executável.

As justificativas completas estão em [notebooks/README.md](notebooks/README.md).

## Regressão contra a planilha oficial

Os valores abaixo são os KPIs gravados no XLS. A comparação de VaR usa somente a interpolação linear da planilha; a API econômica continua usando o quantil discreto.

| Exemplo | EL oficial | VaR99 oficial | Tolerância automatizada |
|---|---:|---:|---:|
| 1A | 14.221.863 | 55.311.503 | menor que 1 unidade monetária |
| 1B | 11.162.856 | 39.946.857 | menor que 1 unidade monetária |
| 1C | 17.277.632 | 62.100.307 | menor que 1 unidade monetária |
| 2 | 14.221.863 | 49.931.502 | menor que 1 unidade monetária |
| 3 | 14.221.863 | 47.368.235 | menor que 1 unidade monetária |

## Testes e reprodução

Execute as identidades matemáticas e regressões contra o XLS:

```bash
python run_tests.py
```

A suíte cobre, entre outros pontos:

1. limite Poisson contra a PMF fechada;
2. momentos da PMF contra A115–A118;
3. preservação da EL depois do banding;
4. validação de pesos e inputs;
5. equivalência entre API funcional e classe;
6. equivalência entre pools homogêneos e expansão linha a linha;
7. subfluxo numérico de \(A_0\) em carteiras grandes;
8. cinco regressões oficiais da planilha;
9. maturidade do backbook PF;
10. horizonte comum de MOB 60;
11. invariância dos eventos reportados quando o horizonte de vintage é ampliado.

Execute todos os notebooks em memória:

```bash
python test_notebooks.py
```

O segundo comando é mais lento porque recalcula todas as distribuições e gráficos do estudo longitudinal.

Para abrir os estudos interativamente:

```bash
jupyter lab
```

## Limitações e uso responsável

- A aproximação Poisson é menos adequada para PDs muito altas ou carteiras pequenas.
- Recuperação e EAD são determinísticas dentro de cada fotografia.
- Fatores Gama setoriais são independentes.
- O banding preserva EL, mas pode alterar a variância; unidades menores reduzem esse efeito.
- VaR não é uma medida coerente e deve ser complementado por stress testing e outras métricas.
- A102 fornece uma aproximação de contribuição ao percentil, não uma decomposição exata de VaR.
- O exemplo multi-ano oficial não é um modelo completo de transição temporal.
- A carteira PF usa parâmetros sintéticos, não estimativas extraídas diretamente das séries do Banco Central.
- Uso real exige calibração interna, tratamento de censura, backtesting, validação fora da amostra, estabilidade e governança.

## Documentação complementar

- [Visão geral](wiki/01-Visao-Geral.md)
- [Dados de entrada](wiki/02-Dados-de-Entrada.md)
- [Modelo de taxa fixa](wiki/03-Modelo-Taxa-Fixa-Poisson.md)
- [Modelo de taxas variáveis](wiki/04-Modelo-Taxa-Variavel-NB.md)
- [Setores e correlação](wiki/05-Setores-e-Correlacao.md)
- [Extensão multi-ano](wiki/06-Multi-Ano.md)
- [Capital econômico](wiki/07-Capital-Economico.md)
- [Aplicações](wiki/08-Aplicacoes.md)
- [Implementação Python](wiki/09-Implementacao-Python.md)
- [Validação](wiki/10-Validacao.md)
- [Referências](wiki/11-Referencias.md)

## Referência bibliográfica

Credit Suisse Financial Products. *CreditRisk+: A Credit Risk Management Framework*. Credit Suisse First Boston International, 1997.

Os direitos sobre o manual e a planilha pertencem aos respectivos titulares. Os arquivos são utilizados aqui como referência metodológica e de reprodução dos exemplos.
