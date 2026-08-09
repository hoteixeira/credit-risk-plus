# Validação

A implementação deste repositório foi validada contra as duas fontes primárias em `references/`: o manual *CreditRisk+ — A Credit Risk Management Framework* (Credit Suisse First Boston, 1997) e a planilha oficial `CreditRisk+.xls`. Esta página descreve o que foi confrontado, com que resultado e quais diferenças permanecem por definição.

---

## 1. Referência Oficial

O PDF do manual está gravado em formato MacBinary II: há 128 bytes de cabeçalho antes do marcador `%PDF`. Removido esse prefixo, o arquivo é o manual completo, com 72 páginas e o Apêndice A inteiro.

A planilha `references/CreditRisk+.xls` contém os exemplos numéricos originais:

- **Exemplo 1A**: 25 contrapartes, 1 setor (Economia Geral).
- **Exemplo 1B**: 23 contrapartes (remoção das contrapartes 24 e 25).
- **Exemplo 1C**: 25 contrapartes com horizonte de 3 anos.
- **Exemplo 2**: 25 contrapartes divididas em 3 setores geográficos exclusivos.
- **Exemplo 3**: 25 contrapartes divididas em 4 setores com pesos fracionários + setor específico.

A planilha **não contém macro VBA nem XLM**. O manual explica por quê na seção B3.1: a implementação original era "a single spreadsheet together with an addin", e esse add-in era um arquivo separado, distribuído em 1997 pelo site do banco. Ele nunca esteve no repositório. Portanto, as colunas de saída do XLS são valores estáticos: são referência, não código executável.

---

## 2. Resultados de Validação

Cada linha abaixo é verificada automaticamente por `run_tests.py`.

| Verificação | Cobertura | Resultado |
|---|---|---|
| Perda esperada | 5 exemplos | diferença < 1 unidade monetária |
| PMF publicada, ponto a ponto | 5 exemplos, 2.331 pontos de grade | diferença ≤ 5×10⁻⁷ em todos os pontos |
| Percentis publicados | 5 exemplos × 8 percentis = 40 valores | diferença < 1 unidade monetária |
| Desvio padrão (manual, seção B3.4) | Exemplo 1A | 12.668.742, diferença < 1 |
| Contribuições de risco | 1A, 1B, 2 e 3 — 98 contrapartes | erro relativo < 10⁻⁵ |

A tolerância de 5×10⁻⁷ na PMF é a própria precisão de impressão da planilha: as probabilidades têm seis casas decimais, então dois valores só são distinguíveis acima de meia unidade da última casa. Bater em todos os pontos da distribuição é uma validação mais forte do que bater em alguns quantis, porque qualquer erro na recursão, no banding ou na convolução setorial apareceria na PMF antes de aparecer num percentil isolado.

**Convenção de quantil.** Os percentis batem sob a interpolação linear que a própria planilha usa. A API continua devolvendo o quantil discreto por padrão, que é o VaR matemático de uma variável discreta; passe `interpolate=True` para reproduzir o XLS. Os dois diferem por menos de uma unidade $L$.

---

## 3. Interpretação das Diferenças

### 3.1 Exemplo 3: setor específico

Reproduzido aplicando diretamente A12.3: o setor específico conserva sua contribuição de média, mas recebe variância zero e converge ao caso Poisson de A11. A hipótese anterior de binomiais negativas individuais com $\alpha_A = 4$ não consta do manual e foi removida.

### 3.2 Contribuições de risco: duas convenções legítimas

A equação 121 do manual é

$$
RC_A = \frac{\nu_A \mu_A}{\sigma}\left( \nu_A + \sum_k \left(\frac{\sigma_k}{\mu_k}\right)^2 \varepsilon_k \theta_{Ak} \right),
$$

mas ela não diz explicitamente se $\mu_A$ é a PD bruta do rating ou a PD compensada pelo banding, $\varepsilon_A/\nu_A$. As duas leituras dão resultados diferentes, e a diferença chega a 5% por contraparte — exatamente nas exposições mais arredondadas para cima.

O algoritmo da planilha foi recuperado a partir dos próprios números publicados. Duas evidências o determinam:

- contrapartes que compartilham banda **e** rating têm contribuição ao desvio padrão **idêntica** (contrapartes 5 e 6, 9 e 10);
- dentro de uma mesma banda, a razão entre contribuições é exatamente a razão das PDs brutas (contrapartes 13, 14 e 15, ratings D, H e F, na proporção 1 : 6 : 2).

Isso só é possível se a planilha usar a **PD bruta**. O vetor resultante não soma ao desvio padrão, e a planilha o **reescala** para que some. O multiplicador $\xi$ usa o VaR de 99% interpolado.

$$
RC^{\sigma}_A = \sigma \cdot \frac{\nu_A\, p_A\,(\nu_A + S_A)}{\sum_B \nu_B\, p_B\,(\nu_B + S_B)}, \qquad S_A = \sum_k \left(\frac{\sigma_k}{\mu_k}\right)^2 \varepsilon_k \theta_{Ak}
$$

Ambas estão disponíveis:

| `convention` | PD usada | Aditividade | Uso |
|---|---|---|---|
| `"manual"` (padrão) | compensada, $\varepsilon_A/\nu_A$ | exata pela equação 123, sem rescala | análise |
| `"spreadsheet"` | bruta do rating | obtida por rescala | reprodução do XLS |

Nenhuma é um erro da outra. A do manual é internamente consistente com a fórmula de variância da equação 118 que o mesmo código usa; a da planilha é o que produziu os números publicados.

---

## 4. Fontes de Discrepância Potenciais

| Fonte | Impacto |
|-------|---------|
| Arredondamento de bandas ($\nu_A$) | Pequeno na distribuição; material apenas na alocação por contraparte |
| Truncamento da distribuição (`max_loss_dollars`) | Mensurado por `tail_mass_upper_bound`; sem renormalização |
| Normalização das PMFs após truncamento | Não realizada; evita distorção de momentos e quantis |
| Implementação do setor específico | Variância zero, conforme A12.3 |
| Convenção de quantil (discreto vs. interpolado) | Menos de uma unidade $L$ |
| Precisão da planilha Excel | Seis casas decimais na PMF; inteiros nas contribuições |

---

## 5. Testes Automatizados

`run_tests.py` verifica:

1. limite Poisson da recursão contra a PMF fechada;
2. momentos da PMF contra as equações analíticas 115–118;
3. preservação exata da perda esperada apesar do arredondamento de bandas;
4. estabilidade da recursão em log quando $e^{-\mu}$ subflui;
5. rejeição de pesos setoriais que violem a equação 90;
6. equivalência entre pools com multiplicidade e expansão contrato a contrato;
7. identidade entre a API funcional e a classe;
8. as cinco linhas da tabela da seção 2 desta página;
9. aditividade da convenção `"manual"` e rejeição de convenções desconhecidas;
10. maturidade do backbook no estudo longitudinal PF.

`test_notebooks.py` executa todos os notebooks em memória, sem alterar os arquivos.

```bash
source venv/bin/activate
python run_tests.py
python test_notebooks.py
```

---

## 6. Reprodutibilidade

O modelo é analítico: dada a mesma carteira, o resultado é determinístico e não depende de semente. A aleatoriedade aparece apenas no gerador de cenário sintético do notebook 11, cujas sementes são fixadas em `RetailSimulationConfig` e cujos fluxos de originação e de eventos são separados, de modo que ampliar o horizonte não reescreve defaults já reportados.

---

## 7. Conclusão

A implementação reproduz integralmente os cinco exemplos oficiais: a distribuição inteira, todos os percentis publicados, o desvio padrão do manual e as contribuições de risco. As diferenças remanescentes são de convenção, estão documentadas e são selecionáveis por parâmetro.

O caso multi-ano reproduz o tratamento de contrapartes virtuais da planilha, mas isso é uma construção contábil: ele não modela migração de rating nem dependência temporal, e deve ser validado separadamente da regressão anual.
