
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

    return {"data": "", "ligas_consultadas": []}


def guardar_estado(estado):
    FICHEIRO.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2),
        encoding="utf-8",
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
    resposta = requests.get(
        f"{BASE_URL}/sports/{liga}/odds",
        params={
            "apiKey": API_KEY,
            "regions": REGIONS,
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
        timeout=TIMEOUT,
    )

    print(f"\nCompetição: {liga}")
    print("HTTP:", resposta.status_code)
    print("Créditos desta consulta:",
          resposta.headers.get("x-requests-last", "não indicado"))
    print("Créditos restantes:",
          resposta.headers.get("x-requests-remaining", "não indicado"))

    if resposta.status_code != 200:
        raise RuntimeError(
            f"Erro na Odds API ({liga}): HTTP {resposta.status_code} "
            f"- {resposta.text[:300]}"
        )

    dados = resposta.json()
    if not isinstance(dados, list):
        raise RuntimeError("A resposta da API não tem o formato esperado.")

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
                ponto = resultado.get("point")

                if not nome or not isinstance(odd, (int, float)) or odd <= 1:
                    continue

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

    # 1X2: só apresentar se existirem odds para as três opções.
    selecoes = [h2h.get((nome, None)) for nome in (casa, "Draw", fora)]

    if all(selecoes):
        soma = sum(1 / item["odd"] for item in selecoes)

        if soma > 0:
            probabilidades = {
                item["nome"]: (1 / item["odd"]) / soma
                for item in selecoes
            }

            favorito = max(
                selecoes,
                key=lambda item: probabilidades[item["nome"]],
            )

            prob = probabilidades[favorito["nome"]] * 100

            mercados.append(
                f"🎯 1X2: {favorito['nome']} — odd {favorito['odd']:.2f}"
            )
            mercados.append(
                f"📊 Probabilidade de mercado ajustada: {prob:.1f}%"
            )

            prob_1x = (probabilidades[casa] + probabilidades["Draw"]) * 100
            prob_x2 = (probabilidades[fora] + probabilidades["Draw"]) * 100

            if prob_1x >= prob_x2:
                mercados.append(
                    f"🔁 Dupla possibilidade 1X — estimativa {prob_1x:.1f}%"
                )
            else:
                mercados.append(
                    f"🔁 Dupla possibilidade X2 — estimativa {prob_x2:.1f}%"
                )

    # Mais de 2,5 golos: só mostrar se houver essa linha.
    over25 = totais.get(("Over", 2.5))

    if over25:
        mercados.append(
            f"⚽ Mais de 2,5 golos: odd {over25['odd']:.2f} "
            f"({over25['casa']})"
        )

    if not mercados:
        return None

    try:
        inicio = datetime.fromisoformat(
            evento["commence_time"].replace("Z", "+00:00")
        )
    except (KeyError, ValueError, TypeError):
        return None

    return {
        "liga": nome_liga,
        "jogo": f"{casa} - {fora}",
        "inicio": inicio,
        "mercados": mercados,
    }


def main():
    if not API_KEY or not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Falta um secret: ODDS_API_KEY, TELEGRAM_BOT_TOKEN "
            "ou TELEGRAM_CHAT_ID."
        )

    hoje = datetime.now(timezone.utc).date().isoformat()
    estado = carregar_estado()

    if estado.get("data") != hoje:
        estado = {"data": hoje, "ligas_consultadas": []}

    consultadas = set(estado.get("ligas_consultadas", []))

    if len(consultadas) >= len(LIGAS):
        print("As oito competições já foram consultadas hoje.")
        return

    agora = datetime.now(timezone.utc)
    candidatos = []
    erros = []

    for nome_liga, chave_liga in LIGAS:
        if chave_liga in consultadas:
            continue

        try:
            eventos = consultar_odds(chave_liga)

            # Guardar o progresso depois de cada consulta bem-sucedida.
            consultadas.add(chave_liga)
            estado["ligas_consultadas"] = sorted(consultadas)
            guardar_estado(estado)

            for evento in eventos:
                analise = analisar_evento(evento, nome_liga)

                if analise and analise["inicio"] > agora:
                    candidatos.append(analise)

        except (requests.RequestException, RuntimeError, ValueError) as erro:
            erros.append(f"{nome_liga}: {erro}")
            print(f"Falha em {nome_liga}: {erro}")

    # Remover eventuais duplicados e ordenar pelos jogos mais próximos.
    unicos = {}

    for jogo in candidatos:
        chave = (jogo["jogo"], jogo["inicio"].isoformat())
        if chave not in unicos:
            unicos[chave] = jogo

    candidatos = sorted(
        unicos.values(),
        key=lambda jogo: jogo["inicio"],
    )[:MAX_SUGESTOES]

    linhas = [
        "⚽ RB TIPS | AI FOOTBALL",
        f"📅 {datetime.now().strftime('%d/%m/%Y')}",
        "🏆 Competições: análise das 8 ligas",
        "",
        "📌 Odds reais disponíveis: 1X2 e Mais de 2,5 golos.",
        "🔁 Dupla possibilidade: estimada a partir das odds 1X2.",
        "🚫 Ambas marcam: indisponível nesta versão.",
        "",
    ]

    if candidatos:
        for numero, jogo in enumerate(candidatos, start=1):
            inicio_local = jogo["inicio"].astimezone()

            linhas.append(f"{numero}. {jogo['jogo']}")
            linhas.append(f"🏆 {jogo['liga']}")
            linhas.append(f"🕒 {inicio_local:%d/%m/%Y %H:%M}")

            linhas.extend(f"• {mercado}" for mercado in jogo["mercados"])
            linhas.append("")
    else:
        linhas.append(
            "Não foram encontradas sugestões com mercados suficientes "
            "nos jogos futuros disponíveis."
        )

    if erros:
        linhas.append(
            f"⚠️ Não foi possível consultar {len(erros)} competição(ões)."
        )

    linhas.append(
        "⚠️ As probabilidades refletem o mercado, não um modelo "
        "independente validado. Não há garantia de lucro. "
        "Aposta com responsabilidade."
    )

    enviar_telegram("\n".join(linhas))
    print("Mensagem enviada ao Telegram.")


if __name__ == "__main__":
    main()
