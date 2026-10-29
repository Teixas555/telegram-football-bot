
import re
import requests
from urllib.parse import urljoin

BASE = "https://cassinostats.com"
PAGINA = BASE + "/pt/jogo/bac-bo/estatisticas"

TERMOS = [
    "bac-bo",
    "historico",
    "últimos resultados",
    "ultimos resultados",
    "player",
    "banker",
    "rounds",
    "history",
    "resultados",
    "dataset",
    "api/",
]

def main():
    sessao = requests.Session()
    sessao.headers["User-Agent"] = "Mozilla/5.0"

    pagina = sessao.get(PAGINA, timeout=30)
    print("Página HTTP:", pagina.status_code)
    pagina.raise_for_status()

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)',
        pagina.text,
        re.IGNORECASE,
    )

    vistos = set()

    for caminho in scripts:
        url = urljoin(BASE, caminho)
        if url in vistos:
            continue
        vistos.add(url)

        try:
            resposta = sessao.get(url, timeout=20)
            if resposta.status_code != 200:
                continue
            codigo = resposta.text
        except requests.RequestException:
            continue

        achados = []
        for termo in TERMOS:
            if termo.lower() in codigo.lower():
                achados.append(termo)

        if achados:
            print("\nFicheiro:", caminho)
            print("Termos encontrados:", ", ".join(achados))

            for termo in ["historico", "ultimos resultados", "history", "dataset"]:
                pos = codigo.lower().find(termo.lower())
                if pos >= 0:
                    contexto = re.sub(
                        r"\s+", " ",
                        codigo[max(0, pos - 180):pos + 300]
                    )
                    print("Contexto:", contexto[:480])
                    break

    print("\nTeste concluído. Nenhum sinal foi enviado.")

if __name__ == "__main__":
    main()
