from ai_service import generate_response

def test_api():
    print("--- Probando Servicio de IA (NVIDIA) ---")
    prompt = "Dame una frase motivadora corta para un estudiante de la ESPE."
    print(f"Pregunta: {prompt}")
    
    response = generate_response(prompt)
    
    if response and not response.startswith("Error"):
        print(f"Respuesta recibida exitosamente:\n{response}")
        print("\n[OK] La conexion funciona correctamente.")
    else:
        print(f" Falló la conexión: {response}")

if __name__ == "__main__":
    test_api()
