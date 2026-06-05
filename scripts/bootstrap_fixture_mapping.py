"""
BOOTSTRAP — rode UMA ÚNICA VEZ pra vincular cada jogo (id 1-72) ao fixture
externo da API-Football.

Pré-requisitos:
- A coluna games.external_fixture_id existe
  (rodar schema_update_external_id.sql no Supabase antes)
- Variáveis de ambiente API_FOOTBALL_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

Como rodar localmente (no Windows PowerShell):
  $env:API_FOOTBALL_KEY="..."
  $env:SUPABASE_URL="https://wyfmrfrsczcpbtwwpuhi.supabase.co"
  $env:SUPABASE_SERVICE_KEY="sb_secret_..."
  python scripts/bootstrap_fixture_mapping.py

Ou via GitHub Actions: ver workflow `bootstrap-fixtures.yml` (manual trigger).
"""

import sys
import requests

from common import (
    LEAGUE_ID, SEASON, API_BASE,
    get_config, api_headers, sb_headers,
    team_matches,
)


def fetch_api_fixtures(cfg):
    url = f'{API_BASE}/fixtures'
    params = {'league': LEAGUE_ID, 'season': SEASON}
    print(f'🔍 Buscando fixtures da API-Football (league={LEAGUE_ID}, season={SEASON})…')
    r = requests.get(url, headers=api_headers(cfg['api_key']), params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    fixtures = data.get('response', []) or []
    print(f'   API retornou {len(fixtures)} fixtures.')
    if data.get('errors'):
        print(f'   ⚠️  Avisos da API: {data["errors"]}')
    return fixtures


def fetch_games(cfg):
    url = f'{cfg["supabase_url"]}/rest/v1/games?select=*&order=id'
    r = requests.get(url, headers=sb_headers(cfg['supabase_key']), timeout=30)
    r.raise_for_status()
    return r.json()


def update_game(cfg, game_id, external_id):
    url = f'{cfg["supabase_url"]}/rest/v1/games?id=eq.{game_id}'
    r = requests.patch(
        url,
        headers=sb_headers(cfg['supabase_key'], prefer='return=minimal'),
        json={'external_fixture_id': external_id},
        timeout=30,
    )
    r.raise_for_status()


def match_fixture(game, fixtures):
    target_date = game['dia']
    sel1, sel2 = game['sel1'], game['sel2']

    def matches(f):
        if f['fixture']['date'][:10] != target_date:
            return False
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        return (
            (team_matches(home, sel1) and team_matches(away, sel2)) or
            (team_matches(home, sel2) and team_matches(away, sel1))
        )

    return [f for f in fixtures if matches(f)]


def main():
    cfg = get_config()

    fixtures = fetch_api_fixtures(cfg)
    if not fixtures:
        print('❌ Nenhum fixture encontrado. Confirme a chave da API-Football,'
              ' a temporada (2026) e a league (1).', file=sys.stderr)
        sys.exit(1)

    games = fetch_games(cfg)
    print(f'\n📋 {len(games)} jogos no Supabase. Iniciando matching…\n')

    matched = 0
    issues = []

    for g in games:
        cands = match_fixture(g, fixtures)
        if len(cands) == 1:
            ext_id = cands[0]['fixture']['id']
            update_game(cfg, g['id'], ext_id)
            print(f'  ✅ Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) → fixture {ext_id}')
            matched += 1
        elif len(cands) == 0:
            print(f'  ⚠️  Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) — SEM MATCH')
            issues.append((g, 'sem match'))
        else:
            print(f'  ⚠️  Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) — {len(cands)} candidatos:')
            for c in cands:
                print(f'       fixture {c["fixture"]["id"]}: {c["teams"]["home"]["name"]} × {c["teams"]["away"]["name"]} ({c["fixture"]["date"][:10]})')
            issues.append((g, f'{len(cands)} candidatos ambíguos'))

    print(f'\n✨ Resultado: {matched}/{len(games)} jogos mapeados.')
    if issues:
        print(f'⚠️  {len(issues)} jogos com problema. Revise PT_TO_EN em common.py'
              ' ou faça matching manual no Supabase.')
        sys.exit(1)


if __name__ == '__main__':
    main()
