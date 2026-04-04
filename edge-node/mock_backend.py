"""
Micro-Step 5: Mock Backend Receiver

A lightweight HTTP server that listens for POST requests on /ingest.
It simply catches the JSON envelopes sent by the daemon, prints them
to the console, and returns a 200 OK status. 

This proves end-to-end network transmission is working before we 
commit to a real database schema.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class MockIngestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle incoming POST requests."""
        if self.path == '/ingest':
            # 1. Read the incoming payload
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # 2. Parse and print it
            try:
                payload = json.loads(post_data.decode('utf-8'))
                print("\n[BACKEND] --- Received Telemetry Payload ---")
                print(f"From Node: {payload.get('node_id')} | Workload: {payload.get('workload_tag')}")
                print(f"Metrics count: {len(payload.get('metrics', {}))}")
                # Print the full JSON for inspection
                print(json.dumps(payload, indent=2))
                print("-" * 50)
                
                # 3. Acknowledge receipt
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server logging to keep terminal clean."""
        pass

def run(port=8080):
    server_address = ('0.0.0.0', port)  # Listens on all IP addresses (localhost, LAN, etc.)
    httpd = HTTPServer(server_address, MockIngestHandler)
    print(f"Mock Backend Server started.")
    print(f"Listening for telemetry on: http://127.0.0.1:{port}/ingest")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mock Server.")
        httpd.server_close()

if __name__ == '__main__':
    run(port=8080)
