import io
import json
import sys

import httpx
import pytest
import numpy as np
from fastapi import FastAPI
from httpx import AsyncClient
from server_api.main import app as fastapi_app
from types import SimpleNamespace


class DummyLayers(list):
    def append(self, name=None, layer=None):  # type: ignore[override]
        super().append({"name": name, "layer": layer})


class DummyTxn:
    def __init__(self, viewer):
        self.viewer = viewer

    def __enter__(self):
        return SimpleNamespace(layers=self.viewer.layers)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class DummyViewer:
    def __init__(self):
        self.layers = DummyLayers()

    def txn(self):
        return DummyTxn(self)

    def __str__(self):
        return "dummy_viewer"


class DummyCoordinateSpace:
    def __init__(self, names, units, scales):
        self.names = names
        self.units = units
        self.scales = scales


class DummyLocalVolume:
    def __init__(self, data, dimensions, volume_type, voxel_offset):
        self.data = data
        self.dimensions = dimensions
        self.volume_type = volume_type
        self.voxel_offset = voxel_offset


@pytest.fixture(autouse=True)
def stub_neuroglancer(monkeypatch):
    dummy_module = SimpleNamespace(
        set_server_bind_address=lambda ip, port: None,
        Viewer=DummyViewer,
        CoordinateSpace=DummyCoordinateSpace,
        LocalVolume=DummyLocalVolume,
    )
    monkeypatch.setitem(sys.modules, "neuroglancer", dummy_module)
    yield


@pytest.fixture
async def app() -> FastAPI:
    return fastapi_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_hello(client: AsyncClient) -> None:
    response = await client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"hello"}


@pytest.mark.asyncio
async def test_neuroglancer(client: AsyncClient) -> None:
    array = np.zeros((2, 2), dtype=np.uint8)
    image_buffer = io.BytesIO()
    label_buffer = io.BytesIO()
    np.save(image_buffer, array)
    np.save(label_buffer, array)
    image_buffer.seek(0)
    label_buffer.seek(0)

    files = {
        "image": ("image.npy", image_buffer, "application/octet-stream"),
        "label": ("label.npy", label_buffer, "application/octet-stream"),
    }

    response = await client.post(
        "/neuroglancer",
        data={"scales": json.dumps([4, 4, 4])},
        files=files,
    )
    assert response.status_code == 200
