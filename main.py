from dotenv import load_dotenv
load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[
        logging.StreamHandler(),                        # console
        logging.FileHandler("bot.log", encoding="utf-8")  # arquivo
    ]
)

log = logging.getLogger(__name__)

import discord as dc
import database as db
import sqlite3
import time
from datetime import datetime, timedelta, timezone
import requests
from zoneinfo import ZoneInfo
import os

def iniciar():
    # registrar_log('Bot Iniciado', "Bot Iniciado")
    start_banco()
    atualizar_partidas()
    main_function()


def get_data():
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return (agora.hour, agora.minute, agora.day)

def get_data_banco():
    return db.buscar_times()

def formatar_data_BR(data_api):
    dt_utc = datetime.fromisoformat(data_api.replace('Z', '+00:00'))

    dt_br = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo"))

    data_formatada = dt_br.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    return data_formatada

ultimo_minuto_rodado = -1

def verifica_novo():
    global ultimo_minuto_rodado
    hora_atual, minuto_atual, dia_atual = get_data()
    hora_banco, minuto_banco, dia_banco = get_data_banco()

    is_new_hora = False
    is_new_minuto = False
    is_new_dia = False

    minutos_alvo = [0, 20, 40]
    for minuto in minutos_alvo:
        if(minuto == minuto_atual and minuto != ultimo_minuto_rodado):
            is_new_hora = True
            ultimo_minuto_rodado = minuto

    if(hora_atual != hora_banco):
        is_new_hora = True
        ultimo_minuto_rodado = minuto_atual
        log.info("Nova hora detectada - atualizando partidas")
        if(hora_atual == 0):
            enviar_dia_lista()
    
    if(minuto_atual != minuto_banco):
        is_new_minuto = True

    if(dia_atual != dia_banco):
        is_new_dia = True
        log.info("Novo dia detectado - executando limpeza")

    return is_new_hora, is_new_minuto, is_new_dia


def start_banco():
    db.iniciar_banco()

def get_matches_48h():
    now = datetime.now(timezone.utc)
    limit_48h = now + timedelta(hours=48)
    
    start_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = limit_48h.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = "https://api.pandascore.co/csgo/matches"

    #Furia, Pain, Legacy, Imperial, Sharks, Mibr, Fluxo, RedCanads, Gaimim, Oddik
    ids_dos_times = [124530, 125751, 133708, 3396, 3260, 3250, 131570, 126227, 130566, 131253]

    params = {
        "range[begin_at]": f"{start_str},{end_str}",
        "filter[status]": "not_started",
        "filter[opponent_id]": ",".join(map(str, ids_dos_times)),
        "sort": "begin_at",
    }

    headers = {
        "Authorization": f"Bearer {os.getenv('BEARER_TOKEN_API')}",
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

def processar_matches():
    partidas_brutas = get_matches_48h()
    partidas_limpas = []

    for partida in partidas_brutas:
        oponentes = partida.get('opponents', [])

        time_1 = oponentes[0]['opponent']['name'] if len(oponentes) >= 1 else "TBD"
        time_2 = oponentes[1]['opponent']['name'] if len(oponentes) >= 2 else "TBD"
        
        dados_liga = partida.get('league', {})
        liga_nome = dados_liga.get('name', 'Liga Desconhecida')
        liga_logo = dados_liga.get('image_url') or "https://static.wikia.nocookie.net/logopedia/images/4/49/Counter-Strike_2_%28Icon%29.png/revision/latest?cb=20230330015359"

        objeto_partida = {
            "id_api": partida['id'],
            "time_1": time_1,
            "time_2": time_2,
            "liga_nome": liga_nome,
            "liga_logo": liga_logo, 
            "timestamp_utc": partida['begin_at'], 
            "timestamp_br": formatar_data_BR(partida['begin_at'])
        }

        partidas_limpas.append(objeto_partida)

    log.info(f"Processadas {len(partidas_limpas)} partidas da API")
    return partidas_limpas

def gravar_partidas_banco(partidas):
    mudancas = db.gravar_partidas(partidas)
    if mudancas:
        avisar_mudanca_horario(mudancas)

def avisar_mudanca_horario(lista_mudancas):
    global CONFIG_WEBHOOKS
    dc.avisar_mudanca_horario(lista_mudancas, CONFIG_WEBHOOKS)

def verifica_warm():
    return db.buscar_partidas_warm()

CONFIG_WEBHOOKS = [
    {
        "url": os.getenv("WEBHOOK_URL_1"),
        "mencoes": ["Aviso"]
    },

    # {
    #     "url": os.getenv("WEBHOOK_URL_2"),
    #     "mencoes": ["<@&796530374519160872>"]
    # },

    ]

def enviar_dia_lista():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    hoje_display = agora_br.strftime('%d/%m/%Y')
    partidas = db.buscar_partidas_hoje()
    dc.enviar_dia_lista(partidas, CONFIG_WEBHOOKS, hoje_display)

def realiza_warm(lista_2h, lista_1h, lista_10min):
    global CONFIG_WEBHOOKS

    categorias = [
        (lista_2h, "warm_2h", "Cerca de 2 Horas para o início", 3447003),
        (lista_1h, "warm_1h", "Cerca de 1 Hora para o início", 15105570),
        (lista_10min, "warm_final", "VAI COMEÇAR!", 15158332)
    ]

    for ids, campo, titulo, cor in categorias:
        for id_api in ids:
            partida = db.buscar_dados_partida(id_api)

            if partida:
                dc.enviar_warm(id_api, campo, titulo, cor, partida, CONFIG_WEBHOOKS)
                db.marcar_warm_enviado(campo, id_api)

    log.info("Warm-ups enviados para Discord com sucesso")


def deletar_partidas_antigas():
    removidas = db.deletar_partidas_antigas()
    if removidas > 0:
        registrar_log(f"Limpeza: {removidas} partidas antigas removidas.", "Limpeza finalizada")
    else:
        registrar_log("Limpeza executada: nenhuma partida antiga encontrada.", "Limpeza finalizada")
    

def atualizar_partidas():
    partidas = processar_matches()
    gravar_partidas_banco(partidas)

def processar_hora():
    atualizar_partidas()

def processar_minuto():
    l2h, l1h, l10min = verifica_warm()
    realiza_warm(l2h, l1h, l10min)

def processar_dia():
    deletar_partidas_antigas()

def uptade_banco_times():
    hora, minuto, dia = get_data()
    db.atualizar_times(hora, minuto, dia)
    
def main_function():
    log.info("Primeira carga de dados ao iniciar...")
    atualizar_partidas() 
    log.info("Bot iniciado com sucesso. Iniciando loop principal...")
    
    while True:
        time.sleep(30) 
        
        is_new_hora, is_new_minuto, is_new_dia = verifica_novo()

        uptade_banco_times()

        if is_new_hora:
            log.info("Atualizando partidas...")
            processar_hora()
        
        if is_new_minuto:
            processar_minuto()

        if is_new_dia:
            processar_dia()

def registrar_log(mensagem_erro, título="Erro Detectado no Bot"):
    dc.registrar_log(mensagem_erro, título, os.getenv("WEBHOOK_URL_3"))

iniciar()