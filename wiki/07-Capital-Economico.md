# Capital Econômico e Contribuições de Risco

Uma vez obtida a distribuição completa de perdas pelo Credit Risk+, derivam-se as métricas de capital. Este capítulo cobre as Seções 4 do documento principal e A13 do Apêndice A.

---

## 1. A Distribuição Completa de Perdas

O output do modelo é a **função de massa de probabilidade (PMF)**:

$$
A_n = \mathbb{P}(\text{perda total} = n \cdot L)
$$

onde $L$ é a unidade de perda.

Da PMF obtemos todas as métricas de interesse.

### 1.1 Função de distribuição acumulada (CDF)

$$
\text{CDF}[n] = \sum_{k=0}^{n} A_k = \mathbb{P}(\text{perda total} \le n \cdot L)
$$

### 1.2 Perda esperada (EL)

$$
\boxed{
EL = \mathbb{E}[\text{Loss}] = \sum_{n=0}^{\infty} n \cdot L \cdot A_n
}
$$

A perda esperada é o valor médio da distribuição de perdas.

### 1.3 Desvio-padrão das perdas

$$
\sigma_{\text{loss}} = \sqrt{\sum_{n=0}^{\infty} (nL - EL)^2 A_n}
$$

---

## 2. Value at Risk (VaR)

O VaR no nível de confiança $q$ é o percentil $q$ da distribuição de perdas:

$$
\boxed{
\text{VaR}(q) = \min\{ n \cdot L : \text{CDF}[n] \ge q \}
}
$$

Tipicamente usa-se $q = 99\%$ como padrão no Credit Risk+, embora instituições mais conservadoras (com target de rating AA) usem $q = 99,9\%$ ou $q = 99,97\%$.

### 2.1 Por que 99%?

O paper recomenda o percentil 99% como padrão para capital econômico de crédito com horizonte de 1 ano. A lógica é:

- Cobre perdas inesperadas na grande maioria dos anos.
- Permite que o banco suporte 1 "mau ano" em 100 sem insolvência.
- Oferece um nível de confiança explícito para comunicação com reguladores e investidores.

### 2.2 Interpolação do VaR

Na implementação computacional, o VaR pode ser interpolado entre os pontos da grade $n \cdot L$:

```python
idx = np.searchsorted(cdf, q)
p_lo, p_hi = cdf[idx - 1], cdf[idx]
frac = (q - p_lo) / (p_hi - p_lo)
var = (idx - 1 + frac) * L
```

---

## 3. Capital Econômico

O **Capital Econômico** (EC) é a diferença entre o VaR e a perda esperada:

$$
\boxed{
EC(q) = \text{VaR}(q) - EL
}
$$

Representa o capital necessário para cobrir **perdas inesperadas** — aquelas que excedem a média histórica.

### 3.1 As três regiões da distribuição

```
 Perda
 ─────────────────────────────────────────────────────►
 │◄── Cobertura por ──►│◄── Capital Econômico ──►│ Cenários
 │  pricing/provision │   (EC = VaR - EL)        │  extremos
 0                   EL                       VaR(99%)
```

| Região | Cobertura |
|--------|-----------|
| Até EL | Pricing, provisões (ACP) |
| EL até VaR(99%) | Capital econômico / ICR |
| Acima de VaR(99%) | Análise de cenários, limites de concentração |

---

## 4. Contribuições de Risco

### 4.1 Definição

A **contribuição de risco** (Risk Contribution, RC) de uma contraparte $A$ é o efeito marginal de $A$ sobre uma métrica de risco do portfólio. O paper propõe uma decomposição aditiva baseada no desvio-padrão e no VaR.

### 4.2 Contribuição ao desvio-padrão

A contribuição ao desvio-padrão é definida como:

$$
RC_A^{\sigma} = E_A \frac{\partial \sigma}{\partial E_A} = \frac{E_A}{2\sigma} \frac{\partial \sigma^2}{\partial E_A}
$$

### 4.3 Variância total da perda

A variância total das perdas pode ser decomposta como:

$$
\sigma^2 = \sum_{k=1}^{K} \varepsilon_k^2 \left( \frac{\sigma_k}{\mu_k} \right)^2 + \sum_A \varepsilon_A \nu_A
$$

### 4.4 Fórmula final de risk contribution

Derivando a expressão da variância e usando $\varepsilon_A = \mu_A \nu_A$, obtemos:

$$
\boxed{
RC_A = \frac{\varepsilon_A}{\sigma} \left[ \sum_{k=1}^{K} \left( \frac{\sigma_k}{\mu_k} \right)^2 \varepsilon_k \theta_{Ak} + \nu_A \right]
}
$$

### 4.5 Propriedade de aditividade

As contribuições ao desvio-padrão somam-se exatamente ao desvio-padrão total:

$$
\sum_A RC_A = \sigma
$$

### 4.6 Contribuição ao VaR

Para obter contribuições aditivas ao VaR, define-se o multiplicador:

$$
\xi = \frac{\text{VaR} - EL}{\sigma}
$$

e aproxima-se:

$$
\boxed{
\widehat{RC}_A = EL_A + \xi \cdot RC_A
}
$$

onde $EL_A = p_A E_A^{\text{net}}$ é a perda esperada da contraparte $A$.

### 4.7 Propriedade de aditividade ao VaR

$$
\boxed{
\sum_A \widehat{RC}_A = \text{VaR}
}
$$

Essa propriedade é fundamental para a gestão de portfólio: permite alocar o capital total de forma aditiva entre contrapartes, setores, ratings ou unidades de negócio.

---

## 5. Aplicações das Contribuições de Risco

### 5.1 Identificação de concentrações

Ordenar as contrapartes por $\widehat{RC}_A$ revela quais concentram mais capital. Frequentemente, poucas contrapartes são responsáveis pela maior parte do capital econômico.

### 5.2 Gestão ativa de portfólio

A relação entre $EL_A$ e $\widehat{RC}_A$ permite identificar operações que:

- Adicionam muito capital por pouca receita (ineficientes).
- São diversificadoras (baixa RC relativa ao EL).
- São concentradoras (alta RC relativa ao EL).

### 5.3 Limites de crédito baseados em risco

O capital pode ser alocado por contraparte de forma igualitária:

$$
\text{Limite}_A \propto \frac{1}{p_A (1 - RR_A)}
$$

Contrapartes de pior rating recebem limites menores, alinhando apetite de risco com qualidade de crédito.

---

## 6. RARoC — Retorno Ajustado ao Risco sobre Capital

O RARoC permite comparar exposições de diferentes ratings, maturidades e tamanhos numa métrica única:

$$
\boxed{
RARoC_A = \frac{\text{Receita de spread}_A - EL_A - \text{Custo de funding}_A - \text{Custo operacional}_A}{\widehat{RC}_A}
}
$$

Contrapartes com RARoC abaixo do custo de capital (hurdle rate) destroem valor para os acionistas.

---

## 7. Implementação Python

As métricas de capital são calculadas a partir da PMF retornada por `calculate_loss_distribution`:

```python
pmf, el = calculate_loss_distribution(...)
loss_values = np.arange(len(pmf)) * unit_size
cdf = np.cumsum(pmf)

# VaR 99%
idx_99 = np.searchsorted(cdf, 0.99)
var_99 = idx_99 * unit_size

# Capital econômico
ec_99 = var_99 - el
```

As contribuições de risco são implementadas no notebook `09_aplicacoes.ipynb`.

---

## 8. Resumo

| Métrica | Fórmula |
|---------|---------|
| Perda esperada | $EL = \sum_n nL A_n$ |
| VaR | $\min\{nL : \text{CDF}[n] \ge q\}$ |
| Capital econômico | $EC = \text{VaR} - EL$ |
| Contribuição ao desvio-padrão | $RC_A = \frac{\varepsilon_A}{\sigma}\left[\sum_k (\sigma_k/\mu_k)^2 \varepsilon_k \theta_{Ak} + \nu_A\right]$ |
| Contribuição ao VaR | $\widehat{RC}_A = EL_A + \xi \cdot RC_A$ |
| RARoC | $(\text{Spread} - EL - \text{Custos}) / \widehat{RC}_A$ |
