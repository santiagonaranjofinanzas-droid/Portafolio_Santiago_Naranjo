import requests
import json

def test_api():
    ports = [8080]
    for port in ports:
        for path in ["/api/v1/bloomberg/latest", "/api/v1/sentinel/context"]:
            url = f"http://localhost:{port}{path}"
            print(f"Querying {url}...")
            try:
                r = requests.get(url, timeout=5)
                print(f"Status Code: {r.status_code}")
                # print first 20 lines of formatted json response
                json_str = json.dumps(r.json(), indent=2)
                lines = json_str.split('\n')
                print('\n'.join(lines[:40]))
                if len(lines) > 40:
                    print("...")
            except Exception as e:
                print(f"Failed: {e}")

if __name__ == "__main__":
    test_api()
