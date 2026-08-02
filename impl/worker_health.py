"""
Sonda HTTP do worker Celery.

O Railway declara a saúde de um serviço por HTTP, e um worker Celery não fala
HTTP — por isso o healthcheck falhava e o deploy do worker era descartado
("1/1 replicas never became healthy"), sem que nada no log dissesse por quê.

A sonda não se limita a dizer "o processo subiu". `/health/ready` faz um ping
de controle no próprio worker, que só responde atravessando o broker: uma
resposta prova, de uma vez, que o Redis está acessível e que o worker está
consumindo. Worker travado com o processo vivo — o modo de falha que mais
engana — aparece aqui como 503, e o Railway reinicia.

Roda em thread daemon, ao lado do worker, iniciada pelo entrypoint.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PING_TIMEOUT = float(os.getenv("WORKER_PING_TIMEOUT", "2.0"))


class _Handler(BaseHTTPRequestHandler):
    def _responder(self, status: int, corpo: dict) -> None:
        dados = json.dumps(corpo).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self) -> None:  # noqa: N802 (nome exigido por BaseHTTPRequestHandler)
        rota = self.path.split("?")[0].rstrip("/") or "/"

        if rota in ("/health/live", "/health", "/"):
            # Vivacidade: o processo respondeu. Nada mais é afirmado.
            self._responder(200, {"status": "alive", "role": "worker"})
            return

        if rota == "/health/ready":
            try:
                from src.celery_worker import celery_app
                respostas = celery_app.control.ping(timeout=PING_TIMEOUT) or []
            except Exception as e:  # noqa: BLE001
                self._responder(503, {"status": "unready", "error": str(e)[:200]})
                return

            if respostas:
                self._responder(200, {"status": "ready", "workers": len(respostas)})
            else:
                self._responder(503, {"status": "unready",
                                      "error": "nenhum worker respondeu ao ping"})
            return

        self._responder(404, {"detail": "not found"})

    def log_message(self, *args) -> None:
        """Silencia o log por requisição: o Railway sonda a cada poucos segundos."""


def iniciar(port: int) -> None:
    """Sobe a sonda numa thread daemon — encerra junto com o worker."""
    servidor = HTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=servidor.serve_forever,
                              name="worker-health", daemon=True)
    thread.start()
    print(f"Sonda de saúde do worker escutando em :{port}", flush=True)


if __name__ == "__main__":
    # Executado como processo próprio pelo entrypoint, em paralelo ao Celery.
    porta = int(os.getenv("PORT", "8000"))
    servidor = HTTPServer(("0.0.0.0", porta), _Handler)
    print(f"Sonda de saúde do worker escutando em :{porta}", flush=True)
    servidor.serve_forever()
