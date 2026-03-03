import os
import socket
import subprocess
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler


class HTTPServerV6(HTTPServer):
    address_family = socket.AF_INET6


def _check_xvfb(display_num: str) -> bool:
    """Check if Xvfb is running on the given display."""
    lock_file = f"/tmp/.X{display_num}-lock"
    return os.path.exists(lock_file)


def _check_streamlit(port: int = 8501) -> bool:
    """Check if Streamlit is listening on the given port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _check_process(name: str) -> bool:
    """Check if a process with the given name is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


class EnvAwareHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            display_num = os.environ.get("DISPLAY_NUM", "1")
            xvfb_ok = _check_xvfb(display_num)
            streamlit_ok = _check_streamlit(8501)

            healthy = xvfb_ok and streamlit_ok
            status = 200 if healthy else 503
            body = {
                "status": "ok" if healthy else "degraded",
                "checks": {
                    "xvfb": xvfb_ok,
                    "streamlit": streamlit_ok,
                },
            }

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())
            return

        if self.path == "/readyz":
            display_num = os.environ.get("DISPLAY_NUM", "1")
            xvfb_ok = _check_xvfb(display_num)
            streamlit_ok = _check_streamlit(8501)
            vnc_ok = _check_process("x11vnc")

            ready = xvfb_ok and streamlit_ok and vnc_ok
            status = 200 if ready else 503
            body = {
                "status": "ready" if ready else "not_ready",
                "checks": {
                    "xvfb": xvfb_ok,
                    "streamlit": streamlit_ok,
                    "x11vnc": vnc_ok,
                },
            }

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())
            return

        if self.path == "/env-config.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            env_vars = {
                "APP_ENDPOINT": os.environ.get("APP_ENDPOINT", "operative-app.hanzo.ai"),
                "VNC_ENDPOINT": os.environ.get("VNC_ENDPOINT", "operative-vnc.hanzo.ai"),
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
