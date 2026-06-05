"""
Funções e constantes compartilhadas entre bootstrap e update.

Fonte de dados: football-data.org v4 (plano grátis cobre World Cup).
- Base: https://api.football-data.org/v4
- Auth: header X-Auth-Token
- Competição "WC" = FIFA World Cup
"""

import os
import sys
import unicodedata

COMPETITION  = 'WC'   # FIFA World Cup (id padrão no football-data.org)
API_BASE     = 'https://api.football-data.org/v4'


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f'❌ Variável de ambiente {name} não definida.', file=sys.stderr)
        sys.exit(1)
    return v


def get_config():
    """Lê as 3 variáveis necessárias do ambiente."""
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
    """Lowercase + remove acentos + remove pontuação simples — pra matching fuzzy."""
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


# Tradução pt-BR (como está no banco) → inglês (como vem da football-data.org).
# Cobertura: nomes diretos + variações comuns. Se a API mudar a grafia, edita aqui.
PT_TO_EN = {
    'México':                'Mexico',
    'África do Sul':         'South Africa',
    'Coreia do Sul':         'South Korea',
    'República Tcheca':      'Czech Republic',
    'Canadá':                'Canada',
    'Bósnia e Herzegovina':  'Bosnia-Herzegovina',
    'Estados Unidos':        'United States',
    'Paraguai':              'Paraguay',
    'Austrália':             'Australia',
    'Turquia':               'Turkey',
    'Catar':                 'Qatar',
    'Suíça':                 'Switzerland',
    'Brasil':                'Brazil',
    'Marrocos':              'Morocco',
    'Haiti':                 'Haiti',
    'Escócia':               'Scotland',
    'Alemanha':              'Germany',
    'Curaçao':               'Curacao',
    'Holanda':               'Netherlands',
    'Japão':                 'Japan',
    'Costa do Marfim':       "Côte d'Ivoire",
    'Equador':               'Ecuador',
    'Suécia':                'Sweden',
    'Tunísia':               'Tunisia',
    'Espanha':               'Spain',
    'Cabo Verde':            'Cape Verde',
    'Bélgica':               'Belgium',
    'Egito':                 'Egypt',
    'Arábia Saudita':        'Saudi Arabia',
    'Uruguai':               'Uruguay',
    'Irã':                   'Iran',
    'Nova Zelândia':         'New Zealand',
    'França':                'France',
    'Senegal':               'Senegal',
    'Iraque':                'Iraq',
    'Noruega':               'Norway',
    'Argentina':             'Argentina',
    'Argélia':               'Algeria',
    'Áustria':               'Austria',
    'Jordânia':              'Jordan',
    'Portugal':              'Portugal',
    'RD Congo':              'DR Congo',
    'Inglaterra':            'England',
    'Croácia':               'Croatia',
    'Gana':                  'Ghana',
    'Panamá':                'Panama',
    'Uzbequistão':           'Uzbekistan',
    'Colômbia':              'Colombia',
}


def team_matches(api_name: str, pt_name: str) -> bool:
    """Heurística: bate nome vindo da API com nome em pt-BR do nosso banco.

    Estratégias (em ordem):
      1. Match exato normalizado contra a tradução pt→en (PT_TO_EN).
      2. Match exato normalizado contra o próprio nome pt-BR
         (caso a API use acentuação igual à nossa).
      3. Substring (em qualquer direção) como fallback —
         cobre variações tipo "USA" vs "United States" ou
         "Iran" vs "IR Iran".
    """
    if not api_name or not pt_name:
        return False
    en_name = PT_TO_EN.get(pt_name, pt_name)
    api_n = normalize(api_name)
    en_n  = normalize(en_name)
    pt_n  = normalize(pt_name)
    if api_n == en_n or api_n == pt_n:
        return True
    return (en_n in api_n) or (api_n in en_n) or (pt_n in api_n)
