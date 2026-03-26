import unittest
from unittest.mock import patch

from starlette.requests import Request

from server_api.main import _build_neuroglancer_public_url


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


if __name__ == "__main__":
    unittest.main()
