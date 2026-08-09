# Referências locais

Arquivos primários usados nos estudos CreditRisk+, Vasicek/IRB e da carteira PF brasileira. Os documentos adicionais foram obtidos de fontes oficiais em 9 de agosto de 2026.

| Arquivo | Instituição e conteúdo | Páginas | SHA-256 |
|---|---|---:|---|
| `BCB_Resolucao_303_2023_IRB.pdf` | Banco Central do Brasil — Resolução BCB 303, incluindo a função de capital e as correlações de varejo do art. 46 | 52 | `82210fa4181b03e017da34f4ab9c8de41bb95492a25fb3bc0d1aeb53068de26d` |
| `BIS_Basel_Framework_consolidated.pdf` | BIS/BCBS — Basel Framework consolidado, incluindo CRE30 e CRE31 | 1.982 | `e65622eaa1820898dca8e10e690a0fcffae8da5b804ce9030418b927b60d84bd` |
| `BCBS_IRB_Risk_Weight_Functions_Explanatory_Note_2005.pdf` | BCBS — derivação ASRF/Vasicek das funções IRB | 19 | `387f8627a148dbd0a6eff3c5a0a020e44044051d3d8f34f0485b8297f49b503d` |
| `CMN_Resolucao_4966_2021_DOU_original.pdf` | Conselho Monetário Nacional — páginas 393–400 da edição 225 do DOU de 29/11/2021, contendo o texto original completo da Resolução CMN 4.966 | 8 | `9fbd3f05968cd2c8f39fd6340a689e634a49b896dc1ef9a8113ace9e0377ab7c` |
| `BCB_Relatorio_Economia_Bancaria_2023.pdf` | Banco Central do Brasil — Relatório de Economia Bancária 2023, referência contextual da carteira PF do notebook 11 | 133 | `bc93976ffc6bc2d0d5ada32b802b69ee5e8e94f6b5602b3ec80ae1bc11926d42` |
| `CreditRisk+.pdf` | Credit Suisse First Boston — manual técnico CreditRisk+ | 72 | `07009077cdea19a9cec1b11776bc84bf4a1395e0149c50ac88406150438b8a51` |
| `CreditRisk+.xls` | Credit Suisse First Boston — planilha oficial de exemplos | — | `4eb77b9e7ca13b6ca1cbd7e7b42e74084915364cc5f722afe6b72c63de26e32b` |

## Fontes oficiais

- BCB: <https://www.bcb.gov.br/content/estabilidadefinanceira/especialnor/Resolu%C3%A7%C3%A3o303.pdf>
- Basel Framework consolidado: <https://www.bis.org/baselframework/BaselFramework.pdf>
- Nota explicativa IRB: <https://www.bis.org/bcbs/irbriskweight.pdf>
- CRE30 navegável: <https://www.bis.org/basel_framework/chapter/CRE/30.htm>
- CRE31 navegável: <https://www.bis.org/basel_framework/chapter/CRE/31.htm>
- Resolução CMN 4.966, versão consolidada no portal do BCB: <https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=4966&tipo=Resolu%C3%A7%C3%A3o+CMN>
- Resolução CMN 4.966, publicação original no DOU: páginas 393–400 da edição 225 de 29/11/2021, obtidas pelo visualizador oficial <https://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=29/11/2021&jornal=515&pagina=393>
- Relatório de Economia Bancária 2023: <https://www.bcb.gov.br/content/publicacoes/relatorioeconomiabancaria/reb2023p.pdf>

O BIS oferece CRE30 e CRE31 como páginas dinâmicas e gera PDFs isolados no navegador. Para preservar um artefato estático publicado diretamente pelo BIS, este repositório armazena o Basel Framework consolidado, que contém integralmente os dois capítulos.

O PDF da Resolução CMN 4.966 preserva sua publicação original no DOU. As páginas do Diário Oficial foram mantidas integrais e, por isso, também contêm pequenos trechos das normas imediatamente anterior e posterior. Como a Resolução 4.966 foi alterada posteriormente, esse arquivo não deve ser tratado como consolidação vigente; para uso regulatório, deve-se consultar a versão consolidada indicada acima, que o BCB informa ter sido atualizada em 29 de agosto de 2025.

## Séries oficiais sem PDF canônico

O notebook 11 também cita duas séries do Sistema Gerenciador de Séries Temporais (SGS). Elas são conjuntos de dados atualizáveis publicados no Portal de Dados Abertos do BCB e, por isso, são mantidas como links oficiais, sem conversão artificial para PDF:

- SGS 21129 — inadimplência de cartão de crédito PF: <https://dadosabertos.bcb.gov.br/dataset/21129-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---cartao-de-credit>
- SGS 21114 — inadimplência de crédito pessoal PF: <https://dadosabertos.bcb.gov.br/dataset/21114-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---credito-pessoal->

Os checksums podem ser conferidos com:

```bash
shasum -a 256 references/BCB_Resolucao_303_2023_IRB.pdf \
  references/BIS_Basel_Framework_consolidated.pdf \
  references/BCBS_IRB_Risk_Weight_Functions_Explanatory_Note_2005.pdf \
  references/CMN_Resolucao_4966_2021_DOU_original.pdf \
  references/BCB_Relatorio_Economia_Bancaria_2023.pdf \
  references/CreditRisk+.pdf \
  references/CreditRisk+.xls
```
