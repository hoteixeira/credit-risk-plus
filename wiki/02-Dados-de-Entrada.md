# Dados de Entrada do Modelo

O Credit Risk+ requer quatro classes principais de dados de entrada para cada contraparte:

1. **Exposição** ($E_A$)
2. **Probabilidade de default** ($p_A$)
3. **Volatilidade da taxa de default** ($\sigma_A$)
4. **Taxa de recuperação** ($RR_A$)

Além disso, para modelos multi-setor, são necessários os **pesos setoriais** ($\theta_{Ak}$).

---

## 1. Exposições

A exposição de uma contraparte representa o valor financeiro em risco caso ocorra um default. A definição exata depende do tipo de instrumento:

| Instrumento | Exposição típica |
|-------------|------------------|
| Empréstimo | Saldo devedor líquido |
| Derivativo | Valor de mercado + add-on de exposição futura potencial |
| Carta de crédito | Valor nominal completo (assumido sacado antes do default) |
| Título | Valor nominal + cupons vencidos |

### Exposição líquida

A exposição usada diretamente no modelo é a **exposição líquida**, após descontar a recuperação esperada:

$$
E_A^{\text{net}} = E_A \times (1 - RR_A)
$$

### Variação temporal

Em horizontes multi-ano, as exposições podem variar ao longo do tempo devido a:

- Amortizações programadas.
- Reembolsos antecipados.
- Variação do valor de mercado (para derivativos).
- Novas operações.

Nesses casos, a exposição deve ser especificada para cada ano do horizonte.

---

## 2. Taxas de Default (PD)

A probabilidade de default anual $p_A$ é a probabilidade de que a contraparte $A$ entre em default no próximo ano.

### Fontes de estimativa

- **Ratings externos**: Moody's, S&P, Fitch fornecem taxas médias históricas de default por categoria de rating.
- **Spreads de mercado**: CDS ou spreads de títulos corporativos podem ser convertidos em PDs implícitas.
- **Modelos internos**: scorecards, regressões logit, modelos de machine learning.

### Tabela de referência do paper

O documento original do Credit Risk+ apresenta a seguinte tabela ilustrativa (Moody's, 1996):

| Rating | PD média anual | Desvio padrão |
|--------|---------------:|--------------:|
| Aaa    | 0,00%          | 0,0%          |
| Aa     | 0,03%          | 0,1%          |
| A      | 0,01%          | 0,0%          |
| Baa    | 0,12%          | 0,3%          |
| Ba     | 1,36%          | 1,3%          |
| B      | 7,27%          | 5,1%          |

> Nota: os valores desta tabela são ilustrativos e não devem ser usados sem validação para uma carteira específica.

### PDs em horizontes diferentes

Para horizontes diferentes de um ano, as PDs devem ser convertidas de forma consistente. A extensão multi-ano do Credit Risk+ utiliza **taxas marginais condicionais**:

$$
p_A^{(t)} = \mathbb{P}(\text{default no ano } t \mid \text{sobreviveu até } t-1)
$$

discutidas detalhadamente em [Extensão Multi-Ano](06-Multi-Ano).

---

## 3. Volatilidade das Taxas de Default

A volatilidade $\sigma_A$ da taxa de default é o elemento que distingue o Credit Risk+ de um simples modelo de Poisson.

### Intuição

Mesmo que saibamos que a PD média histórica de um rating Ba é 1,36%, no próximo ano a taxa efetiva pode ser:

- **0,5%** em uma expansão econômica.
- **3,0%** em uma recessão.

Essa **incerteza de segundo nível** — incerteza sobre a própria taxa média — é o que $\sigma_A$ modela.

### Interpretação econômica

A volatilidade da PD captura a sensibilidade da contraparte a fatores sistêmicos:

- Contrapartes altamente cíclicas têm alta $\sigma_A$.
- Contrapartes estáveis ou diversificadas têm baixa $\sigma_A$.
- Em dados históricos, o desvio-padrão das taxas de default é frequentemente da mesma ordem de magnitude da média.

### Razão desvio/média

O paper observa que, para ratings mais arriscados, a razão $\sigma / \mu$ pode ser próxima de 1:

| Rating | PD | Vol PD | $\sigma / \mu$ |
|--------|---:|-------:|---------------:|
| Ba     | 1,36% | 1,30% | 0,96 |
| B      | 7,27% | 5,10% | 0,70 |

### Relação com setores

Na implementação multi-setor, a volatilidade setorial $\sigma_k$ é uma média ponderada das volatilidades individuais:

$$
\sigma_k = \sum_A \theta_{Ak} \sigma_A \frac{E_A / L}{\nu_A}
$$

onde $\nu_A = \lceil E_A / L \rceil$ é a banda de exposição.

---

## 4. Taxas de Recuperação

Em caso de default, a perda líquida é:

$$
\text{Loss}_A = E_A \times (1 - RR_A)
$$

A taxa de recuperação $RR_A$ depende fortemente da **senioridade** da dívida e das características do colateral.

### Tabela de referência

| Tipo de dívida | Média | Desvio padrão |
|----------------|------:|--------------:|
| Senior secured bank loans | 71,2% | 21,1% |
| Senior unsecured public debt | 47,5% | 26,3% |
| Subordinated public debt | 28,3% | 20,1% |
| Junior subordinated debt | 14,7% | 8,7% |

### Tratamento no modelo

No Credit Risk+, as taxas de recuperação são tipicamente:

- **Determinísticas**: aplicadas diretamente para obter $E_A^{\text{net}}$.
- **Constantes por tipo de ativo**: todas as contrapartes de uma mesma classe recebem o mesmo $RR$.

A incerteza na recuperação pode ser incorporada de forma aproximada ajustando a exposição líquida esperada.

---

## 5. Pesos Setoriais

Para modelos multi-setor, cada contraparte $A$ é alocada aos setores $k = 1, \dots, K$ através de pesos:

$$
\theta_{Ak} \ge 0, \qquad \sum_{k=1}^{K} \theta_{Ak} = 1
$$

### Casos especiais

- **Setor único**: $\theta_{A1} = 1$ para todas as contrapartes.
- **Setores exclusivos**: $\theta_{Ak} \in \{0, 1\}$.
- **Setores fracionários**: $0 < \theta_{Ak} < 1$, permitindo que uma contraparte seja exposta a múltiplos fatores.

### Setor idiossincrático

O setor idiossincrático (ou *specific sector*) captura a parcela do risco de uma contraparte que não é explicada por fatores sistêmicos. Tipicamente representado por $\theta_{A,\text{specific}}$, com os demais pesos representando fatores compartilhados.

---

## 6. Discretização das Exposições (Exposure Banding)

Antes da aplicação das recursões, as exposições são discretizadas em múltiplos inteiros de uma unidade base $L$:

$$
L = \left\lceil \frac{\max_A E_A^{\text{net}}}{100} \right\rceil
$$

$$
\nu_A = \left\lceil \frac{E_A^{\text{net}}}{L} \right\rceil
$$

A escolha $L = \max(E_A^{\text{net}})/100$ garante que a maior exposição seja representada por aproximadamente 100 bandas, balanceando:

- **Precisão**: bandas pequenas reduzem o erro de arredondamento.
- **Custo computacional**: bandas grandes reduzem o número de estados da distribuição.

### Erro de bandagem

O erro introduzido pela bandagem é pequeno. O paper mostra que:

- A **perda esperada** é preservada.
- O **desvio-padrão** é ligeiramente superestimado por uma quantidade da ordem de $L$.

Ver [Modelo de Taxa Fixa: Poisson](03-Modelo-Taxa-Fixa-Poisson) para a demonstração formal.

---

## 7. Resumo dos Inputs por Contraparte

| Símbolo | Descrição | Unidade |
|---------|-----------|---------|
| $E_A$ | Exposição bruta | Moeda |
| $RR_A$ | Taxa de recuperação | Adimensional [0,1] |
| $E_A^{\text{net}} = E_A(1-RR_A)$ | Exposição líquida | Moeda |
| $p_A$ | Probabilidade média de default | Adimensional [0,1] |
| $\sigma_A$ | Desvio-padrão da PD | Adimensional [0,1] |
| $\theta_{Ak}$ | Peso da contraparte no setor $k$ | Adimensional [0,1] |
| $L$ | Unidade de perda | Moeda |
| $\nu_A = \lceil E_A^{\text{net}}/L \rceil$ | Banda de exposição | Inteiro |
| $\varepsilon_A = p_A E_A^{\text{net}}/L$ | Perda esperada em unidades de $L$ | Adimensional |

---

## 8. Qualidade dos Dados

A qualidade dos outputs do Credit Risk+ depende diretamente da qualidade dos inputs:

- **PDs devem ser forward-looking**: preferencialmente baseadas em cenários econômicos, não apenas médias históricas.
- **Volatilidades devem refletir incerteza sistêmica**: não apenas erro amostral.
- **Exposições devem ser medidas no momento do default**: incluindo potencial futuro para instrumentos não-amortizáveis.
- **Setores devem ser economicamente significativos**: agrupar contrapartes que realmente respondam a fatores comuns.

A validação dos inputs é uma etapa crítica e frequentemente mais desafiadora do que a matemática do modelo em si.
