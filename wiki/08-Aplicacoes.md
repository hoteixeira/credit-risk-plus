# Aplicações Práticas

O Credit Risk+ não é apenas um modelo de medição de risco; é uma plataforma para diversas aplicações práticas de gestão de crédito. Este capítulo descreve as principais aplicações discutidas no documento oficial e implementadas nos notebooks.

---

## 1. Provisão Anual de Crédito (ACP)

A **Provisão Anual de Crédito** (ou Loan Loss Provision) é a cobertura contábil para a perda esperada da carteira.

### 1.1 Fórmula

$$
\boxed{
ACP = \sum_A E_A^{\text{net}} \cdot p_A = \sum_A EL_A = EL
}
$$

A ACP é carregada ao P&L anualmente como o "preço" de fazer negócios com risco de crédito.

### 1.2 Interpretação

- A ACP cobre a **perda esperada** em média.
- Não cobre perdas inesperadas (essas são função do capital).
- Deve ser recalculada periodicamente conforme as PDs e exposições evoluem.

---

## 2. Reserva Incremental de Crédito (ICR)

A **Reserva Incremental de Crédito** (Incremental Credit Reserve) funciona como um buffer para variações das perdas efetivas em torno da ACP.

### 2.1 Mecanismo

- **Anos bons** (perdas < ACP): o excedente credita o ICR, até um limite máximo (ICR Cap).
- **Anos ruins** (perdas > ACP): o ICR absorve o excesso antes de impactar o capital.

### 2.2 ICR Cap

$$
\boxed{
ICR\ Cap = \text{VaR}(99\%) - EL = EC(99\%)
}
$$

O ICR Cap é equivalente ao Capital Econômico. Em conjunto com a ACP, cobre perdas até o percentil 99%.

---

## 3. Limites de Crédito Baseados em Risco

### 3.1 Limites tradicionais vs. baseados em risco

Limites tradicionais fixam exposições máximas por contraparte independentemente do risco. Limites baseados em risco alocam capital igualmente entre contrapartes.

### 3.2 Alocação igual de capital

Se cada contraparte deve ter a mesma contribuição de risco $\widehat{RC}$, então:

$$
E_A \cdot p_A \cdot (1 - RR_A) \propto \text{constante}
$$

Portanto:

$$
\boxed{
\text{Limite}_A \propto \frac{1}{p_A (1 - RR_A)}
}
$$

### 3.3 Implicações

- Contrapartes de pior rating recebem limites menores.
- Contrapartes com melhor rating podem ter limites maiores.
- O apetite de risco é alocado de forma eficiente.

---

## 4. Stress Testing

A velocidade computacional do Credit Risk+ torna o stress testing prático e iterativo.

### 4.1 Tipos de cenário

| Cenário | Alteração nos inputs |
|---------|---------------------|
| Recessão leve | Aumento de 20% nas PDs |
| Recessão moderada | Aumento de 50% nas PDs |
| Recessão severa | Dobra das PDs |
| Crise setorial | Redução do número efetivo de setores |
| Queda na recuperação | Redução geral nos recovery rates |
| Aumento de volatilidade | Aumento nas $\sigma_A$ |

### 4.2 Vantagem analítica

Diferentemente de modelos de simulação, o Credit Risk+ recalcula toda a distribuição em milissegundos. Isso permite:

- Análise de sensibilidade em tempo real.
- Otimização de portfólio com restrições de capital.
- Relatórios de cenários para comitês de risco.

---

## 5. Otimização de Portfólio

### 5.1 Redução de concentração

O Exemplo 1B do paper ilustra a remoção das duas maiores exposições:

| Métrica | Exemplo 1A | Exemplo 1B | Variação |
|---------|-----------:|-----------:|:--------:|
| Número de contrapartes | 25 | 23 | −8% |
| EL | \$14.221.863 | \$11.162.856 | −21,5% |
| VaR(99%) | \$55.311.503 | \$39.946.857 | −27,8% |

A queda no VaR é proporcionalmente maior que a queda no EL — demonstrando o valor de reduzir concentrações.

### 5.2 Fronteira eficiente

O modelo permite construir fronteiras de retorno esperado vs. capital econômico, auxiliando decisões de:

- Novas operações.
- Saídas de posições.
- Substituição de contrapartes.

---

## 6. RARoC e Precificação

### 6.1 Fórmula geral

$$
RARoC_A = \frac{\text{Spread}_A - EL_A - \text{Custo de funding}_A - \text{Custo operacional}_A}{\widehat{RC}_A}
$$

### 6.2 Decisão de preço mínimo

O spread mínimo para cobrir todos os custos e o capital é:

$$
\text{Spread}_{\min} = EL_A + \text{Custos}_A + h \cdot \widehat{RC}_A
$$

onde $h$ é o hurdle rate (custo de capital).

### 6.3 Comparação entre ratings

O RARoC permite comparar negócios de diferentes qualidades de crédito numa base comum de eficiência de capital.

---

## 7. Gestão de Portfólio de Varejo

O notebook `11_safras_pf_brasil_creditriskplus.ipynb` aplica o CreditRisk+ a uma carteira PF sintética de cartão e crédito parcelado. O estoque inicial contém 180 meses de safras históricas e uma cauda agregada de cartões antigos; depois de 12 meses de burn-in, 24 novas safras são reportadas e todas permanecem em observação até MOB 60. Um gate de convergência controla nível, mix, EL/EAD e distribuição por MOB antes da análise. Em cada um dos 24 fechamentos reportados, a distribuição é calculada com pools homogêneos e multiplicidades exatas, sem converter EAD em contagem de defaults.

O cenário inclui seasoning, amortização ou utilização, originação, saídas, choque macroeconômico e mudanças de underwriting. Esses mecanismos geram os inputs do modelo; não são hipóteses originais do CreditRisk+. EL, VaR discreto e capital econômico são calculados pela implementação canônica e a massa truncada é controlada explicitamente.

Os parâmetros são ilustrativos e precisam ser recalibrados e validados com dados observados antes de uso bancário.

Ver [Implementação Python](09-Implementacao-Python) para mais detalhes.

---

## 8. Resumo

| Aplicação | Uso |
|-----------|-----|
| ACP | Cobertura contábil da perda esperada |
| ICR | Buffer para variações em torno da ACP |
| Limites de crédito | Alocação eficiente de apetite de risco |
| Stress testing | Avaliação de cenários adversos |
| Otimização | Redução de concentração e fronteira eficiente |
| RARoC | Precificação e comparação de eficiência de capital |
