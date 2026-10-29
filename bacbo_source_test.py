
import re
import requests
from html import unescape

URL = "https://cassinostats.com/pt/jogo/bac-bo/estatisticas"

def main():
    print("A testar a fonte gratuita Cassino Stats...")

    try:
        resposta = requests.get(
            URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=25,
        )

        print("Código HTTP:", resposta.status_code)
        resposta.raise_for_status()

        html = resposta.text
        texto = unescape(re.sub(r"<[^>]+>", " ", html))
        texto = re.sub(r"\s+", " ", texto)

        print("Tamanho da página:", len(html))
        print("\nResultados encontrados:")

        for palavra in ["Player", "Banker", "Empate", "Últimos resultados"]:
            print(f"{palavra}: {'SIM' if palavra.lower() in texto.lower() else 'NÃO'}")

        print("\nExcerto da página:")
        print(texto[:2500])

        print("\nTeste concluído.")

    except requests.RequestException as erro:
        print("Falha ao consultar a página:", erro)

if __name__ == "__main__":
    main()
