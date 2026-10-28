
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

API_KEY = os.environ["API_FOOTBALL_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API_URL = "https://v3.football.api-sports.io"

LIGAS = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "Liga dos Campeões",
    3: "Liga Europa",
    848: "Liga Conferência",
}

def pedido_api(endpoint, parametros=None):
    url = API_URL + endpoint
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)

    pedido = urllib.request.Request(
        url, headers={"x-apisports-key": API_KEY}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    if dados.get("errors"):
        raise RuntimeError("Erro da API-Football: " + str(dados["errors"]))

    return dados.get("response", [])

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dados = json.dumps({
        "chat_id": CHAT_ID,
        "text": mensagem,
        "disable_web_page_preview": True
    }).encode("utf-8")

    pedido = urllib.request.Request(
        url, data=dados,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        resultado = json.loads(resposta.read().decode("utf-8"))

    if not resultado.get("ok"):
        raise RuntimeError("Falha ao enviar mensagem ao Telegram.")

def numero_estatistica(equipa, nome):
    for item in equipa.get("statistics", []):
        if item.get("type") == nome:
            valor = item.get("value")
            if valor is None:
                return 0
            if isinstance(valor, str):
                valor = valor.replace("%", "").strip()
            try:
                return float(valor)
            except (ValueError, TypeError):
                return 0
    return 0

def main():
    ids_ligas = "-".join(str(x) for x in LIGAS)
    jogos = pedido_api("/fixtures", {"live": ids_ligas})

    candidatos = []

    for jogo in jogos:
        liga = jogo.get("league", {})
        fixture = jogo.get("fixture", {})
        status = fixture.get("status", {}).get("short")
        minuto = fixture.get("status", {}).get("elapsed")
        golos = jogo.get("goals", {})
        casa = golos.get("home")
        fora = golos.get("away")

        if liga.get("id") not in LIGAS:
            continue
        if status not in ("1H", "2H", "HT", "ET", "LIVE"):
            continue
        if not isinstance(minuto, int) or not 55 <= minuto <= 80:
            continue
        if casa is None or fora is None:
            continue
        if casa + fora > 2:
            continue

        candidatos.append(jogo)

    if not candidatos:
        print("Verificação concluída: sem jogos elegíveis.")
        return

    # Apenas um jogo por execução para limitar as consultas.
    jogo = candidatos[0]
    fixture = jogo["fixture"]
    equipas = jogo["teams"]
    golos = jogo["goals"]
    liga = jogo["league"]
    id_jogo = fixture["id"]

    estatisticas = pedido_api(
        "/fixtures/statistics", {"fixture": id_jogo}
    )

    if len(estatisticas) < 2:
        print("Estatísticas insuficientes.")
        return

    remates_baliza = sum(
        numero_estatistica(e, "Shots on Goal") for e in estatisticas
    )
    remates_totais = sum(
        numero_estatistica(e, "Total Shots") for e in estatisticas
    )
    cantos = sum(
        numero_estatistica(e, "Corner Kicks") for e in estatisticas
    )

    print(
        f"Análise: {equipas['home']['name']} - "
        f"{equipas['away']['name']}; minuto "
        f"{fixture['status']['elapsed']}; remates à baliza "
        f"{remates_baliza}; remates totais {remates_totais}; "
        f"cantos {cantos}"
    )

    if remates_baliza < 3 or remates_totais < 10 or cantos < 4:
        print("Critérios de alerta não atingidos.")
        return

    casa = equipas["home"]["name"]
    fora = equipas["away"]["name"]
    minuto = fixture["status"]["elapsed"]

    mensagem = (
        "⚽ ALERTA LIVE — PRESSÃO OFENSIVA\n\n"
        f"🏆 {LIGAS.get(liga['id'], liga.get('name', 'Competição'))}\n"
        f"⚔️ {casa} {golos['home']} - {golos['away']} {fora}\n"
        f"⏱️ Minuto: {minuto}'\n\n"
        f"🎯 Remates à baliza: {int(remates_baliza)}\n"
        f"🥅 Remates totais: {int(remates_totais)}\n"
        f"🚩 Cantos: {int(cantos)}\n\n"
        "ℹ️ Indicadores estatísticos de pressão ofensiva; "
        "não garantem que saia outro golo."
    )

    enviar_telegram(mensagem)
    print("Alerta enviado.")

if __name__ == "__main__":
    main()
