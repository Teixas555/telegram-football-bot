
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY = os.environ["API_FOOTBALL_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API_URL = "https://v3.football.api-sports.io"
MAX_JOGOS = 20
FUSO = ZoneInfo("Europe/Lisbon")


def pedido_api(endpoint, parametros=None):
    url = API_URL + endpoint
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)

    pedido = urllib.request.Request(
        url,
        headers={"x-apisports-key": API_KEY}
    )

    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    if dados.get("errors"):
        raise RuntimeError("A API devolveu um erro. Verifica a chave e a quota.")

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

    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        resultado = json.loads(resposta.read().decode("utf-8"))

    if not resultado.get("ok"):
        raise RuntimeError("O Telegram não aceitou a mensagem.")


def tendencia_golos(valor):
    if not valor:
        return "Sem indicação"

    texto = str(valor).strip().lower()

    if "over" in texto or texto.startswith("+"):
        return "Mais de 2,5 golos"
    if "under" in texto or texto.startswith("-"):
        return "Menos de 2,5 golos"

    return str(valor)


def percentagem(valor):
    if valor is None or str(valor).strip() == "":
        return "N/D"
    return str(valor)


def main():
    hoje = datetime.now(FUSO).date().isoformat()

    mensagem = [
        "⚽ PREVISÕES DE FUTEBOL",
        f"📅 {hoje}",
        "",
        "Previsões estatísticas — não são garantias."
    ]

    jogos = pedido_api("/fixtures", {"date": hoje})

    jogos = [
        jogo for jogo in jogos
        if jogo.get("fixture", {}).get("status", {}).get("short") in ("NS", "TBD")
    ]

    jogos.sort(key=lambda jogo: jogo.get("fixture", {}).get("date", ""))

    if not jogos:
        enviar_telegram(
            f"⚽ PREVISÕES DE FUTEBOL\n📅 {hoje}\n\n"
            "Não encontrei jogos futuros disponíveis para hoje."
        )
        return

    analisados = 0

    for jogo in jogos[:MAX_JOGOS]:
        fixture = jogo.get("fixture", {})
        equipas = jogo.get("teams", {})
        liga = jogo.get("league", {})

        id_jogo = fixture.get("id")
        casa = equipas.get("home", {}).get("name", "Equipa da casa")
        fora = equipas.get("away", {}).get("name", "Equipa visitante")
        campeonato = liga.get("name", "Competição")
        hora = fixture.get("date", "")

        try:
            hora_local = datetime.fromisoformat(
                hora.replace("Z", "+00:00")
            ).astimezone(FUSO).strftime("%H:%M")
        except (ValueError, TypeError):
            hora_local = "--:--"

        try:
            previsoes = pedido_api("/predictions", {"fixture": id_jogo})
        except Exception:
            continue

        if not previsoes:
            continue

        previsao = previsoes[0].get("predictions", {})
        percent = previsao.get("percent") or {}

        mensagem_jogo = (
            f"🏆 {campeonato}\n"
            f"🕒 {hora_local} — hora de Portugal\n"
            f"⚔️ {casa} - {fora}\n"
            f"📊 1X2 (estimativa):\n"
            f"  🏠 Casa: {percentagem(percent.get('home'))}\n"
            f"  🤝 Empate: {percentagem(percent.get('draw'))}\n"
            f"  ✈️ Fora: {percentagem(percent.get('away'))}\n"
            f"⚽ Golos: {tendencia_golos(previsao.get('under_over'))}"
        )

        mensagem.append("")
        mensagem.append(mensagem_jogo)
        analisados += 1

    if analisados == 0:
        mensagem.extend([
            "",
            "Não foram encontradas previsões disponíveis para os jogos futuros de hoje."
        ])
    else:
        mensagem.extend([
            "",
            f"✅ Jogos com previsões: {analisados}",
            "ℹ️ As percentagens e tendências podem não estar disponíveis para todos os jogos."
        ])

    texto = "\n".join(mensagem)

    # O Telegram limita as mensagens a cerca de 4096 caracteres.
    if len(texto) > 3900:
        texto = texto[:3850] + "\n\nMensagem abreviada para caber no Telegram."

    enviar_telegram(texto)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        enviar_telegram(
            "⚠️ O bot de previsões encontrou um erro ao consultar a API. "
            "Verifica a API key e a quota diária no painel da API-Football."
        )
        raise
