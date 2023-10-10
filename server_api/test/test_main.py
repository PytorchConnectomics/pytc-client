from fastapi.testclient import TestClient
import pytest

client = TestClient(app)

# Test for the hello endpoint
def test_hello():
    response = client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"hello"}

# Test for neuroglancer endpoint
@pytest.mark.skip(reason="This test needs actual files to check and neuroglancer server setup.")
def test_neuroglancer():
    # TODO: Replace.
    request_data = {

    }
    response = client.post("/neuroglancer", json=request_data)
    assert response.status_code == 200
    # Add more assertions based on your expected output.

# Test for start_model_training endpoint
def test_start_model_training():
    request_data = { }
    response = client.post("/start_model_training", json=request_data)
    assert response.status_code == 200
    assert response.json() == {"message": "Model training started successfully"}

# Add similar tests for the other endpoints as well.

# Test for get_tensorboard_url endpoint
# TODO: Need to scope out proper behavior
def test_get_tensorboard_url():
    response = client.get('/get_tensorboard_url')
    assert response.status_code == 200
    assert response.text == "http://localhost:6006/"

# Test for check_files endpoint
@pytest.mark.skip(reason="This test needs actual files to check.")
def test_check_files():
    request_data = { }
    response = client.post('/check_files', json=request_data)
    assert response.status_code == 200
    # Add more assertions based on your expected output.
