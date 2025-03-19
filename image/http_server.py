import os
import socket
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler


class HTTPServerV6(HTTPServer):
    address_family = socket.AF_INET6


class EnvAwareHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/env-config.json":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            
            # Only expose the endpoints we need for the UI
            env_vars = {
                "APP_ENDPOINT": os.environ.get("APP_ENDPOINT", "operative-app.hanzo.ai"),
                "VNC_ENDPOINT": os.environ.get("VNC_ENDPOINT", "operative-vnc.hanzo.ai")
            }
            
            self.wfile.write(json.dumps(env_vars).encode())
            return
        
        return super().do_GET()


def run_server():
    os.chdir(os.path.dirname(__file__) + "/static_content")
    server_address = ("::", 8080)
    httpd = HTTPServerV6(server_address, EnvAwareHandler)
    print("Starting HTTP server on port 8080...")  # noqa: T201
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
