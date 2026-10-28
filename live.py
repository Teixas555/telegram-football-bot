
import os
import json
import urllib.request
import urllib.parse
import urllib.error

API_KEY = os.environ["API_FOOTBALL_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API_URL = "https://v3.football.api-sports.io"

LIGAS_PERMITIDAS = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "Liga dos Campeões",
    3: "Liga Europa",
    848: "Liga Conferência",
}

# Limite por execução: 1 consulta de jogos + 1 de estatísticas
MAX_CONSULTAS_LIVE = 2


def pedido_api(endpoint, parametros=None):
    url = API_URL + endpoint

    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)

    pedido = urllib.request.Request(
        url,
        headers={"x-apisports-key": API_KEY}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    if dados.get("errors"):
        raise RuntimeError("Erro devolvido pela API-Football.")

    return dados.get("response", [])


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    dados = json.dumps({
        "chat_id": CHAT_ID,
        "text": mensagem,
        "disable_web_page_preview": True
    }).encode("utf-8")

    pedido = urllib.request.Request(
        url,
        data=dados,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        resultado = json.loads(resposta.read().decode("utf-8"))

    if not resultado.get("ok"):
        raise RuntimeError("O Telegram não aceitou a mensagem.")


def obter_estatistica(equipa, nome):
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


def analisar_jogo(jogo):
    fixture = jogo.get("fixture", {})
    equipas = jogo.get("teams", {})
    golos = jogo.get("goals", {})
    liga = jogo.get("league", {})
    tempo = fixture.get("status", {}).get("elapsed")

    if not isinstance(tempo, (int, float)):
        return None

    # Analisar apenas a segunda parte, entre os minutos 55 e 80.
    if not 55 <= tempo <= 80:
        return None

    total_golos = (golos.get("home") or 0) + (golos.get("away") or 0)

    # Procurar jogos ainda equilibrados, sem muitos golos já marcados.
    if total_golos > 2:
        return None

    return {
        "id": fixture.get("id"),
        "casa": equipas.get("home", {}).get("name", "Casa"),
        "fora": equipas.get("away", {}).get("name", "Fora"),
        "resultado": f"{golos.get('home', 0)} - {golos.get('away', 0)}",
        "minuto": tempo,
        "liga": LIGAS_PERMITIDAS.get(
            liga.get("id"), "Competição"
        ),
    }


def main():
    ligas = "-".join(str(liga) for liga in LIGAS_PERMITIDAS)

    # Consulta única para listar os jogos LIVE das oito competições.
    jogos = pedido_api("/fixtures", {"live": ligas})

    jogos = [
        jogo for jogo in jogos
        if jogo.get("league", {}).get("id") in LIGAS_PERMITIDAS
        and jogo.get("fixture", {}).get("status", {}).get("short")
        in ("1H", "2H", "HT", "ET", "LIVE")
    ]

    candidatos = []

    for jogo in jogos:
        candidato = analisar_jogo(jogo)
        if candidato:
            candidatos.append(candidato)

    if not candidatos:
        print("Sem jogos elegíveis para análise LIVE nesta execução.")
        return

    # Apenas um jogo por execução para proteger a quota diária.
    candidato = candidatos[0]

    # Segunda e última consulta API desta execução.
    estatisticas = pedido_api(
        "/fixtures/statistics",
        {"fixture": candidato["id"]}
    )

    if len(estatisticas) < 2:
        print("Estatísticas insuficientes para avaliar o jogo.")
        return

    equipa_casa = estatisticas[0]
    equipa_fora = estatisticas[1]

    remates_baliza = (
        obter_estatistica(equipa_casa, "Shots on Goal")
        + obter_estatistica(equipa_fora, "Shots on Goal")
    )

    remates_totais = (
        obter_estatistica(equipa_casa, "Total Shots")
        + obter_estatistica(equipa_fora, "Total Shots")
    )

    cantos = (
        obter_estatistica(equipa_casa, "Corner Kicks")
        + obter_estatistica(equipa_fora, "Corner Kicks")
    )

    print(
        f"Análise: {candidato['casa']} - {candidato['fora']} | "
        f"Remates à baliza: {remates_baliza} | "
        f"Remates totais: {remates_totais} | Cantos: {cantos}"
    )

    # Indicadores simples; não representam probabilidades calculadas.
    if remates_baliza >= 3 and remates_totais >= 10 and cantos >= 4:
        mensagem = (
            "⚽ ALERTA LIVE — POSSÍVEL PRESSÃO OFENSIVA\n\n"
            f"🏆 {candidato['liga']}\n"
            f"⚔️ {candidato['casa']} - {candidato['fora']}\n"
            f"📊 Resultado: {candidato['resultado']}\n"
            f"⏱️ Minuto: {candidato['minuto']}'\n\n"
            f"🎯 Remates à baliza: {int(remates_baliza)}\n"
            f"🥅 Remates totais: {int(remates_totais)}\n"
            f"🚩 Cantos: {int(cantos)}\n\n"
            "ℹ️ Há indicadores de pressão ofensiva, mas isto não "
            "garante que saia outro golo."
        )

        enviar_telegram(mensagem)
        print("Alerta enviado para o Telegram.")
    else:
        print("Os indicadores definidos para o alerta não foram atingidos.")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print(f"Erro no bot LIVE: {erro}")
        raise
