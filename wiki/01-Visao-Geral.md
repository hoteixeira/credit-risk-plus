# Visão Geral do Credit Risk+

## 1. Contexto Histórico

Antes da publicação do **Credit Risk+** em 1997, a gestão de risco de crédito em instituições financeiras era predominantemente baseada em:

- **Limites individuais por contraparte**: controles sobre a exposição máxima a cada devedor.
- **Ratings e scoring**: classificação de qualidade de crédito.
- **Análise setorial qualitativa**: restrições industriais ou geográficas.

Embora essas técnicas controlem fatores individuais, elas não fornecem uma medida integrada da **distribuição completa de perdas** do portfólio. Em particular, não quantificam adequadamente:

- **Concentração de risco**: a contribuição desproporcional de grandes exposições.
- **Diversificação**: o benefício de expor o capital a fatores de risco independentes.
- **Capital econômico**: o capital necessário para cobrir perdas inesperadas com determinado nível de confiança.

O Credit Risk+, publicado pelo **Credit Suisse First Boston** em dezembro de 1996 (documento técnico de 1997), introduziu uma abordagem analítica fechada para modelar a distribuição de perdas por default de crédito.

## 2. Inovações do Modelo

O modelo se distingue por quatro características fundamentais:

### 2.1 Abordagem Atuarial

Em vez de usar modelos financeiros baseados em correlações de ativos (como o Merton-KMV) ou simulações de Monte Carlo, o Credit Risk+ adota técnicas da **teoria do risco atuarial**:

- Modelagem do número de eventos de default como um processo de contagem.
- Uso de **probability generating functions (PGFs)** para obter distribuições fechadas.
- Derivação de recursões eficientes para a função de massa de probabilidade (PMF) das perdas.

### 2.2 Não Modelagem de Causas de Default

O Credit Risk+ **não tenta explicar por que** um obrigador entra em default. Em vez disso, modela **com que frequência** defaults ocorrem e **qual a magnitude** das perdas associadas. Isso evita:

- A especificação de modelos estruturais complexos para o valor da firma.
- A estimação de correlações de ativos entre todas as parceiras de uma carteira.

### 2.3 Solução Analítica Fechada

A distribuição de perdas é calculada exatamente por **recursão**, sem necessidade de simulação de Monte Carlo. As vantagens computacionais são:

- **Velocidade**: portfólios com milhões de exposições podem ser avaliados em frações de segundo.
- **Reprodutibilidade**: resultados determinísticos para um mesmo conjunto de inputs.
- **Facilidade de stress testing**: cenários podem ser recalculados instantaneamente.

### 2.4 Incorporação de Correlação via Volatilidade

Em vez de especificar uma matriz de correlação de defaults (difícil de estimar e instável), o modelo captura dependência através da **volatilidade das taxas de default**. A intuição é que fatores macroeconômicos comuns fazem com que as taxas de default de muitos obrigadores se movam juntas no tempo.

## 3. Tipos de Risco de Crédito

O Credit Risk+ trata exclusivamente do **risco de default**:

> Risco de que uma contraparte não honre suas obrigações financeiras, gerando uma perda igual à exposição menos o valor recuperado.

Outros tipos de risco de crédito **não** são modelados:

| Tipo de risco | Descrição | Framework usual |
|---------------|-----------|-----------------|
| **Risco de default** | Perda devido ao não-pagamento | Credit Risk+ |
| **Risco de spread** | Variação no prêmio de risco de mercado | VaR de mercado |
| **Risco de migração** | Mudança de rating afetando mark-to-market | CreditMetrics |
| **Risco de recuperação** | Incerteza no valor recuperado | Modelos auxiliares |

> Nota: embora o Credit Risk+ permita diferentes taxas de recuperação, elas são tratadas como determinísticas nos exemplos clássicos.

## 4. Componentes do Framework

O framework pode ser visualizado em três pilares:

```
┌─────────────────────────────────────────────────────────────┐
│                    Credit Risk+                              │
├───────────────────┬─────────────────────┬───────────────────┤
│  Medição do Risco │  Capital Econômico  │   Aplicações      │
│                   │                     │                   │
│  • Exposições     │  • Distribuição de  │  • Provisioning   │
│  • Default rates  │    perdas completa  │  • Limites de     │
│  • Volatilidades  │  • VaR e percentis  │    crédito        │
│  • Recovery rates │  • Capital Econômico│  • Stress testing │
│  • Modelo CR+     │  • Risk contributions│  • Gestão de      │
│                   │                     │    portfólio      │
└───────────────────┴─────────────────────┴───────────────────┘
```

### 4.1 Medição do Risco

Os inputs principais são:

- Exposições líquidas por contraparte.
- Probabilidades de default (PD) médias.
- Volatilidades das PDs.
- Taxas de recuperação (recovery rates).
- Estrutura de setores e correlações implícitas.

### 4.2 Capital Econômico

O output central é a **distribuição completa de perdas**, da qual derivam:

- **Perda Esperada (EL)**: média da distribuição.
- **Value at Risk (VaR)**: percentil de alta confiança (ex: 99%).
- **Capital Econômico (EC)**: $EC = VaR - EL$.
- **Risk Contributions (RC)**: decomposição aditiva do VaR por contraparte.

### 4.3 Aplicações

- **Provisão Anual de Crédito (ACP)**: cobertura da perda esperada.
- **Reserva Incremental de Crédito (ICR)**: buffer para variações em torno da ACP.
- **Limites de crédito baseados em risco**: alocação de capital por contraparte.
- **Stress testing**: análise de cenários macroeconômicos adversos.
- **RARoC**: retorno ajustado ao risco sobre capital.

## 5. Visão Geral do Processo de Modelagem

O modelo opera em dois estágios sequenciais:

```
Estágio 1: Frequência de defaults
    ↓  Distribuição do número de eventos de default
Estágio 2: Severidade das perdas
    ↓  Distribuição das perdas monetárias agregadas
```

No **Estágio 1**, modela-se quantas contrapartes darão default. No **Estágio 2**, converte-se o número de defaults em perdas financeiras, considerando que cada default tem uma exposição associada.

## 6. Horizonte de Tempo

O modelo padrão tem **horizonte de um ano**, consistente com a prática regulatória e de gestão de capital. A extensão multi-ano (discutida em [Extensão Multi-Ano](06-Multi-Ano)) permite considerar horizontes de vários anos para carteiras hold-to-maturity.

## 7. Pressupostos Fundamentais

O Credit Risk+ baseia-se nos seguintes pressupostos:

1. **Eventos de default são raros**: as probabilidades individuais de default são pequenas.
2. **Não há causalidade entre defaults**: a dependência entre defaults surge apenas através de fatores sistêmicos comuns (setores).
3. **A exposição é conhecida**: incertezas de mark-to-market futuro não são modeladas explicitamente.
4. **A taxa de default é estocástica**: a incerteza na própria taxa média é modelada por uma distribuição Gama.
5. **Setores são independentes**: fatores sistêmicos de setores distintos são mutuamente independentes.

## 8. Relação com Outros Modelos

| Modelo | Abordagem | Captura de correlação |
|--------|-----------|----------------------|
| **Credit Risk+** | Atuarial, PGFs, recursão | Volatilidade das PDs / setores Gama |
| **CreditMetrics** | Migração de ratings, mark-to-market | Matriz de correlação de ativos |
| **KMV / Merton** | Estrutural, distância até o default | Correlação de ativos subjacentes |
| **CreditPortfolioView** | Macroecônomico, regressão logit | Fatores macroeconômicos |
| **Copula models** | Simulação, dependência via copula | Matriz de correlação ou copula escolhida |

A principal vantagem do Credit Risk+ é a **tratabilidade analítica** combinada com uma captura econômica razoável da dependência de defaults através de fatores sistêmicos.

## 9. Estrutura do Repositório

A implementação deste projeto segue a estrutura:

```
credit-risk-plus/
├── references/
│   ├── CreditRisk+.pdf        # Documento oficial (Credit Suisse, 1997)
│   └── CreditRisk+.xls        # Planilha de referência com exemplos
├── creditriskplus/
│   ├── simple_model.py        # Implementação principal (NB recursion)
│   ├── data.py                # Dados dos portfólios de exemplo
│   ├── plots.py               # Utilitários de visualização
│   ├── model.py               # Modelo alternativo
│   └── variable_model.py      # Extenções variáveis
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
└── wiki/                      # Esta documentação
```

## 10. Próximos Passos

Para uma compreensão completa, recomenda-se seguir a wiki na ordem:

1. [Dados de Entrada](02-Dados-de-Entrada)
2. [Modelo de Taxa Fixa: Poisson](03-Modelo-Taxa-Fixa-Poisson)
3. [Modelo de Taxa Variável: Binomial Negativa](04-Modelo-Taxa-Variavel-NB)
4. [Setores e Correlação](05-Setores-e-Correlacao)
5. [Extensão Multi-Ano](06-Multi-Ano)
6. [Capital Econômico](07-Capital-Economico)
