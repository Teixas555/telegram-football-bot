
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
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as ficheiro:
            estado = json.load(ficheiro)
        return estado if isinstance(estado, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar_estado(estado):
    with STATE_FILE.open("w", encoding="utf-8") as ficheiro:
        json.dump(estado, ficheiro, ensure_ascii=False, indent=2)


def obter_resultados():
    resposta = requests.get(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resposta.raise_for_status()
    dados = resposta.json()

    if dados.get("available") is not True:
        raise RuntimeError("Histórico Bac Bo indisponível.")

    rondas = dados.get("rounds")
    if not isinstance(rondas, list) or not rondas:
        raise RuntimeError("A fonte não devolveu rondas válidas.")

    validas = [
        ronda for ronda in rondas
        if ronda.get("outcome") in ("P", "B", "T")
        and ronda.get("id")
    ]

    if not validas:
        raise RuntimeError("Não foram encontrados resultados válidos.")

    return validas


def encontrar_sequencia(rondas):
    # A fonte apresenta primeiro a ronda mais recente.
    # Os empates são ignorados na contagem.
    resultados = [
        ronda for ronda in rondas
        if ronda["outcome"] in ("P", "B")
    ]

    if len(resultados) < 3:
        return None

    lado = resultados[0]["outcome"]

    if any(r["outcome"] != lado for r in resultados[:3]):
        return None

    # Identifica o início da sequência completa para evitar
    # repetir o sinal enquanto a mesma sequência continua.
    sequencia = [
        ronda for ronda in resultados
        if ronda["outcome"] == lado
    ]

    inicio = sequencia[0]
    for ronda in resultados:
        if ronda["outcome"] != lado:
            break
        inicio = ronda

    return lado, inicio["id"], resultados[0]["id"]


def enviar_sinal(lado, ronda_id):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Faltam TELEGRAM_BOT_TOKEN ou CASINO_CHAT_ID.")

    nome = "PLAYER" if lado == "P" else "BANKER"

    mensagem = (
        "🎲 RB TIPS CASINO AI\n\n"
        f"📌 ENTRADA EXPERIMENTAL: {nome}\n"
        "🎯 Jogo: Bac Bo\n"
        "📊 Regra: 3 resultados consecutivos iguais\n"
        "⚠️ Sem garantia de acerto ou lucro."
    )

    resposta = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": mensagem,
        },
        timeout=20,
    )
    resposta.raise_for_status()

    dados = resposta.json()
    if not dados.get("ok"):
        raise RuntimeError("O Telegram não confirmou o envio.")


def main():
    rondas = obter_resultados()
    estado = carregar_estado()

    sequencia = encontrar_sequencia(rondas)

    if sequencia is None:
        # Não enviar mensagens quando não há entrada.
        return

    lado, inicio_id, ronda_recente_id = sequencia
    chave = f"{lado}:{inicio_id}"

    if estado.get("ultima_sequencia_enviada") == chave:
        return

    # Só registar o sinal depois de o Telegram confirmar o envio.
    enviar_sinal(lado, ronda_recente_id)

    estado["ultima_sequencia_enviada"] = chave
    estado["ultima_ronda_verificada"] = rondas[0]["id"]
    guardar_estado(estado)


if __name__ == "__main__":
    main()
