import requests
import time
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from models import Partida
from config import BEARER_TOKEN, IDS_TIMES
from discord import registrar_log

log = logging.getLogger(__name__)

def formatar_data_BR(data_api):
    dt_utc = datetime.fromisoformat(data_api.replace('Z', '+00:00'))
    dt_br = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
    data_formatada = dt_br.strftime('%Y-%m-%dT%H:%M:%SZ')
    return data_formatada

def get_matches_48h():
    now = datetime.now(timezone.utc)
    limit_48h = now + timedelta(hours=48)
    
    start_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = limit_48h.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = "https://api.pandascore.co/csgo/matches"

    params = {
        "range[begin_at]": f"{start_str},{end_str}",
        "filter[status]": "not_started",
        "filter[opponent_id]": ",".join(map(str, IDS_TIMES)),
        "sort": "begin_at",
    }

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    tentativas = 3
    for i in range(tentativas):
        try:
            log.info(f"Tentativa {i+1} de {tentativas}...")
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status() 
            
            
            if(response):
                log.info("Sucesso na requisição!")
                return response.json()
            else:
                return []

        except requests.exceptions.RequestException as e:
            if(response):
                status_code = response
            else:
                status_code = 'Erro desconhecido'
            log.warning(f"Falha na tentativa {i+1}: Status {status_code}")
            
            if i < tentativas - 1: # Se não for a última tentativa
                espera = (i + 1) * 5 # 5s, 10s...
                log.info(f"Aguardando {espera}s para tentar novamente...")
                time.sleep(espera)
            else:
                registrar_log(f"Erro persistente após {tentativas} tentativas: {e}")
                return []
        
def processar_matches() -> list[Partida]:
    partidas_brutas = get_matches_48h()
    partidas_limpas = []

    for partida in partidas_brutas:
        oponentes = partida.get('opponents', [])

        time_1 = oponentes[0]['opponent']['name'] if len(oponentes) >= 1 else "TBD"
        time_2 = oponentes[1]['opponent']['name'] if len(oponentes) >= 2 else "TBD"
        
        dados_liga = partida.get('league', {})

        partidas_limpas.append(Partida(
            id_api=partida['id'],
            time_1=time_1,
            time_2=time_2,
            liga_nome=dados_liga.get('name', 'Liga Desconhecida'),
            liga_logo=dados_liga.get('image_url') or "https://static.wikia.nocookie.net/logopedia/images/4/49/Counter-Strike_2_%28Icon%29.png/revision/latest?cb=20230330015359",
            timestamp_utc=partida['begin_at'],
            timestamp_br=formatar_data_BR(partida['begin_at'])
        ))

    log.info(f"Processadas {len(partidas_limpas)} partidas da API")
    return partidas_limpas