import requests

url = "http://127.0.0.1:8080/api/v1/ai/chat"
payload = {
    "prompt": "Hola, ¿quién eres y qué modelo de inteligencia artificial estás utilizando?",
    "focus": "Analista IA",
    "context": {
        "summary": {
            "net_profit": 1500.0,
            "expectancy": 1.5,
            "sqn": 2.1
        }
    },
    "messages": []
}

try:
    response = requests.post(url, json=payload, timeout=30)
    print("Status Code:", response.status_code)
    print("Response JSON:")
    print(response.json())
except Exception as e:
    print("Error calling local API:", e)
