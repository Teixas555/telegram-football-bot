
import json
import os
from pathlib import Path

import requests

# Fonte pública de resultados Bac Bo
API_URL = "https://cassinostats.com/api/history/bac-bo"

# Ficheiro para guardar o estado e evitar sinais duplicados
STATE_FILE = Path("bacbo_results.json")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CASINO_CHAT_ID")


def carregar_estado():
    if not STATE_FILE.exists():
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            estado = json.load(f)
        return estado if isinstance(estado, dict) else {}
    except (OSError, json.JSONDecodeError):
        print("Aviso: não foi possível ler o estado anterior.")
        return {}


def guardar_estado(estado):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def obter_resultados():
    print("A consultar a fonte pública de Bac Bo...")

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
        raise RuntimeError("O histórico Bac Bo está indisponível.")

    rondas = dados.get("rounds")

    if not isinstance(rondas, list) or not rondas:
        raise RuntimeError("A fonte não devolveu resultados.")

    validas = [
        ronda for ronda in rondas
        if isinstance(ronda, dict)
        and ronda.get("outcome") in ("P", "B", "T")
        and ronda.get("id") is not None
    ]

    if not validas:
        raise RuntimeError("Não existem resultados válidos.")

    print("Resultados válidos recebidos:", len(validas))
    print(
        "Últimos resultados:",
        [r["outcome"] for r in validas[:10]]
    )

    return validas


def encontrar_sequencia(rondas):
    # A fonte apresenta a ronda mais recente primeiro.
    # P = Player, B = Banker, T = empate.
    # Os empates são ignorados na contagem.

    resultados = [
        ronda for ronda in rondas
        if ronda["outcome"] in ("P", "B")
    ]

    if len(resultados) < 3:
        print("Ainda não existem 3 resultados não empatados.")
        return None

    lado = resultados[0]["outcome"]
    contagem = 0
    inicio_id = None

    for ronda in resultados:
        if ronda["outcome"] != lado:
            break

        contagem += 1
        inicio_id = ronda["id"]

    print("Lado da sequência:", "PLAYER" if lado == "P" else "BANKER")
    print("Resultados consecutivos:", contagem)

    if contagem < 3:
        print("Sem entrada: não há 3 resultados consecutivos iguais.")
        return None

    return lado, inicio_id


def enviar_sinal(lado):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Falta configurar TELEGRAM_BOT_TOKEN ou CASINO_CHAT_ID."
        )

    nome = "PLAYER" if lado == "P" else "BANKER"

    mensagem = (
        "🎲 RB TIPS CASINO AI\n\n"
        f"📌 ENTRADA EXPERIMENTAL: {nome}\n"
        "🎯 Jogo: Bac Bo\n"
        "📊 Regra: 3 resultados consecutivos iguais\n"
        "⚠️ Sinal experimental; não garante acerto nem lucro."
    )

    resposta = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": mensagem,
        },
        timeout=25,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    if not dados.get("ok"):
        raise RuntimeError(
            "O Telegram recusou o envio: "
            + str(dados.get("description", "erro desconhecido"))
        )

    print("Telegram confirmou o envio do sinal:", nome)


def main():
    print("===================================")
    print("RB TIPS CASINO AI - INÍCIO")
    print("===================================")

    rondas = obter_resultados()
    estado = carregar_estado()

    ronda_mais_recente = rondas[0]["id"]
    print("ID da ronda mais recente:", ronda_mais_recente)

    sequencia = encontrar_sequencia(rondas)

    if sequencia is None:
        print("Nenhuma entrada encontrada.")
        estado["ultima_ronda_verificada"] = ronda_mais_recente
        guardar_estado(estado)
        return

    lado, inicio_id = sequencia
    chave = f"{lado}:{inicio_id}"

    if estado.get("ultima_sequencia_enviada") == chave:
        print("Esta sequência já foi sinalizada. Sem mensagem duplicada.")
        estado["ultima_ronda_verificada"] = ronda_mais_recente
        guardar_estado(estado)
        return

    print("A tentar enviar o sinal para o Telegram...")
    enviar_sinal(lado)

    # Guardar apenas depois de o Telegram confirmar o envio.
    estado["ultima_sequencia_enviada"] = chave
    estado["ultima_ronda_verificada"] = ronda_mais_recente
    guardar_estado(estado)

    print("Sinal enviado e estado guardado.")
    print("RB TIPS CASINO AI - FIM")


if __name__ == "__main__":
    main()
