
import json
import os
import sys
from pathlib import Path

import requests

API_URL = "https://cassinostats.com/api/history/bac-bo"
STATE_FILE = Path("bacbo_results.json")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CASINO_CHAT_ID")


def enviar_telegram(mensagem):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Falta configurar TELEGRAM_BOT_TOKEN ou CASINO_CHAT_ID."
        )

    resposta = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": mensagem},
        timeout=25,
    )
    resposta.raise_for_status()

    dados = resposta.json()
    if not dados.get("ok"):
        raise RuntimeError(str(dados.get("description", "Erro Telegram")))

    print("Telegram confirmou o envio.")


def obter_resultados():
    resposta = requests.get(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
    )
    resposta.raise_for_status()

    dados = resposta.json()
    rondas = dados.get("rounds", [])

    if dados.get("available") is not True or not isinstance(rondas, list):
        raise RuntimeError("Histórico Bac Bo indisponível.")

    validas = [
        r for r in rondas
        if isinstance(r, dict)
        and r.get("outcome") in ("P", "B", "T")
        and r.get("id") is not None
    ]

    if not validas:
        raise RuntimeError("A fonte não devolveu resultados válidos.")

    return validas


def carregar_estado():
    if not STATE_FILE.exists():
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            estado = json.load(f)
        return estado if isinstance(estado, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def guardar_estado(estado):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def encontrar_sequencia(rondas):
    resultados = [
        r for r in rondas if r["outcome"] in ("P", "B")
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
        inicio_id = str(ronda["id"])

    if contagem < 3:
        return None

    return lado, inicio_id


def main():
    manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

    print("RB TIPS CASINO AI iniciado.")

    # O teste manual confirma apenas a ligação ao Telegram.
    if manual:
        enviar_telegram(
            "🧪 TESTE RB TIPS CASINO AI\n\n"
            "✅ O GitHub conseguiu enviar esta mensagem para o Telegram.\n"
            "🎲 Vou verificar a fonte de resultados Bac Bo."
        )

    rondas = obter_resultados()

    print("Rondas recebidas:", len(rondas))
    print("Últimos resultados:", [r["outcome"] for r in rondas[:10]])

    estado = carregar_estado()

    # Avaliar sinais pendentes, se existirem.
    ids = [str(r["id"]) for r in rondas]

    for sinal in estado.get("sinais", []):
        if sinal.get("estado") != "PENDENTE":
            continue

        id_sinal = str(sinal.get("ronda_sinal_id"))
        if id_sinal not in ids:
            continue

        indice = ids.index(id_sinal)
        if indice == 0:
            continue

        # A ronda imediatamente posterior é a mais antiga
        # entre as rondas mais recentes do que o sinal.
        resultado = rondas[indice - 1]["outcome"]

        if resultado == "T":
            sinal["estado"] = "EMPATE"
        elif resultado == sinal["lado"]:
            sinal["estado"] = "WIN"
        else:
            sinal["estado"] = "LOSS"

        sinal["resultado_observado"] = resultado

        enviar_telegram(
            "📊 RESULTADO DO SINAL\n\n"
            f"Entrada: {'PLAYER' if sinal['lado'] == 'P' else 'BANKER'}\n"
            f"Resultado: {sinal['estado']}\n"
            f"Ronda seguinte: {resultado}"
        )

    sequencia = encontrar_sequencia(rondas)

    if sequencia is None:
        print("Sem entrada: não há três resultados consecutivos iguais.")
        guardar_estado(estado)
        if manual:
            enviar_telegram(
                "ℹ️ TESTE CONCLUÍDO\n\n"
                "A fonte respondeu corretamente, mas não há entrada "
                "segundo a regra atual."
            )
        return

    lado, inicio_id = sequencia
    chave = f"{lado}:{inicio_id}"

    if estado.get("ultima_sequencia_enviada") == chave:
        print("Sequência já sinalizada.")
        guardar_estado(estado)
        if manual:
            enviar_telegram(
                "ℹ️ TESTE CONCLUÍDO\n\n"
                "A fonte respondeu, mas esta sequência já foi sinalizada."
            )
        return

    nome = "PLAYER" if lado == "P" else "BANKER"

    enviar_telegram(
        "🎲 RB TIPS CASINO AI\n\n"
        f"📌 ENTRADA EXPERIMENTAL: {nome}\n"
        "📊 Regra: três resultados consecutivos iguais\n"
        "⚠️ Sem garantia de acerto ou lucro."
    )

    estado.setdefault("sinais", []).append({
        "lado": lado,
        "ronda_sinal_id": str(rondas[0]["id"]),
        "sequencia_inicio_id": inicio_id,
        "estado": "PENDENTE",
        "resultado_observado": None,
    })

    estado["ultima_sequencia_enviada"] = chave
    estado["ultima_ronda_verificada"] = str(rondas[0]["id"])
    guardar_estado(estado)

    print("Sinal enviado e histórico guardado.")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print("ERRO:", repr(erro))
        if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
            enviar_telegram(
                "⚠️ ERRO NO TESTE RB TIPS CASINO AI\n\n"
                f"{type(erro).__name__}: {erro}"
            )
        sys.exit(1)
