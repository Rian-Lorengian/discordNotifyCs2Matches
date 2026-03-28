from dataclasses import dataclass

@dataclass
class Partida:
    id_api: int
    time_1: str
    time_2: str
    liga_nome: str
    liga_logo: str
    timestamp_utc: str
    timestamp_br: str

@dataclass
class WebhookConfig:
    url: str
    mencoes: list[str]