"""
UPDATE — rodado em cron pelo GitHub Actions.

Estratégia híbrida:
1. Consulta /competitions/WC/matches pra ver quais estão FINISHED (1 chamada)
2. Pra cada FINISHED que ainda não está no nosso banco, consulta o
   endpoint individual /matches/{id} (que sempre tem o placar atualizado,
   ao contrário do bulk que tem delay no free tier)
3. Faz UPSERT em official_results

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
    """Lista jogos FINISHED. Pega TODOS os matches e filtra em Python —
    o filtro ?status=FINISHED da API às vezes retorna 0 mesmo havendo jogos
    encerrados (algum cache deles)."""
    url = f'{API_BASE}/competitions/{COMPETITION}/matches'
    r = requests.get(url, headers=api_headers(cfg['football_token']), timeout=30)
    if r.status_code != 200:
        print(f'❌ HTTP {r.status_code}: {r.text[:300]}', file=sys.stderr)
        sys.exit(1)
    all_matches = r.json().get('matches', []) or []
    finished = [m for m in all_matches if m.get('status') == 'FINISHED']
    print(f'   (total no endpoint: {len(all_matches)} | FINISHED: {len(finished)})')
    return finished


def fetch_single_match(cfg, match_id):
    """Endpoint individual — sempre tem o placar correto, mesmo quando o bulk vem NULL."""
    url = f'{API_BASE}/matches/{match_id}'
    r = requests.get(url, headers=api_headers(cfg['football_token']), timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def fetch_mapped_games(cfg):
    """{ external_fixture_id: {id, sel1, sel2} } dos jogos mapeados no Supabase."""
    url = (
        f'{cfg["supabase_url"]}/rest/v1/games'
        '?select=id,sel1,sel2,external_fixture_id'
        '&external_fixture_id=not.is.null'
    )
    r = requests.get(url, headers=sb_headers(cfg['supabase_key']), timeout=30)
    r.raise_for_status()
    return {row['external_fixture_id']: row for row in r.json()}


def fetch_existing_results(cfg):
    """Set { game_id } dos placares já gravados — pra não re-consultar."""
    url = f'{cfg["supabase_url"]}/rest/v1/official_results?select=game_id'
    r = requests.get(url, headers=sb_headers(cfg['supabase_key']), timeout=30)
    r.raise_for_status()
    return {row['game_id'] for row in r.json()}


def upsert_result(cfg, game_id, gols_sel1, gols_sel2):
    url = f'{cfg["supabase_url"]}/rest/v1/official_results'
    headers = sb_headers(
        cfg['supabase_key'],
        prefer='resolution=merge-duplicates,return=minimal',
    )
    payload = {'game_id': game_id, 'gols_sel1': gols_sel1, 'gols_sel2': gols_sel2}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()


def extract_score(match):
    """Extrai (home, away) do score.fullTime. Retorna (None, None) se não houver."""
    full = (match.get('score') or {}).get('fullTime') or {}
    return full.get('home'), full.get('away')


def main():
    cfg = get_config()

    print('🔍 Buscando jogos encerrados na football-data.org…')
    finished = fetch_finished_matches(cfg)
    print(f'   {len(finished)} matches com status FINISHED.')

    mapping = fetch_mapped_games(cfg)
    print(f'   {len(mapping)} jogos da base têm fixture mapeado.')

    existing = fetch_existing_results(cfg)
    print(f'   {len(existing)} placares já estão no banco (serão pulados).\n')

    if not mapping:
        print('❌ Nenhum jogo está mapeado. Rode o bootstrap antes.', file=sys.stderr)
        sys.exit(1)

    updated, unmapped, fallback, pendentes, errors = 0, 0, 0, 0, 0

    for m in finished:
        ext_id = m['id']
        g = mapping.get(ext_id)
        if not g:
            unmapped += 1
            continue

        # Já gravamos? Pula — economiza chamada de API.
        if g['id'] in existing:
            continue

        # Tenta o placar do bulk
        h_goals, a_goals = extract_score(m)
        used_fallback = False

        # Bulk veio NULL → fallback no endpoint individual
        if h_goals is None or a_goals is None:
            single = fetch_single_match(cfg, ext_id)
            if single:
                h_goals, a_goals = extract_score(single)
                if h_goals is not None and a_goals is not None:
                    used_fallback = True

        # Mesmo assim NULL? API ainda não tem — pula esse e tenta no próximo cron.
        if h_goals is None or a_goals is None:
            print(f'  ⏳ Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}): '
                  f'FINISHED mas placar ainda NULL — tenta no próximo ciclo')
            pendentes += 1
            continue

        # Determina orientação (home da API = sel1 ou sel2 da nossa base?)
        home_name = (m.get('homeTeam') or {}).get('name', '')
        if team_matches(home_name, g['sel1']):
            gols_sel1, gols_sel2 = h_goals, a_goals
        else:
            gols_sel1, gols_sel2 = a_goals, h_goals

        try:
            upsert_result(cfg, g['id'], gols_sel1, gols_sel2)
            tag = ' (via /matches/{id})' if used_fallback else ''
            print(f'  ✅ Jogo #{g["id"]:>2} ({g["sel1"]} × {g["sel2"]}): '
                  f'{gols_sel1} × {gols_sel2}{tag}')
            updated += 1
            if used_fallback:
                fallback += 1
        except requests.HTTPError as e:
            print(f'  ❌ Erro ao gravar jogo #{g["id"]}: {e}', file=sys.stderr)
            errors += 1

    print(f'\n✨ {updated} resultado(s) atualizado(s).')
    if fallback:
        print(f'   {fallback} veio(vieram) do endpoint individual (bulk estava NULL).')
    if pendentes:
        print(f'   {pendentes} jogo(s) FINISHED ainda sem placar nos dois endpoints — '
              f'serão tentados no próximo ciclo.')
    if unmapped:
        print(f'   {unmapped} match(es) sem mapeamento (esperado pra knockout antes do sorteio).')
    if errors:
        print(f'❌ {errors} erro(s) ao gravar.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
