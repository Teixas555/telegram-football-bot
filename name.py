
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def get_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "TelegramFootballBot/1.0"}
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=25) as response:
        result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError("Telegram não aceitou a mensagem.")

def main():
    now = datetime.now(timezone.utc)
    start = now.date().isoformat()
    end = (now.date() + timedelta(days=1)).isoformat()

    url = (
        "https://kiqiq.com/api/v1/predictions?"
        + urllib.parse.urlencode({
            "from": start, "to": end, "limit": 100
        })
    )

    data = get_json(url)
    fixtures = data.get("fixtures", [])
    candidates = []

    for game in fixtures:
        try:
            kickoff = datetime.fromisoformat(
                game["kickoff_iso"].replace("Z", "+00:00")
            )
            if not (now < kickoff <= now + timedelta(hours=30)):
                continue

            probs = {
                "Vitória da equipa da casa": float(game["home_win_prob"]),
                "Empate": float(game["draw_prob"]),
                "Vitória da equipa visitante": float(game["away_win_prob"]),
            }
            market, probability = max(probs.items(), key=lambda x: x[1])

            if probability >= 0.55:
                candidates.append((probability, kickoff, game, market))
        except (KeyError, TypeError, ValueError):
            continue

    candidates.sort(key=lambda item: item[0], reverse=True)

    lines = [
        "⚽ SUGESTÕES DE FUTEBOL",
        "Previsões estatísticas — não são garantias.",
        ""
    ]

    if not candidates:
        lines.append(
            "Não foram encontrados jogos com probabilidade "
            "igual ou superior a 55% nos dados disponíveis."
        )
    else:
        for probability, kickoff, game, market in candidates[:5]:
            lines.extend([
                f"🏆 {game.get('competition', 'Competição não indicada')}",
                f"{game.get('home', '?')} - {game.get('away', '?')}",
                f"📊 Sugestão: {market}",
                f"Probabilidade estimada: {probability:.0%}",
                f"🕒 {kickoff.strftime('%d/%m %H:%M UTC')}",
                ""
            ])

    lines.extend([
        "⚠️ Probabilidades estimadas por um modelo estatístico.",
        "Não representam uma garantia de resultado."
    ])

    send_telegram("\n".join(lines))

if __name__ == "__main__":
    main()
