
import re
import requests
from html import unescape

URL = "https://betmind.org/catalogador-bacbo"

def main():
    print("A testar a página pública do BETMIND...")

    try:
        resposta = requests.get(
            URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
                )
            },
            timeout=25,
        )

        print("Código HTTP:", resposta.status_code)
        print("Tipo de conteúdo:", resposta.headers.get(
            "Content-Type", "desconhecido"
        ))

        resposta.raise_for_status()
        html = resposta.text

        titulo = re.search(
            r"<title[^>]*>(.*?)</title>",
            html,
            re.IGNORECASE | re.DOTALL,
        )

        if titulo:
            print("Título:", unescape(titulo.group(1)).strip())

        print("Tamanho da página:", len(html), "caracteres")
        print("\nVerificação de palavras:")

        for palavra in [
            "PLAYER",
            "BANKER",
            "TIE",
            "BAC BO",
            "BACBO",
            "resultados",
            "application/json",
        ]:
            encontrada = palavra.lower() in html.lower()
            print(f"{palavra}: {'ENCONTRADO' if encontrada else 'NÃO ENCONTRADO'}")

        texto = re.sub(r"\s+", " ", html)
        print("\nInício do HTML recebido:")
        print(texto[:1200])

        print(
            "\nNOTA: encontrar estas palavras não confirma que "
            "os resultados reais estejam acessíveis."
        )

    except requests.RequestException as erro:
        print("Não foi possível consultar a página.")
        print("Erro:", erro)


if __name__ == "__main__":
    main()
