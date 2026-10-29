
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
TIMEOUT = 25
FICHEIRO = Path("ai_usage.json")

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


def carregar_estado():
    if FICHEIRO.exists():
        try:
            estado = json.loads(FICHEIRO.read_text(encoding="utf-8"))
            if isinstance(estado, dict):
                return estado
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
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
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
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
        timeout=TIMEOUT,
    )

    print("Código HTTP Odds API:", resposta.status_code)
    print(
        "Créditos utilizados:",
        resposta.headers.get("x-requests-used", "não indicado"),
    )
    print(
        "Créditos restantes:",
        resposta.headers.get("x-requests-remaining", "não indicado"),
    )

    if resposta.status_code != 200:
        raise RuntimeError(
            f"Odds API HTTP {resposta.status_code}: "
            f"{resposta.text[:400]}"
        )

    dados = resposta.json()
    if not isinstance(dados, list):
        raise RuntimeError("A resposta de odds não tem o formato esperado.")

    return dados


def recolher_resultados(evento, mercado_chave):
    resultados = {}

    for casa in evento.get("bookmakers", []):
        for mercado in casa.get("markets", []):
            if mercado.get("key") != mercado_chave:
                continue

            for resultado in mercado.get("outcomes", []):
                nome = resultado.get("name")
                odd = resultado.get("price")

                if not nome or not isinstance(odd, (int, float)) or odd <= 1:
                    continue

                ponto = resultado.get("point")
                chave = (nome, ponto)

                atual = resultados.get(chave)
                if atual is None or odd > atual["odd"]:
                    resultados[chave] = {
                        "nome": nome,
                        "odd": float(odd),
                        "casa": casa.get("title", "Casa desconhecida"),
                        "ponto": ponto,
                    }

    return resultados


def analisar_evento(evento, nome_liga):
    casa = evento.get("home_team")
    fora = evento.get("away_team")

    if not casa or not fora:
        return None

    h2h = recolher_resultados(evento, "h2h")
    totais = recolher_resultados(evento, "totals")
    mercados = []

    # Probabilidades 1X2 ajustadas para remover aproximadamente
    # a margem da casa, usando as melhores odds disponíveis.
    nomes_esperados = [casa, "Draw", fora]
    selecoes = [h2h.get((nome, None)) for nome in nomes_esperados]

    if all(selecoes):
        soma = sum(1 / item["odd"] for item in selecoes)

        if soma > 0:
            probabilidades = {
                item["nome"]: (1 / item["odd"]) / soma
                for item in selecoes
            }

            favorito = max(
                selecoes,
                key=lambda item: probabilidades[item["nome"]]
            )
            prob_favorito = probabilidades[favorito["nome"]] * 100

            mercados.append(
                f"🎯 1X2: {favorito['nome']} — odd {favorito['odd']:.2f}"
            )
            mercados.append(
                f"📊 Probabilidade de mercado ajustada: "
                f"{prob_favorito:.1f}%"
            )

            # Dupla possibilidade calculada a partir do 1X2.
            prob_1x = (
                probabilidades[casa] + probabilidades["Draw"]
            ) * 100
            prob_x2 = (
                probabilidades[fora] + probabilidades["Draw"]
            ) * 100

            if prob_1x >= prob_x2:
                mercados.append(
                    f"🔁 Dupla possibilidade estimada: 1X ({prob_1x:.1f}%)"
                )
            else:
                mercados.append(
                    f"🔁 Dupla possibilidade estimada: X2 ({prob_x2:.1f}%)"
                )

    # Mais de 2,5 golos: exige uma linha Over 2.5.
    over25 = totais.get(("Over", 2.5))
    if over25:
        mercados.append(
            f"⚽ Mais de 2,5 golos: odd {over25['odd']:.2f} "
            f"({over25['casa']})"
        )

    if not mercados:
        return None

    inicio = evento.get("commence_time", "")
    return {
        "liga": nome_liga,
        "jogo": f"{casa} - {fora}",
        "inicio": inicio,
        "mercados": mercados,
    }


def main():
    if not API_KEY or not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Falta um dos secrets: ODDS_API_KEY, "
            "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID."
        )

    hoje = datetime.now(timezone.utc).date().isoformat()
    estado = carregar_estado()

    if estado.get("data") != hoje:
        estado = {"data": hoje, "pedidos": 0}

    if estado.get("pedidos", 0) >= 1:
        print(
            "A consulta diária já foi registada. "
            "Não será feita outra consulta para evitar gastar créditos."
        )
        return

    # Rotação: consulta uma das oito ligas por dia.
    indice = datetime.now(timezone.utc).date().toordinal() % len(LIGAS)
    nome_liga, chave_liga = LIGAS[indice]

    # Regista antes do pedido para reduzir o risco de repetição.
    estado["pedidos"] = 1
    guardar_estado(estado)

    eventos = consultar_odds(chave_liga)
    agora = datetime.now(timezone.utc)
    candidatos = []

    for evento in eventos:
        try:
            inicio = datetime.fromisoformat(
                evento["commence_time"].replace("Z", "+00:00")
            )
        except (KeyError, ValueError, TypeError):
            continue

        if inicio <= agora:
            continue

        analise = analisar_evento(evento, nome_liga)
        if analise:
            candidatos.append(analise)

    candidatos.sort(key=lambda item: item["inicio"])
    candidatos = candidatos[:MAX_SUGESTOES]

    linhas = [
        "⚽ RB TIPS | AI FOOTBALL",
        f"📅 {datetime.now().strftime('%d/%m/%Y')}",
        f"🏆 Competição analisada: {nome_liga}",
        "",
        "📌 Mercados com odds reais: 1X2 e Mais de 2,5 golos,",
        "quando disponíveis.",
        "🔁 Dupla possibilidade: probabilidade derivada do 1X2.",
        "🚫 Ambas marcam: sem odds nesta versão.",
        "",
    ]

    if not candidatos:
        linhas.append(
            "Não foram encontrados jogos futuros com mercados suficientes."
        )
    else:
        for numero, jogo in enumerate(candidatos, start=1):
            linhas.append(f"{numero}. {jogo['jogo']}")
            linhas.append(f"🏆 {jogo['liga']}")

            if jogo["inicio"]:
                linhas.append(f"🕒 {jogo['inicio']}")

            linhas.extend(f"• {mercado}" for mercado in jogo["mercados"])
            linhas.append("")

    linhas.append(
        "⚠️ As probabilidades refletem o mercado e não um modelo "
        "independente validado. Não há garantia de lucro. "
        "Aposta com responsabilidade."
    )

    enviar_telegram("\n".join(linhas))
    print("Mensagem enviada ao Telegram.")


if __name__ == "__main__":
    main()
