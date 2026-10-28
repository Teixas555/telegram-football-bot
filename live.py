
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

API_KEY = os.environ["API_FOOTBALL_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API_URL = "https://v3.football.api-sports.io"
FICHEIRO_HISTORICO = "live_alerts.json"
FICHEIRO_CONSUMO = "live_usage.json"
LIMITE_LIVE = 60
DIAS_HISTORICO = 7

LIGAS = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "Liga dos Campeões",
    3: "Liga Europa",
    848: "Liga Conferência",
}


def hoje_utc():
    return datetime.now(timezone.utc).date().isoformat()


def ler_json(caminho):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_json(caminho, dados):
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def carregar_consumo():
    dados = ler_json(FICHEIRO_CONSUMO)

    if dados.get("data") != hoje_utc():
        return {"data": hoje_utc(), "count": 0}

    try:
        count = max(0, int(dados.get("count", 0)))
    except (TypeError, ValueError):
        count = LIMITE_LIVE

    return {"data": hoje_utc(), "count": count}


def pedido_api(endpoint, parametros=None):
    consumo = carregar_consumo()

    if consumo["count"] >= LIMITE_LIVE:
        raise RuntimeError("LIMITE_DIARIO_LIVE_ATINGIDO")

    # Registar a tentativa antes de fazer o pedido.
    consumo["count"] += 1
    guardar_json(FICHEIRO_CONSUMO, consumo)

    url = API_URL + endpoint

    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)

    pedido = urllib.request.Request(
        url, headers={"x-apisports-key": API_KEY}
    )

    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    if dados.get("errors"):
        raise RuntimeError(
            "Erro da API-Football: " + str(dados["errors"])
        )

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


def carregar_historico():
    return ler_json(FICHEIRO_HISTORICO)


def limpar_historico(historico):
    limite = (
        datetime.now(timezone.utc).timestamp()
        - DIAS_HISTORICO * 86400
    )

    return {
        jogo_id: instante
        for jogo_id, instante in historico.items()
        if isinstance(instante, (int, float))
        and instante >= limite
    }


def numero_estatistica(equipa, nome):
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


def classificar_pressao(remates_baliza, remates_totais, cantos):
    if (
        remates_baliza >= 7
        and remates_totais >= 18
        and cantos >= 8
    ):
        return (
            "NÍVEL 3 — PRESSÃO MUITO FORTE",
            "🔥",
            "Indicadores estatísticos muito elevados."
        )

    if (
        remates_baliza >= 5
        and remates_totais >= 14
        and cantos >= 6
    ):
        return (
            "NÍVEL 2 — PRESSÃO FORTE",
            "🟠",
            "Indicadores estatísticos fortes."
        )

    if (
        remates_baliza >= 3
        and remates_totais >= 10
        and cantos >= 4
    ):
        return (
            "NÍVEL 1 — PRESSÃO MODERADA",
            "🟡",
            "Indicadores estatísticos acima dos mínimos."
        )

    return (
        "SEM NÍVEL",
        "⚪",
        "Os critérios mínimos não foram atingidos."
    )


def sugerir_mercados(
    casa, fora, minuto,
    golos_casa, golos_fora,
    remates_baliza, remates_totais, cantos
):
    sugestoes = []
    total_golos = golos_casa + golos_fora

    # Mercado de golos: linha imediatamente acima
    # do total atual. Não é uma previsão de probabilidade.
    if minuto <= 80 and total_golos <= 2:
        linha_golos = total_golos + 0.5
        sugestoes.append(
            f"⚽ Golos: Mais de {linha_golos:.1f} "
            "golos no jogo — analisar"
        )

    # Mercado de cantos: linha acima do total atual.
    if minuto <= 80 and cantos >= 4:
        linha_cantos = int(cantos) + 0.5
        sugestoes.append(
            f"🚩 Cantos: Mais de {linha_cantos:.1f} "
            "cantos no jogo — analisar"
        )

    # Estatísticas individuais para o mercado de resultado.
    baliza_casa = numero_estatistica(
        casa, "Shots on Goal"
    )
    baliza_fora = numero_estatistica(
        fora, "Shots on Goal"
    )
    total_casa = numero_estatistica(
        casa, "Total Shots"
    )
    total_fora = numero_estatistica(
        fora, "Total Shots"
    )

    diferenca = golos_casa - golos_fora

    if diferenca == 0:
        if (
            baliza_casa >= baliza_fora + 2
            and total_casa >= total_fora
        ):
            sugestoes.append(
                "🏆 Resultado: Casa ou Empate (1X) — analisar"
            )
        elif (
            baliza_fora >= baliza_casa + 2
            and total_fora >= total_casa
        ):
            sugestoes.append(
                "🏆 Resultado: Visitante ou Empate (X2) — analisar"
            )

    elif diferenca > 0:
        if (
            baliza_casa >= baliza_fora
            and total_casa >= total_fora
        ):
            sugestoes.append(
                "🏆 Resultado: Casa ou Empate (1X) — analisar"
            )

    else:
        if (
            baliza_fora >= baliza_casa
            and total_fora >= total_casa
        ):
            sugestoes.append(
                "🏆 Resultado: Visitante ou Empate (X2) — analisar"
            )

    return sugestoes


def main():
    historico = limpar_historico(carregar_historico())
    guardar_json(FICHEIRO_HISTORICO, historico)

    consumo = carregar_consumo()
    guardar_json(FICHEIRO_CONSUMO, consumo)

    if consumo["count"] >= LIMITE_LIVE:
        print("Limite diário LIVE atingido; sem novas consultas.")
        return

    ids_ligas = "-".join(str(x) for x in LIGAS)
    jogos = pedido_api("/fixtures", {"live": ids_ligas})

    candidatos = []

    for jogo in jogos:
        liga = jogo.get("league", {})
        fixture = jogo.get("fixture", {})
        status = fixture.get("status", {}).get("short")
        minuto = fixture.get("status", {}).get("elapsed")
        golos = jogo.get("goals", {})
        id_jogo = fixture.get("id")
        casa = golos.get("home")
        fora = golos.get("away")

        if liga.get("id") not in LIGAS:
            continue

        if status not in ("1H", "2H", "HT", "ET", "LIVE"):
            continue

        if not isinstance(minuto, int) or not 55 <= minuto <= 80:
            continue

        if casa is None or fora is None or casa + fora > 2:
            continue

        if id_jogo is None or str(id_jogo) in historico:
            continue

        candidatos.append(jogo)

    # Máximo de uma consulta de estatísticas por execução.
    for jogo in candidatos:
        consumo = carregar_consumo()

        if consumo["count"] >= LIMITE_LIVE:
            print("Limite diário atingido antes das estatísticas.")
            return

        fixture = jogo["fixture"]
        equipas = jogo["teams"]
        golos = jogo["goals"]
        liga = jogo["league"]
        id_jogo = str(fixture["id"])

        estatisticas = pedido_api(
            "/fixtures/statistics",
            {"fixture": id_jogo}
        )

        if len(estatisticas) < 2:
            print("Estatísticas insuficientes.")
            return

        casa_stats = estatisticas[0]
        fora_stats = estatisticas[1]

        remates_baliza = sum(
            numero_estatistica(e, "Shots on Goal")
            for e in estatisticas
        )
        remates_totais = sum(
            numero_estatistica(e, "Total Shots")
            for e in estatisticas
        )
        cantos = sum(
            numero_estatistica(e, "Corner Kicks")
            for e in estatisticas
        )

        print(
            f"{equipas['home']['name']} - "
            f"{equipas['away']['name']}: "
            f"{remates_baliza} remates à baliza, "
            f"{remates_totais} remates totais, "
            f"{cantos} cantos."
        )

        nivel, emoji_nivel, descricao_nivel = (
            classificar_pressao(
                remates_baliza,
                remates_totais,
                cantos
            )
        )

        if nivel == "SEM NÍVEL":
            print("Critérios mínimos de pressão não atingidos.")
            return

        minuto = fixture["status"]["elapsed"]
        golos_casa = golos["home"]
        golos_fora = golos["away"]

        sugestoes = sugerir_mercados(
            casa_stats,
            fora_stats,
            minuto,
            golos_casa,
            golos_fora,
            remates_baliza,
            remates_totais,
            cantos
        )

        if sugestoes:
            texto_sugestoes = "\n".join(
                f"• {sugestao}" for sugestao in sugestoes
            )
        else:
            texto_sugestoes = (
                "Não existem indicadores suficientes "
                "para sugerir um mercado de resultado."
            )

        mensagem = (
            "👑 RB TIPS\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{emoji_nivel} {nivel}\n"
            f"{descricao_nivel}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 {LIGAS.get(liga['id'], 'Competição')}\n"
            f"⚽ {equipas['home']['name']} "
            f"{golos_casa} - {golos_fora} "
            f"{equipas['away']['name']}\n"
            f"⏱️ Minuto de jogo: {minuto}'\n\n"
            "📊 ESTATÍSTICAS\n"
            "──────────────────\n"
            f"🎯 Remates à baliza: {int(remates_baliza)}\n"
            f"🥅 Remates totais: {int(remates_totais)}\n"
            f"🚩 Cantos: {int(cantos)}\n\n"
            "💡 MERCADOS A ANALISAR\n"
            "──────────────────\n"
            f"{texto_sugestoes}\n\n"
            "⚠️ O nível mede apenas os indicadores "
            "estatísticos definidos. Não representa uma "
            "probabilidade calculada nem garante golos, "
            "resultados ou lucro. Confirma sempre as odds "
            "e o contexto do jogo.\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🖤 RB TIPS | Analisar antes de apostar"
        )

        enviar_telegram(mensagem)

        historico[id_jogo] = (
            datetime.now(timezone.utc).timestamp()
        )
        guardar_json(FICHEIRO_HISTORICO, historico)

        print(f"Alerta enviado: {nivel}.")
        return

    print("Verificação concluída; nenhum alerta novo.")


if __name__ == "__main__":
    main()
