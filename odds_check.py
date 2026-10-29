
import os
import requests

API_KEY = os.getenv("ODDS_API_KEY")
URL = "https://api.the-odds-api.com/v4/sports/"


def main():
    if not API_KEY:
        raise RuntimeError(
            "Falta o secret ODDS_API_KEY nas definições do GitHub."
        )

    resposta = requests.get(
        URL,
        params={"apiKey": API_KEY},
        timeout=25
    )

    print("Código HTTP:", resposta.status_code)

    if resposta.status_code != 200:
        raise RuntimeError(
            "Erro da API: " + resposta.text[:300]
        )

    dados = resposta.json()

    if not isinstance(dados, list):
        raise RuntimeError("A resposta da API não é uma lista.")

    print("\nCOMPETIÇÕES DE FUTEBOL DISPONÍVEIS")
    print("-" * 40)

    encontradas = 0

    for desporto in dados:
        chave = desporto.get("key", "")
        grupo = desporto.get("group", "")

        if "soccer" in chave.lower() or "soccer" in grupo.lower():
            print(
                desporto.get("title", chave),
                "|",
                chave
            )
            encontradas += 1

    if encontradas == 0:
        print("Não foram encontradas competições de futebol.")

    print("\nTeste concluído.")
    print("Esta consulta não utiliza créditos de odds.")


if __name__ == "__main__":
    main()
