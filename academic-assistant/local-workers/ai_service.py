import os
import requests
import json
from dotenv import load_dotenv

#Load environment variables
load_dotenv()

INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")
MODEL = os.getenv("NVIDIA_MODEL", "google/gemma-4-31b-it")

def generate_response(prompt, system_prompt="Eres un asistente académico experto de la universidad ESPE de Ecuador. Responde de forma clara, profesional y motivadora.", stream=False):
    """
    Generates a response from the NVIDIA AI API.
    """
    if not API_KEY:
        return "Error: NVIDIA_API_KEY no configurado en el entorno."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "text/event-stream" if stream else "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.95,
        "stream": stream,
    }

    try:
        response = requests.post(INVOKE_URL, headers=headers, json=payload, stream=stream, timeout=15)
        
        if response.status_code != 200:
            return f"Error de API (Status {response.status_code}): {response.text}"

        if stream:
            return response.iter_lines()
        else:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return f"Respuesta inesperada de la API: {json.dumps(data)}"
                
    except Exception as e:
        return f"Error de conexión con NVIDIA AI: {str(e)}"

if __name__ == "__main__":
    # Test call
    print("Probando conexión con NVIDIA AI...")
    res = generate_response("Hola, ¿quién eres?")
    print(f"Respuesta: {res}")
