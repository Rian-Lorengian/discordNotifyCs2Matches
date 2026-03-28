import requests
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from models import WebhookConfig
from typing import Any

log = logging.getLogger(__name__)


def montar_embed(titulo, descricao, cor, campos=None, thumbnail=None, footer="Horários podem mudar.\n© Rian"):
    embed = {
        "title": titulo,
        "description": descricao,
        "color": cor,
        "footer": {"text": footer}
    }
    if campos:
        embed["fields"] = campos
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    return embed


def enviar_webhook(url, payload):
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error(f"Erro ao enviar para o webhook {url}: {e}")


def enviar_para_todos(config_webhooks: list[WebhookConfig], embed=None, conteudo=""):
    for config in config_webhooks:
        mencoes = " ".join(config.mencoes)
        payload: dict[str, Any] = {"content": f"{mencoes}\n{conteudo}" if conteudo else mencoes}
        if embed:
            payload["embeds"] = [embed]
        enviar_webhook(config.url, payload)
        time.sleep(2)


def registrar_log(mensagem_erro, título="Erro Detectado no Bot", webhook_url=None):
    log.error(mensagem_erro)

    if not webhook_url:
        return

    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y %H:%M:%S')
    embed = montar_embed(
        titulo=título,
        descricao=f"```python\n{mensagem_erro}\n```",
        cor=15158332,
        campos=[{"name": "Data e Hora", "value": f"`{agora}`", "inline": True}],
        footer="© Rian"
    )
    payload = {"content": "Atenção!", "embeds": [embed]}
    enviar_webhook(webhook_url, payload)


def avisar_mudanca_horario(lista_mudancas, config_webhooks):
    for m in lista_mudancas:
        dt_v = datetime.fromisoformat(m['velho'].replace('Z', '+00:00')).strftime('%d/%m %H:%M')
        dt_n = datetime.fromisoformat(m['novo'].replace('Z', '+00:00')).strftime('%d/%m %H:%M')
        texto = f"⚠️ **HORÁRIO ALTERADO**\n**{m['time_1']} vs {m['time_2']}**\nDe: ` {dt_v} `\nPara: ` {dt_n} `"
        enviar_para_todos(config_webhooks, conteudo=texto)


def enviar_dia_lista(partidas, config_webhooks, hoje_display):
    if not partidas:
        return

    mensagem = f"📅 **PARTIDAS DE HOJE ({hoje_display})**\n\n"
    for p in partidas:
        t1, t2, ts_br, liga = p
        hora = datetime.fromisoformat(ts_br.replace('Z', '+00:00')).strftime('%H:%M')
        mensagem += f"• `{hora}` - **{t1} vs {t2}** ({liga})\n"

    enviar_para_todos(config_webhooks, conteudo=mensagem)


def enviar_warm(id_api, campo, titulo, cor, partida, config_webhooks):
    t1, t2, hora, liga_nome, liga_logo = partida
    dt_obj = datetime.fromisoformat(hora.replace('Z', '+00:00'))
    hora_formatada = dt_obj.strftime('%d/%m às %H:%M')

    embed = montar_embed(
        titulo=titulo,
        descricao=f"**{t1} vs {t2}**",
        cor=cor,
        campos=[
            {"name": "Horário", "value": f"`{hora_formatada}`", "inline": True},
            {"name": "Campeonato", "value": f"`{liga_nome}`", "inline": True}
        ],
        thumbnail=liga_logo
    )
    enviar_para_todos(config_webhooks, embed=embed)