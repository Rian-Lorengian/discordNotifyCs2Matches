from dotenv import load_dotenv
import os
import logging
from models import WebhookConfig

load_dotenv()

log = logging.getLogger(__name__)

def _exigir(chave):
    valor = os.getenv(chave)
    if not valor:
        raise EnvironmentError(f"Variável de ambiente obrigatória não encontrada: {chave}")
    return valor

# API
BEARER_TOKEN = _exigir("BEARER_TOKEN_API")

# Webhooks
WEBHOOK_LOGS = _exigir("WEBHOOK_URL_3")

CONFIG_WEBHOOKS = [
    WebhookConfig(url=_exigir("WEBHOOK_URL_1"), mencoes=["Aviso"]),
    WebhookConfig(url=_exigir("WEBHOOK_URL_2"), mencoes=["<@&796530374519160872>"]),
]

# Times monitorados
# Furia, Pain, Legacy, Imperial, Sharks, Mibr, Fluxo, RedCanids, Gaimin, Oddik
IDS_TIMES = [124530, 125751, 133708, 3396, 3260, 3250, 131570, 126227, 130566, 131253]