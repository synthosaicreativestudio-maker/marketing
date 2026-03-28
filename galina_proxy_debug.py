import http.server
import json
import requests
import os
import traceback

class GalinaProxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path == '/v1/chat/completions':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req = json.loads(post_data)
                
                prompt = req['messages'][-1]['content']
                api_key = os.getenv('GEMINI_API_KEY')
                # Try both 40000 (SOCKS) and 8445 (HTTP) if needed
                proxy = 'socks5h://127.0.0.1:40000'
                
                url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}'
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                print(f"Forwarding request to Gemini... (API Key: {api_key[:5]}...)")
                resp = requests.post(url, json=payload, proxies={'https': proxy}, timeout=30)
                resp_json = resp.json()
                
                if 'candidates' not in resp_json:
                    print(f"API Error Response: {json.dumps(resp_json)}")
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(resp_json).encode())
                    return

                text = resp_json['candidates'][0]['content']['parts'][0]['text']
                res = {
                    'choices': [{'message': {'content': text}}]
                }
                
                print(f"Success! Response length: {len(text)}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(res).encode())
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            print(f"Proxy Exception: {str(e)}")
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

if __name__ == '__main__':
    print("Starting Galina Proxy on 18789...")
    server = http.server.HTTPServer(('0.0.0.0', 18789), GalinaProxy)
    server.serve_forever()
