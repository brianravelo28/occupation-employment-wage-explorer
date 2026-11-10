"""The command Render runs: the same in every place it is written, and it serves the dashboard."""
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import ROOT


def command_in(path, pattern):
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.M)
    assert match, path
    return shlex.split(match.group(1))


def test_the_start_command_is_the_same_in_render_yaml_and_procfile():
    in_yaml = command_in("render.yaml", r"startCommand:\s*(.+)")
    in_procfile = command_in("Procfile", r"web:\s*(.+)")
    assert in_yaml == in_procfile
    assert in_yaml[0] == "gunicorn" and "app.app:server" in in_yaml and "gthread" in in_yaml


def test_the_deployment_doc_quotes_the_same_command():
    doc = (ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
    command = " ".join(command_in("Procfile", r"web:\s*(.+)"))
    assert command in doc


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.status, response.read()


@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn does not run on Windows; the Linux CI run covers this test")
def test_the_render_start_command_serves_the_dashboard():
    port = free_port()
    args = [("127.0.0.1:%d" % port) if a.startswith("0.0.0.0:") else a for a in command_in("Procfile", r"web:\s*(.+)")]
    args = [sys.executable, "-m", "gunicorn"] + args[1:]
    proc = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while True:
            try:
                status, body = fetch(base + "/")
                break
            except OSError:
                assert proc.poll() is None, "gunicorn exited: " + (proc.stdout.read() or "")
                assert time.time() < deadline, "gunicorn did not start in 90 seconds"
                time.sleep(0.5)
        assert status == 200 and b"Occupation Employment" in body
        # Dash fires every tab's requests at once on page load; the threaded worker has to answer all of them.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch, [base + "/_dash-layout", base + "/_dash-dependencies"] * 4))
        assert all(status == 200 for status, _ in results)
        assert b"Occupation Search" in results[0][1]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
