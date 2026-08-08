# Auditoria técnica e matemática do CreditRisk+

Data da revisão: 8 de agosto de 2026.

## 1. Escopo e referências

Foram revisados o pacote `creditriskplus`, os scripts de validação, a documentação Wiki, os notebooks e os dois artefatos oficiais em `references`: o manual *CreditRisk+ — A Credit Risk Management Framework* (CSFB, 1997) e sua planilha `CreditRisk+.xls`.

O confronto matemático concentrou-se nas Seções A3–A5 (banding e recursão Poisson), A7–A10 (fatores, mistura Poisson–Gama e recursão variável), A11–A12 (limites e decomposição geral), A13 (momentos e contribuições de risco) e nos Exemplos 1A–1C, 2 e 3 da planilha.

## 2. Parecer

Após as correções desta auditoria, o núcleo funcional está alinhado às equações do manual e reproduz os cinco exemplos da planilha com diferença inferior a uma unidade monetária na EL e no VaR de 99% sob a mesma interpolação do XLS. A API econômica mantém o quantil discreto como definição padrão.

O modelo continua sujeito às aproximações que pertencem ao próprio CreditRisk+: aproximação Poisson para eventos raros, discretização da severidade, fatores Gama independentes e parâmetros pontuais de EAD/PD/recuperação. Essas limitações não são bugs e agora estão separadas dos erros de implementação.

## 3. Achados e correções

| Severidade | Achado anterior | Consequência | Correção |
|---|---|---|---|
| Crítica | No limite fixo, `A[0]` usava `exp(-sum(epsilon))` | Confundia perda em unidades com número de defaults; podia causar underflow e PMF nula | `A[0]=exp(-mu)`, com `mu=sum(epsilon/nu)`, conforme A3/A11 |
| Crítica | O setor específico era uma convolução de NBs individuais com `alpha=4` | Introduzia volatilidade inexistente em A12.3 e errava o VaR do Exemplo 3 em 0,579% | Variância do setor específico fixada em zero; limite Poisson de A11 |
| Crítica | `variable_model.py` calculava `mu` com dimensões incorretas e ignorava setores após o primeiro | API pública podia devolver uma distribuição sem relação com o modelo documentado | Módulo transformado em camada legada sobre o núcleo canônico |
| Alta | `model.py` tinha outra recursão, ajuste ad hoc de `A0` e contribuições aproximadas incorretas | Duas APIs do mesmo pacote produziam resultados incompatíveis | Classe reescrita como fachada do núcleo único; contribuições implementam A121/A102 |
| Alta | Toda PMF truncada era normalizada para somar um | Transferia artificialmente a massa omitida para o domínio calculado, alterando momentos e quantis | Nenhuma renormalização; `tail_mass_upper_bound` e EL truncada são expostas |
| Alta | VaR interpolado era tratado como o quantil do modelo | Interpolação entre pontos sem massa não é o VaR de uma variável discreta | Quantil discreto por padrão; interpolação existe apenas para regressão com o XLS |
| Alta | O extrator calculava a EL a partir da coluna truncada da PMF | Produzia “referências” cerca de 0,3% abaixo do output oficial | Leitura dos KPIs gravados na tabela de percentis do XLS |
| Média | Não havia validação rigorosa de dimensões, domínios e pesos | Inputs inválidos podiam contaminar silenciosamente os resultados | Validação de finitude, intervalos, shapes, pesos que somam um e índices setoriais |
| Média | Convoluções densas e loops quadráticos tornavam testes muito lentos | O Exemplo 2 podia levar minutos e a simulação longitudinal ficava impraticável | Epsilons agregados por banda e convolução setorial por FFT |
| Média | A simulação antiga de varejo tratava EAD agregado como intensidade de defaults | Distribuição e capital não correspondiam ao CreditRisk+ | Notebook antigo marcado como substituído; novo motor usa pools com multiplicidades exatas |
| Média | Os notebooks 6–8 não reproduziam integralmente os exemplos oficiais | Conteúdo pedagógico contradizia código e planilha | Notebooks reescritos sobre a API canônica e reexecutados |

## 4. Correspondência entre manual e código

| Requisito | Equação/seção | Implementação |
|---|---|---|
| Exposição líquida de recuperação | Seção 3 do manual | `net_exposures = EAD * (1-recovery)` |
| Bandas inteiras e preservação da EL | A11–A13 | `ceil(EAD_liquida/L)` e `epsilon=p*EAD_liquida/L`; a PD ajustada é `epsilon/nu` |
| Média setorial | A94/A96 | `mu_k=sum(theta*epsilon/nu)` |
| Volatilidade setorial | A97 | `sigma_k=sum(theta*sigma_A*exact_band/nu)` |
| Parâmetros Gama/NB | A52/A60 | `alpha=mu²/sigma²`, `beta=sigma²/mu`, `p=beta/(1+beta)` |
| Recursão variável | A79/A80 | Forma algébrica estável, sem o produto indeterminado `alpha*p` |
| Limite fixo | A81–A85 | Recursão Poisson com `A0=exp(-mu)` |
| Setores independentes | A62/A68 | Produto das PGFs por convolução FFT |
| Decomposição fracionária | A90–A97 | Matriz `N x K`, pesos não negativos que somam um |
| Setor específico | A12.3 | Mesma média e `sigma_specific=0` |
| Momentos | A115–A118 | `analytic_loss_moments` |
| Contribuição ao sigma e ao percentil | A121/A102 | Método `calculate_risk_contributions` da classe |

## 5. Regressão numérica

Valores abaixo são os outputs gravados no XLS. O VaR comparado usa exclusivamente a interpolação linear da própria planilha; o VaR discreto da API será, em geral, um ponto adjacente da grade.

| Exemplo | EL do XLS | VaR99 do XLS | Tolerância automatizada |
|---|---:|---:|---:|
| 1A | 14.221.863 | 55.311.503 | menor que 1 |
| 1B | 11.162.856 | 39.946.857 | menor que 1 |
| 1C | 17.277.632 | 62.100.307 | menor que 1 |
| 2 | 14.221.863 | 49.931.502 | menor que 1 |
| 3 | 14.221.863 | 47.368.235 | menor que 1 |

A suíte também verifica:

1. igualdade da recursão fixa com a PMF Poisson fechada;
2. igualdade dos momentos da PMF com A115–A118;
3. preservação exata da EL apesar do arredondamento de bandas;
4. rejeição de pesos setoriais inválidos;
5. identidade entre API funcional e classe;
6. aditividade das contribuições ao desvio padrão;
7. equivalência, até `2e-16`, entre pools com multiplicidade e expansão contrato a contrato.

## 6. Aproximações e controles numéricos

### 6.1 Banding

O manual menciona arredondamento à unidade mais próxima e depois discute o viés conservador do arredondamento para cima. A planilha usa `L=ceil(max(EAD)/100)` e bandas superiores; essa convenção foi mantida para reprodutibilidade. O ajuste da frequência preserva a EL original, mas o termo idiossincrático da variância pode ficar levemente superestimado. Reduzir `L` diminui esse efeito ao custo de mais estados.

### 6.2 Truncamento

A PMF é uma série infinita. `max_loss_dollars` define apenas onde a computação termina. A massa omitida é `1-sum(pmf)`; nenhum resultado é renormalizado. Um quantil lança erro se a CDF truncada não alcançar a confiança pedida. No notebook longitudinal, o limite é ampliado automaticamente até massa omitida menor que `1e-8` e cobertura do VaR 99,9%.

### 6.3 FFT

A FFT é usada somente para multiplicar PGFs setoriais já calculadas. Resíduos negativos abaixo de `1e-15` são eliminados; um valor negativo material dispara erro. Não há reescala posterior.

### 6.4 Multiplicidades de varejo

Um pool homogêneo com `m` contratos multiplica por `m` suas contribuições a `epsilon`, `mu` e `sigma`. Isso é exatamente a soma que resultaria de repetir as `m` linhas; não é uma aproximação adicional. A homogeneidade dos parâmetros dentro do pool, por outro lado, é uma escolha de segmentação a ser refinada em implantação real.

## 7. Qualidade, comentários e APIs

As fórmulas não triviais têm comentários com referência às equações, todos os módulos, classes e funções possuem docstrings e a validação está separada da lógica de cálculo. `simple_model.py` é a única fonte matemática. `model.py` é uma fachada orientada a objetos e `variable_model.py` existe apenas para retrocompatibilidade, emitindo `DeprecationWarning`.

O retorno histórico `(pmf, el)` foi preservado. Novas aplicações devem usar `calculate_loss_distribution_detailed`, que também fornece unidade, EL da PMF truncada, massa omitida e parâmetros de cada setor.

## 8. Notebook PF por safras

`notebooks/11_safras_pf_brasil_creditriskplus.ipynb` foi criado e executado com:

- 36 safras mensais, 12 de ramp-up e 24 reportadas;
- cartão de crédito e crédito pessoal parcelado;
- faixas A–D, seasoning, amortização/utilização, defaults, saídas e originação;
- choque macro, contração de oferta e tightening de underwriting;
- fatores específico, macro, cartão e parcelado;
- CreditRisk+ em cada uma das 24 safras e em cada um dos 24 fechamentos;
- EL, sigma, VaR 95%/99%/99,9%, capital, massa truncada, produto e vintage;
- tabelas executivas, séries temporais, composição e heatmap de MOB.

O cenário é sintético. As fontes do Banco Central são usadas como enquadramento e definição, não como alegação de que os parâmetros simulados foram estimados diretamente das séries.

## 9. Limitações remanescentes

- Defaults são aproximados por Poisson, hipótese estrutural do CreditRisk+ e menos adequada para PDs muito altas ou carteiras pequenas.
- Recuperação é determinística. LGD estocástica exigiria extensão da severidade.
- Fatores setoriais são independentes; fatores correlacionados exigem outra construção.
- O Exemplo 1C reproduz o tratamento virtual do XLS, mas não substitui um modelo completo de migração e dependência temporal.
- Contribuição a VaR segue a aproximação A102; apenas a contribuição ao desvio padrão é analítica exata.
- A simulação PF precisa de calibração, backtesting, estabilidade, validação fora da amostra e governança antes de qualquer uso prudencial ou decisório.

## 10. Comandos de verificação

```bash
source venv/bin/activate
python run_tests.py
python test_notebooks.py
```

O primeiro comando cobre as identidades matemáticas e a planilha. O segundo executa todos os notebooks em memória e é deliberadamente mais lento.
