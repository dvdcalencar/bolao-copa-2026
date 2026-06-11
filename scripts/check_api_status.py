"""
DEBUG — mostra o status ATUAL de todos os 72 jogos direto da
football-data.org. Útil pra confirmar se um placar já foi marcado
como FINISHED na fonte ou se a API ainda está atrasada.

Variável de ambiente: FOOTBALL_DATA_TOKEN
"""

import os
import sys
import requests
from collections import Counter

API_BASE    = 'https://api.football-data.org/v4'
COMPETITION = 'WC'

token = os.environ.get('FOOTBALL_DATA_TOKEN')
if not token:
    print('❌ FOOTBALL_DATA_TOKEN não está definido.', file=sys.stderr)
    sys.exit(1)

url = f'{API_BASE}/competitions/{COMPETITION}/matches'
r = requests.get(url, headers={'X-Auth-Token': token}, timeout=30)
if r.status_code != 200:
    print(f'❌ HTTP {r.status_code}: {r.text[:200]}', file=sys.stderr)
    sys.exit(1)

matches = r.json().get('matches', []) or []

ICONS = {
    'FINISHED':  '✅',
    'IN_PLAY':   '🔴',
    'PAUSED':    '⏸️',
    'TIMED':     '📅',
    'SCHEDULED': '📅',
    'POSTPONED': '⏳',
    'SUSPENDED': '⏸️',
    'CANCELLED': '❌',
    'AWARDED':   '⚖️',
}

# ─── TESTE EXTRA: endpoint /v4/matches (que a homepage deles usa) ──
print('🧪 Testando endpoint /v4/matches (mesmo da homepage)…')
r_alt = requests.get(f'{API_BASE}/matches',
                     headers={'X-Auth-Token': token}, timeout=30)
if r_alt.status_code == 200:
    alt_matches = r_alt.json().get('matches', [])
    print(f'   /v4/matches retornou {len(alt_matches)} jogos hoje (todas competições).')
    # Procura jogos da Copa neles
    wc_alt = [m for m in alt_matches if (m.get('competition') or {}).get('code') == 'WC']
    print(f'   Desses, {len(wc_alt)} são da Copa do Mundo (WC).')
    fin_alt = [m for m in wc_alt if m['status'] == 'FINISHED']
    if fin_alt:
        print(f'   Jogos FINISHED da Copa via /v4/matches:')
        for m in fin_alt:
            s = (m.get('score') or {}).get('fullTime') or {}
            sh, sa = s.get('home'), s.get('away')
            h = safe_team(m.get('homeTeam'))
            a = safe_team(m.get('awayTeam'))
            score = f"{sh}×{sa}" if sh is not None else "NULL"
            print(f'      Match {m["id"]}: {h} {score} {a}')
else:
    print(f'   ⚠️  /v4/matches retornou HTTP {r_alt.status_code}')
print()

print(f'📊 {len(matches)} matches retornados via /competitions/WC/matches.\n')
print(f'{"#":>5} {"Status":<11} {"Data UTC":<17} {"Mandante":>22}  {"Placar":^8}  {"Visitante":<22}')
print('─' * 100)

def safe_team(team_obj):
    """Trata homeTeam/awayTeam que pode ser None (jogo de mata-mata sem time definido)."""
    if not team_obj:
        return 'TBD'
    name = team_obj.get('name')
    return (name or 'TBD')[:22]

for m in sorted(matches, key=lambda x: x.get('utcDate', '')):
    ic     = ICONS.get(m['status'], '❓')
    ext_id = m['id']
    date   = m.get('utcDate', '')[:16].replace('T', ' ')
    home   = safe_team(m.get('homeTeam'))
    away   = safe_team(m.get('awayTeam'))
    s      = (m.get('score') or {}).get('fullTime') or {}
    sh, sa = s.get('home'), s.get('away')
    score  = f"{sh}×{sa}" if sh is not None and sa is not None else '─×─'
    print(f'{ext_id:>5} {ic} {m["status"]:<9} {date:<17} {home:>22}  {score:^8}  {away:<22}')

print('\n📈 RESUMO POR STATUS:')
for status, qtd in Counter(m['status'] for m in matches).most_common():
    print(f'   {ICONS.get(status, "❓")} {status}: {qtd}')

# ─── INVESTIGAÇÃO: FINISHED sem placar ───────────────────────
suspeitos = []
for m in matches:
    if m['status'] != 'FINISHED':
        continue
    s = (m.get('score') or {}).get('fullTime') or {}
    if s.get('home') is None or s.get('away') is None:
        suspeitos.append(m)

if suspeitos:
    print(f'\n🔎 INVESTIGANDO {len(suspeitos)} jogo(s) FINISHED sem placar — '
          f'consultando /matches/{{id}} (mesmo endpoint que a homepage usa):\n')
    for m in suspeitos:
        mid  = m['id']
        home = safe_team(m.get('homeTeam'))
        away = safe_team(m.get('awayTeam'))
        r2 = requests.get(f'{API_BASE}/matches/{mid}',
                          headers={'X-Auth-Token': token}, timeout=30)
        if r2.status_code != 200:
            print(f'   Match {mid} ({home} × {away}): HTTP {r2.status_code}')
            continue
        m2 = r2.json()
        s2 = (m2.get('score') or {}).get('fullTime') or {}
        sh, sa = s2.get('home'), s2.get('away')
        if sh is not None and sa is not None:
            print(f'   ⚠️  Match {mid} ({home} × {away}):')
            print(f'      /competitions/WC/matches → status FINISHED, placar NULL')
            print(f'      /matches/{mid}            → status FINISHED, placar {sh}×{sa}  ← TEM!')
        else:
            print(f'   Match {mid} ({home} × {away}): ambos endpoints sem placar.')
    print(f'\n   Se o endpoint individual já tem o placar mas o do filtro de competição não,')
    print(f'   confirma que tem CACHE no endpoint /competitions/WC/matches que a gente usa.')
    print(f'   Solução: trocar a query pra usar /matches?competitions=WC ou puxar individual.')
