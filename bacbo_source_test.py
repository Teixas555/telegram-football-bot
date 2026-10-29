
import re
import requests
from urllib.parse import urljoin

BASE = "https://cassinostats.com"
PAGINA = BASE + "/pt/jogo/bac-bo/estatisticas"

def main():
    print("A investigar o código público do Cassino Stats...")

    sessao = requests.Session()
    sessao.headers["User-Agent"] = "Mozilla/5.0"

    resposta = sessao.get(PAGINA, timeout=30)
    print("Página HTTP:", resposta.status_code)
    resposta.raise_for_status()

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)',
        resposta.text,
        re.IGNORECASE,
    )

    termos = ["/api/sinal", "/api/pausa", "fetch(", "axios", "bac-bo"]

    encontrados = 0

    for caminho in scripts:
        url = urljoin(BASE, caminho)

        try:
            r = sessao.get(url, timeout=20)
            if r.status_code != 200:
                continue

            codigo = r.text

            for termo in termos:
                inicio = 0
                while True:
                    pos = codigo.lower().find(termo.lower(), inicio)
                    if pos == -1:
                        break

                    excerto = codigo[max(0, pos - 250):pos + 350]
                    excerto = re.sub(r"\s+", " ", excerto)

                    print("\nFicheiro:", caminho)
                    print("Termo:", termo)
                    print("Contexto:", excerto[:600])

                    encontrados += 1
                    inicio = pos + len(termo)

                    if encontrados >= 30:
                        print("\nLimite de resultados atingido.")
                        return

        except requests.RequestException:
            continue

    if encontrados == 0:
        print("Não foram encontrados contextos relevantes.")

    print("\nInvestigação concluída.")

if __name__ == "__main__":
    main()
