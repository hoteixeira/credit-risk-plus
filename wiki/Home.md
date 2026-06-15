# Credit Risk+ Wiki

Bem-vindo à documentação técnica completa do projeto **Credit Risk+**. Esta wiki foi construída a partir do paper oficial *CreditRisk+: A Credit Risk Management Framework* (Credit Suisse First Boston, 1997) e da implementação em Python disponível neste repositório.

## Propósito

O objetivo desta wiki é fornecer uma referência rigorosa, autocontida e detalhada sobre:

1. O arcabouço teórico do modelo Credit Risk+.
2. As demonstrações matemáticas das fórmulas de distribuição de perdas.
3. A implementação computacional em Python.
4. Os exemplos numéricos e aplicações práticas.

## Público-alvo

- Quantitative analysts e modeladores de risco de crédito.
- Desenvolvedores que precisam entender ou estender a implementação.
- Estudantes e pesquisadores interessados em modelagem de risco de crédito atuarial.

## Índice da Wiki

| Página | Descrição |
|--------|-----------|
| [Visão Geral](01-Visao-Geral) | Contexto histórico, motivação e componentes do framework. |
| [Dados de Entrada](02-Dados-de-Entrada) | Exposições, probabilidades de default, volatilidades e taxas de recuperação. |
| [Modelo de Taxa Fixa: Poisson](03-Modelo-Taxa-Fixa-Poisson) | Derivação da distribuição de Poisson para número de defaults e recursão de perdas. |
| [Modelo de Taxa Variável: Binomial Negativa](04-Modelo-Taxa-Variavel-NB) | Mistura Poisson-Gama, distribuição binomial negativa e recursão geral. |
| [Setores e Correlação](05-Setores-e-Correlacao) | Setores sistemáticos, pesos fracionários, setor idiossincrático e correlações implícitas. |
| [Extensão Multi-Ano](06-Multi-Ano) | Horizonte de vários anos, contrapartes virtuais e taxas marginais condicionais. |
| [Capital Econômico](07-Capital-Economico) | VaR, capital econômico e contribuições de risco. |
| [Aplicações Práticas](08-Aplicacoes) | Provisão, limites, stress testing, otimização e RARoC. |
| [Implementação Python](09-Implementacao-Python) | Estrutura do código, API principal e notebooks. |
| [Validação](10-Validacao) | Comparação com a planilha oficial e precisão dos resultados. |
| [Referências](11-Referencias) | Bibliografia e recursos adicionais. |

## Referência Rápida: Fórmulas Principais

A distribuição de perdas do Credit Risk+ é obtida através da **probability generating function (PGF)**:

### Caso de taxas fixas (Poisson)

$$
G(z) = \exp\!\left[ \mu \bigl(P(z) - 1\bigr) \right]
$$

com recursão:

$$
A_n = \frac{1}{n} \sum_{j: \nu_j \le n} \varepsilon_j \, A_{n - \nu_j}, \qquad A_0 = e^{-\mu}
$$

### Caso de taxas variáveis (binomial negativa)

$$
G(z) = \prod_{k=1}^{K} \left( \frac{1 - p_k}{1 - p_k P_k(z)} \right)^{\alpha_k}
$$

com recursão geral:

$$
A_n = \frac{p}{n \mu} \sum_{j: \nu_j \le n} \varepsilon_j \left( \alpha - 1 + \frac{n}{\nu_j} \right) A_{n - \nu_j}, \qquad A_0 = (1 - p)^{\alpha}
$$

onde, para cada setor $k$:

$$
\mu_k = \sum_A \theta_{Ak} \frac{\varepsilon_A}{\nu_A}, \qquad
\sigma_k = \sum_A \theta_{Ak} \sigma_A \frac{E_A / L}{\nu_A}, \qquad
\alpha_k = \frac{\mu_k^2}{\sigma_k^2}, \qquad
\beta_k = \frac{\sigma_k^2}{\mu_k}, \qquad
p_k = \frac{\beta_k}{1 + \beta_k}
$$

## Convenções de Notação

- $N$: número de contrapartes (obrigadores).
- $K$: número de setores.
- $E_A$: exposição bruta da contraparte $A$.
- $E_A^{\text{net}} = E_A (1 - RR_A)$: exposição líquida após recuperação.
- $p_A$: probabilidade média de default de $A$.
- $\sigma_A$: desvio-padrão da taxa de default de $A$.
- $L$: unidade de perda (band size).
- $\nu_A = \lceil E_A^{\text{net}} / L \rceil$: banda de exposição.
- $\varepsilon_A = p_A E_A^{\text{net}} / L$: perda esperada em unidades de $L$.
- $\theta_{Ak}$: peso da contraparte $A$ no setor $k$, com $\sum_k \theta_{Ak} = 1$.

## Contribuindo

Se encontrar erros, imprecisões ou quiser sugerir melhorias, sinta-se à vontade para abrir uma issue ou enviar um pull request. A precisão técnica é a prioridade máxima desta documentação.
