"""
Funções e constantes compartilhadas entre bootstrap e update.
"""

import os
import sys
import unicodedata

LEAGUE_ID = 1       # FIFA World Cup (League ID padrão da API-Football)
SEASON    = 2026
API_BASE  = 'https://v3.football.api-sports.io'


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        print(f'❌ Variável de ambiente {name} não definida.', file=sys.stderr)
        sys.exit(1)
    return v


def get_config():
    """Lê as 3 variáveis necessárias do ambiente."""
    return {
        'api_key':         env('API_FOOTBALL_KEY'),
        'supabase_url':    env('SUPABASE_URL').rstrip('/'),
        'supabase_key':    env('SUPABASE_SERVICE_KEY'),
    }


def api_headers(api_key: str) -> dict:
    return {
        'x-rapidapi-key':  api_key,
        'x-rapidapi-host': 'v3.football.api-sports.io',
    }


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
    """Lowercase + remove acentos pra matching fuzzy."""
    if not s:
        return ''
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


# Tradução pt-BR (como está no banco) → inglês (como vem da API-Football).
# Se a API mudar a grafia de algum time, basta atualizar aqui.
PT_TO_EN = {
    'México':                'Mexico',
    'África do Sul':         'South Africa',
    'Coreia do Sul':         'South Korea',
    'República Tcheca':      'Czech Republic',
    'Canadá':                'Canada',
    'Bósnia e Herzegovina':  'Bosnia and Herzegovina',
    'Estados Unidos':        'USA',
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
    'Costa do Marfim':       'Ivory Coast',
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
    """Heurística: bate o nome vindo da API com o nome em pt-BR do nosso banco."""
    en_name = PT_TO_EN.get(pt_name, pt_name)
    api_n = normalize(api_name)
    pt_n  = normalize(pt_name)
    en_n  = normalize(en_name)
    if api_n == en_n or api_n == pt_n:
        return True
    # fallback: substring match (cobre variações como "USA" vs "United States")
    return en_n in api_n or api_n in en_n or pt_n in api_n
