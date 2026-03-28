import sqlite3
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from models import Partida

log = logging.getLogger(__name__)

DB_PATH = "cs2_matches.db"
_conn = None


def get_db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _conn


def iniciar_banco():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS times(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_hour INTEGER,
            last_minuto INTEGER,
            last_dia INTEGER,
            first_req INTEGER,
            sec_req INTEGER
        )''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partidas(
            id_api INTEGER PRIMARY KEY,
            time_1 TEXT,
            time_2 TEXT,
            liga_nome TEXT,
            liga_logo TEXT,
            timestamp_UTC TEXT,
            timestamp_BR TEXT,
            warm_2h INTEGER DEFAULT 1,
            warm_1h INTEGER DEFAULT 1,
            warm_final INTEGER DEFAULT 0
        )''')

    conn.commit()

    cursor.execute("SELECT * FROM times WHERE id = 1")
    existe = cursor.fetchone()

    hora, minuto, dia = get_hora_atual()

    if existe is None:
        sql = "INSERT INTO times (last_hour, last_minuto, last_dia, first_req, sec_req) VALUES (?, ?, ?, ?, ?)"
    else:
        sql = "UPDATE times SET last_hour = ?, last_minuto = ?, last_dia = ?, first_req = ?, sec_req = ? WHERE id = 1"

    cursor.execute(sql, (hora, minuto, dia, False, False))
    conn.commit()


def get_hora_atual():
    from zoneinfo import ZoneInfo
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return agora.hour, agora.minute, agora.day


def buscar_times():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT last_hour, last_minuto, last_dia FROM times WHERE id = 1")
    return cursor.fetchone()


def atualizar_times(hora, minuto, dia):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE times SET last_hour = ?, last_minuto = ?, last_dia = ? WHERE id = 1",
        (hora, minuto, dia)
    )
    conn.commit()


def buscar_timestamp_partida(id_api):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp_BR FROM partidas WHERE id_api = ?", (id_api,))
    resultado = cursor.fetchone()
    return resultado[0] if resultado else None


def gravar_partidas(partidas: list[Partida]):
    conn = get_db()
    cursor = conn.cursor()

    sql_upsert = """
    INSERT INTO partidas (id_api, time_1, time_2, liga_nome, liga_logo, timestamp_UTC, timestamp_BR)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id_api) DO UPDATE SET
        time_1 = excluded.time_1,
        time_2 = excluded.time_2,
        liga_nome = excluded.liga_nome,
        liga_logo = excluded.liga_logo,
        timestamp_UTC = excluded.timestamp_UTC,
        warm_final = CASE WHEN timestamp_BR != excluded.timestamp_BR THEN 0 ELSE warm_final END,
        timestamp_BR = excluded.timestamp_BR;
    """

    hoje_br = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%Y-%m-%d')
    mudancas_horario = []

    for p in partidas:
        horario_antigo = buscar_timestamp_partida(p.id_api) 
        horario_novo = p.timestamp_br

        if horario_antigo and horario_antigo != horario_novo and horario_novo[:10] == hoje_br:
            mudancas_horario.append({
                "time_1": p.time_1,
                "time_2": p.time_2,
                "velho": horario_antigo,
                "novo": horario_novo
            })

        valores = (
            p.id_api, p.time_1, p.time_2,
            p.liga_nome, p.liga_logo,
            p.timestamp_utc, p.timestamp_br
        )
        cursor.execute(sql_upsert, valores)

    conn.commit()
    return mudancas_horario


def buscar_partidas_hoje():
    conn = get_db()
    cursor = conn.cursor()
    hoje_sql = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT time_1, time_2, timestamp_BR, liga_nome
        FROM partidas
        WHERE date(timestamp_BR) = ?
        ORDER BY timestamp_BR ASC
    """, (hoje_sql,))
    return cursor.fetchall()


def buscar_partidas_warm():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_api FROM partidas
        WHERE warm_2h = 0
          AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 120
          AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 > 60
    """)
    lista_2h = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT id_api FROM partidas
        WHERE warm_1h = 0
          AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 60
          AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 > 10
    """)
    lista_1h = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT id_api FROM partidas
        WHERE warm_final = 0
          AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 10
    """)
    lista_10min = [row[0] for row in cursor.fetchall()]

    return lista_2h, lista_1h, lista_10min


def buscar_dados_partida(id_api):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT time_1, time_2, timestamp_BR, liga_nome, liga_logo FROM partidas WHERE id_api = ?",
        (id_api,)
    )
    return cursor.fetchone()


def marcar_warm_enviado(campo, id_api):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE partidas SET {campo} = 1 WHERE id_api = ?", (id_api,))
    conn.commit()


def deletar_partidas_antigas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM partidas
        WHERE (julianday('now', '-3 hours') - julianday(timestamp_BR)) >= 1
    """)
    removidas = cursor.rowcount
    conn.commit()
    return removidas