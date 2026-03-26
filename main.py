import sqlite3
import time
from datetime import datetime, timedelta, timezone
import requests
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

database = sqlite3.connect("cs2_matches.db")
cursor = database.cursor()

def iniciar():
    # registrar_log('Bot Iniciado', "Bot Iniciado")
    start_banco()
    # atualizar_partidas()
    main_function()


def get_data():
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return (agora.hour, agora.minute, agora.day)

def get_data_banco():
    cursor.execute("SELECT last_hour, last_minuto, last_dia FROM times WHERE id = 1")
    hora, minuto, dia = cursor.fetchone()
    return (hora, minuto, dia)

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
        ultimo_minuto_rodado = minuto
        if(hora_atual == 0):
            enviar_dia_lista()
    
    if(minuto_atual != minuto_banco):
        is_new_minuto = True

    if(dia_atual != dia_banco):
        is_new_dia = True

    return is_new_hora, is_new_minuto, is_new_dia


def start_banco():
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

    database.commit()

    cursor.execute("SELECT * from times WHERE id = 1")
    temp_a = cursor.fetchone()
    
    hora, minuto, dia = get_data() 
    
    if temp_a == None:
        sql = "INSERT INTO times (last_hour, last_minuto, last_dia, first_req, sec_req) VALUES (?, ?, ?, ?, ?)"
    else:
        sql = "UPDATE times SET last_hour = ?, last_minuto = ?, last_dia = ?, first_req = ?, sec_req = ? WHERE id = 1"
    
    cursor.execute(sql, (hora, minuto, dia, False, False))
    database.commit()

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
        "Authorization": f"Bearer {os.getenv('BEARER_TOKEN_API')} ",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    tentativas = 3
    for i in range(tentativas):
        try:
            # print(f"Tentativa {i+1} de {tentativas}...")
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status() 
            
            
            if(response):
                # print("Sucesso na requisição!")
                return response.json()
            else:
                return []

        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if e.response else "Timeout/Conexão"
            print(f"Falha na tentativa {i+1}: Status {response}")
            
            if i < tentativas - 1: # Se não for a última tentativa
                espera = (i + 1) * 5 # 5s, 10s...
                # print(f"Aguardando {espera}s para tentar novamente...")
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

    return partidas_limpas

def gravar_partidas_banco(partidas):
    hoje_br = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%Y-%m-%d')
    
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
    
    mudancas_horario = []

    for p in partidas:
        # 1. Verifica se a partida já existe
        cursor.execute("SELECT timestamp_BR FROM partidas WHERE id_api = ?", (p['id_api'],))
        resultado = cursor.fetchone()
        
        if resultado:
            horario_antigo = resultado[0]
            horario_novo = p['timestamp_br']
            
            # Condição 1 o horário mudou?
            # Condição 2 a nova data da partida é HOJE? (comparamos os primeiros 10 caracteres: YYYY-MM-DD)
            if horario_antigo != horario_novo and horario_novo[:10] == hoje_br:
                mudancas_horario.append({
                    "time_1": p['time_1'],
                    "time_2": p['time_2'],
                    "velho": horario_antigo,
                    "novo": horario_novo
                })

        valores = (p['id_api'], p['time_1'], p['time_2'], p['liga_nome'], p['liga_logo'], p['timestamp_utc'], p['timestamp_br'])
        cursor.execute(sql_upsert, valores)
    
    database.commit()

    if mudancas_horario:
        avisar_mudanca_horario(mudancas_horario)

def avisar_mudanca_horario(lista_mudancas):
    global CONFIG_WEBHOOKS
    for m in lista_mudancas:
        dt_v = datetime.fromisoformat(m['velho'].replace('Z', '+00:00')).strftime('%d/%m %H:%M')
        dt_n = datetime.fromisoformat(m['novo'].replace('Z', '+00:00')).strftime('%d/%m %H:%M')
        
        texto = f"⚠️ **HORÁRIO ALTERADO**\n**{m['time_1']} vs {m['time_2']}**\nDe: ` {dt_v} `\nPara: ` {dt_n} `"
        
        for config in CONFIG_WEBHOOKS:
            mencoes_str = " ".join(config["mencoes"])
            
            payload = {"content": f"{mencoes_str}\n{texto}"}
            
            try:
                requests.post(config["url"], json=payload, timeout=10)
            except:
                pass

def verifica_warm():
    lista_2h = []
    lista_1h = []
    lista_10min = []

    # 1. Entre 2h e 1h (Faltando 120 a 60 minutos)
    query_2h = """
    SELECT id_api FROM partidas 
    WHERE warm_2h = 0 
      AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 120
      AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 > 60
    """
    cursor.execute(query_2h)
    lista_2h = [row[0] for row in cursor.fetchall()]

    # 2. Entre 1h e 10 min (Faltando 60 a 10 minutos)
    query_1h = """
    SELECT id_api FROM partidas 
    WHERE warm_1h = 0 
      AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 60
      AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 > 10
    """
    cursor.execute(query_1h)
    lista_1h = [row[0] for row in cursor.fetchall()]

    # 3. Menos de 10 minutos (Faltando 10 a 0 minutos)
    query_10min = """
    SELECT id_api FROM partidas 
    WHERE warm_final = 0 
      AND (julianday(timestamp_BR) - julianday('now', '-3 hours')) * 1440 <= 10
    """
    cursor.execute(query_10min)
    lista_10min = [row[0] for row in cursor.fetchall()]
    
    return lista_2h, lista_1h, lista_10min

CONFIG_WEBHOOKS = [
    {
        "url": os.getenv("WEBHOOK_URL_1"),
        "mencoes": ["Aviso"]
    },

    {
        "url": os.getenv("WEBHOOK_URL_2"),
        "mencoes": ["<@&796530374519160872>"]
    },

    ]

def enviar_dia_lista():
    global CONFIG_WEBHOOKS
    
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    hoje_sql = agora_br.strftime('%Y-%m-%d') # Formato para o banco (YYYY-MM-DD)
    hoje_display = agora_br.strftime('%d/%m/%Y') # Formato para o Discord (DD/MM/YYYY)
    
    query = """
    SELECT time_1, time_2, timestamp_BR, liga_nome 
    FROM partidas 
    WHERE date(timestamp_BR) = ?
    ORDER BY timestamp_BR ASC
    """
    
    try:
        cursor.execute(query, (hoje_sql,))
        partidas = cursor.fetchall()
        
        if not partidas:
            return

        mensagem = f"📅 **PARTIDAS DE HOJE ({hoje_display})**\n\n"
        
        for p in partidas:
            t1, t2, ts_br, liga = p
            hora = datetime.fromisoformat(ts_br.replace('Z', '+00:00')).strftime('%H:%M')
            mensagem += f"• `{hora}` - **{t1} vs {t2}** ({liga})\n"

        for config in CONFIG_WEBHOOKS:
            url = config["url"]
            mencoes = " ".join(config["mencoes"])
            
            payload = {
                "content": f"{mencoes}\n{mensagem}"
            }
            
            r = requests.post(url, json=payload)
            r.raise_for_status()
            
    except Exception as e:
        registrar_log(f"Erro ao enviar lista do dia: {e}")

def realiza_warm(lista_2h, lista_1h, lista_10min):

    global CONFIG_WEBHOOKS

    categorias = [
        (lista_2h, "warm_2h", "Cerca de 2 Horas para o início", 3447003),
        (lista_1h, "warm_1h", "Cerca de 1 Hora para o início", 15105570),
        (lista_10min, "warm_final", "VAI COMEÇAR!", 15158332)
    ]

    for ids, campo, titulo, cor in categorias:
        for id_api in ids:
            cursor.execute("SELECT time_1, time_2, timestamp_BR, liga_nome, liga_logo FROM partidas WHERE id_api = ?", (id_api,))
            partida = cursor.fetchone()

            if partida:
                t1, t2, hora, liga_nome, liga_logo = partida
                dt_obj = datetime.fromisoformat(hora.replace('Z', '+00:00'))
                hora_formatada = dt_obj.strftime('%d/%m às %H:%M')

                embed = {
                    "title": f"{titulo}",
                    "description": f"**{t1} vs {t2}**",
                    "color": cor,
                    "thumbnail": {"url": liga_logo}, 
                    "fields": [
                        {"name": "Horário", "value": f" `{hora_formatada}`", "inline": True},
                        {"name": "Campeonato", "value": f"`{liga_nome}`", "inline": True}
                    ],
                    "footer": {
                        "text": "Horários podem mudar.\n© Rian"
                    }
                }

                for config in CONFIG_WEBHOOKS:
                    url = config["url"]
                    mencoes_lista = config["mencoes"]
                    
                    string_mencoes = " ".join(mencoes_lista)
                    conteudo = f"{string_mencoes}" if mencoes_lista else ""

                    payload = {
                        "content": conteudo,
                        "embeds": [embed]
                    }

                    try:
                        r = requests.post(url, json=payload)
                        r.raise_for_status()
                    except Exception as e:
                        registrar_log(f"Erro ao enviar para o webhook {url}: {e}")

                cursor.execute(f"UPDATE partidas SET {campo} = 1 WHERE id_api = ?", (id_api,))

    database.commit()


def deletar_partidas_antigas():
    try:

        query = """
        DELETE FROM partidas 
        WHERE (julianday('now', '-3 hours') - julianday(timestamp_BR)) >= 1
        """
        
        cursor.execute(query)
        linhas_removidas = cursor.rowcount
        
        database.commit()
        
        if linhas_removidas > 0:
            registrar_log(f"Limpeza concluída: {linhas_removidas} partidas antigas removidas.", "Limpeza finalizada com sucesso")
        else:
            registrar_log("Limpeza executada: Nenhuma partida antiga encontrada para remoção.", "Limpeza finalizada com sucesso")
            
    except Exception as e:
        registrar_log(f"Erro ao deletar partidas antigas: {e}")
    

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
    sql = "UPDATE times SET last_hour = ?, last_minuto = ?, last_dia = ? WHERE id = 1"
    cursor.execute(sql, (hora, minuto, dia))
    database.commit()
    
def main_function():
    # print("Primeira carga de dados ao iniciar...")

    load_dotenv()
    # atualizar_partidas() 
    registrar_log("bot iniciado e primeira carga de partidas realizada com sucesso.", "Bot Iniciado")
    
    while True:
        time.sleep(30) 
        
        is_new_hora, is_new_minuto, is_new_dia = verifica_novo()

        uptade_banco_times()

        if is_new_hora:
            # print(f"Atualizando partidas...")
            processar_hora()
        
        if is_new_minuto:
            processar_minuto()

        if is_new_dia:
            processar_dia()

def registrar_log(mensagem_erro, título="Erro Detectado no Bot"):
    WEBHOOK_ERROS = os.getenv("WEBHOOK_URL_3")
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y %H:%M:%S')
    
    payload = {
        "content": "Atenção!", 
        "embeds": [{
            "title": título,
            "description": f"```python\n{mensagem_erro}\n```",
            "color": 15158332, 
            "fields": [
                {"name": "Data e Hora", "value": f"`{agora}`", "inline": True}
            ],
            "footer": {"text": "© Rian"}
        }]
    }

    try:
        r = requests.post(WEBHOOK_ERROS, json=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"Falha crítica ao enviar log para o Discord: {e}")


iniciar()