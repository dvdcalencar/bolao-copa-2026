"""
UPDATE — rodado em cron pelo GitHub Actions.
Busca jogos encerrados na football-data.org e faz UPSERT em official_results.

Variáveis de ambiente: FOOTBALL_DATA_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import sys
import requests

from common import (
    COMPETITION, API_BASE,
    get_config, api_headers, sb_headers,
    team_matches,
)


def fetch_finished_matches(cfg):
    """Pega matches com status FINISHED."""
    url = f'{API_BASE}/competitions/{COMPETITION}/matches'
    params = {'status': 'FINISHED'}
    r = requests.get(url, headers=api_headers(cfg['football_token']),
                     params=params, timeout=30)
    if r.status_code != 200:
        print(f'❌ HTTP {r.status_code}: {r.text[:300]}', file=sys.stderr)
        sys.exit(1)
    return r.json().get('matches', []) or []


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

    print('🔍 Buscando jogos encerrados na football-data.org…')
    finished = fetch_finished_matches(cfg)
    print(f'   {len(finished)} matches com status FINISHED.')

    print('🔍 Buscando mapeamento de jogos no Supabase…')
    mapping = fetch_mapped_games(cfg)
    print(f'   {len(mapping)} jogos da base têm fixture mapeado.\n')

    if not mapping:
        print('❌ Nenhum jogo está mapeado. Rode o bootstrap_fixture_mapping.py primeiro.',
              file=sys.stderr)
        sys.exit(1)

    updated, unmapped, errors = 0, 0, 0

    for m in finished:
        ext_id = m['id']
        g = mapping.get(ext_id)
        if not g:
            unmapped += 1
            continue

        # Score do tempo regulamentar (fullTime)
        full = (m.get('score') or {}).get('fullTime') or {}
        h_goals = full.get('home')
        a_goals = full.get('away')
        if h_goals is None or a_goals is None:
            continue

        home_name = (m.get('homeTeam') or {}).get('name', '')

        # home da API = sel1 ou sel2 da base? Determina pela comparação de nomes.
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
        print(f'   {unmapped} match(es) encerrado(s) sem mapeamento.')
    if errors:
        print(f'❌ {errors} erro(s) ao gravar.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
