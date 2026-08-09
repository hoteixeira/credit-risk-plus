# Auditoria técnica e matemática do CreditRisk+

Data da revisão: 8 de agosto de 2026.

## 1. Escopo e referências

Foram revisados o pacote `creditriskplus`, os scripts de validação, a documentação Wiki, os notebooks e os dois artefatos oficiais em `references`: o manual *CreditRisk+ — A Credit Risk Management Framework* (CSFB, 1997) e a planilha `CreditRisk+.xls`.

O PDF está gravado em MacBinary II, com 128 bytes de cabeçalho antes do marcador `%PDF`. Removido esse prefixo, é o manual completo em 72 páginas. O confronto cobriu as seções A2–A5 (Poisson e banding), A6–A10 (fatores, mistura Poisson–Gama e recursão variável), A11–A12 (limites e decomposição geral), A13 (momentos, contribuições e correlação) e o Apêndice B (exemplos publicados).

## 2. Parecer

O núcleo matemático está correto e reproduz integralmente os artefatos oficiais. A verificação não se limitou a comparar dois KPIs por exemplo: foi confrontada a distribuição inteira, ponto a ponto, em toda a grade publicada, além de todos os percentis, do desvio padrão impresso no manual e das contribuições de risco de cada contraparte.

A única divergência conhecida — a alocação de risco por contraparte — foi diagnosticada e resolvida nesta auditoria. Ela não era um erro: era uma ambiguidade da equação 121 quanto a qual PD usar. As duas leituras existem hoje como convenções explícitas e ambas são verificadas automaticamente.

O modelo continua sujeito às aproximações que pertencem ao próprio CreditRisk+ — aproximação Poisson para eventos raros, discretização da severidade, fatores Gama independentes e parâmetros pontuais de EAD/PD/recuperação. Essas limitações são estruturais e estão separadas dos erros de implementação.

## 3. Evidência de conformidade

Toda linha abaixo é verificada por `run_tests.py` a cada execução.

| Verificação | Cobertura | Resultado |
|---|---|---|
| PMF publicada, ponto a ponto | 5 exemplos, 2.331 pontos de grade | diferença ≤ 5×10⁻⁷ em **todos** os pontos |
| Percentis publicados | 5 exemplos × 8 percentis = 40 valores | diferença < 1 unidade monetária |
| Perda esperada | 5 exemplos | diferença < 1 unidade monetária |
| Desvio padrão (manual, B3.4) | Exemplo 1A: 12.668.742 | diferença < 1 |
| Contribuições de risco | 1A, 1B, 2 e 3 — 98 contrapartes | erro relativo < 10⁻⁵ |

A tolerância de 5×10⁻⁷ é a precisão de impressão da planilha: as probabilidades têm seis casas decimais, então dois valores só se distinguem acima de meia unidade da última casa. Em outras palavras, a implementação bate com a referência até o último dígito que a referência publica.

Bater na PMF inteira é mais forte do que bater em quantis: qualquer erro na recursão, no banding ou na convolução setorial apareceria na distribuição antes de aparecer num percentil isolado.

## 4. Correspondência entre manual e código

| Requisito | Equação/seção | Implementação |
|---|---|---|
| Exposição líquida de recuperação | Seção 3 | `net_exposures = EAD * (1-recovery)` |
| Bandas inteiras e preservação da EL | eq. 11–13 | `ceil(EAD_liquida/L)`; `epsilon = p*EAD_liquida/L`; PD compensada `epsilon/nu` |
| Recursão de taxa fixa | eq. 25 | `A_n = (1/n) sum(epsilon_j * A_{n-nu_j})` |
| Condição inicial fixa | eq. 26 | `A_0 = exp(-mu)`, com `mu = sum(epsilon/nu)` |
| PGF multi-ano | eq. 36–37 | Contrapartes virtuais em `create_example_1c_portfolio` |
| Parâmetros Gama/NB | eq. 52, 60 | `alpha = mu²/sigma²`, `beta = sigma²/mu`, `p = beta/(1+beta)` |
| Recursão de taxa variável | eq. 79–80 | Forma algébrica estável; ver seção 6.3 |
| Condição inicial variável | eq. 55 | `A_0 = (1-p)^alpha`, via `-(mu/beta)*log1p(beta)` |
| Setores independentes | eq. 62, 68 | Produto das PGFs por convolução FFT |
| Decomposição fracionária | eq. 90, 94–97 | Matriz `N x K`, pesos não negativos que somam um |
| Setor específico | A12.3 | Mesma média, `sigma = 0` |
| Limite Poisson | eq. 81–85 | Verificado por teste contra a forma fechada |
| Variância com banding | eq. 29 | `sum(epsilon_A * nu_A)` |
| Momentos completos | eq. 115–118 | `analytic_loss_moments` |
| Contribuição ao sigma | eq. 121 | `calculate_risk_contributions`, duas convenções |
| Contribuição ao percentil | eq. 102 | `RC_A = EL_A + xi*RC_sigma_A` |
| Aditividade | eq. 123 | Testada a 10⁻¹² na convenção do manual |

## 5. Achados desta auditoria

| Severidade | Achado | Consequência | Correção |
|---|---|---|---|
| Alta | Contribuições de risco divergiam da coluna publicada em até 5,1% por contraparte | A única saída do modelo que não reproduzia a referência oficial | Algoritmo da planilha recuperado e implementado como `convention="spreadsheet"`; ver seção 6.1 |
| Alta | A suíte validava apenas EL e VaR99 por exemplo | A PMF completa, 40 percentis, o sigma do manual e 98 contribuições publicadas ficavam sem verificação; alegações de conformidade não eram reexecutáveis | `extract_expected.py` reescrito para ler tudo; seis novos testes de regressão |
| Média | `plot_risk_contributions` fixava a coluna `risk_contribution_99pct` | `KeyError` para qualquer percentil diferente de 99 | Coluna detectada a partir do DataFrame |
| Média | `plot_loss_distribution` desenhava o suporte inteiro | Eixo 55× mais largo que a região útil (4.250 milhões contra um percentil 99,9 de 77 milhões); gráfico ilegível | Eixo recortado em torno do quantil 99,9 com folga |
| Baixa | `create_summary_table` não declarava a convenção de quantil | O leitor comparava 55.454.586 com os 55.311.503 do XLS sem explicação | Convenção rotulada em cada linha; parâmetro `interpolate` |
| Baixa | `model.py` reimplementava a regra de `unit_size` | Duplicação da regra e perda da guarda de exposição positiva | Reuso de `_compute_unit_size` |
| Baixa | `data.py` e `plots.py` grafavam "contrapartees" e não citavam equações | Eram os únicos módulos fora do padrão de comentários do pacote | Corrigidos e nivelados |
| Baixa | `wiki/10-Validacao.md` citava "a simulação Markov do notebook 10" | Referência a um notebook excluído e a uma simulação inexistente | Página reescrita |
| Baixa | `wiki/03` afirmava `mu = sum(p_A)` como igualdade | Escondia justamente a compensação de PD que gera as duas convenções de contribuição | Corrigido para aproximação, com a PD compensada explicitada |
| Baixa | `wiki/04` afirmava que `alpha*p` "permanece constante" | É um limite, `alpha*p = mu/(1+beta)`; a redação sugeria identidade | Corrigido, com a motivação numérica da forma estável |

Correções de auditorias anteriores, já incorporadas: `A_0 = exp(-mu)` no limite fixo, setor específico com variância zero, unificação de `variable_model.py` e `model.py` sobre um único núcleo, ausência de renormalização da PMF truncada, quantil discreto como padrão e validação rigorosa de domínios.

## 6. Pontos delicados

### 6.1 As duas convenções de contribuição de risco

A equação 121 é

```
RC_A = (nu_A * mu_A / sigma) * (nu_A + sum_k (sigma_k/mu_k)^2 * epsilon_k * theta_Ak)
```

O manual não diz se `mu_A` é a PD bruta do rating ou a PD compensada pelo banding, `epsilon_A/nu_A`. As duas leituras divergem em até 5% por contraparte, sempre nas exposições mais arredondadas para cima.

A planilha não contém VBA nem XLM — o add-in de 1997 era um arquivo separado que nunca esteve no repositório —, mas o algoritmo foi recuperado dos próprios números publicados:

- contrapartes que compartilham banda **e** rating têm contribuição ao sigma **idêntica** (contrapartes 5 e 6; 9 e 10);
- dentro da mesma banda, a razão entre contribuições é exatamente a razão das PDs brutas (contrapartes 13, 14 e 15 — ratings D, H e F — na proporção 1 : 6 : 2).

Isso força a PD bruta. Ajustando `RC_sigma / (p_A * nu_A)` contra `nu_A`, o ajuste é afim com resíduo de 3×10⁻⁶ e produz um denominador diferente do sigma publicado: a planilha **reescala** o vetor para que ele some ao sigma correto. O multiplicador `xi` usa o VaR de 99% interpolado.

```
RC_sigma_A = sigma * [nu_A * p_A * (nu_A + S_A)] / sum_B[nu_B * p_B * (nu_B + S_B)]
S_A        = sum_k (sigma_k/mu_k)^2 * epsilon_k * theta_Ak
RC_A       = EL_A + xi * RC_sigma_A,   xi = (VaR99_interpolado - EL) / sigma
```

Reproduz as quatro colunas anuais com erro máximo de 0,00027%, que é o arredondamento dos inteiros impressos.

O padrão continua sendo `convention="manual"`, que usa a PD compensada e é a única internamente consistente com a fórmula de variância da equação 118 usada pelo mesmo código: nela a identidade da equação 123 vale exatamente, sem rescala. `convention="spreadsheet"` existe para reprodução e auditoria.

### 6.2 Banding

O manual menciona arredondamento à unidade mais próxima em A3.3 e, em A4.2, discute o viés conservador do arredondamento para cima. A planilha usa `L = ceil(max(EAD)/100)` e bandas superiores; essa convenção foi mantida e é confirmada pelo casamento exato da PMF em todos os exemplos. O ajuste de frequência preserva a EL original, mas o termo idiossincrático da variância fica levemente superestimado, exatamente como a equação 30 prevê. Reduzir `L` diminui o efeito ao custo de mais estados.

### 6.3 Estabilidade da recursão variável

A recursão da equação 79 envolve o produto `alpha * p`, que é da forma `infinito × 0` quando a volatilidade tende a zero. A implementação nunca o forma: usa as identidades exatas `alpha*p/mu = 1/(1+beta)` e `p/mu = beta/(mu*(1+beta))`, estáveis em toda a faixa e que degeneram suavemente no caso Poisson. Quando `A_0` subflui em float64, a mesma recursão é executada em espaço logarítmico.

### 6.4 Truncamento

A PMF é uma série infinita. `max_loss_dollars` define apenas onde a computação termina. A massa omitida é exposta em `tail_mass_upper_bound` e **nenhum resultado é renormalizado**: um truncamento insuficiente fica visível em vez de contaminar silenciosamente os quantis. Um quantil lança erro se a CDF truncada não alcançar a confiança pedida.

### 6.5 FFT

A FFT multiplica apenas PGFs setoriais já calculadas. Resíduos negativos abaixo de 1e-15 são eliminados; um valor negativo material dispara erro. Não há reescala posterior.

### 6.6 Multiplicidades de varejo

Um pool homogêneo com `m` contratos multiplica por `m` suas contribuições a `epsilon`, `mu` e `sigma`. Isso é exatamente a soma que resultaria de repetir as `m` linhas — verificado por teste a 2×10⁻¹⁶ — e não é aproximação adicional. A homogeneidade dentro do pool, por outro lado, é uma escolha de segmentação.

## 7. Qualidade, comentários e APIs

`simple_model.py` é a única fonte matemática. `model.py` é uma fachada orientada a objetos sobre ele e `variable_model.py` existe apenas para retrocompatibilidade, emitindo `DeprecationWarning`. Um teste garante que classe e função não divirjam.

As fórmulas não triviais têm comentários com referência às equações e todos os módulos, classes e funções possuem docstrings. Nesta auditoria, `data.py` e `plots.py` — que ainda seguiam o padrão antigo — foram nivelados: as tabelas de rating e as carteiras agora citam sua procedência no manual e explicam o que cada parâmetro significa.

O retorno histórico `(pmf, el)` foi preservado. Novas aplicações devem usar `calculate_loss_distribution_detailed`, que também fornece unidade, EL da PMF truncada, massa omitida e parâmetros de cada setor.

## 8. Notebooks

Nove notebooks são mantidos, todos executáveis e com asserções internas de regressão. O parecer individual e a justificativa das duas exclusões estão em `notebooks/README.md`.

`notebooks/11_safras_pf_brasil_creditriskplus.ipynb` é um cenário sintético de carteira PF brasileira, com backbook de 180 safras, 12 meses de burn-in, 24 safras reportadas acompanhadas até MOB 60, choque macro e quatro fatores. Um gate de regime compara dois fechamentos sazonais equivalentes antes do reporte e interrompe a execução se a carteira não estiver madura. O cenário executado apresentou EAD `+0,31%`, clientes `+0,48%`, EL/EAD `+0,11 p.p.`, mudança máxima de mix `0,29 p.p.` e distância etária `0,36%`.

As fontes do Banco Central são usadas como enquadramento e definição, não como alegação de que os parâmetros simulados foram estimados diretamente das séries.

## 9. Limitações remanescentes

- Defaults são aproximados por Poisson, hipótese estrutural do CreditRisk+ e menos adequada para PDs muito altas ou carteiras pequenas.
- Recuperação é determinística. LGD estocástica exigiria estender a severidade.
- Fatores setoriais são independentes; fatores correlacionados exigem outra construção.
- O Exemplo 1C reproduz o tratamento virtual do XLS, que é contábil: não substitui um modelo de migração de rating e dependência temporal.
- A contribuição ao percentil segue a aproximação da equação 102. Apenas a contribuição ao desvio padrão é analítica exata. O manual demonstra a diferença na seção B3.7: as contribuições das contrapartes 24 e 25 somam 19,7 milhões, mas removê-las reduz o percentil de 99% em 15,4 milhões.
- A simulação PF precisa de calibração, backtesting, validação fora da amostra e governança antes de qualquer uso prudencial ou decisório.

## 10. Comandos de verificação

```bash
source venv/bin/activate
python run_tests.py
python test_notebooks.py
```

O primeiro cobre as identidades matemáticas e toda a regressão contra a planilha. O segundo executa os notebooks em memória e é deliberadamente mais lento.
