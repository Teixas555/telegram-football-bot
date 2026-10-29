
import re
import requests
from urllib.parse import urljoin

URL = "https://cassinostats.com/pt/jogo/bac-bo/estatisticas"

def main():
    print("A procurar fontes de dados do Bac Bo...")

    resposta = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    print("HTTP:", resposta.status_code)
    resposta.raise_for_status()

    html = resposta.text

    print("\n--- Ficheiros JavaScript ---")
    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    for src in scripts[:25]:
        print(urljoin(URL, src))

    print("\n--- Referências a possíveis fontes de dados ---")
    padrao = r"""["']([^"'\\\s]{0,180}(?:/api/|graphql|websocket|bac.bo|bac-bo|history|results|resultados)[^"'\\\s]{0,180})["']"""

    encontrados = sorted(set(re.findall(padrao, html, re.IGNORECASE)))

    for item in encontrados[:60]:
        print(item)

    if not encontrados:
        print("Não foram encontradas referências óbvias.")

    print("\nFim do teste. Nenhuma mensagem foi enviada.")

if __name__ == "__main__":
    main()
