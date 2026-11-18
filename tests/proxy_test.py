"""Visitors' real addresses behind the Pi's proxy (Caddy), and who gets into Admin without a password.

Run from the project folder:  python tests/proxy_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import server  # noqa: E402


def req(peer, forwarded=None):
    """A request handler as the server would see it, without opening a socket."""
    h = server.Handler.__new__(server.Handler)
    h.client_address = (peer, 50000)
    h.headers = {"X-Forwarded-For": forwarded} if forwarded is not None else {}
    return h


def with_trusted(text):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    server.TRUSTED_FILE = path
    server._trusted_cache.update(mtime=None)
    return path


def no_trusted_file():
    server.TRUSTED_FILE = os.path.join(tempfile.gettempdir(), "no_such_trusted_admin.txt")
    server._trusted_cache.update(mtime=None)


def test_this_machine_is_local():
    no_trusted_file()
    for peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        h = req(peer)
        assert h._local() and h._trusted() and h._addr() == peer


def test_visitor_through_proxy_is_not_local():
    no_trusted_file()
    h = req("127.0.0.1", "192.168.1.50")
    assert h._addr() == "192.168.1.50"
    assert not h._local()
    assert not h._trusted()


def test_bigbox_through_proxy_is_trusted_by_default():
    no_trusted_file()
    h = req("127.0.0.1", "192.168.1.213")
    assert h._addr() == "192.168.1.213" and not h._local() and h._trusted()


def test_bigbox_direct_to_port_is_trusted():
    no_trusted_file()
    h = req("192.168.1.213")
    assert h._addr() == "192.168.1.213" and not h._local() and h._trusted()


def test_header_from_the_network_is_ignored():
    """Someone sending the header straight to :8765 can't pretend to be BIGBOX or the Pi."""
    no_trusted_file()
    h = req("192.168.1.50", "192.168.1.213")
    assert h._addr() == "192.168.1.50"
    assert not h._trusted()
    h = req("192.168.1.50", "127.0.0.1")
    assert not h._local() and not h._trusted()


def test_rightmost_forwarded_address_wins():
    """Caddy appends the address it saw; anything a visitor put in front is ignored."""
    no_trusted_file()
    h = req("127.0.0.1", "192.168.1.213, 192.168.1.50")
    assert h._addr() == "192.168.1.50" and not h._trusted()
    h = req("::1", "::ffff:192.168.1.213")
    assert h._addr() == "192.168.1.213" and h._trusted()


def test_trusted_file_replaces_the_default():
    path = with_trusted("# trusted Admin computers\n192.168.1.99   # new PC\n\n")
    try:
        assert req("192.168.1.99")._trusted()
        assert not req("192.168.1.213")._trusted()
        assert req("127.0.0.1")._trusted()          # the Pi itself is always allowed
    finally:
        os.remove(path)
    no_trusted_file()
    assert req("192.168.1.213")._trusted()          # file gone: back to BIGBOX


def test_empty_trusted_file_trusts_no_other_computer():
    path = with_trusted("# nobody\n")
    try:
        assert not req("192.168.1.213")._trusted()
        assert req("127.0.0.1")._trusted()
    finally:
        os.remove(path)
    no_trusted_file()


def test_via_records_the_real_address():
    no_trusted_file()
    h = req("127.0.0.1", "192.168.1.50")
    h.headers["User-Agent"] = "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) Safari/605.1"
    v = h._via()
    assert v["address"] == "192.168.1.50" and v["device"].startswith("iPad")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
