"""
DEBUG — testa 3 endpoints da football-data.org pra entender por que o placar
não está aparecendo. Compara /competitions/WC/matches × /matches/{id} × /matches.
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

HEADERS = {'X-Auth-Token': token}

ICONS = {
    'FINISHED': '✅', 'IN_PLAY': '🔴', 'PAUSED': '⏸️', 'TIMED': '📅',
    'SCHEDULED': '📅', 'POSTPONED': '⏳', 'SUSPENDED': '⏸️',
    'CANCELLED': '❌', 'AWARDED': '⚖️',
}


def safe_team(team_obj):
    if not team_obj:
        return 'TBD'
    return (team_obj.get('name') or 'TBD')[:22]


def safe_score(m):
    s = (m.get('score') or {}).get('fullTime') or {}
    sh, sa = s.get('home'), s.get('away')
    if sh is None or sa is None:
        return 'NULL'
    return f'{sh}×{sa}'


# ─── ENDPOINT 1: /v4/matches (mesmo da homepage) ─────────────────
print('🧪 ENDPOINT 1 — /v4/matches (mesmo da homepage deles)')
r = requests.get(f'{API_BASE}/matches', headers=HEADERS, timeout=30)
if r.status_code == 200:
    data = r.json().get('matches', []) or []
    wc = [m for m in data if (m.get('competition') or {}).get('code') == 'WC']
    print(f'   Total retornado: {len(data)} | Da Copa: {len(wc)}')
    for m in wc:
        print(f'   {m["id"]}  status={m["status"]:<10} placar={safe_score(m)}  '
              f'{safe_team(m.get("homeTeam"))} × {safe_team(m.get("awayTeam"))}')
else:
    print(f'   ⚠️  HTTP {r.status_code}: {r.text[:200]}')
print()

# ─── ENDPOINT 2: /v4/competitions/WC/matches (o que usamos no cron) ──
print('🧪 ENDPOINT 2 — /v4/competitions/WC/matches (o que o cron usa)')
r = requests.get(f'{API_BASE}/competitions/{COMPETITION}/matches',
                 headers=HEADERS, timeout=30)
matches = r.json().get('matches', []) if r.status_code == 200 else []
print(f'   Total retornado: {len(matches)}')

finished = [m for m in matches if m['status'] == 'FINISHED']
print(f'   FINISHED: {len(finished)}')
for m in finished:
    print(f'   {m["id"]}  placar={safe_score(m)}  '
          f'{safe_team(m.get("homeTeam"))} × {safe_team(m.get("awayTeam"))}')
print()

# ─── ENDPOINT 3: /v4/matches/{id} pra cada FINISHED sem placar ───
print('🧪 ENDPOINT 3 — /v4/matches/{id} individual pros FINISHED sem placar')
suspeitos = [m for m in finished if safe_score(m) == 'NULL']
if not suspeitos:
    print('   Nenhum FINISHED sem placar — nada a testar.')
else:
    for m in suspeitos:
        mid = m['id']
        r2 = requests.get(f'{API_BASE}/matches/{mid}', headers=HEADERS, timeout=30)
        if r2.status_code == 200:
            placar = safe_score(r2.json())
            print(f'   Match {mid}: status={r2.json().get("status")}  placar={placar}')
        else:
            print(f'   Match {mid}: HTTP {r2.status_code}')
print()

# ─── RESUMO POR STATUS ──────────────────────────────────────────
print('📈 RESUMO POR STATUS (do endpoint /competitions/WC/matches):')
for status, qtd in Counter(m['status'] for m in matches).most_common():
    print(f'   {ICONS.get(status, "❓")} {status}: {qtd}')

# ─── TABELA COMPLETA (compacta) ─────────────────────────────────
print('\n📋 TODOS OS 104 JOGOS:')
print(f'{"#":>5}  {"Status":<10}  {"Data UTC":<17}  {"Mandante":>22}  {"Placar":^7}  {"Visitante":<22}')
print('─' * 100)
for m in sorted(matches, key=lambda x: x.get('utcDate', '')):
    ic = ICONS.get(m['status'], '❓')
    date = m.get('utcDate', '')[:16].replace('T', ' ')
    print(f'{m["id"]:>5}  {ic} {m["status"]:<8}  {date:<17}  '
          f'{safe_team(m.get("homeTeam")):>22}  {safe_score(m):^7}  {safe_team(m.get("awayTeam")):<22}')
