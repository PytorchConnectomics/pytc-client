import httpx
import unittest
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from server_api.main import *

class TestServerAPI(unittest.TestCase):
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
        data = {
            "image": "test_image",
            "label": "test_label",
            "scales": [4, 4, 4]
        }
        # The actual testing of this route may need to be adjusted based on your actual functionality.
        # You might need to mock calls to `neuroglancer` or other external libraries.
        response = await client.post("/neuroglancer", json=data)
        assert response.status_code == 200
    
if __name__ == '__main__':
    unittest.main()