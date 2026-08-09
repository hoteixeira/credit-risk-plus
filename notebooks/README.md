# Validação dos notebooks

Data da última revisão: 9 de agosto de 2026.

## Parecer

Foram mantidos dez notebooks. Todos executam integralmente, sem erro. Os estudos CreditRisk+ usam a API matemática canônica e distinguem o quantil discreto do modelo da interpolação usada apenas para reproduzir a planilha oficial. Os exemplos oficiais contêm asserções de regressão; o estudo PF contém controles de horizonte, massa truncada e cobertura dos quantis; o estudo Vasicek/IRB contém reconciliações analíticas de EL, perda adversa, capital, RWA e contribuições Euler.

"Sem simplificações" não pode significar eliminar hipóteses que definem o próprio CreditRisk+. Permanecem explícitas a aproximação Poisson, a discretização de severidades, os fatores Gama independentes, EAD/PD/LGD pontuais e, no estudo PF, a homogeneidade dentro de cada pool sintético. Não há aproximação adicional escondida para transformar EAD em número de contratos ou para renormalizar a cauda truncada.

## Matriz de validação

| Notebook | Papel | Evidência e parecer |
|---|---|---|
| `01_introducao.ipynb` | Fundamentos | Corrige a natureza paramétrica e analítica do modelo; explicita hipóteses, PGF de perdas, setores e definições de risco. Mantido. |
| `02_modelo_fixo.ipynb` | Limite Poisson | Implementa a PGF composta e a recursão fixa; confere massa, EL e variância contra fórmulas analíticas. Mantido. |
| `03_modelo_variavel.ipynb` | Poisson–Gama | A variável Gama é a intensidade setorial, não a PD individual; parâmetros e momentos seguem A52/A60/A115–A118. Mantido. |
| `04_exemplo_1A.ipynb` | Regressão oficial e contribuições | Reproduz EL e VaR99 interpolado do XLS e valida as contribuições A121/A102, sem atribuição proporcional ad hoc. Mantido. |
| `05_exemplo_1B.ipynb` | Concentração | Reproduz o XLS e separa corretamente efeito finito de remoção de contribuição Euler/aditiva. Mantido. |
| `06_exemplo_1C_multi_ano.ipynb` | Exemplo oficial multi-ano | Reproduz a construção de contrapartes virtuais e os KPIs do XLS; declara que ela não é um modelo temporal completo. Mantido. |
| `07_exemplo_2_setores_geo.ipynb` | Setores exclusivos | Reproduz três fatores geográficos e os KPIs oficiais, com pesos unitários por contraparte. Mantido. |
| `08_exemplo_3_setores_fracionarios.ipynb` | Pesos fracionários | Reproduz o XLS com quatro setores e aplica literalmente o setor específico com variância zero de A12.3. Mantido. |
| `11_safras_pf_brasil_creditriskplus.ipynb` | Carteira PF longitudinal | Reconstrói backbook maduro, executa 12 meses de burn-in e acompanha as 24 safras reportadas até o mesmo MOB 60; um gate de convergência precede o CreditRisk+. Mantido como cenário sintético, não como calibração de mercado. |
| `12_vasicek_irb_pf.ipynb` | Vasicek/IRB e capital marginal | Reutiliza os dados do notebook 11, separa PD TTC de PD PIT, aplica as funções IRB de varejo, calcula 24 fechamentos e materializa contribuições Euler por contrato. QRRE é hipótese explícita com sensibilidade conservadora; o resultado é metodológico, não uma apuração regulatória autorizada. |

## Notebooks excluídos

| Arquivo | Motivo |
|---|---|
| `09_aplicacoes.ipynb` | Misturava a distribuição CreditRisk+ com regras ad hoc de provisão, limites, preço e RARoC, sem base no manual nem calibração externa. Corrigir exigiria definir uma metodologia gerencial independente; mantê-lo sugeriria uma validade inexistente. |
| `10_simulacao_portfolio_varejo.ipynb` | Era apenas um aviso de substituição e não continha análise executável. O estudo válido está no notebook 11. |

## Critérios automatizados

- execução limpa de todas as células pelo `test_notebooks.py`;
- asserções internas de regressão contra `references/CreditRisk+.xls` nos exemplos 1A–1C, 2 e 3;
- preservação da EL após banding e confronto de momentos analíticos;
- aditividade das contribuições ao desvio padrão;
- ausência de renormalização da PMF truncada e controle explícito da massa omitida;
- gate de maturidade do backbook por nível, EL/EAD, mix de produto e distribuição por MOB;
- quantis recusados quando a CDF computada não alcança o nível solicitado.
- integração Gauss–Hermite de `E[P(D|W)] = PD` no Vasicek/IRB;
- diferença finita da derivada de capital em relação à EAD e equivalência entre pools e expansão contratual;
- reconciliação mensal `capital = perda adversa − EL` e `RWA = 12,5 × capital`;
- soma exata das contribuições Euler de todos os contratos no fechamento crítico.

Detalhes matemáticos, tolerâncias e limitações estão em `AUDITORIA_TECNICA.md`.
