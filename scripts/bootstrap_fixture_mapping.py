"""
BOOTSTRAP — rode UMA ÚNICA VEZ pra vincular cada jogo (id 1-72) ao match
externo da football-data.org.

Pré-requisitos:
- A coluna games.external_fixture_id existe
  (rodar schema_update_external_id.sql no Supabase antes)
- Secrets/variáveis: FOOTBALL_DATA_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY

Roda pela aba Actions do GitHub: workflow "Bootstrap Mapping (manual)".
"""

import sys
import requests

from common import (
    COMPETITION, API_BASE,
    get_config, api_headers, sb_headers,
    team_matches,
)


def fetch_api_matches(cfg):
    """Busca todos os jogos da Copa pela football-data.org."""
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
    """Busca os 72 jogos do Supabase."""
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


def match_for_game(game, matches):
    """Acha o(s) match(es) da API que batem com o jogo do banco.

    Critério: data do jogo (utcDate vs games.dia) + nomes dos dois times
    em qualquer ordem (home/away).
    """
    target_date = game['dia']
    sel1, sel2 = game['sel1'], game['sel2']

    candidates = []
    for m in matches:
        # utcDate vem em ISO: "2026-06-11T20:00:00Z" — só os 10 primeiros chars
        if m.get('utcDate', '')[:10] != target_date:
            continue
        home = (m.get('homeTeam') or {}).get('name', '')
        away = (m.get('awayTeam') or {}).get('name', '')
        if (team_matches(home, sel1) and team_matches(away, sel2)) or \
           (team_matches(home, sel2) and team_matches(away, sel1)):
            candidates.append(m)
    return candidates


def main():
    cfg = get_config()

    matches = fetch_api_matches(cfg)
    if not matches:
        print('❌ Nenhum match encontrado. Verifique o token e se a Copa 2026 está no plano.',
              file=sys.stderr)
        sys.exit(1)

    games = fetch_games(cfg)
    print(f'\n📋 {len(games)} jogos no Supabase. Iniciando matching…\n')

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
            issues.append((g, 'sem match'))
        else:
            print(f'  ⚠️  Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}) — {len(cands)} candidatos:')
            for c in cands:
                print(f'       match {c["id"]}: {c["homeTeam"]["name"]} × {c["awayTeam"]["name"]} ({c["utcDate"][:10]})')
            issues.append((g, f'{len(cands)} candidatos ambíguos'))

    print(f'\n✨ Resultado: {matched}/{len(games)} jogos mapeados.')
    if issues:
        print(f'⚠️  {len(issues)} jogos com problema. Revise PT_TO_EN em common.py.')
        sys.exit(1)


if __name__ == '__main__':
    main()
