
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_URL = "https://api.api-ninjas.com/v1"
FUSO = ZoneInfo("Europe/Lisbon")

API_KEY = os.getenv("API_NINJAS_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def consultar_api(endpoint, parametros):
    resposta = requests.get(
        f"{API_URL}/{endpoint}",
        headers={"X-Api-Key": API_KEY},
        params=parametros,
        timeout=25
    )
    resposta.raise_for_status()
    dados = resposta.json()

    if not isinstance(dados, list):
        raise RuntimeError(f"Resposta inesperada da API: {dados}")

    return dados


def enviar_telegram(mensagem):
    resposta = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "disable_web_page_preview": True
        },
        timeout=25
    )
    resposta.raise_for_status()

    if not resposta.json().get("ok"):
        raise RuntimeError("O Telegram não confirmou o envio.")


def numero(valor, padrao=0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float(padrao)


def main():
    if not API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Falta configurar API_NINJAS_KEY, "
            "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID."
        )

    hoje = datetime.now(FUSO).date()

    # A API usa a data do jogo no fuso horário dos Estados Unidos.
    # A consulta sem data devolve os jogos do dia da liga.
    jogos = consultar_api(
        "basketballgames",
        {"league": "nba"}
    )

    classificacoes = consultar_api(
        "basketballstandings",
        {"league": "nba"}
    )

    equipas = {}
    for linha in classificacoes:
        equipa = linha.get("team", {})
        nome = equipa.get("name")

        if nome:
            jogos_disputados = numero(linha.get("games_played"))
            vitorias = numero(linha.get("wins"))
            aproveitamento = numero(
                linha.get("win_pct"),
                vitorias / jogos_disputados if jogos_disputados else 0.5
            )

            equipas[nome] = {
                "aproveitamento": aproveitamento,
                "jogos": jogos_disputados,
                "marcados": numero(linha.get("points_for")),
                "sofridos": numero(linha.get("points_against")),
                "diferencial": numero(linha.get("point_differential"))
            }

    jogos_do_dia = [
        jogo for jogo in jogos
        if jogo.get("status") == "scheduled"
        and jogo.get("date") == hoje.isoformat()
    ]

    if not jogos_do_dia:
        mensagem = (
            "🏀 RB TIPS | NBA\n\n"
            f"Não encontrei jogos agendados para {hoje:%d/%m/%Y} "
            "na data consultada pela API.\n\n"
            "Não foram gerados palpites. A data da API usa o "
            "calendário dos Estados Unidos."
        )
        enviar_telegram(mensagem)
        print("Não foram encontrados jogos para a data consultada.")
        return

    linhas = [
        "🏀 RB TIPS | NBA",
        f"📅 Jogos NBA — {hoje:%d/%m/%Y}",
        "",
        "📊 ESTIMATIVAS ESTATÍSTICAS",
        "Não são garantias nem aconselhamento financeiro.",
        ""
    ]

    for jogo in jogos_do_dia[:10]:
        casa = jogo.get("home_team", {}).get("name", "Equipa da casa")
        fora = jogo.get("away_team", {}).get("name", "Equipa visitante")
        hora = jogo.get("start_time", "")

        estat_casa = equipas.get(casa, {})
        estat_fora = equipas.get(fora, {})

        linhas.append(f"🏀 {fora} vs {casa}")

        if hora:
            try:
                inicio = datetime.fromisoformat(
                    hora.replace("Z", "+00:00")
                ).astimezone(FUSO)
                linhas.append(f"🕒 Hora de Portugal: {inicio:%H:%M}")
            except ValueError:
                pass

        if (
            estat_casa.get("jogos", 0) > 0
            and estat_fora.get("jogos", 0) > 0
        ):
            # Combina aproveitamento e diferencial médio por jogo.
            dif_casa = (
                estat_casa["diferencial"] / estat_casa["jogos"]
            )
            dif_fora = (
                estat_fora["diferencial"] / estat_fora["jogos"]
            )

            forca_casa = (
                0.65 * estat_casa["aproveitamento"]
                + 0.35 * (0.5 + dif_casa / 40)
            )
            forca_fora = (
                0.65 * estat_fora["aproveitamento"]
                + 0.35 * (0.5 + dif_fora / 40)
            )

            if forca_casa > forca_fora:
                linhas.append(f"🎯 Vencedor estimado: {casa}")
            elif forca_fora > forca_casa:
                linhas.append(f"🎯 Vencedor estimado: {fora}")
            else:
                linhas.append("🎯 Vencedor estimado: jogo equilibrado")

            media_casa = (
                estat_casa["marcados"] / estat_casa["jogos"]
                + estat_fora["sofridos"] / estat_fora["jogos"]
            ) / 2

            media_fora = (
                estat_fora["marcados"] / estat_fora["jogos"]
                + estat_casa["sofridos"] / estat_casa["jogos"]
            ) / 2

            total = media_casa + media_fora
            linhas.append(f"📈 Total estimado: {total:.0f} pontos")
            linhas.append(
                "ℹ️ Estimativa calculada com médias da época; "
                "não representa uma linha oficial de apostas."
            )
        else:
            linhas.append(
                "🎯 Previsão indisponível: faltam resultados "
                "suficientes na classificação."
            )

        linhas.append("")

    linhas.append(
        "RB TIPS | Analisa sempre o risco. "
        "Nenhum resultado é garantido."
    )

    enviar_telegram("\n".join(linhas))
    print(f"Mensagem enviada. Jogos analisados: {len(jogos_do_dia[:10])}")


if __name__ == "__main__":
    main()
