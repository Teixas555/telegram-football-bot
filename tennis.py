
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_URL = "https://api.tennisdatabaseapi.com/v1"
FUSO = ZoneInfo("Europe/Lisbon")

API_KEY = os.getenv("TDA_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def consultar_jogos():
    resposta = requests.get(
        f"{API_URL}/fixtures",
        headers={"Authorization": f"Bearer {API_KEY}"},
        params={
            "tour": "men",
            "per_page": 200
        },
        timeout=30
    )
    resposta.raise_for_status()
    dados = resposta.json()

    if "error" in dados:
        raise RuntimeError(f"Erro da API de ténis: {dados['error']}")

    return dados.get("data", [])


def enviar_telegram(mensagem):
    resposta = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "disable_web_page_preview": True
        },
        timeout=30
    )
    resposta.raise_for_status()

    if not resposta.json().get("ok"):
        raise RuntimeError("O Telegram não confirmou o envio.")


def hora_portugal(valor):
    if not valor:
        return "Hora por confirmar"

    try:
        inicio = datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        ).astimezone(FUSO)
        return inicio.strftime("%d/%m às %H:%M")
    except (ValueError, TypeError):
        return "Hora por confirmar"


def main():
    if not API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Falta configurar TDA_KEY, TELEGRAM_BOT_TOKEN "
            "ou TELEGRAM_CHAT_ID nos Secrets do GitHub."
        )

    agora = datetime.now(FUSO)
    jogos = consultar_jogos()
    candidatos = []

    for jogo in jogos:
        if jogo.get("tour") != "men":
            continue

        # ATP Tour e Grand Slams; exclui Challenger, ITF e pares.
        torneio = jogo.get("tournament") or {}
        nivel = torneio.get("tier")

        if nivel not in ("tour", "slam"):
            continue

        if jogo.get("status") != "scheduled":
            continue

        inicio_texto = jogo.get("start_time")
        if not inicio_texto:
            continue

        try:
            inicio = datetime.fromisoformat(
                inicio_texto.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        if inicio.astimezone(FUSO) < agora:
            continue

        jogador1 = jogo.get("player_1") or {}
        jogador2 = jogo.get("player_2") or {}
        info1 = jogador1.get("player") or {}
        info2 = jogador2.get("player") or {}

        nome1 = info1.get("name")
        nome2 = info2.get("name")
        chances = jogo.get("elo_chance") or {}

        p1 = chances.get("player_1")
        p2 = chances.get("player_2")

        if not nome1 or not nome2 or p1 is None or p2 is None:
            continue

        try:
            p1 = float(p1)
            p2 = float(p2)
        except (TypeError, ValueError):
            continue

        # Só seleciona jogos em que o Elo indica uma vantagem
        # de pelo menos 60% para um dos jogadores.
        melhor = max(p1, p2)
        if melhor < 0.60:
            continue

        if p1 >= p2:
            favorito = nome1
            probabilidade = p1
            ranking = jogador1.get("rank")
        else:
            favorito = nome2
            probabilidade = p2
            ranking = jogador2.get("rank")

        candidatos.append({
            "inicio": inicio,
            "torneio": torneio.get("name", "Torneio por confirmar"),
            "jogador1": nome1,
            "jogador2": nome2,
            "favorito": favorito,
            "probabilidade": probabilidade,
            "ranking": ranking,
            "superficie": torneio.get("surface", "não indicada"),
            "hora": hora_portugal(inicio_texto)
        })

    # Maior probabilidade primeiro; máximo de 8 jogos.
    candidatos.sort(
        key=lambda jogo: jogo["probabilidade"],
        reverse=True
    )
    selecionados = candidatos[:8]

    linhas = [
        "🎾 RB TIPS | ATP MASCULINO",
        f"📅 {agora.strftime('%d/%m/%Y')}",
        "",
        "📊 PREVISÕES ESTATÍSTICAS",
        "Baseadas na probabilidade Elo da API.",
        "Não são garantias nem aconselhamento financeiro.",
        ""
    ]

    if not selecionados:
        linhas.extend([
            "Não encontrei jogos ATP/Grand Slam por disputar",
            "com dados Elo suficientes e favorito acima de 60%.",
            "",
            "Não foram gerados palpites para hoje."
        ])
    else:
        for i, jogo in enumerate(selecionados, start=1):
            linhas.append(
                f"{i}. 🎾 {jogo['jogador1']} vs {jogo['jogador2']}"
            )
            linhas.append(f"🏆 {jogo['torneio']}")
            linhas.append(f"🕒 Portugal: {jogo['hora']}")
            linhas.append(f"🎯 Vencedor estimado: {jogo['favorito']}")
            linhas.append(
                f"📈 Probabilidade Elo: "
                f"{jogo['probabilidade']:.0%}"
            )
            linhas.append(
                f"🎾 Superfície: {jogo['superficie']}"
            )
            linhas.append("")

    linhas.extend([
        "ℹ️ Uma probabilidade estatística não garante",
        "que o jogador vença. Avalia sempre o risco.",
        "",
        "RB TIPS | Joga com responsabilidade."
    ])

    enviar_telegram("\n".join(linhas))
    print(
        f"Mensagem enviada. Jogos selecionados: "
        f"{len(selecionados)}"
    )


if __name__ == "__main__":
    main()
