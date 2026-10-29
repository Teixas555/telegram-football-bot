
import re
import requests
from urllib.parse import urljoin

BASE = "https://cassinostats.com"
PAGINA = BASE + "/pt/jogo/bac-bo/estatisticas"

PADROES = [
    r'fetch\([^)]{0,300}',
    r'axios\.[a-z]+\([^)]{0,300}',
    r'["\'](/api/[^"\']{1,200})["\']',
    r'["\'](https?://[^"\']{1,200})["\']',
    r'["\']([^"\']*(?:historico|history|rounds|resultados)[^"\']*)["\']',
]

def main():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"

    r = s.get(PAGINA, timeout=30)
    print("Página HTTP:", r.status_code)
    r.raise_for_status()

    scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)',
        r.text,
        re.I
    )

    encontrados = set()

    for caminho in scripts:
        try:
            js = s.get(urljoin(BASE, caminho), timeout=20)
            if js.status_code != 200:
                continue
            codigo = js.text
        except requests.RequestException:
            continue

        if not any(x in codigo.lower() for x in
                   ["bac-bo", "historico", "rounds", "resultados"]):
            continue

        for padrao in PADROES:
            for m in re.finditer(padrao, codigo, re.I):
                trecho = re.sub(r"\s+", " ", m.group(0))
                encontrados.add((caminho, trecho[:300]))

    print("\nPossíveis pedidos de dados encontrados:")
    for ficheiro, trecho in sorted(encontrados):
        print("\nFicheiro:", ficheiro)
        print(trecho)

    print("\nTeste concluído. Nenhuma mensagem foi enviada.")

if __name__ == "__main__":
    main()
