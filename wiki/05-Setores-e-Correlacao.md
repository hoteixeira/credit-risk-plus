# Setores e Correlação

Uma das contribuições mais importantes do Credit Risk+ é a modelagem da **dependência entre defaults** através de **fatores sistêmicos setoriais**. Em vez de especificar diretamente uma matriz de correlação entre todos os pares de contrapartes, o modelo utiliza uma estrutura de setores na qual contrapartes expostas aos mesmos fatores sistêmicos têm defaults correlacionados.

Este capítulo cobre as Seções A7, A8, A9, A12 e A13 do Apêndice A do paper oficial.

---

## 1. Motivação para Setores

Se todas as contrapartes pertencerem a um único setor, um único fator Gama afeta todas — o que implica **correlação máxima**. Na prática, contrapartes em setores ou geografias diferentes respondem a fatores econômicos distintos. A estrutura de setores permite capturar:

- **Diversificação setorial**: riscos independentes reduzem o capital agregado.
- **Concentração**: exposição excessiva a um único fator aumenta o capital.
- **Correlações implícitas**: derivadas da alocação a setores comuns.

---

## 2. Alocação por Setores com Pesos

### 2.1 Pesos setoriais

Cada contraparte $A$ é alocada aos setores $k = 1, \dots, K$ com pesos:

$$
\theta_{Ak} \ge 0, \qquad \sum_{k=1}^{K} \theta_{Ak} = 1
$$

### 2.2 Caso simples: setores exclusivos

No caso mais simples, cada contraparte pertence a exatamente um setor:

$$
\theta_{Ak} = \begin{cases} 1, & A \in S_k \\ 0, & \text{caso contrário} \end{cases}
$$

### 2.3 Caso geral: pesos fracionários

No caso geral, uma contraparte pode ser exposta a múltiplos fatores sistêmicos simultaneamente. Por exemplo, uma empresa pode estar exposta a:

- Fatores do país de origem.
- Fatores do setor industrial.
- Fatores globais.
- Fatores idiossincráticos específicos.

---

## 3. Parâmetros por Setor

### 3.1 Média e volatilidade setorial

Para cada setor $k$, os parâmetros são calculados como médias ponderadas:

$$
\boxed{
\mu_k = \sum_A \theta_{Ak} \mu_A = \sum_A \theta_{Ak} \frac{\varepsilon_A}{\nu_A}
}
$$

$$
\boxed{
\sigma_k = \sum_A \theta_{Ak} \sigma_A \frac{E_A / L}{\nu_A}
}
$$

onde $\mu_A = \varepsilon_A / \nu_A$ é a contribuição da contraparte $A$ ao número esperado de defaults.

### 3.2 Parâmetros Gama e NB

Uma vez calculados $\mu_k$ e $\sigma_k$, obtemos:

$$
\alpha_k = \frac{\mu_k^2}{\sigma_k^2}, \qquad \beta_k = \frac{\sigma_k^2}{\mu_k}, \qquad p_k = \frac{\beta_k}{1 + \beta_k}
$$

### 3.3 Banda de exposição

**Detalhe crucial**: a banda $\nu_A = \lceil E_A / L \rceil$ é calculada com a **exposição total** de $A$, não com a fração setorial. Isso preserva a severidade da perda dado um default: se $A$ der default, a perda é sempre $E_A$, não $\theta_{Ak} E_A$.

A fração setorial $\theta_{Ak}$ escala apenas a **frequência esperada** de default no setor $k$:

$$
\varepsilon_A^{(k)} = \theta_{Ak} \, p_A \frac{E_A}{L}
$$

---

## 4. PGF Multi-Setor

### 4.1 Independência entre setores

Como os fatores Gama de setores distintos são independentes, a PGF total do portfólio é o produto das PGFs setoriais:

$$
\boxed{
G(z) = \prod_{k=1}^{K} G_k(z) = \prod_{k=1}^{K} \left( \frac{1 - p_k}{1 - p_k P_k(z)} \right)^{\alpha_k}
}
$$

### 4.2 Implementação por convolução

Na prática, a distribuição total é obtida calculando a PMF de cada setor individualmente e depois convoluindo as PMFs:

$$
\text{PMF}_{\text{total}} = \text{PMF}_1 * \text{PMF}_2 * \dots * \text{PMF}_K
$$

Em Python:

```python
pmf_total = pmf_setor_1
for k in range(1, K):
    pmf_total = np.convolve(pmf_total, pmf_setor_k)[:max_n+1]
```

---

## 5. Efeito da Diversificação Setorial

A diversificação setorial reduz o VaR porque a convolução de distribuições independentes tem cauda mais leve. O paper ilustra isso com o portfólio de 25 contrapartes:

| Configuração | VaR(99%) | Redução vs. 1 setor |
|-------------|----------:|--------------------:|
| 1 setor | \$55.311.503 | — |
| 3 setores geográficos | \$49.931.502 | −9,7% |
| 4 setores + específico | \$47.368.235 | −14,4% |

---

## 6. Setor Idiossincrático (Specific Sector)

### 6.1 O problema

Na alocação com pesos fracionários, parte do risco de cada contraparte pode não ser explicada por nenhum fator setorial. Este é o risco **específico** ou **idiossincrático** da contraparte.

### 6.2 Modelagem como setor específico

O paper propõe modelar o componente idiossincrático criando um setor adicional no qual cada contraparte tem seu **próprio fator Gama independente**. A convenção é fixar o coeficiente de variação em:

$$
CV = \frac{\sigma_A}{\mu_A} = \frac{1}{\sqrt{\alpha_A}} = 0,5
$$

do que implica:

$$
\alpha_A = 4
$$

### 6.3 Parâmetros do setor idiossincrático

Para cada contraparte $A$ com peso $\theta_A > 0$ no setor específico:

$$
\mu_A = \theta_A \frac{\varepsilon_A}{\nu_A}
$$

$$
\beta_A = \frac{\mu_A}{\alpha_A} = \frac{\mu_A}{4}
$$

$$
p_A = \frac{\beta_A}{1 + \beta_A}
$$

### 6.4 PMF individual e convolução

A PMF de cada contraparte no setor específico é uma NB com suporte em $\{0, \nu_A, 2\nu_A, \dots\}$. A recursão escalar é:

$$
A_A[0] = (1 - p_A)^4
$$

$$
A_A[k \cdot \nu_A] = p_A \frac{3 + k}{k} A_A[(k-1) \cdot \nu_A]
$$

A PMF do setor idiossincrático total é a convolução sequencial das PMFs individuais:

$$
\text{PMF}_{\text{idio}} = A_1 * A_2 * \dots * A_N
$$

### 6.5 Implementação Python

A função `_idiosyncratic_sector_distribution` implementa essa convolução:

```python
beta_a = 0.25 * mu_a
p_a = beta_a / (1.0 + beta_a)

A_indiv[0] = (1.0 - p_a) ** 4
for kk in range(1, max_n // v_a + 1):
    n_idx = kk * v_a
    A_indiv[n_idx] = p_a * (3 + kk) / kk * A_indiv[n_idx - v_a]

# Convolução sequencial
conv = np.convolve(A, A_indiv)
A = conv[:max_n + 1]
```

---

## 7. Correlações Pareadas Implícitas

### 7.1 Definição

Seja $I_A$ a variável indicadora de default da contraparte $A$:

$$
I_A = \begin{cases} 1, & \text{se } A \text{ default} \\ 0, & \text{caso contrário} \end{cases}
$$

A correlação pareada é:

$$
\rho_{AB} = \mathrm{Corr}(I_A, I_B) = \frac{\mathbb{E}[I_A I_B] - \mathbb{E}[I_A]\mathbb{E}[I_B]}{\sqrt{\mathrm{Var}(I_A) \mathrm{Var}(I_B)}}
$$

### 7.2 Aproximação para defaults raros

Para pequenas probabilidades de default, o paper mostra que:

$$
\rho_{AB} \approx \sqrt{\mu_A \mu_B} \sum_{k=1}^{K} \theta_{Ak} \theta_{Bk} \left( \frac{\sigma_k}{\mu_k} \right)^2
$$

### 7.3 Interpretação

- Se $A$ e $B$ não compartilham nenhum setor ($\theta_{Ak}\theta_{Bk} = 0$ para todo $k$), a correlação é zero.
- A correlação é proporcional ao produto dos pesos setoriais comuns.
- A magnitude é da ordem de $\sqrt{\mu_A \mu_B}$, tipicamente pequena (consistente com dados empíricos).
- Valores muito altos de $\mu$ e $\sigma$ podem teoricamente produzir $\rho_{AB} > 1$, refletindo a aproximação para defaults raros.

---

## 8. General Sector Analysis (Seção A12)

### 8.1 Formulação geral

A PGF multi-setor pode ser vista como uma integral múltipla:

$$
G(z) = \prod_{k=1}^{K} \int_0^{\infty} e^{x_k(P_k(z)-1)} f_k(x_k) \, dx_k = \int_0^{\infty} \cdots \int_0^{\infty} e^{\sum_k x_k(P_k(z)-1)} \prod_k f_k(x_k) \, dx_k
$$

O expoente pode ser escrito em termos de obrigadores:

$$
\sum_{k=1}^{K} x_k(P_k(z)-1) = \sum_{A,k} \theta_{Ak} \frac{x_k}{\mu_k} \frac{\varepsilon_A}{\nu_A} (z^{\nu_A} - 1)
$$

A taxa de default efetiva da contraparte $A$ é:

$$
x_A = \frac{\varepsilon_A}{\nu_A} \sum_{k=1}^{K} \theta_{Ak} \frac{x_k}{\mu_k}
$$

### 8.2 Recuperação do caso setorial simples

O caso de setores exclusivos é recuperado quando $\theta_{Ak} \in \{0, 1\}$.

### 8.3 Setor específico como limite

Pela Seção A11, um setor com variância zero equivale ao limite de infinitos sub-setores independentes. Assim, o setor idiossincrático pode ser representado por um setor adicional com $\sigma_{\text{specific}} = 0$ e pesos $\theta_{A,\text{specific}}$.

---

## 9. Resumo

| Conceito | Fórmula |
|----------|---------|
| Peso setorial | $\sum_k \theta_{Ak} = 1$ |
| Média setorial | $\mu_k = \sum_A \theta_{Ak} \varepsilon_A / \nu_A$ |
| Volatilidade setorial | $\sigma_k = \sum_A \theta_{Ak} \sigma_A (E_A/L) / \nu_A$ |
| PGF total | $G(z) = \prod_k G_k(z)$ |
| Convolução | $\text{PMF}_{\text{total}} = *_k \text{PMF}_k$ |
| Setor idiossincrático | $\alpha_A = 4$ (CV = 0,5) |
| Correlação pareada | $\rho_{AB} \approx \sqrt{\mu_A \mu_B} \sum_k \theta_{Ak}\theta_{Bk}(\sigma_k/\mu_k)^2$ |
