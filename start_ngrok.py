from pyngrok import ngrok

# Открываем туннель на порт 5000
public_url = ngrok.connect(5000)

print(f"ngrok запущен: {public_url}")

while True:
    False
    
