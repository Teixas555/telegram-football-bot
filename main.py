
import json
import os
import urllib.parse
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

message = (
    "⚽ BOT DE FUTEBOL ATIVO!\n\n"
    "A ligação ao GitHub Actions e ao Telegram está a funcionar!\n"
    "Vamos preparar as previsões de jogos."
)

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": message
}).encode()

request = urllib.request.Request(url, data=data)

with urllib.request.urlopen(request, timeout=20) as response:
    result = json.loads(response.read().decode())

if not result.get("ok"):
    raise RuntimeError("O Telegram não confirmou o envio.")

print("Mensagem enviada com sucesso!")
