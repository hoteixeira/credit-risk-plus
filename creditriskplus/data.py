"""Carteiras e tabelas de rating dos exemplos oficiais do CreditRisk+.

Todos os números deste módulo são transcrições literais do manual do Credit
Suisse First Boston (1997) e da planilha `references/CreditRisk+.xls`. Eles não
são calibrações nem estimativas: existem para que os exemplos publicados possam
ser reproduzidos exatamente e usados como regressão.

Cada contraparte precisa de três informações para entrar no modelo:

* a exposição, que define o tamanho da perda caso ela quebre;
* a taxa média de default, que é a probabilidade anual de que isso ocorra;
* a volatilidade dessa taxa, que mede o quanto a média pode variar de um ano
  para o outro por razões sistemáticas — é ela que engorda a cauda da
  distribuição e separa o CreditRisk+ de um modelo Poisson simples.

O manual adverte que as taxas destes exemplos são deliberadamente altas e
servem apenas para ilustração.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Tabela 9 do manual: mapeamento de rating para taxa média de default e sua
# volatilidade. Note que, em todas as linhas, a volatilidade é exatamente metade
# da média. Na notação do Apêndice A isso é sigma_A/p_A = 0,5, a razão que a
# seção A7.3 chama de "flat ratio" e que, pela equação 44, se propaga para o
# setor inteiro como sigma_k = 0,5 * mu_k.
RATING_TABLE = {
    'A': {'mean': 0.015, 'std': 0.0075},      # 1.5% média, 0.75% volatilidade
    'B': {'mean': 0.016, 'std': 0.0080},      # 1.6% média, 0.80% volatilidade
    'C': {'mean': 0.030, 'std': 0.0150},      # 3.0% média, 1.50% volatilidade
    'D': {'mean': 0.050, 'std': 0.0250},      # 5.0% média, 2.50% volatilidade
    'E': {'mean': 0.075, 'std': 0.0375},      # 7.5% média, 3.75% volatilidade
    'F': {'mean': 0.100, 'std': 0.0500},      # 10.0% média, 5.00% volatilidade
    'G': {'mean': 0.150, 'std': 0.0750},      # 15.0% média, 7.50% volatilidade
    'H': {'mean': 0.300, 'std': 0.1500},      # 30.0% média, 15.00% volatilidade
}

# Estrutura a termo do Exemplo 1C, transcrita da aba Example1C do XLS.
# São taxas marginais: a probabilidade de a contraparte quebrar durante o ano t,
# dado que sobreviveu aos anos anteriores. A seção A5.2 exige justamente taxas
# marginais, porque a construção de contrapartes virtuais da seção A5.3 supõe
# que defaults da mesma contraparte em anos diferentes são mutuamente exclusivos.
# Ratings ruins têm taxas decrescentes ao longo dos anos porque quem sobrevive
# ao primeiro ano já demonstrou resiliência; ratings bons têm o padrão inverso.
MULTI_YEAR_RATING_TABLE = {
    'A': {
        'year_1': {'mean': 0.015, 'std': 0.0075},
        'year_2': {'mean': 0.025, 'std': 0.0125},
        'year_3': {'mean': 0.035, 'std': 0.0175},
    },
    'B': {
        'year_1': {'mean': 0.016, 'std': 0.0080},
        'year_2': {'mean': 0.031, 'std': 0.0155},
        'year_3': {'mean': 0.042, 'std': 0.0210},
    },
    'C': {
        'year_1': {'mean': 0.030, 'std': 0.0150},
        'year_2': {'mean': 0.044, 'std': 0.0220},
        'year_3': {'mean': 0.053, 'std': 0.0265},
    },
    'D': {
        'year_1': {'mean': 0.050, 'std': 0.0250},
        'year_2': {'mean': 0.063, 'std': 0.0315},
        'year_3': {'mean': 0.070, 'std': 0.0350},
    },
    'E': {
        'year_1': {'mean': 0.075, 'std': 0.0375},
        'year_2': {'mean': 0.086, 'std': 0.0430},
        'year_3': {'mean': 0.086, 'std': 0.0430},
    },
    'F': {
        'year_1': {'mean': 0.100, 'std': 0.0500},
        'year_2': {'mean': 0.101, 'std': 0.0505},
        'year_3': {'mean': 0.096, 'std': 0.0480},
    },
    'G': {
        'year_1': {'mean': 0.150, 'std': 0.0750},
        'year_2': {'mean': 0.131, 'std': 0.0655},
        'year_3': {'mean': 0.111, 'std': 0.0555},
    },
    'H': {
        'year_1': {'mean': 0.300, 'std': 0.1500},
        'year_2': {'mean': 0.199, 'std': 0.0995},
        'year_3': {'mean': 0.134, 'std': 0.0670},
    },
}


def load_portfolio_from_xls(xls_path, sheet_name='Exposures&StaticData'):
    """
    Carrega portfólio de contrapartes do arquivo XLS.

    Parâmetros:
    -----------
    xls_path : str
        Caminho para o arquivo CreditRisk+.xls
    sheet_name : str
        Nome da aba contendo os dados de portfólio

    Retorna:
    --------
    pd.DataFrame
        DataFrame com colunas: obligor_id, exposure, rating
    """
    df = pd.read_excel(xls_path, sheet_name=sheet_name, header=None)

    # Encontra a linha de cabeçalho (procura por "Name" na coluna B)
    header_row = None
    for i, row in enumerate(df.iterrows()):
        if 'Name' in row[1].values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Cabeçalho não encontrado no arquivo XLS")

    # Lê os dados após o cabeçalho
    data_rows = []
    for i in range(header_row + 1, len(df)):
        obligor_id = df.iloc[i, 1]
        exposure = df.iloc[i, 2]
        rating = df.iloc[i, 3]

        # Pula linhas vazias
        if pd.isna(obligor_id) or pd.isna(exposure) or pd.isna(rating):
            continue

        data_rows.append({
            'obligor_id': int(obligor_id),
            'exposure': float(exposure),
            'rating': str(rating).strip()
        })

    portfolio = pd.DataFrame(data_rows)
    return portfolio


def get_default_rates(rating, year=None, multi_year=False):
    """
    Obtém taxas de default para um rating específico.

    Parâmetros:
    -----------
    rating : str
        Rating de crédito (A-H)
    year : int, optional
        Ano (1, 2, 3) para modelo multi-ano
    multi_year : bool
        Se True, usa tabela multi-ano

    Retorna:
    --------
    dict
        Dicionário com 'mean' e 'std' (volatilidade)
    """
    if multi_year and year is not None:
        table = MULTI_YEAR_RATING_TABLE
        year_key = f'year_{year}'
        return table[rating][year_key]
    else:
        return RATING_TABLE[rating]


def create_example_1a_portfolio():
    """
    Cria o portfólio de Example 1A (25 contrapartes, 1 setor, taxas variáveis).

    Transcrição da Tabela 8 do manual. As exposições já são líquidas de
    recuperação, como o próprio manual declara na seção B2 ("The exposure
    amounts are net of recovery"), por isso os exemplos rodam com recuperação
    zero. Todas as contrapartes ficam no mesmo fator de economia geral, o que
    torna esta a carteira mais concentrada dos exemplos: não há diversificação
    entre fatores para reduzir a cauda.

    Valores publicados para conferência: exposição agregada 130.513.072,
    perda esperada 14.221.863 e desvio padrão 12.668.742.

    Retorna:
    --------
    pd.DataFrame
        Portfólio com colunas: obligor_id, exposure, rating, mean_default_rate, std_default_rate, sector
    """
    portfolio_data = [
        (1, 358475, 'H'),
        (2, 1089819, 'H'),
        (3, 1799710, 'F'),
        (4, 1933116, 'G'),
        (5, 2317327, 'G'),
        (6, 2410929, 'G'),
        (7, 2652184, 'H'),
        (8, 2957685, 'G'),
        (9, 3137989, 'D'),
        (10, 3204044, 'D'),
        (11, 4727724, 'A'),
        (12, 4830517, 'D'),
        (13, 4912097, 'D'),
        (14, 4928989, 'H'),
        (15, 5042312, 'F'),
        (16, 5320364, 'E'),
        (17, 5435457, 'D'),
        (18, 5517586, 'C'),
        (19, 5764596, 'E'),
        (20, 5847845, 'C'),
        (21, 6466533, 'H'),
        (22, 6480322, 'H'),
        (23, 7727651, 'B'),
        (24, 15410906, 'F'),
        (25, 20238895, 'E'),
    ]

    rows = []
    for obligor_id, exposure, rating in portfolio_data:
        rates = get_default_rates(rating)
        rows.append({
            'obligor_id': obligor_id,
            'exposure': exposure,
            'rating': rating,
            'mean_default_rate': rates['mean'],
            'std_default_rate': rates['std'],
            'sector_weight_general_economy': 1.0  # 100% in General Economy sector
        })

    return pd.DataFrame(rows)


def create_example_1a_23_obligor_portfolio():
    """
    Cria o portfólio de Example 1B (25 contrapartes menos 24 e 25 = 23 contrapartes).

    O manual usa este exemplo, na seção B3.7, para mostrar que gerenciar risco de
    crédito não é o mesmo que reduzir exposição: as duas contrapartes retiradas
    respondem por 21,5% da perda esperada mas por 27,8% do percentil de 99%.
    Concentração custa capital mais do que proporcionalmente.

    Retorna:
    --------
    pd.DataFrame
        Portfólio com 23 contrapartes
    """
    portfolio = create_example_1a_portfolio()
    # Remove contrapartes 24 e 25
    return portfolio[portfolio['obligor_id'] <= 23].reset_index(drop=True)


def create_example_2_3sector_portfolio():
    """
    Cria portfólio de Example 2 (3 setores geográficos: EUA, Japão, Europa).
    Alocação exclusiva (hard allocation).

    É o caso da seção A7 do manual: cada contraparte pertence a exatamente um
    setor, ou seja, os pesos são a função delta da equação 91. Como os três
    fatores são independentes, a distribuição total é a convolução das três
    distribuições setoriais. A mesma carteira do Exemplo 1A tem aqui um VaR de
    99% menor (49,9 contra 55,3 milhões) sem que nada na exposição mude: a
    diferença é puro benefício de diversificação entre fatores.

    Retorna:
    --------
    pd.DataFrame
        Portfólio com pesos de setor (EUA, Japão, Europa)
    """
    # Alocações do exemplo 2 (alocação exclusiva a um setor cada)
    sector_allocation = {
        1: {'US': 1, 'Japan': 0, 'Europe': 0},
        2: {'US': 0, 'Japan': 1, 'Europe': 0},
        3: {'US': 0, 'Japan': 1, 'Europe': 0},
        4: {'US': 1, 'Japan': 0, 'Europe': 0},
        5: {'US': 0, 'Japan': 0, 'Europe': 1},
        6: {'US': 0, 'Japan': 0, 'Europe': 1},
        7: {'US': 1, 'Japan': 0, 'Europe': 0},
        8: {'US': 0, 'Japan': 1, 'Europe': 0},
        9: {'US': 0, 'Japan': 0, 'Europe': 1},
        10: {'US': 0, 'Japan': 0, 'Europe': 1},
        11: {'US': 1, 'Japan': 0, 'Europe': 0},
        12: {'US': 0, 'Japan': 0, 'Europe': 1},
        13: {'US': 0, 'Japan': 0, 'Europe': 1},
        14: {'US': 0, 'Japan': 1, 'Europe': 0},
        15: {'US': 0, 'Japan': 0, 'Europe': 1},
        16: {'US': 0, 'Japan': 0, 'Europe': 1},
        17: {'US': 1, 'Japan': 0, 'Europe': 0},
        18: {'US': 1, 'Japan': 0, 'Europe': 0},
        19: {'US': 1, 'Japan': 0, 'Europe': 0},
        20: {'US': 1, 'Japan': 0, 'Europe': 0},
        21: {'US': 1, 'Japan': 0, 'Europe': 0},
        22: {'US': 0, 'Japan': 0, 'Europe': 1},
        23: {'US': 0, 'Japan': 1, 'Europe': 0},
        24: {'US': 0, 'Japan': 0, 'Europe': 1},
        25: {'US': 1, 'Japan': 0, 'Europe': 0},
    }

    portfolio = create_example_1a_portfolio()

    # Remove pesos de setor geral e adiciona setores geográficos
    portfolio_2sector = portfolio.drop(columns=['sector_weight_general_economy']).copy()

    for obligor_id in portfolio['obligor_id']:
        alloc = sector_allocation[obligor_id]
        portfolio_2sector.loc[portfolio_2sector['obligor_id'] == obligor_id, 'sector_weight_US'] = alloc['US']
        portfolio_2sector.loc[portfolio_2sector['obligor_id'] == obligor_id, 'sector_weight_Japan'] = alloc['Japan']
        portfolio_2sector.loc[portfolio_2sector['obligor_id'] == obligor_id, 'sector_weight_Europe'] = alloc['Europe']

    return portfolio_2sector


def create_example_3_4sector_portfolio():
    """
    Cria portfólio de Example 3 (4 setores: Específico, EUA, Japão, Europa).
    Alocação fracionária (pesos somam a 1.0 para cada contraparte).

    É a análise setorial generalizada da seção A12: cada contraparte sofre
    influência de vários fatores ao mesmo tempo, com pesos ``theta_Ak`` que somam
    um (equação 90). O setor "Specific" recebe o tratamento de A12.3 — mantém sua
    contribuição de média mas tem a volatilidade zerada, representando o limite de
    muitos fatores idiossincráticos independentes que se cancelam na carteira.
    Por isso este exemplo tem o menor VaR dos três (47,4 milhões): parte da
    volatilidade deixa de ser sistemática.

    Retorna:
    --------
    pd.DataFrame
        Portfólio com pesos fracionários de 4 setores
    """
    # Alocações fracionárias do exemplo 3
    sector_allocation = {
        1: {'Specific': 0.50, 'US': 0.30, 'Japan': 0.10, 'Europe': 0.10},
        2: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.25, 'Europe': 0.25},
        3: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.20, 'Europe': 0.30},
        4: {'Specific': 0.75, 'US': 0.05, 'Japan': 0.10, 'Europe': 0.10},
        5: {'Specific': 0.50, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.30},
        6: {'Specific': 0.50, 'US': 0.20, 'Japan': 0.10, 'Europe': 0.20},
        7: {'Specific': 0.25, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.55},
        8: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.20, 'Europe': 0.30},
        9: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.25, 'Europe': 0.25},
        10: {'Specific': 0.75, 'US': 0.10, 'Japan': 0.05, 'Europe': 0.10},
        11: {'Specific': 0.50, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.30},
        12: {'Specific': 0.50, 'US': 0.20, 'Japan': 0.10, 'Europe': 0.20},
        13: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.25, 'Europe': 0.25},
        14: {'Specific': 0.25, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.55},
        15: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.30, 'Europe': 0.20},
        16: {'Specific': 0.75, 'US': 0.10, 'Japan': 0.05, 'Europe': 0.10},
        17: {'Specific': 0.50, 'US': 0.20, 'Japan': 0.10, 'Europe': 0.20},
        18: {'Specific': 0.50, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.30},
        19: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.20, 'Europe': 0.30},
        20: {'Specific': 0.25, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.55},
        21: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.20, 'Europe': 0.30},
        22: {'Specific': 0.75, 'US': 0.10, 'Japan': 0.05, 'Europe': 0.10},
        23: {'Specific': 0.25, 'US': 0.25, 'Japan': 0.20, 'Europe': 0.30},
        24: {'Specific': 0.50, 'US': 0.20, 'Japan': 0.10, 'Europe': 0.20},
        25: {'Specific': 0.75, 'US': 0.10, 'Japan': 0.10, 'Europe': 0.05},
    }

    portfolio = create_example_1a_portfolio()

    # Remove peso de setor geral e adiciona 4 setores
    portfolio_4sector = portfolio.drop(columns=['sector_weight_general_economy']).copy()

    for obligor_id in portfolio['obligor_id']:
        alloc = sector_allocation[obligor_id]
        portfolio_4sector.loc[portfolio_4sector['obligor_id'] == obligor_id, 'sector_weight_Specific'] = alloc['Specific']
        portfolio_4sector.loc[portfolio_4sector['obligor_id'] == obligor_id, 'sector_weight_US'] = alloc['US']
        portfolio_4sector.loc[portfolio_4sector['obligor_id'] == obligor_id, 'sector_weight_Japan'] = alloc['Japan']
        portfolio_4sector.loc[portfolio_4sector['obligor_id'] == obligor_id, 'sector_weight_Europe'] = alloc['Europe']

    return portfolio_4sector


def create_example_1c_portfolio():
    """
    Cria o portfólio de virtual de Example 1C (horizonte 3 anos, 40 contrapartes virtuais).

    Cada par (contraparte, ano) é tratado como uma contraparte virtual independente
    com sua exposição específica do ano e taxa marginal condicional de default.

    A justificativa está na seção A5.3: como defaults da mesma contraparte em anos
    diferentes são mutuamente exclusivos, a PGF multi-ano da equação 36 tem
    exatamente a mesma forma da PGF anual da equação 17. A recursão anual, portanto,
    vale sem alteração. O truque é contábil, não estatístico: ele não modela
    migração de rating nem dependência temporal entre os anos.

    O perfil de exposição por ano reflete amortizações e vencimentos de créditos:
    - Ano 1: todas as 25 contrapartes originais
    - Ano 2: 10 contrapartes com exposição não-zero (algumas com valor reduzido)
    - Ano 3: 5 contrapartes com exposição não-zero

    Retorna:
    --------
    pd.DataFrame
        40 contrapartes virtuais com: virtual_id, obligor_id, year, exposure,
        rating, mean_default_rate, std_default_rate, sector_weight_general_economy
    """
    # Perfil de exposição por ano (extraído da planilha Excel, aba Example1C)
    # Format: {obligor_id: {year: exposure}}
    exposure_profile = {
        1:  {1: 358475,    2: 358475,    3: 0},
        2:  {1: 1089819,   2: 0,         3: 0},
        3:  {1: 1799710,   2: 0,         3: 0},
        4:  {1: 1933116,   2: 966558,    3: 0},
        5:  {1: 2317327,   2: 0,         3: 0},
        6:  {1: 2410929,   2: 0,         3: 0},
        7:  {1: 2652184,   2: 0,         3: 0},
        8:  {1: 2957685,   2: 0,         3: 0},
        9:  {1: 3137989,   2: 3137989,   3: 3137989},
        10: {1: 3204044,   2: 3204044,   3: 0},
        11: {1: 4727724,   2: 4727724,   3: 4727724},
        12: {1: 4830517,   2: 0,         3: 0},
        13: {1: 4912097,   2: 4912097,   3: 0},
        14: {1: 4928989,   2: 0,         3: 0},
        15: {1: 5042312,   2: 0,         3: 0},
        16: {1: 5320364,   2: 0,         3: 0},
        17: {1: 5435457,   2: 2717728.5, 3: 0},
        18: {1: 5517586,   2: 5517586,   3: 5517586},
        19: {1: 5764596,   2: 2882298,   3: 1441149},
        20: {1: 5847845,   2: 5847845,   3: 5847845},
        21: {1: 6466533,   2: 0,         3: 0},
        22: {1: 6480322,   2: 0,         3: 0},
        23: {1: 7727651,   2: 0,         3: 0},
        24: {1: 15410906,  2: 0,         3: 0},
        25: {1: 20238895,  2: 0,         3: 0},
    }

    base_portfolio = create_example_1a_portfolio()
    base_dict = base_portfolio.set_index('obligor_id').to_dict('index')

    rows = []
    virtual_id = 0
    for year in [1, 2, 3]:
        for obligor_id in range(1, 26):
            exp = exposure_profile[obligor_id][year]
            if exp <= 0:
                continue
            virtual_id += 1
            rating = base_dict[obligor_id]['rating']
            year_key = f'year_{year}'
            rates = MULTI_YEAR_RATING_TABLE[rating][year_key]
            rows.append({
                'virtual_id': virtual_id,
                'obligor_id': obligor_id,
                'year': year,
                'exposure': float(exp),
                'rating': rating,
                'mean_default_rate': rates['mean'],
                'std_default_rate': rates['std'],
                'sector_weight_general_economy': 1.0,
            })

    return pd.DataFrame(rows)
