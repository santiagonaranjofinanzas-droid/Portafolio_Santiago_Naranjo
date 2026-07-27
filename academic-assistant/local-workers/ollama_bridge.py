import http.server
import json
import time
import requests
from ai_service import generate_response

PORT = 11435

class AIBridgeHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/summarize':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                params = json.loads(post_data)
                prompt = params.get("prompt", "")
                
                print(f"Proxying request to NVIDIA AI (prompt length: {len(prompt)})...")
                
                # We use the centralized service
                ai_response = generate_response(prompt)
                
                # Format response as Ollama does for frontend compatibility
                # Ollama returns {"response": "..."} when stream=False
                result = {
                    "response": ai_response,
                    "model": "nvidia-gemma-31b",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    "done": True
                }
                
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
            except Exception as e:
                print(f"Error in bridge: {e}")
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return # Concise logs

def run_bridge():
    server = http.server.HTTPServer(('127.0.0.1', PORT), AIBridgeHandler)
    print(f"NVIDIA AI Automation Bridge running on http://127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_bridge()
