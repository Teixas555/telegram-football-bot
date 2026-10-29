
import os
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CASINO_CHAT_ID")

FICHEIRO = Path("bacbo_results.json")
TIMEOUT = 20

RESULTADOS_VALIDOS = {"PLAYER", "BANKER", "TIE"}


def carregar_resultados():
    if not FICHEIRO.exists():
        return []

    try:
        dados = json.loads(FICHEIRO.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def guardar_resultados(resultados):
    FICHEIRO.write_text(
        json.dumps(resultados[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def enviar_telegram(mensagem):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Falta configurar TELEGRAM_BOT_TOKEN ou CASINO_CHAT_ID."
        )

    resposta = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
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


def calcular_estatisticas(resultados):
    recentes = resultados[-50:]
    total = len(recentes)

    contagens = {
        nome: recentes.count(nome)
        for nome in sorted(RESULTADOS_VALIDOS)
    }

    linhas = [
        "🎲 RB TIPS CASINO AI",
        "📊 Estatísticas do Bac Bo",
        "",
        f"Resultados registados: {total}",
    ]

    if total == 0:
        linhas.extend([
            "",
            "Ainda não existem resultados registados.",
            "Não há dados suficientes para análise.",
        ])
        return "\n".join(linhas)

    for nome in ("PLAYER", "BANKER", "TIE"):
        percentagem = contagens[nome] / total * 100
        linhas.append(
            f"{nome}: {contagens[nome]} ({percentagem:.1f}%)"
        )

    linhas.append("")

    ultimo = recentes[-1]
    linhas.append(f"Último resultado registado: {ultimo}")

    sequencia = 1
    for resultado in reversed(recentes[:-1]):
        if resultado != ultimo:
            break
        sequencia += 1

    linhas.append(f"Sequência atual: {ultimo} x{sequencia}")
    linhas.append("")

    linhas.append(
        "🔎 Leitura: estatísticas históricas, não uma previsão "
        "fiável da próxima ronda."
    )
    linhas.append(
        "⛔ Sinal: SEM ENTRADA — não existe vantagem demonstrada "
        "apenas com estes resultados."
    )
    linhas.append(
        "⚠️ O histórico não garante resultados futuros. "
        "Joga com responsabilidade."
    )

    return "\n".join(linhas)


def main():
    resultados = carregar_resultados()

    mensagem = calcular_estatisticas(resultados)
    enviar_telegram(mensagem)

    print("Relatório enviado para o grupo RB TIPS CASINO AI.")


if __name__ == "__main__":
    main()
