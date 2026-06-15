# Validação

A implementação deste repositório foi validada contra a planilha oficial `CreditRisk+.xls` do Credit Suisse. Esta página descreve os resultados e as fontes de discrepância.

---

## 1. Referência Oficial

A planilha `references/CreditRisk+.xls` contém os exemplos numéricos originais do paper:

- **Exemplo 1A**: 25 contrapartes, 1 setor (Economia Geral).
- **Exemplo 1B**: 23 contrapartes (remoção das contrapartes 24 e 25).
- **Exemplo 1C**: 25 contrapartes com horizonte de 3 anos.
- **Exemplo 2**: 25 contrapartes divididas em 3 setores geográficos exclusivos.
- **Exemplo 3**: 25 contrapartes divididas em 4 setores com pesos fracionários + setor específico.

---

## 2. Resultados de Validação

| Exemplo | Descrição | E[Loss] (ref) | VaR(99%) (ref) | Erro EL | Erro VaR |
|---------|-----------|--------------:|---------------:|:-------:|:--------:|
| 1A | 25 contrapartes, 1 setor | \$14.221.863 | \$55.311.503 | 0,000% | 0,000% |
| 1B | 23 contrapartes | \$11.162.856 | \$39.946.857 | 0,000% | 0,000% |
| 1C | 25 contrapartes, 3 anos | \$17.277.632 | \$62.100.307 | 0,000% | 0,000% |
| 2 | 3 setores geográficos | \$14.221.863 | \$49.931.502 | 0,000% | 0,000% |
| 3 | 4 setores + específico | \$14.221.863 | \$47.368.235 | 0,000% | +0,579% |

---

## 3. Interpretação dos Erros

### 3.1 Casos exatos (1A, 1B, 1C, 2)

Nos exemplos 1A, 1B, 1C e 2, os erros são menores que 0,001%, considerando a precisão de ponto flutuante e arredondamentos da planilha.

### 3.2 Exemplo 3: erro de +0,579%

O Exemplo 3 envolve o setor idiossincrático (*Specific Sector*), cuja implementação na planilha original depende de detalhes do código VBA não publicados. A implementação deste repositório:

- Usa $\alpha_A = 4$ para cada contraparte no setor específico.
- Calcula a PMF do setor por convolução de NBs individuais.
- É matematicamente consistente com a Seção A12 do paper.

O erro de +0,579% no VaR(99%) é o melhor resultado obtido sem acesso ao código VBA original. A perda esperada (EL) permanece exata.

---

## 4. Fontes de Discrepância Potenciais

| Fonte | Impacto |
|-------|---------|
| Arredondamento de bandas ($\nu_A$) | Pequeno; controlado pela escolha de $L$ |
| Truncamento da distribuição (`max_loss_dollars`) | Pequeno se a cauda for finita |
| Normalização das PMFs após truncamento | Menor que 0,001% nos exemplos testados |
| Implementação do setor específico | Principal fonte no Exemplo 3 |
| Precisão da planilha Excel | Limitada ao formato numérico do Excel |

---

## 5. Testes Automatizados

Os scripts de teste verificam:

1. Reprodução dos valores de EL e VaR dos exemplos.
2. Convergência do modelo NB para o modelo Poisson quando $\sigma \to 0$.
3. Aditividade das contribuições de risco.
4. Soma da PMF igual a 1.
5. Execução sem erros dos notebooks.

Para executar todos os testes:

```bash
source venv/bin/activate
python run_tests.py
```

---

## 6. Reprodutibilidade

Todos os resultados são determinísticos para um dado conjunto de inputs. A semente aleatória é fixada onde necessário (por exemplo, na simulação Markov do notebook 10).

---

## 7. Conclusão

A implementação reproduz os resultados oficiais com alta precisão. As eventuais discrepâncias são explicáveis por escolhas de implementação numericamente equivalentes ou por limitações de acesso ao código original da planilha.
