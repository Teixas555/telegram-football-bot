
import requests
import json

BASE = "https://cassinostats.com"

def testar(caminho):
    url = BASE + caminho
    print("\nA testar:", caminho)

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": BASE + "/pt/jogo/bac-bo/estatisticas",
            },
            timeout=20,
        )

        print("HTTP:", r.status_code)
        print("Tipo:", r.headers.get("content-type", "desconhecido"))

        try:
            dados = r.json()
            print(json.dumps(dados, ensure_ascii=False)[:3000])
        except ValueError:
            print(r.text[:1000])

    except requests.RequestException as e:
        print("Erro:", e)

def main():
    testar("/api/live")
    testar("/api/history/bac-bo")

    print("\nTeste concluído. Nenhuma mensagem foi enviada.")

if __name__ == "__main__":
    main()
