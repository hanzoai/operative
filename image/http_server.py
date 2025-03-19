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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            
            # Get environment variables to expose to the client
            env_vars = {
                "APP_ENDPOINT": os.environ.get("APP_ENDPOINT", ""),
                "VNC_ENDPOINT": os.environ.get("VNC_ENDPOINT", ""),
                "API_ENDPOINT": os.environ.get("API_ENDPOINT", "")
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
