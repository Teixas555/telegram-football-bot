
import os
import json
import urllib.request
import urllib.parse

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
        raise RuntimeError("A API-Football devolveu um erro.")

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

def main():
    ligas = "-".join(str(liga) for liga in LIGAS_PERMITIDAS)

    jogos = pedido_api("/fixtures", {"live": ligas})

    jogos = [
        jogo for jogo in jogos
        if jogo.get("league", {}).get("id") in LIGAS_PERMITIDAS
        and jogo.get("fixture", {}).get("status", {}).get("short")
        in ("1H", "2H", "HT", "ET", "LIVE")
    ]

    mensagem = [
        "🤖 BOT LIVE — VERIFICAÇÃO CONCLUÍDA",
        "",
        "✅ O bot executou e conseguiu consultar a API-Football.",
        f"⚽ Jogos ao vivo nas 8 competições: {len(jogos)}",
        "",
    ]

    if jogos:
        mensagem.append("📋 Jogos encontrados:")
        for jogo in jogos[:10]:
            equipas = jogo.get("teams", {})
            golos = jogo.get("goals", {})
            fixture = jogo.get("fixture", {})
            liga_id = jogo.get("league", {}).get("id")
            minuto = fixture.get("status", {}).get("elapsed")
            casa = equipas.get("home", {}).get("name", "Casa")
            fora = equipas.get("away", {}).get("name", "Fora")
            gc = golos.get("home")
            gf = golos.get("away")

            mensagem.append(
                f"🏆 {LIGAS_PERMITIDAS.get(liga_id, 'Competição')}\n"
                f"⚔️ {casa} {gc} - {gf} {fora}\n"
                f"⏱️ Minuto: {minuto if minuto is not None else '?'}"
            )
    else:
        mensagem.append(
            "ℹ️ Neste momento não foram encontrados jogos ao vivo "
            "nas competições selecionadas."
        )

    mensagem.extend([
        "",
        "ℹ️ Esta é uma mensagem de teste. Ainda não significa que "
        "exista uma oportunidade de golo."
    ])

    enviar_telegram("\n".join(mensagem))
    print("Mensagem de verificação enviada para o Telegram.")

if __name__ == "__main__":
    main()
