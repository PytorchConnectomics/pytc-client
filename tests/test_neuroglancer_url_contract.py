import unittest
from unittest.mock import patch

from starlette.requests import Request

from server_api.main import _build_neuroglancer_public_url
from server_api import main as server_main


class DummyViewer:
    def __init__(self, token):
        self.token = token


def make_request(*, host="localhost:4242", scheme="http", extra_headers=None):
    headers = [(b"host", host.encode("utf-8"))]
    for key, value in (extra_headers or {}).items():
        headers.append((key.lower().encode("utf-8"), value.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": scheme,
        "path": "/neuroglancer",
        "raw_path": b"/neuroglancer",
        "query_string": b"",
        "headers": headers,
        "server": ("localhost", 4242),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


class NeuroglancerUrlContractTests(unittest.TestCase):
    def setUp(self):
        self._log_patch = patch.object(server_main, "append_app_event")
        self._log_patch.start()

    def tearDown(self):
        self._log_patch.stop()
        with server_main._retained_neuroglancer_viewers_lock:
            server_main._retained_neuroglancer_viewers.clear()

    def test_default_public_url_uses_request_host_with_neuroglancer_port(self):
        request = make_request(host="localhost:4242", scheme="http")

        public_url = _build_neuroglancer_public_url(
            "http://0.0.0.0:4244/v/abc123?foo=1",
            request,
        )

        self.assertEqual(public_url, "http://localhost:4244/v/abc123?foo=1")

    def test_public_base_env_prefixes_viewer_path(self):
        request = make_request(host="localhost:4242", scheme="http")

        with patch.dict(
            "os.environ",
            {"PYTC_NEUROGLANCER_PUBLIC_BASE": "https://viewer.example.com/ng"},
            clear=True,
        ):
            public_url = _build_neuroglancer_public_url(
                "http://0.0.0.0:4244/v/demo",
                request,
            )

        self.assertEqual(public_url, "https://viewer.example.com/ng/v/demo")

    def test_forwarded_headers_override_request_scheme_and_host(self):
        request = make_request(
            host="localhost:4242",
            scheme="http",
            extra_headers={
                "x-forwarded-proto": "https",
                "x-forwarded-host": "viewer.internal:4242",
            },
        )

        public_url = _build_neuroglancer_public_url(
            "http://0.0.0.0:4244/v/proxy",
            request,
        )

        self.assertEqual(public_url, "https://viewer.internal:4244/v/proxy")

    def test_retain_neuroglancer_viewer_keeps_strong_reference(self):
        viewer = DummyViewer("viewer-token")

        token = server_main._retain_neuroglancer_viewer(
            viewer,
            public_url="https://viewer.example.com/ng/v/viewer-token/",
            internal_viewer_url="http://127.0.0.1:4244/v/viewer-token/",
            mode="visualization",
            workflow_id=7,
            image_path="/data/image.h5",
            label_path="/data/label.h5",
        )

        self.assertEqual(token, "viewer-token")
        self.assertIs(
            server_main._retained_neuroglancer_viewers["viewer-token"]["viewer"],
            viewer,
        )

    def test_retain_neuroglancer_viewer_evicts_oldest_over_capacity(self):
        previous_limit = server_main.PYTC_NEUROGLANCER_MAX_VIEWERS
        server_main.PYTC_NEUROGLANCER_MAX_VIEWERS = 1
        try:
            server_main._retain_neuroglancer_viewer(
                DummyViewer("old"),
                public_url="https://viewer.example.com/ng/v/old/",
                internal_viewer_url="http://127.0.0.1:4244/v/old/",
                mode="visualization",
            )
            server_main._retain_neuroglancer_viewer(
                DummyViewer("new"),
                public_url="https://viewer.example.com/ng/v/new/",
                internal_viewer_url="http://127.0.0.1:4244/v/new/",
                mode="visualization",
            )

            self.assertNotIn("old", server_main._retained_neuroglancer_viewers)
            self.assertIn("new", server_main._retained_neuroglancer_viewers)
        finally:
            server_main.PYTC_NEUROGLANCER_MAX_VIEWERS = previous_limit


if __name__ == "__main__":
    unittest.main()
