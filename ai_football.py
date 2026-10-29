
import os
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.getenv("ODDS_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://api.the-odds-api.com/v4"
REGIONS = "eu"
MAX_SUGESTOES = 5

LIGAS = [
    ("Premier League", "soccer_epl"),
    ("La Liga", "soccer_spain_la_liga"),
    ("Serie A", "soccer_italy_serie_a"),
    ("Bundesliga", "soccer_germany_bundesliga"),
    ("Ligue 1", "soccer_france_ligue_one"),
    ("Champions League", "soccer_uefa_champs_league"),
    ("Europa League", "soccer_uefa_europa_league"),
    ("Conference League", "soccer_uefa_europa_conference_league"),
]

FICHEIRO = Path("ai_usage.json")
TIMEOUT = 25


def carregar_estado():
    if FICHEIRO.exists():
        try:
            return json.loads(FICHEIRO.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    return {"data": "", "pedidos": 0}


def guardar_estado(estado):
    FICHEIRO.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    resposta = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": mensagem,
            "disable_web_page_preview": True
        },
        timeout=TIMEOUT
    )
    resposta.raise_for_status()

    if not resposta.json().get("ok"):
        raise RuntimeError("O Telegram não confirmou o envio.")


def consultar_odds(liga):
    url = f"{BASE_URL}/sports/{liga}/odds"

    resposta = requests.get(
        url,
        params={
            "apiKey": API_KEY,
            "regions": REGIONS,
            "markets": "h2h,totals,btts",
            "oddsFormat": "decimal",
            "dateFormat": "iso"
        },
        timeout=TIMEOUT
    )

    if resposta.status_code != 200:
        raise RuntimeError(
            f"Odds API HTTP {resposta.status_code}: "
            f"{resposta.text[:250]}"
        )

    return resposta.json(), resposta.headers


def melhor_odd(evento, mercado_chave):
    opcoes = []

    for casa in evento.get("bookmakers", []):
        for mercado in casa.get("markets", []):
            if mercado.get("key") != mercado_chave:
                continue

            for resultado in mercado.get("outcomes", []):
                odd = resultado.get("price")

                if isinstance(odd, (int, float)) and odd > 1:
                    opcoes.append({
                        "nome": resultado.get("name", ""),
                        "odd": float(odd),
                        "casa": casa.get("title", "Casa desconhecida"),
                        "ponto": resultado.get("point")
                    })

    return max(opcoes, key=lambda x: x["odd"]) if opcoes else None


def analisar_evento(evento, nome_liga):
    casa = evento.get("home_team", "Equipa da casa")
    fora = evento.get("away_team", "Equipa visitante")
    nome_jogo = f"{casa} - {fora}"

    mercados = []

    # 1X2: apresenta a melhor odd de cada resultado.
    resultados_1x2 = []
    for equipa in [casa, "Draw", fora]:
        melhor = None

        for bookmaker in evento.get("bookmakers", []):
            for mercado in bookmaker.get("markets", []):
                if mercado.get("key") != "h2h":
                    continue

                for resultado in mercado.get("outcomes", []):
                    if resultado.get("name") == equipa:
                        odd = resultado.get("price")
                        if isinstance(odd, (int, float)) and odd > 1:
                            if melhor is None or odd > melhor["odd"]:
                                melhor = {
                                    "nome": equipa,
                                    "odd": float(odd),
                                    "casa": bookmaker.get("title", "")
                                }

        if melhor:
            resultados_1x2.append(melhor)

    # Estimativa de probabilidades 1X2 sem margem da casa.
    if len(resultados_1x2) == 3:
        soma = sum(1 / item["odd"] for item in resultados_1x2)

        if soma > 0:
            probabilidades = [
                (item["nome"], (1 / item["odd"]) / soma * 100, item["odd"])
                for item in resultados_1x2
            ]

            favorito = max(probabilidades, key=lambda x: x[1])
            mercados.append(
                f"1X2: {favorito[0]} | odd {favorito[2]:.2f} "
                f"| prob. implícita ajustada {favorito[1]:.1f}%"
            )

            # Dupla possibilidade calculada a partir das probabilidades 1X2.
            prob_casa = next(p for n, p, _ in probabilidades if n == casa)
            prob_empate = next(p for n, p, _ in probabilidades if n == "Draw")
            prob_fora = next(p for n, p, _ in probabilidades if n == fora)

            dupla = max(
                ("1X", prob_casa + prob_empate),
                ("X2", prob_fora + prob_empate),
                key=lambda x: x[1]
            )

            mercados.append(
                f"Dupla possibilidade estimada: {dupla[0]} "
                f"({dupla[1]:.1f}%)"
            )

    # Mais de 2,5 golos: usa o mercado totals se a linha existir.
    over25 = None
    for bookmaker in evento.get("bookmakers", []):
        for mercado in bookmaker.get("markets", []):
            if mercado.get("key") != "totals":
                continue

            for resultado in mercado.get("outcomes", []):
                if (
                    resultado.get("name", "").lower() == "over"
                    and resultado.get("point") == 2.5
                ):
                    odd = resultado.get("price")
                    if isinstance(odd, (int, float)) and odd > 1:
                        if over25 is None or odd > over25["odd"]:
                            over25 = {
                                "odd": float(odd),
                                "casa": bookmaker.get("title", "")
                            }

    if over25:
        mercados.append(
            f"Mais de 2,5 golos: odd {over25['odd']:.2f} "
            f"({over25['casa']})"
        )

    # Ambas marcam: só apresenta se a API devolver esse mercado.
    btts = melhor_odd(evento, "btts")
    if btts:
        mercados.append(
            f"Ambas marcam — {btts['nome']}: "
            f"odd {btts['odd']:.2f} ({btts['casa']})"
        )

    if not mercados:
        return None

    inicio = evento.get("commence_time", "")
    return {
        "liga": nome_liga,
        "jogo": nome_jogo,
        "inicio": inicio,
        "mercados": mercados
    }


def main():
    if not API_KEY or not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Confirma os secrets ODDS_API_KEY, "
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."
        )

    hoje = datetime.now(timezone.utc).date().isoformat()
    estado = carregar_estado()

    if estado.get("data") != hoje:
        estado = {"data": hoje, "pedidos": 0}

    # Rotação diária: uma liga por dia para poupar créditos.
    # Ao fim de 8 dias, todas as ligas terão sido consultadas.
    indice = datetime.now(timezone.utc).date().toordinal() % len(LIGAS)
    nome_liga, chave_liga = LIGAS[indice]

    # Limite de segurança: no máximo 1 consulta Odds API por execução.
    if estado["pedidos"] >= 1:
        print("Limite diário desta execução já atingido.")
        return

    # Regista antes da consulta para evitar repetições em caso de erro.
    estado["pedidos"] += 1
    guardar_estado(estado)

    eventos, headers = consultar_odds(chave_liga)

    print("Liga consultada:", nome_liga)
    print("Pedidos restantes:", headers.get("x-requests-remaining", "não indicado"))
    print("Créditos usados:", headers.get("x-requests-used", "não indicado"))
    print("Eventos recebidos:", len(eventos))

    agora = datetime.now(timezone.utc)
    candidatos = []

    for evento in eventos:
        try:
            inicio = datetime.fromisoformat(
                evento["commence_time"].replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            continue

        if inicio <= agora:
            continue

        analise = analisar_evento(evento, nome_liga)
        if analise:
            candidatos.append(analise)

    # Até 5 jogos, sem afirmar que são apostas de valor garantido.
    candidatos = candidatos[:MAX_SUGESTOES]

    linhas = [
        "⚽ RB TIPS | AI FOOTBALL",
        f"📅 {datetime.now().strftime('%d/%m/%Y')}",
        f"🏆 Liga analisada: {nome_liga}",
        "",
        "Odds pré-jogo e estimativas estatísticas.",
        "As probabilidades refletem o mercado, não um modelo validado.",
        ""
    ]

    if not candidatos:
        linhas.append(
            "Hoje não foram encontrados jogos futuros com odds suficientes."
        )
    else:
        for numero, jogo in enumerate(candidatos, start=1):
            linhas.append(f"{numero}. {jogo['jogo']}")
            linhas.append(f"🏆 {jogo['liga']}")

            if jogo["inicio"]:
                linhas.append(f"🕒 {jogo['inicio']}")

            for mercado in jogo["mercados"]:
                linhas.append(f"• {mercado}")

            linhas.append("")

    linhas.append(
        "⚠️ Informação estatística, não garantia de resultado. "
        "Aposta apenas com responsabilidade."
    )

    enviar_telegram("\n".join(linhas))
    print("Mensagem enviada ao Telegram.")


if __name__ == "__main__":
    main()
