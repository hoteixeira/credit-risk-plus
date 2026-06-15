# Extensão Multi-Ano

O Credit Risk+ pode ser estendido para horizontes de mais de um ano, o que é relevante para carteiras **hold-to-maturity** ou para análise de capital econômico em horizontes regulatórios mais longos. A extensão é discutida na Seção A5 do Apêndice A do paper oficial.

---

## 1. Motivação

Muitas exposições de crédito têm maturidades superiores a um ano. Para essas operações, o risco de default ao longo da vida total do instrumento pode ser relevante. O modelo multi-ano permite:

- Incorporar variação de exposição ao longo do tempo (amortização).
- Usar taxas de default marginais condicionais por ano.
- Calcular a distribuição acumulada de perdas em horizontes de $T$ anos.

---

## 2. Contrapartes Virtuais

A ideia central é transformar cada contraparte real em $T$ **contrapartes virtuais**, uma para cada ano $t = 1, \dots, T$:

| Característica | Ano $t$ |
|----------------|---------|
| Exposição | $E_A^{(t)}$ |
| Banda | $\nu_A^{(t)} = \lceil E_A^{(t)} / L \rceil$ |
| PD marginal condicional | $p_A^{(t)}$ |
| Perda esperada | $\varepsilon_A^{(t)} = p_A^{(t)} E_A^{(t)} / L$ |

Cada par $(A, t)$ é tratado como uma exposição independente no mesmo esquema de bandas do modelo de um ano.

---

## 3. Taxas Marginais Condicionais

### 3.1 Sobrevivência acumulada

Seja $S_A^{(t)}$ a probabilidade de que a contraparte $A$ **não** tenha dado default até o ano $t$:

$$
S_A^{(0)} = 1
$$

A sobrevivência acumulada evolui como:

$$
S_A^{(t)} = S_A^{(t-1)} \bigl(1 - p_A^{(t)}\bigr)
$$

### 3.2 Definição da taxa marginal

A taxa de default marginal condicional é:

$$
\boxed{
p_A^{(t)} = \mathbb{P}(\text{default no ano } t \mid \text{sobreviveu até } t-1) = 1 - \frac{S_A^{(t)}}{S_A^{(t-1)}}
}
$$

### 3.3 Estrutura a termo a partir de ratings

As probabilidades de sobrevivência acumulada podem ser derivadas de uma **matriz de transição de ratings** elevada à potência $t$:

$$
S_A^{(t)} = 1 - \bigl(M^t\bigr)_{R_A, \text{default}}
$$

onde $M$ é a matriz de transição anual e $R_A$ é o rating atual da contraparte $A$.

### 3.4 Interpretação econômica

As taxas marginais condicionais capturam o fato de que:

- Uma contraparte só pode dar default no ano $t$ se sobreviveu até $t-1$.
- Ratings piores tendem a taxas marginais decrescentes ao longo do tempo (efeito de seleção: os piores defaultam cedo).
- Ratings melhores podem ter taxas marginais crescentes inicialmente devido a downgrades.

---

## 4. PGF Multi-Ano

### 4.1 PGF de uma contraparte real

Para uma única contraparte $j$ ao longo de $T$ anos, a PGF das perdas é:

$$
G_j(z) = 1 - \sum_{t=1}^{T} p_j^{(t)} + \sum_{t=1}^{T} p_j^{(t)} z^{\nu_j^{(t)}} = 1 + \sum_{t=1}^{T} p_j^{(t)}\bigl(z^{\nu_j^{(t)}} - 1\bigr)
$$

### 4.2 Aproximação para probabilidades pequenas

Para $p_j^{(t)} \ll 1$:

$$
\log G_j(z) \approx \sum_{t=1}^{T} p_j^{(t)}\bigl(z^{\nu_j^{(t)}} - 1\bigr) = \sum_{t=1}^{T} \frac{\varepsilon_j^{(t)}}{\nu_j^{(t)}}\bigl(z^{\nu_j^{(t)}} - 1\bigr)
$$

### 4.3 PGF do portfólio

Agrupando por tamanho de exposição:

$$
\log G(z) = \sum_{j,t} \frac{\varepsilon_j^{(t)}}{\nu_j^{(t)}}\bigl(z^{\nu_j^{(t)}} - 1\bigr)
$$

Esta é exatamente a mesma forma funcional do modelo de um ano. Portanto, toda a teoria (Poisson, NB, recursões, setores) continua válida, desde que cada $(j, t)$ seja tratado como uma contraparte virtual.

---

## 5. Exemplo 1C: 25 Contrapartes em 3 Anos

O paper apresenta o Exemplo 1C, em que um portfólio de 25 contrapartes é analisado ao longo de 3 anos:

- Ano 1: todas as 25 contrapartes têm exposição.
- Ano 2: 10 contrapartes ainda têm exposição.
- Ano 3: 5 contrapartes ainda têm exposição.

Total de contrapartes virtuais: $25 + 10 + 5 = 40$.

A aplicação do modelo Credit Risk+ a essas 40 exposições virtuais produz:

| Métrica | Valor |
|---------|------:|
| E[Loss] | \$17.277.632 |
| VaR(99%) | \$62.100.307 |

---

## 6. Considerações Práticas

### 6.1 Correspondência com ratings

As taxas marginais condicionais dependem do rating da contraparte em cada ano. No modelo simples, assume-se que o rating permanece constante (a menos que ocorra default). Modelos mais sofisticados incorporam migração de ratings via cadeias de Markov.

### 6.2 Exposições variáveis

A exposição $E_A^{(t)}$ deve refletir:

- Amortizações contratuais.
- Pagamentos de principal.
- Novos desembolsos.
- Reembolsos antecipados.

### 6.3 Taxas de recuperação

A taxa de recuperação pode variar ao longo do tempo ou ser constante. Na prática, usa-se uma recuperação média esperada para cada tipo de instrumento.

### 6.4 Volatilidades

As volatilidades das taxas marginais podem ser escalonadas a partir das volatilidades anuais. O paper propõe relações proporcionais, embora a estimação detalhada dependa de dados históricos.

---

## 7. Implementação Python

O módulo `creditriskplus.data` contém a tabela multi-ano `MULTI_YEAR_RATING_TABLE`, que fornece as taxas médias e volatilidades marginais por rating e ano:

```python
{
    'A': {
        'year_1': {'mean': 0.015, 'std': 0.0075},
        'year_2': {'mean': 0.025, 'std': 0.0125},
        'year_3': {'mean': 0.035, 'std': 0.0175},
    },
    ...
}
```

O notebook `06_exemplo_1C_multi_ano.ipynb` demonstra a construção das contrapartes virtuais e a aplicação do `calculate_loss_distribution`.

---

## 8. Resumo

| Conceito | Fórmula |
|----------|---------|
| Sobrevivência acumulada | $S_A^{(t)} = S_A^{(t-1)}(1 - p_A^{(t)})$ |
| Taxa marginal condicional | $p_A^{(t)} = 1 - S_A^{(t)}/S_A^{(t-1)}$ |
| PGF multi-ano | $\log G(z) = \sum_{j,t} \frac{\varepsilon_j^{(t)}}{\nu_j^{(t)}}(z^{\nu_j^{(t)}} - 1)$ |
| Contrapartes virtuais | Cada $(A, t)$ tratado como exposição independente |
| Forma funcional | Idêntica ao modelo de um ano |
