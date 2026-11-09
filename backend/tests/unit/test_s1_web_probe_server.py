"""The test-only browser probe serves a fixed allowlist, never the checkout."""

from __future__ import annotations

import http.client
import importlib.util
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "scripts/serve-s1-web-probe.py"
SPEC = importlib.util.spec_from_file_location("finex_s1_probe_server", SOURCE)
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
HTML_PATH = "/tool/local_web_transport_probe.html"
JS_PATH = "/build/qa/local_web_transport_probe.js"


@pytest.fixture
def isolated_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[http.client.HTTPConnection, Path]]:
    html = tmp_path / "public-probe.html"
    javascript = tmp_path / "public-probe.js"
    html.write_text("<title>controlled unit probe</title>", encoding="utf-8")
    javascript.write_text("void 0;", encoding="utf-8")
    monkeypatch.setattr(
        PROBE,
        "ASSETS",
        {
            HTML_PATH: (html, "text/html; charset=utf-8"),
            JS_PATH: (javascript, "text/javascript; charset=utf-8"),
        },
    )
    server = PROBE.ThreadingHTTPServer(("127.0.0.1", 0), PROBE.ProbeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        yield client, javascript
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive(), "Only the owned unit server must be reaped."


def test_committed_server_has_only_two_fixed_public_assets() -> None:
    assert set(PROBE.ASSETS) == {HTML_PATH, JS_PATH}
    assert PROBE.ASSETS[HTML_PATH][0] == PROBE.ROOT / HTML_PATH.lstrip("/")
    assert PROBE.ASSETS[JS_PATH][0] == PROBE.ROOT / JS_PATH.lstrip("/")


def test_probe_response_forbids_network_and_caching(
    isolated_server: tuple[http.client.HTTPConnection, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    client, _ = isolated_server
    client.request("GET", HTML_PATH)
    response = client.getresponse()
    assert response.status == 200
    assert response.read() == b"<title>controlled unit probe</title>"
    assert response.getheader("Cache-Control") == "no-store"
    assert response.getheader("X-Content-Type-Options") == "nosniff"
    policy = response.getheader("Content-Security-Policy") or ""
    assert "connect-src 'none'" in policy
    assert "default-src 'none'" in policy
    assert "base-uri 'none'" in policy and "frame-ancestors 'none'" in policy
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/.env",
        "/backend/.local/state.sqlite3",
        "/../README.md",
        "/build/qa/",
        HTML_PATH + "?qa=marker",
        HTML_PATH + "#qa-marker",
    ],
)
def test_other_paths_and_query_are_not_exposed_or_reflected(
    isolated_server: tuple[http.client.HTTPConnection, Path],
    path: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client, _ = isolated_server
    client.request("GET", path, headers={"Authorization": "synthetic-unit-only"})
    response = client.getresponse()
    assert response.status == 404
    assert response.read() == b"Not found"
    assert capsys.readouterr() == ("", "")


def test_head_has_correct_length_without_a_body(
    isolated_server: tuple[http.client.HTTPConnection, Path],
) -> None:
    client, _ = isolated_server
    client.request("HEAD", JS_PATH)
    response = client.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Length") == str(len(b"void 0;"))
    assert response.read() == b""


def test_missing_compiled_asset_is_a_safe_failure(
    isolated_server: tuple[http.client.HTTPConnection, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    client, javascript = isolated_server
    javascript.unlink()  # Only this pytest fixture's internally created temporary asset.
    client.request("GET", JS_PATH)
    response = client.getresponse()
    assert response.status == 503
    assert response.read() == b"Compile the controlled probe first."
    assert capsys.readouterr() == ("", "")
