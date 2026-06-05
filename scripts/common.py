"""
Funções e constantes compartilhadas entre bootstrap e update.

Fonte: football-data.org v4. Auth: header X-Auth-Token.
Competition WC = FIFA World Cup.
"""

import os
import sys
import unicodedata

COMPETITION = 'WC'
API_BASE    = 'https://api.football-data.org/v4'


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f'❌ Variável de ambiente {name} não definida.', file=sys.stderr)
        sys.exit(1)
    return v


def get_config():
    return {
        'football_token':  env('FOOTBALL_DATA_TOKEN'),
        'supabase_url':    env('SUPABASE_URL').rstrip('/'),
        'supabase_key':    env('SUPABASE_SERVICE_KEY'),
    }


def api_headers(token: str) -> dict:
    return {'X-Auth-Token': token}


def sb_headers(sb_key: str, *, prefer: str | None = None) -> dict:
    h = {
        'apikey':        sb_key,
        'Authorization': f'Bearer {sb_key}',
        'Content-Type':  'application/json',
    }
    if prefer:
        h['Prefer'] = prefer
    return h


def normalize(s: str) -> str:
    """Lowercase + remove acentos/pontuação simples — pra matching fuzzy."""
    if not s:
        return ''
    nfkd = unicodedata.normalize('NFKD', s)
    no_acc = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return (no_acc
            .lower()
            .replace('-', ' ')
            .replace("'", '')
            .replace('.', '')
            .strip())


# Mapeamento PT → lista de nomes aceitos (a API pode usar variações:
# Türkiye/Turkey, Korea Republic/South Korea, Czechia/Czech Republic etc.)
PT_TO_EN = {
    'México':                ['Mexico'],
    'África do Sul':         ['South Africa'],
    'Coreia do Sul':         ['Korea Republic', 'South Korea', 'Korea'],
    'República Tcheca':      ['Czechia', 'Czech Republic'],
    'Canadá':                ['Canada'],
    'Bósnia e Herzegovina':  ['Bosnia-Herzegovina', 'Bosnia and Herzegovina',
                              'Bosnia & Herzegovina', 'Bosnia'],
    'Estados Unidos':        ['United States', 'USA'],
    'Paraguai':              ['Paraguay'],
    'Austrália':             ['Australia'],
    'Turquia':               ['Türkiye', 'Turkiye', 'Turkey'],
    'Catar':                 ['Qatar'],
    'Suíça':                 ['Switzerland'],
    'Brasil':                ['Brazil'],
    'Marrocos':              ['Morocco'],
    'Haiti':                 ['Haiti'],
    'Escócia':               ['Scotland'],
    'Alemanha':              ['Germany'],
    'Curaçao':               ['Curaçao', 'Curacao'],
    'Holanda':               ['Netherlands'],
    'Japão':                 ['Japan'],
    'Costa do Marfim':       ["Côte d'Ivoire", 'Cote d Ivoire', 'Ivory Coast'],
    'Equador':               ['Ecuador'],
    'Suécia':                ['Sweden'],
    'Tunísia':               ['Tunisia'],
    'Espanha':               ['Spain'],
    'Cabo Verde':            ['Cape Verde', 'Cabo Verde'],
    'Bélgica':               ['Belgium'],
    'Egito':                 ['Egypt'],
    'Arábia Saudita':        ['Saudi Arabia'],
    'Uruguai':               ['Uruguay'],
    'Irã':                   ['Iran', 'IR Iran', 'Islamic Republic of Iran'],
    'Nova Zelândia':         ['New Zealand'],
    'França':                ['France'],
    'Senegal':               ['Senegal'],
    'Iraque':                ['Iraq'],
    'Noruega':               ['Norway'],
    'Argentina':             ['Argentina'],
    'Argélia':               ['Algeria'],
    'Áustria':               ['Austria'],
    'Jordânia':              ['Jordan'],
    'Portugal':              ['Portugal'],
    'RD Congo':              ['Congo DR', 'DR Congo', 'Democratic Republic of Congo',
                              'Congo Democratic Republic'],
    'Inglaterra':            ['England'],
    'Croácia':               ['Croatia'],
    'Gana':                  ['Ghana'],
    'Panamá':                ['Panama'],
    'Uzbequistão':           ['Uzbekistan'],
    'Colômbia':              ['Colombia'],
}


def team_matches(api_name: str, pt_name: str) -> bool:
    """Tenta bater nome vindo da API com nome em pt-BR.
    Estratégias (em ordem):
      1. Match exato (normalizado) contra qualquer alias em PT_TO_EN
      2. Match exato contra o próprio nome pt-BR
      3. Substring em qualquer direção como fallback
    """
    if not api_name or not pt_name:
        return False
    aliases = PT_TO_EN.get(pt_name, [pt_name])
    if isinstance(aliases, str):
        aliases = [aliases]
    api_n = normalize(api_name)
    for cand in [*aliases, pt_name]:
        cand_n = normalize(cand)
        if not cand_n:
            continue
        if api_n == cand_n:
            return True
        if cand_n in api_n or api_n in cand_n:
            return True
    return False
