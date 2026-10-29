
import json
import os
from pathlib import Path

import requests

API_URL = "https://cassinostats.com/api/history/bac-bo"
STATE_FILE = Path("bacbo_results.json")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CASINO_CHAT_ID")


def carregar_estado():
    if not STATE_FILE.exists():
        return {
            "ultima_sequencia_enviada": None,
            "ultima_ronda_verificada": None,
            "sinais": [],
        }

    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            estado = json.load(f)

        if not isinstance(estado, dict):
            estado = {}

        estado.setdefault("ultima_sequencia_enviada", None)
        estado.setdefault("ultima_ronda_verificada", None)
        estado.setdefault("sinais", [])

        if not isinstance(estado["sinais"], list):
            estado["sinais"] = []

        return estado

    except (OSError, json.JSONDecodeError):
        print("Aviso: não foi possível ler o histórico.")
        return {
            "ultima_sequencia_enviada": None,
            "ultima_ronda_verificada": None,
            "sinais": [],
        }


def guardar_estado(estado):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def obter_resultados():
    print("A consultar os resultados de Bac Bo...")

    resposta = requests.get(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://cassinostats.com/pt/jogo/bac-bo/estatisticas",
        },
        timeout=25,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    if dados.get("available") is not True:
        raise RuntimeError("Histórico Bac Bo indisponível.")

    rondas = dados.get("rounds")

    if not isinstance(rondas, list) or not rondas:
        raise RuntimeError("A fonte não devolveu rondas.")

    validas = [
        r for r in rondas
        if isinstance(r, dict)
        and r.get("outcome") in ("P", "B", "T")
        and r.get("id") is not None
    ]

    if not validas:
        raise RuntimeError("Não existem resultados válidos.")

    print("Rondas recebidas:", len(validas))
    print("Últimos resultados:", [r["outcome"] for r in validas[:10]])

    return validas


def enviar_telegram(mensagem):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Faltam os secrets TELEGRAM_BOT_TOKEN ou CASINO_CHAT_ID."
        )

    resposta = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": mensagem},
        timeout=25,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    if not dados.get("ok"):
        raise RuntimeError(
            "Erro do Telegram: "
            + str(dados.get("description", "erro desconhecido"))
        )

    print("Mensagem enviada ao Telegram.")


def encontrar_sequencia(rondas):
    resultados = [
        r for r in rondas
        if r["outcome"] in ("P", "B")
    ]

    if len(resultados) < 3:
        return None

    lado = resultados[0]["outcome"]
    contagem = 0
    inicio_id = None

    for ronda in resultados:
        if ronda["outcome"] != lado:
            break

        contagem += 1
        inicio_id = ronda["id"]

    print("Sequência atual:", contagem)

    if contagem < 3:
        return None

    return lado, inicio_id


def avaliar_sinais_pendentes(rondas, estado):
    # A fonte apresenta as rondas da mais recente para a mais antiga.
    ids = [str(r["id"]) for r in rondas]
    alterado = False

    for sinal in estado["sinais"]:
        if sinal.get("estado") != "PENDENTE":
            continue

        id_sinal = str(sinal["ronda_sinal_id"])

        if id_sinal not in ids:
            print(
                "Sinal pendente: a ronda original já não está "
                "disponível no histórico."
            )
            continue

        indice = ids.index(id_sinal)
        rondas_posteriores = rondas[:indice]

        if not rondas_posteriores:
            continue

        # A última das rondas mais recentes é a primeira
        # que ocorreu depois da ronda em que foi emitido o sinal.
        resultado = rondas_posteriores[-1]["outcome"]

        if resultado == "T":
            sinal["estado"] = "EMPATE"
        elif resultado == sinal["lado"]:
            sinal["estado"] = "WIN"
        else:
            sinal["estado"] = "LOSS"

        sinal["resultado_observado"] = resultado
        alterado = True

        nome_lado = "PLAYER" if sinal["lado"] == "P" else "BANKER"
        nome_resultado = {
            "P": "PLAYER",
            "B": "BANKER",
            "T": "EMPATE",
        }[resultado]

        mensagem = (
            "🎲 RB TIPS CASINO AI\n\n"
            f"📊 Resultado do sinal: {sinal['estado']}\n"
            f"📌 Entrada: {nome_lado}\n"
            f"🎯 Resultado seguinte: {nome_resultado}\n"
            "ℹ️ Registo experimental; não garante lucro."
        )

        enviar_telegram(mensagem)

    return alterado


def enviar_estatisticas(estado):
    avaliados = [
        s for s in estado["sinais"]
        if s.get("estado") in ("WIN", "LOSS", "EMPATE")
    ]

    wins = sum(s["estado"] == "WIN" for s in avaliados)
    losses = sum(s["estado"] == "LOSS" for s in avaliados)
    empates = sum(s["estado"] == "EMPATE" for s in avaliados)
    pendentes = sum(
        s.get("estado") == "PENDENTE" for s in estado["sinais"]
    )

    decididos = wins + losses
    taxa = (wins / decididos * 100) if decididos else 0

    mensagem = (
        "📈 RB TIPS CASINO AI — ESTATÍSTICAS\n\n"
        f"🔢 Sinais registados: {len(estado['sinais'])}\n"
        f"✅ WIN: {wins}\n"
        f"❌ LOSS: {losses}\n"
        f"🤝 EMPATE: {empates}\n"
        f"⏳ Pendentes: {pendentes}\n"
        f"🎯 Taxa de acerto (sem empates): {taxa:.1f}%\n\n"
        "ℹ️ Estatísticas experimentais, sem garantia de lucro."
    )

    enviar_telegram(mensagem)


def main():
    print("=== RB TIPS CASINO AI ===")

    rondas = obter_resultados()
    estado = carregar_estado()

    # Avaliar primeiro sinais que já existiam.
    avaliar_sinais_pendentes(rondas, estado)

    sequencia = encontrar_sequencia(rondas)

    if sequencia is None:
        print("Sem entrada: não há três resultados iguais.")
        estado["ultima_ronda_verificada"] = str(rondas[0]["id"])
        guardar_estado(estado)
        return

    lado, inicio_id = sequencia
    chave = f"{lado}:{inicio_id}"

    if estado.get("ultima_sequencia_enviada") == chave:
        print("Esta sequência já foi sinalizada.")
        guardar_estado(estado)
        return

    nome = "PLAYER" if lado == "P" else "BANKER"

    mensagem = (
        "🎲 RB TIPS CASINO AI\n\n"
        f"📌 ENTRADA EXPERIMENTAL: {nome}\n"
        "🎯 Jogo: Bac Bo\n"
        "📊 Regra: 3 resultados consecutivos iguais\n"
        "⚠️ Não existe garantia de acerto ou lucro."
    )

    # O sinal é registado como pendente e avaliado
    # quando a fonte disponibilizar uma ronda posterior.
    enviar_telegram(mensagem)

    estado["sinais"].append({
        "lado": lado,
        "ronda_sinal_id": str(rondas[0]["id"]),
        "sequencia_inicio_id": str(inicio_id),
        "estado": "PENDENTE",
        "resultado_observado": None,
    })

    estado["ultima_sequencia_enviada"] = chave
    estado["ultima_ronda_verificada"] = str(rondas[0]["id"])

    guardar_estado(estado)
    print("Sinal guardado no histórico.")


if __name__ == "__main__":
    main()
