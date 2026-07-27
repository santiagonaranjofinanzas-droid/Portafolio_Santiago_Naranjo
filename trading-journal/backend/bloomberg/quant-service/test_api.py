from fastapi.testclient import TestClient
from app.main import app

def test_prediction():
    client = TestClient(app)
    with client:
        payload = {
            "features": {
                "SP500": 0.01,
                "GOLD": -0.005,
                "OIL": 0.02,
                "BOND10Y": -0.01,
                "USD": 0.002
            },
            "state_vector": [0.0, 0.0, 0.0],
            "timestamp": "2026-04-27T10:00:00Z"
        }
        res = client.post("/predict", json=payload)
        print("Status Code:", res.status_code)
        print("Response JSON:", res.json())

if __name__ == "__main__":
    test_prediction()
