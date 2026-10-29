
import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NBA_URL = "https://v2.nba.api-sports.io"
TIMEZONE = ZoneInfo("Europe/Lisbon")

API_KEY = os.getenv("API_NBA_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def nba_get(endpoint, params=None):
    response = requests.get(
        f"{NBA_URL}/{endpoint}",
        headers={"x-apisports-key": API_KEY},
        params=params or {},
        timeout=25
    )
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        raise RuntimeError(f"Erro API-NBA: {data['errors']}")

    return data.get("response", [])


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "disable_web_page_preview": True
        },
        timeout=25
    )
    response.raise_for_status()

    resultado = response.json()
    if not resultado.get("ok"):
        raise RuntimeError("O Telegram não confirmou o envio.")


def main():
    if not API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Faltam secrets: API_NBA_KEY, TELEGRAM_BOT_TOKEN "
            "ou TELEGRAM_CHAT_ID."
        )

    hoje = datetime.now(TIMEZONE).date()

    # A API trabalha com a data local do jogo.
    jogos = nba_get(
        "games",
        {"league": "standard", "season": hoje.year, "date": hoje.isoformat()}
    )

    por_comecar = []
    for jogo in jogos:
        estado = str(jogo.get("status", {}).get("short", ""))
        if estado == "1":
            por_comecar.append(jogo)

    if not por_comecar:
        mensagem = (
            "🏀 RB TIPS | NBA\n\n"
            f"Não encontrei jogos por começar para {hoje:%d/%m/%Y} "
            "na API-NBA.\n\n"
            "Isto pode acontecer devido ao calendário ou à data "
            "utilizada pela API. Não foram gerados palpites."
        )
        enviar_telegram(mensagem)
        print("Sem jogos por começar.")
        return

    linhas = [
        "🏀 RB TIPS | NBA",
        f"📅 Jogos encontrados: {hoje:%d/%m/%Y}",
        "",
        "⚠️ Pré-análise — não são garantias de resultado.",
        ""
    ]

    for jogo in por_comecar[:8]:
        casa = jogo.get("teams", {}).get("home", {}).get("name", "Equipa da casa")
        fora = jogo.get("teams", {}).get("visitors", {}).get("name", "Equipa visitante")
        hora = jogo.get("date", {}).get("start", "")

        linhas.append(f"🏀 {fora} vs {casa}")
        if hora:
            linhas.append(f"🕒 Hora indicada pela API: {hora}")

        # Não inventar vencedor nem linha de pontos sem estatísticas.
        linhas.append("🎯 Vencedor: por avaliar com estatísticas.")
        linhas.append("📊 Total de pontos: por avaliar com estatísticas.")
        linhas.append("")

    linhas.append(
        "A próxima etapa é acrescentar forma recente e médias de pontos "
        "para calcular estimativas fundamentadas."
    )
    enviar_telegram("\n".join(linhas))
    print(f"Mensagem enviada. Jogos encontrados: {len(por_comecar)}")


if __name__ == "__main__":
    main()
