"""
BOOTSTRAP — vincula cada jogo (id 1-72) ao external_fixture_id do
football-data.org.

Estratégia: match por PAR DE TIMES (sel1 × sel2 em qualquer ordem),
sem exigir que a data bata. Se houver mais de um candidato (raro no group
stage onde cada par joga apenas 1 vez), prefere o que está na mesma data.
Mostra debug detalhado pra qualquer falha residual.
"""

import sys
import requests

from common import (
    COMPETITION, API_BASE,
    get_config, api_headers, sb_headers,
    team_matches,
)


def fetch_api_matches(cfg):
    url = f'{API_BASE}/competitions/{COMPETITION}/matches'
    print(f'🔍 Buscando matches em {url}…')
    r = requests.get(url, headers=api_headers(cfg['football_token']), timeout=30)
    if r.status_code != 200:
        print(f'❌ HTTP {r.status_code}: {r.text[:300]}', file=sys.stderr)
        sys.exit(1)
    data = r.json()
    matches = data.get('matches', []) or []
    print(f'   API retornou {len(matches)} matches.')
    return matches


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


def home_away(m):
    return (
        (m.get('homeTeam') or {}).get('name', ''),
        (m.get('awayTeam') or {}).get('name', ''),
    )


def match_for_game(game, matches):
    """Acha candidatos batendo PAR DE TIMES (independente da data)."""
    sel1, sel2 = game['sel1'], game['sel2']
    cands = []
    for m in matches:
        home, away = home_away(m)
        if (team_matches(home, sel1) and team_matches(away, sel2)) or \
           (team_matches(home, sel2) and team_matches(away, sel1)):
            cands.append(m)

    # Tiebreak: se mais de um, prefere mesma data
    if len(cands) > 1:
        same_date = [c for c in cands if c.get('utcDate', '')[:10] == game['dia']]
        if same_date:
            return same_date
    return cands


def debug_failure(game, matches):
    """Loga o que tem na API perto desse jogo, pra ajudar a diagnosticar."""
    sel1, sel2 = game['sel1'], game['sel2']

    same_date = [m for m in matches if m.get('utcDate', '')[:10] == game['dia']]
    if same_date:
        print(f'      Jogos na data {game["dia"]} na API:')
        for m in same_date[:6]:
            h, a = home_away(m)
            print(f'        • {h} × {a}  ({m["utcDate"][11:16]} UTC)')
    else:
        print(f'      ⓘ Nenhum jogo na data {game["dia"]} na API.')

    has_sel1 = [m for m in matches if team_matches(home_away(m)[0], sel1)
                                   or team_matches(home_away(m)[1], sel1)]
    has_sel2 = [m for m in matches if team_matches(home_away(m)[0], sel2)
                                   or team_matches(home_away(m)[1], sel2)]
    print(f'      "{sel1}" aparece em {len(has_sel1)} match(es). '
          f'"{sel2}" aparece em {len(has_sel2)} match(es).')


def main():
    cfg = get_config()
    matches = fetch_api_matches(cfg)
    if not matches:
        print('❌ Nenhum match retornado pela API.', file=sys.stderr)
        sys.exit(1)

    games = fetch_games(cfg)
    print(f'\n📋 {len(games)} jogos no Supabase. Iniciando matching '
          f'(por par de times, sem exigir data)…\n')

    matched = 0
    issues = []

    for g in games:
        cands = match_for_game(g, matches)
        if len(cands) == 1:
            ext_id = cands[0]['id']
            update_game(cfg, g['id'], ext_id)
            print(f'  ✅ Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) → match {ext_id}')
            matched += 1
        elif len(cands) == 0:
            print(f'  ⚠️  Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) — SEM MATCH')
            debug_failure(g, matches)
            issues.append((g, 'sem match'))
        else:
            print(f'  ⚠️  Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) — {len(cands)} ambíguos:')
            for c in cands:
                h, a = home_away(c)
                print(f'       match {c["id"]}: {h} × {a} ({c["utcDate"][:10]})')
            issues.append((g, f'{len(cands)} candidatos'))

    print(f'\n✨ Resultado: {matched}/{len(games)} jogos mapeados.')
    if issues:
        print(f'⚠️  {len(issues)} jogos com problema. Cola o log e me passa pra ajustar.')
        sys.exit(1)


if __name__ == '__main__':
    main()
