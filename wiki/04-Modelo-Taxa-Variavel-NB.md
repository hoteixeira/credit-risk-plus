# Modelo de Taxa Variável: Distribuição Binomial Negativa

A versão completa do Credit Risk+ trata as taxas de default como **variáveis aleatórias**. A modelagem da incerteza nas taxas de default é a inovação central do framework, pois permite reproduzir a volatilidade observada dos defaults e introduzir correlações implícitas entre contrapartes.

Este capítulo cobre as Seções A6 a A11 do Apêndice A do paper oficial.

---

## 1. Motivação: Defaults Não São Poisson

Dados históricos mostram que a variância do número anual de defaults é muito maior do que a média — algo que um modelo Poisson puro não consegue explicar. A explicação é que as **taxas de default são voláteis no tempo**, afetadas por fatores sistêmicos como:

- Condições macroeconômicas.
- Condições setoriais.
- Ciclos de crédito.

O Credit Risk+ modela essa volatilidade assumindo que as taxas médias de default seguem uma **distribuição Gama**.

---

## 2. Mistura Poisson-Gama

### 2.1 Modelo condicional

Condicional a uma taxa média de default $x_k$ para um setor $k$, o número de defaults no setor segue uma distribuição de Poisson:

$$
F_k(z \mid x_k = x) = e^{x(z-1)}
$$

### 2.2 Distribuição Gama para a taxa de default

A variável $x_k$ é modelada como Gama com parâmetros de forma $\alpha_k$ e escala $\beta_k$:

$$
f_k(x) = \frac{1}{\beta_k^{\alpha_k} \Gamma(\alpha_k)} e^{-x/\beta_k} x^{\alpha_k - 1}, \qquad x > 0
$$

com:

$$
\mu_k = \mathbb{E}[x_k] = \alpha_k \beta_k
$$

$$
\sigma_k^2 = \mathrm{Var}(x_k) = \alpha_k \beta_k^2
$$

Invertendo:

$$
\alpha_k = \frac{\mu_k^2}{\sigma_k^2}, \qquad \beta_k = \frac{\sigma_k^2}{\mu_k}
$$

### 2.3 PGF incondicional

A PGF incondicional é obtida integrando sobre $x_k$:

$$
F_k(z) = \int_0^{\infty} e^{x(z-1)} f_k(x) \, dx
$$

Substituindo a densidade Gama:

$$
F_k(z) = \frac{1}{\beta_k^{\alpha_k} \Gamma(\alpha_k)} \int_0^{\infty} e^{x(z-1)} e^{-x/\beta_k} x^{\alpha_k - 1} \, dx
$$

Agrupando os termos exponenciais:

$$
F_k(z) = \frac{1}{\beta_k^{\alpha_k} \Gamma(\alpha_k)} \int_0^{\infty} e^{-x(1/\beta_k + 1 - z)} x^{\alpha_k - 1} \, dx
$$

Fazendo a mudança de variável $y = x(1/\beta_k + 1 - z)$, obtemos:

$$
F_k(z) = \left( \frac{1/\beta_k}{1/\beta_k + 1 - z} \right)^{\alpha_k} = \left( \frac{1}{1 + \beta_k(1 - z)} \right)^{\alpha_k}
$$

Definindo:

$$
p_k = \frac{\beta_k}{1 + \beta_k}
$$

obtemos a forma canônica:

$$
\boxed{
F_k(z) = \left( \frac{1 - p_k}{1 - p_k z} \right)^{\alpha_k}
}
$$

### 2.4 Distribuição binomial negativa

Expandindo a PGF:

$$
F_k(z) = (1 - p_k)^{\alpha_k} \sum_{n=0}^{\infty} \binom{n + \alpha_k - 1}{n} p_k^n z^n
$$

Logo, a probabilidade de $n$ defaults no setor $k$ é:

$$
\boxed{
\mathbb{P}(n \text{ defaults}) = (1 - p_k)^{\alpha_k} \binom{n + \alpha_k - 1}{n} p_k^n
}
$$

que é a distribuição **binomial negativa** (Negative Binomial, NB) com parâmetros $\alpha_k$ e $p_k$.

### 2.5 Propriedades da NB

- Média: $\mathbb{E}[N_k] = \alpha_k \frac{p_k}{1 - p_k} = \mu_k$
- Variância: $\mathrm{Var}(N_k) = \alpha_k \frac{p_k}{(1 - p_k)^2} = \mu_k + \sigma_k^2$

A variância é maior que a média, refletindo a incerteza adicional da taxa de default.

---

## 3. PGF das Perdas com Taxas Variáveis

### 3.1 Composição com severidade

Agora compomos a PGF de defaults com o polinômio de severidade do setor, analogamente ao caso Poisson:

$$
G_k(z) = F_k(P_k(z)) = \left( \frac{1 - p_k}{1 - p_k P_k(z)} \right)^{\alpha_k}
$$

onde:

$$
P_k(z) = \frac{1}{\mu_k} \sum_{A \in S_k} \frac{\varepsilon_A}{\nu_A} z^{\nu_A}
$$

### 3.2 PGF do portfólio multi-setor

Como os fatores Gama de setores distintos são independentes, a PGF total é o produto das PGFs setoriais:

$$
\boxed{
G(z) = \prod_{k=1}^{K} G_k(z) = \prod_{k=1}^{K} \left( \frac{1 - p_k}{1 - p_k P_k(z)} \right)^{\alpha_k}
}
$$

### 3.3 Interpretação econômica

O fator Gama subjacente a cada setor é **compartilhado** por todas as contrapartes daquele setor. Quando o fator está alto (recessão), todas as contrapartes têm PDs elevadas simultaneamente — gerando correlação implícita entre defaults.

---

## 4. Recursão Geral para a PMF

### 4.1 Derivada logarítmica racional

Seja uma função com expansão em série:

$$
G(z) = \sum_{n=0}^{\infty} A_n z^n
$$

cuja derivada logarítmica é uma função racional:

$$
\frac{d}{dz} \log G(z) = \frac{G'(z)}{G(z)} = \frac{A(z)}{B(z)}
$$

onde $A(z)$ e $B(z)$ são polinômios:

$$
A(z) = a_0 + a_1 z + \dots + a_r z^r
$$

$$
B(z) = b_0 + b_1 z + \dots + b_s z^s
$$

### 4.2 Fórmula geral de recorrência

Rearranjando:

$$
B(z) G'(z) = A(z) G(z)
$$

Substituindo as séries e igualando coeficientes de $z^n$, obtemos:

$$
\boxed{
A_{n+1} = \frac{1}{b_0 (n+1)} \left[ \sum_{i=0}^{\min(r,n)} a_i A_{n-i} - \sum_{j=0}^{\min(s-1,n-1)} b_{j+1}(n-j) A_{n-j} \right]
}
$$

### 4.3 Aplicação ao caso de um setor

Para um único setor, a derivada logarítmica de:

$$
G(z) = \left( \frac{1 - p}{1 - p P(z)} \right)^{\alpha}
$$

é:

$$
\frac{G'(z)}{G(z)} = \frac{p \alpha \sum_j \frac{\varepsilon_j}{\nu_j} z^{\nu_j - 1}}{1 - \frac{p}{\mu} \sum_j \frac{\varepsilon_j}{\nu_j} z^{\nu_j}}
$$

### 4.4 Recursão NB

Aplicando a fórmula geral, obtemos a recursão do Credit Risk+ para taxas variáveis:

$$
\boxed{
A_n = \frac{p}{n \mu} \sum_{j: \nu_j \le n} \varepsilon_j \left( \alpha - 1 + \frac{n}{\nu_j} \right) A_{n - \nu_j}
}
$$

com condição inicial:

$$
\boxed{
A_0 = (1 - p)^{\alpha}
}
$$

### 4.5 Caso especial $\nu_j = 1$

Quando todas as exposições são menores que $L$ (portfólios de varejo), temos $\nu_j = 1$ para todas as bandas. A recursão simplifica para:

$$
\boxed{
A_n = \frac{p}{n \mu} \left( \alpha - 1 + n \right) \sum_j \varepsilon_j A_{n-1}
}
$$

Como $\sum_j \varepsilon_j = \mu$ quando $\nu_j = 1$:

$$
A_n = p \frac{\alpha - 1 + n}{n} A_{n-1}
$$

Essa forma escalar é computacionalmente muito eficiente.

---

## 5. Convergência para o Caso Poisson

O modelo com taxas variáveis converge para o caso de taxas fixas quando a volatilidade tende a zero.

### 5.1 Limite $\sigma_k \to 0$

Quando $\sigma_k \to 0$:

- $\beta_k = \sigma_k^2 / \mu_k \to 0$
- $p_k = \beta_k / (1 + \beta_k) \to 0$
- $\alpha_k = \mu_k^2 / \sigma_k^2 \to \infty$
- $\alpha_k p_k = \dfrac{\mu_k}{1 + \beta_k} \to \mu_k$

O último item é um **limite**, não uma identidade: para $\beta_k > 0$ o produto vale $\mu_k/(1+\beta_k)$, estritamente menor que $\mu_k$. Ele só converge para $\mu_k$ quando $\beta_k \to 0$.

Essa distinção tem consequência numérica direta. O produto $\alpha_k p_k$ é da forma $\infty \times 0$, e calculá-lo literalmente perde precisão justamente no regime de baixa volatilidade. Por isso a implementação nunca forma esse produto: ela usa as identidades algébricas exatas

$$
\frac{\alpha_k p_k}{\mu_k} = \frac{1}{1 + \beta_k}, \qquad \frac{p_k}{\mu_k} = \frac{\beta_k}{\mu_k (1 + \beta_k)},
$$

que são estáveis em toda a faixa de $\beta_k$ e degeneram suavemente no caso Poisson.

### 5.2 Limite da PGF

Usando $(1 - p_k)^{\alpha_k} \to e^{-\mu_k}$ e $(1 - p_k z)^{-\alpha_k} \to e^{\mu_k z}$:

$$
\left( \frac{1 - p_k}{1 - p_k z} \right)^{\alpha_k} \to e^{\mu_k(z-1)}
$$

Portanto:

$$
G_k(z) \to e^{\mu_k(P_k(z) - 1)}
$$

que é a PGF do caso Poisson.

### 5.3 Limite da recursão

Na recursão NB:

$$
A_n = \frac{p}{n \mu} \sum_j \varepsilon_j \left( \alpha - 1 + \frac{n}{\nu_j} \right) A_{n - \nu_j}
$$

quando $\alpha \to \infty$ e $p \to 0$ com $\alpha p \to \mu$, o termo dominante é $\alpha$:

$$
A_n \to \frac{1}{n \mu} \sum_j \varepsilon_j \, \mu \, A_{n - \nu_j} = \frac{1}{n} \sum_j \varepsilon_j A_{n - \nu_j}
$$

recuperando a recursão Poisson.

---

## 6. Implementação Python

A recursão NB geral é implementada em `creditriskplus.simple_model._sector_distribution`:

```python
alpha_k = mu_k ** 2 / sigma_k ** 2
beta_k  = sigma_k ** 2 / mu_k
p_k     = beta_k / (1.0 + beta_k)

A[0] = (1.0 - p_k) ** alpha_k
for n in range(1, max_n + 1):
    s_val = 0.0
    for vj, ej in zip(bands, epsilons):
        if vj <= n:
            s_val += ej * (alpha_k - 1.0 + n / vj) * A[n - vj]
    A[n] = (p_k / (n * mu_k)) * s_val
```

A função `calculate_loss_distribution` combina vários setores por convolução.

---

## 7. Resumo

| Conceito | Fórmula |
|----------|---------|
| Taxa de default estocástica | $x_k \sim \Gamma(\alpha_k, \beta_k)$ |
| Parâmetros Gama | $\alpha_k = \mu_k^2 / \sigma_k^2$, $\beta_k = \sigma_k^2 / \mu_k$ |
| Parâmetro NB | $p_k = \beta_k / (1 + \beta_k)$ |
| PGF de defaults | $F_k(z) = \left( \frac{1-p_k}{1-p_k z} \right)^{\alpha_k}$ |
| PGF de perdas (um setor) | $G_k(z) = \left( \frac{1-p_k}{1-p_k P_k(z)} \right)^{\alpha_k}$ |
| PGF de perdas (multi-setor) | $G(z) = \prod_k G_k(z)$ |
| PMF NB | $\mathbb{P}(n) = (1-p_k)^{\alpha_k} \binom{n+\alpha_k-1}{n} p_k^n$ |
| Recursão NB | $A_n = \frac{p}{n\mu} \sum_j \varepsilon_j (\alpha - 1 + n/\nu_j) A_{n-\nu_j}$ |
| Condição inicial | $A_0 = (1-p)^{\alpha}$ |
| Limite Poisson | Quando $\sigma_k \to 0$ |
