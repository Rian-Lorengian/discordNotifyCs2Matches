from dotenv import load_dotenv
import logging
from config import CONFIG_WEBHOOKS, WEBHOOK_LOGS, IDS_TIMES, BEARER_TOKEN
import discord as dc
import database as db
import time
from datetime import datetime, timedelta, timezone
import requests
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from logging.handlers import RotatingFileHandler
from models import Partida
import api

class BRFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("America/Sao_Paulo"))
        return dt.strftime(datefmt or "%d/%m/%Y %H:%M:%S")

formatter = BRFormatter(fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = RotatingFileHandler(
    "bot.log",
    maxBytes=5 * 1024 * 1024,  
    backupCount=3,              
    encoding="utf-8"
)
file_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])

log = logging.getLogger(__name__)

logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)

def iniciar():
    start_banco()
    main_function()


def get_data():
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return (agora.hour, agora.minute, agora.day)


def start_banco():
    db.iniciar_banco()

def gravar_partidas_banco(partidas):
    mudancas = db.gravar_partidas(partidas)
    if mudancas:
        avisar_mudanca_horario(mudancas)

def avisar_mudanca_horario(lista_mudancas):
    global CONFIG_WEBHOOKS
    dc.avisar_mudanca_horario(lista_mudancas, CONFIG_WEBHOOKS)

def verifica_warm():
    return db.buscar_partidas_warm()

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

    # log.info("Warm-ups enviados para Discord com sucesso")


def deletar_partidas_antigas():
    removidas = db.deletar_partidas_antigas()
    if removidas > 0:
        registrar_log(f"Limpeza: {removidas} partidas antigas removidas.", "Limpeza finalizada")
    else:
        registrar_log("Limpeza executada: nenhuma partida antiga encontrada.", "Limpeza finalizada")
    

def atualizar_partidas():
    partidas = api.processar_matches()
    mudancas = db.gravar_partidas(partidas)
    if mudancas:
        dc.avisar_mudanca_horario(mudancas, CONFIG_WEBHOOKS)

def processar_minuto():
    # logging.info("Processar minuto executado")
    l2h, l1h, l10min = verifica_warm()
    realiza_warm(l2h, l1h, l10min)

def processar_dia():
    deletar_partidas_antigas()
    
def main_function():
    log.info("Primeira carga de dados ao iniciar...")
    atualizar_partidas()
    log.info("Bot iniciado com sucesso. Iniciando loop principal...")
    
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    # A cada 20 minutos — busca partidas na API
    scheduler.add_job(atualizar_partidas, "interval", minutes=20)

    # A cada 1 minuto — verifica warms
    scheduler.add_job(processar_minuto, "interval", minutes=1)

    # Todo dia à meia-noite — envia lista do dia e limpa partidas antigas
    scheduler.add_job(enviar_dia_lista, "cron", hour=0, minute=0)
    scheduler.add_job(processar_dia,    "cron", hour=0, minute=1)

    log.info("Scheduler iniciado.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot encerrado.")

def registrar_log(mensagem_erro, título="Erro Detectado no Bot"):
    dc.registrar_log(mensagem_erro, título, WEBHOOK_LOGS)

iniciar()