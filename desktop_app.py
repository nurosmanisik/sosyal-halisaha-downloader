from __future__ import annotations

import os
import socket
import threading
from dataclasses import dataclass

from werkzeug.serving import BaseWSGIServer, make_server

from app import app

APP_TITLE = "Sosyal Hali Saha Downloader"


@dataclass
class DesktopServer:
    host: str
    port: int
    server: BaseWSGIServer
    thread: threading.Thread

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)


def main() -> int:
    _ensure_homebrew_path()
    server = _start_server()
    try:
        _open_window(server.url)
    finally:
        server.stop()
    return 0


def _ensure_homebrew_path() -> None:
    path_parts = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    current_path = os.environ.get("PATH", "")
    for path in reversed(path_parts):
        if path not in current_path.split(os.pathsep):
            current_path = f"{path}{os.pathsep}{current_path}" if current_path else path
    os.environ["PATH"] = current_path


def _start_server() -> DesktopServer:
    host = "127.0.0.1"
    port = _free_port()
    server = make_server(host, port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return DesktopServer(host=host, port=port, server=server, thread=thread)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _open_window(url: str) -> None:
    import webview

    webview.create_window(
        APP_TITLE,
        url,
        width=1180,
        height=820,
        min_size=(980, 680),
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    raise SystemExit(main())
