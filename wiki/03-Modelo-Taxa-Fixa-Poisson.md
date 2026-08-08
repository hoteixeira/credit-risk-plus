# Modelo de Taxa Fixa: Distribuição de Poisson

Este capítulo desenvolve a versão mais simples do Credit Risk+, em que as taxas de default são tratadas como **determinísticas**. Este é o caso discutido nas Seções A2 a A5 do Apêndice A do paper oficial.

A derivação segue duas etapas:

1. **Estágio 1**: distribuição do **número de defaults**.
2. **Estágio 2**: distribuição das **perdas monetárias**.

---

## 1. Estágio 1: Número de Defaults

### 1.1 Notação

Considere uma carteira com $N$ contrapartes. Para cada contraparte $A$:

$$
p_A = \text{probabilidade anual de default de } A
$$

Definimos a **probability generating function (PGF)** para o número total de defaults:

$$
F(z) = \sum_{n=0}^{\infty} \mathbb{P}(n \text{ defaults}) \, z^n
$$

### 1.2 PGF individual

Para uma única contraparte, o número de defaults em um ano é uma variável Bernoulli:

$$
F_A(z) = (1 - p_A) + p_A z = 1 + p_A(z - 1)
$$

### 1.3 PGF do portfólio

Como os defaults são independentes (sob taxas fixas), a PGF do portfólio é o produto das PGFs individuais:

$$
F(z) = \prod_A F_A(z) = \prod_A \bigl[1 + p_A(z - 1)\bigr]
$$

Tomando logaritmos:

$$
\log F(z) = \sum_A \log\bigl[1 + p_A(z - 1)\bigr]
$$

### 1.4 Aproximação para probabilidades pequenas

Em carteiras de crédito, $p_A \ll 1$ para todas as contrapartes. Usando $\log(1 + x) \approx x$ para $x$ pequeno:

$$
\log\bigl[1 + p_A(z - 1)\bigr] \approx p_A(z - 1)
$$

Portanto:

$$
\log F(z) \approx \sum_A p_A(z - 1) = \mu(z - 1)
$$

donde:

$$
\mu = \sum_A p_A
$$

é o **número esperado de defaults** do portfólio.

Logo:

$$
F(z) \approx e^{\mu(z - 1)} = e^{-\mu} e^{\mu z}
$$

Expandindo em série de Taylor:

$$
F(z) = e^{-\mu} \sum_{n=0}^{\infty} \frac{\mu^n}{n!} z^n
$$

### 1.5 Distribuição de Poisson

Igualando coeficientes de $z^n$, obtemos:

$$
\boxed{
\mathbb{P}(n \text{ defaults}) = \frac{e^{-\mu} \mu^n}{n!}
}
$$

que é a clássica distribuição de Poisson com parâmetro $\mu$.

### 1.6 Propriedades e limitação

A distribuição de Poisson tem:

- Média: $\mathbb{E}[N] = \mu$
- Variância: $\mathrm{Var}(N) = \mu$

A limitação fundamental é que a variância igual à média é inconsistente com dados históricos: a volatilidade observada do número de defaults é tipicamente muito maior que $\sqrt{\mu}$. Essa discrepância motiva a introdução de taxas de default estocásticas, tratada em [Modelo de Taxa Variável: Binomial Negativa](04-Modelo-Taxa-Variavel-NB).

---

## 2. Estágio 2: Distribuição de Perdas

### 2.1 O problema

A mesma perda agregada pode surgir de:

- Um único default de grande exposição.
- Vários defaults de pequenas exposições.

Portanto, a distribuição das perdas monetárias não é Poisson. O Credit Risk+ resolve isso através do **exposure banding** e da composição da PGF de frequência com a PGF de severidade.

### 2.2 Exposure banding

As exposições líquidas são agrupadas em bandas de tamanho $L$:

$$
L = \left\lceil \frac{\max_A E_A^{\text{net}}}{100} \right\rceil, \qquad
\nu_A = \left\lceil \frac{E_A^{\text{net}}}{L} \right\rceil
$$

A exposição da contraparte $A$ é aproximada por $L \nu_A$, e a perda esperada em unidades de $L$ é:

$$
\varepsilon_A = \frac{p_A E_A^{\text{net}}}{L}
$$

Agrupando todas as contrapartes na mesma banda $j$ (com exposição comum $\nu_j$):

$$
\varepsilon_j = \sum_{A: \nu_A = \nu_j} \varepsilon_A
$$

### 2.3 PGF das perdas

Definimos a PGF das perdas agregadas:

$$
G(z) = \sum_{n=0}^{\infty} \mathbb{P}(\text{perda agregada} = nL) \, z^n
$$

Cada banda $j$ comporta-se como um processo Poisson em que cada evento produz uma perda de $\nu_j$ unidades:

$$
G_j(z) = \sum_{n=0}^{\infty} \frac{e^{-\mu_j} \mu_j^n}{n!} z^{n \nu_j} = e^{-\mu_j + \mu_j z^{\nu_j}}
$$

onde

$$
\mu_j = \frac{\varepsilon_j}{\nu_j}
$$

Como as bandas são independentes:

$$
G(z) = \prod_j G_j(z) = \exp\!\left[ -\sum_j \mu_j + \sum_j \mu_j z^{\nu_j} \right]
$$

Definindo:

$$
\mu = \sum_j \mu_j = \sum_j \frac{\varepsilon_j}{\nu_j}
$$

e o **polinômio de severidade**:

$$
P(z) = \frac{\sum_j \mu_j z^{\nu_j}}{\mu} = \frac{\sum_j (\varepsilon_j / \nu_j) z^{\nu_j}}{\sum_j (\varepsilon_j / \nu_j)}
$$

obtemos a forma compacta:

$$
\boxed{
G(z) = e^{\mu(P(z) - 1)} = F(P(z))
}
$$

Essa equação expressa matematicamente a composição de duas fontes de aleatoriedade:

1. **Frequência**: o número de defaults segue Poisson ($F$).
2. **Severidade**: cada default tem magnitude determinada por $P(z)$.

### 2.4 PGF em termos de obrigadores

Equivalentemente, podemos escrever:

$$
P(z) = \frac{1}{\mu} \sum_A \frac{\varepsilon_A}{\nu_A} z^{\nu_A}
$$

com:

$$
\mu = \sum_A \frac{\varepsilon_A}{\nu_A} = \sum_A p_A
$$

pois $\varepsilon_A / \nu_A = p_A E_A^{\text{net}} / (L \nu_A) \approx p_A$ quando o arredondamento para bandas é pequeno.

---

## 3. Recursão para a PMF das Perdas

### 3.1 Definição dos coeficientes

Seja $A_n = \mathbb{P}(\text{perda agregada} = nL)$. Por definição:

$$
G(z) = \sum_{n=0}^{\infty} A_n z^n
$$

### 3.2 Diferenciação logarítmica

Temos:

$$
\log G(z) = \sum_j \mu_j (z^{\nu_j} - 1)
$$

Derivando:

$$
\frac{G'(z)}{G(z)} = \sum_j \mu_j \nu_j z^{\nu_j - 1} = \sum_j \frac{\varepsilon_j}{\nu_j} \nu_j z^{\nu_j - 1} = \sum_j \varepsilon_j z^{\nu_j - 1}
$$

Portanto:

$$
z G'(z) = G(z) \sum_j \varepsilon_j z^{\nu_j}
$$

Substituindo as séries:

$$
z G'(z) = \sum_{n=1}^{\infty} n A_n z^n
$$

$$
G(z) \sum_j \varepsilon_j z^{\nu_j} = \sum_{n=0}^{\infty} A_n z^n \sum_j \varepsilon_j z^{\nu_j} = \sum_{n=0}^{\infty} \left( \sum_{j: \nu_j \le n} \varepsilon_j A_{n - \nu_j} \right) z^n
$$

Igualando coeficientes de $z^n$ para $n \ge 1$:

$$
n A_n = \sum_{j: \nu_j \le n} \varepsilon_j A_{n - \nu_j}
$$

### 3.3 Fórmula de recorrência

$$
\boxed{
A_n = \frac{1}{n} \sum_{j: \nu_j \le n} \varepsilon_j A_{n - \nu_j}
}
$$

com condição inicial:

$$
\boxed{
A_0 = G(0) = e^{-\mu} = \exp\!\left( -\sum_j \frac{\varepsilon_j}{\nu_j} \right)
}
$$

### 3.4 Caso especial: $\nu_j = 1$ para todas as bandas

Quando todas as exposições são muito menores que $L$ (por exemplo, portfólios de varejo com $L = \$1.000.000$ e exposições médias de $\$50.000$), temos $\nu_A = 1$ para todas as contrapartes. A recursão simplifica para:

$$
A_n = \frac{\varepsilon}{n} A_{n-1}
$$

onde $\varepsilon = \sum_A \varepsilon_A$. Isso equivale a uma distribuição Poisson com severidade unitária:

$$
A_n = \frac{e^{-\varepsilon} \varepsilon^n}{n!}
$$

---

## 4. Erro da Bandagem de Exposições

### 4.1 Perda esperada preservada

A bandagem substitui a exposição real $E_A^{\text{net}}$ por $L \nu_A$, onde $\nu_A = \lceil E_A^{\text{net}}/L \rceil$. A perda esperada total em unidades de $L$ é:

$$
\hat{\varepsilon} = \sum_A p_A \nu_A
$$

Como $\nu_A - 1 < E_A^{\text{net}}/L \le \nu_A$, o erro relativo na perda esperada é limitado por $L / E_A^{\text{net}}$ para cada contraparte. Para carteiras com muitas exposições pequenas, o erro agregado é pequeno.

### 4.2 Desvio-padrão superestimado

Sejam:

$$
\varepsilon = \sum_j \varepsilon_j, \qquad \sigma^2 = \sum_j \nu_j \varepsilon_j
$$

os momentos exatos (sem bandagem) e $\hat{\sigma}^2 = \sum_j \hat{\nu}_j \varepsilon_j$ os momentos com bandagem. Como $\nu_j \le \hat{\nu}_j \le \nu_j + 1$:

$$
\sigma^2 \le \hat{\sigma}^2 \le \sigma^2 + \varepsilon
$$

Portanto:

$$
\sigma \le \hat{\sigma} \le \sigma \left( 1 + \frac{\varepsilon}{2\sigma^2} \right) \approx \sigma + \frac{\varepsilon}{2\sigma}
$$

O desvio-padrão é superestimado por uma quantidade da ordem de $L / \sigma_{\text{loss}}$, que tende a zero quando $L$ é pequeno comparado à dispersão das perdas.

---

## 5. Extensão Multi-Ano com Taxas Fixas

Para um horizonte de $T$ anos, cada contraparte $j$ gera $T$ **contrapartes virtuais**, uma para cada ano $t$:

- Exposição: $L \nu_j^{(t)}$
- Perda esperada: $\varepsilon_j^{(t)} = p_j^{(t)} E_j^{(t)} / L$

onde $p_j^{(t)}$ é a taxa marginal condicional de default no ano $t$.

A PGF multi-ano tem a mesma forma funcional da PGF de um ano:

$$
G(z) = \exp\!\left[ \sum_{j,t} \frac{\varepsilon_j^{(t)}}{\nu_j^{(t)}} \bigl(z^{\nu_j^{(t)}} - 1\bigr) \right]
$$

Portanto, a recursão (25) continua válida, bastando tratar cada par $(j, t)$ como uma exposição virtual independente.

---

## 6. Implementação Python

A recursão de taxa fixa está implementada no fallback do módulo `creditriskplus.simple_model`:

```python
# Caso Poisson puro (sigma = 0): mu = sum(epsilon_j / nu_j)
A[0] = np.exp(-mu)
for n in range(1, max_n + 1):
    s_val = 0.0
    for vj, ej in zip(bands, epsilons):
        if vj <= n:
            s_val += ej * A[n - vj]
    A[n] = s_val / n
```

A função principal `calculate_loss_distribution` usa o caso geral de taxa variável (NB), que converge para Poisson quando $\sigma \to 0$.

---

## 7. Resumo

| Conceito | Fórmula |
|----------|---------|
| Número esperado de defaults | $\mu = \sum_A p_A$ |
| PGF de defaults | $F(z) = e^{\mu(z-1)}$ |
| PGF de perdas | $G(z) = e^{\mu(P(z)-1)}$ |
| Polinômio de severidade | $P(z) = \frac{1}{\mu} \sum_j \frac{\varepsilon_j}{\nu_j} z^{\nu_j}$ |
| Recursão Poisson | $A_n = \frac{1}{n} \sum_{j: \nu_j \le n} \varepsilon_j A_{n-\nu_j}$ |
| Condição inicial | $A_0 = e^{-\mu}$ |
