"""
UPDATE — rodado em cron pelo GitHub Actions.
Busca jogos encerrados na API-Football e faz UPSERT em official_results.

Variáveis de ambiente esperadas:
  API_FOOTBALL_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import sys
import requests

from common import (
    LEAGUE_ID, SEASON, API_BASE,
    get_config, api_headers, sb_headers,
    team_matches,
)


def fetch_finished_fixtures(cfg):
    """Pega fixtures com status FT (Match Finished)."""
    url = f'{API_BASE}/fixtures'
    params = {'league': LEAGUE_ID, 'season': SEASON, 'status': 'FT'}
    r = requests.get(url, headers=api_headers(cfg['api_key']), params=params, timeout=30)
    r.raise_for_status()
    return r.json().get('response', []) or []


def fetch_mapped_games(cfg):
    """Pega { external_fixture_id: {id, sel1, sel2} } dos jogos mapeados."""
    url = (
        f'{cfg["supabase_url"]}/rest/v1/games'
        '?select=id,sel1,sel2,external_fixture_id'
        '&external_fixture_id=not.is.null'
    )
    r = requests.get(url, headers=sb_headers(cfg['supabase_key']), timeout=30)
    r.raise_for_status()
    return {row['external_fixture_id']: row for row in r.json()}


def upsert_result(cfg, game_id, gols_sel1, gols_sel2):
    url = f'{cfg["supabase_url"]}/rest/v1/official_results'
    headers = sb_headers(
        cfg['supabase_key'],
        prefer='resolution=merge-duplicates,return=minimal',
    )
    payload = {
        'game_id':   game_id,
        'gols_sel1': gols_sel1,
        'gols_sel2': gols_sel2,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()


def main():
    cfg = get_config()

    print('🔍 Buscando jogos encerrados na API…')
    finished = fetch_finished_fixtures(cfg)
    print(f'   {len(finished)} fixtures com status FT.')

    print('🔍 Buscando mapeamento de jogos no Supabase…')
    mapping = fetch_mapped_games(cfg)
    print(f'   {len(mapping)} jogos da base têm fixture mapeado.\n')

    if not mapping:
        print('❌ Nenhum jogo está mapeado. Rode o bootstrap_fixture_mapping.py primeiro.',
              file=sys.stderr)
        sys.exit(1)

    updated, unmapped, errors = 0, 0, 0

    for f in finished:
        ext_id = f['fixture']['id']
        g = mapping.get(ext_id)
        if not g:
            unmapped += 1
            continue

        h_goals = f['goals']['home']
        a_goals = f['goals']['away']
        if h_goals is None or a_goals is None:
            continue

        home_name = f['teams']['home']['name']

        # Descobre a ordem: home da API corresponde a sel1 ou sel2 da nossa base?
        if team_matches(home_name, g['sel1']):
            gols_sel1, gols_sel2 = h_goals, a_goals
        else:
            gols_sel1, gols_sel2 = a_goals, h_goals

        try:
            upsert_result(cfg, g['id'], gols_sel1, gols_sel2)
            print(f'  ✅ Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}): {gols_sel1} × {gols_sel2}')
            updated += 1
        except requests.HTTPError as e:
            print(f'  ❌ Erro ao gravar jogo #{g["id"]}: {e}', file=sys.stderr)
            errors += 1

    print(f'\n✨ {updated} resultado(s) atualizado(s).')
    if unmapped:
        print(f'   {unmapped} fixture(s) encerrado(s) sem mapeamento (rode o bootstrap).')
    if errors:
        print(f'❌ {errors} erro(s) ao gravar — saindo com código 1.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
