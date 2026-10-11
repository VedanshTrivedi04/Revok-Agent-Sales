"""Tiny OpenAI-compatible HTTP server for tests (the installed `openai` uses its own httpx fork, so
respx cannot intercept it; a real local server also exercises the real network path).

Queue responses with `server.push(content=...)` or `server.push(status=503)`. Requests are recorded.
"""

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeLLMServer:
    def __init__(self) -> None:
        self.queue: deque[tuple[int, str]] = deque()
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a: Any) -> None:
                pass

            def do_POST(self) -> None:
                n = int(self.headers.get("content-length", 0))
                outer.requests.append(json.loads(self.rfile.read(n) or b"{}"))
                status, content = outer.queue.popleft() if outer.queue else (500, "")
                if status != 200:
                    body = json.dumps({"error": {"message": "x", "type": "e"}}).encode()
                else:
                    body = json.dumps(
                        {
                            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
                            "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": content}}],
                            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                        }
                    ).encode()  # fmt: skip
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def push(self, content: str = "", status: int = 200) -> None:
        self.queue.append((status, content))

    def start(self) -> "FakeLLMServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
