import os
import shutil
from fastapi.testclient import TestClient

from src.main import app

# Ensure the model file is in the correct location before running tests
if os.path.exists("model_pipeline.pkl") and not os.path.exists("src/model_pipeline.pkl"):
    shutil.copy("model_pipeline.pkl", "src/model_pipeline.pkl")

def test_health():
    with TestClient(app) as client:
        response = client.get("/lab/health")
        assert response.status_code == 200
        assert "time" in response.json()

def test_hello_valid():
    with TestClient(app) as client:
        response = client.get("/lab/hello?name=John")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello John"}

def test_hello_missing():
    with TestClient(app) as client:
        response = client.get("/lab/hello")  # No name provided
        assert response.status_code != 200

def test_hello_misspelled_param():
    with TestClient(app) as client:
        response = client.get("/lab/hello?nam=John")  # Misspelled param
        assert response.status_code != 200  

def test_hello_reversed_param():
    with TestClient(app) as client:
        response = client.get("/lab/hello?John=name")  # Invalid format
        assert response.status_code != 200

def test_not_found():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

def test_predict_endpoint():
    with TestClient(app) as client:
        payload = {
            "MedInc": 3.5,
            "HouseAge": 20,
            "AveRooms": 5.0,
            "AveBedrms": 1.0,
            "Population": 500,
            "AveOccup": 2.5,
            "Latitude": 37.5,
            "Longitude": -122.3
        }

        response = client.post("/lab/predict", json=payload)
        
        assert response.status_code == 200
        assert "prediction" in response.json()
        assert isinstance(response.json()["prediction"], float)

def test_predict_valid_input():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": 34.0,
            "Longitude": -118.0
        })
        assert response.status_code == 200
        json_data = response.json()
        assert "prediction" in json_data
        assert isinstance(json_data["prediction"], float)

def test_predict_missing_field():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0
            # Missing required fields
        })
        assert response.status_code != 200

def test_predict_extra_field():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": 34.0,
            "Longitude": -118.0,
            "Extrafield": 0.0
        })
        assert response.status_code != 200

def test_predict_invalid_latitude_negative():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": -100.0,  # Invalid latitude
            "Longitude": -118.0
        })
        assert response.status_code != 200
        error_detail = response.json()["detail"][0]["msg"]
        assert error_detail == "Value error, Invalid value for Latitude"

def test_predict_invalid_latitude_positive():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": 100.0,  # Invalid latitude
            "Longitude": -118.0
        })
        assert response.status_code != 200
        error_detail = response.json()["detail"][0]["msg"]
        assert error_detail == "Value error, Invalid value for Latitude"

def test_predict_invalid_longitude_negative():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": 34.0,
            "Longitude": -200.0  # Invalid longitude
        })
        assert response.status_code != 200
        error_detail = response.json()["detail"][0]["msg"]
        assert error_detail == "Value error, Invalid value for Longitude"

def test_predict_invalid_longitude_positive():
    with TestClient(app) as client:
        response = client.post("/lab/predict", json={
            "MedInc": 8.0,
            "HouseAge": 20.0,
            "AveRooms": 6.0,
            "AveBedrms": 1.5,
            "Population": 1000.0,
            "AveOccup": 3.0,
            "Latitude": 34.0,
            "Longitude": 200.0  # Invalid longitude
        })
        assert response.status_code != 200
        error_detail = response.json()["detail"][0]["msg"]
        assert error_detail == "Value error, Invalid value for Longitude"

# New tests for bulk prediction endpoint
def test_bulk_predict_endpoint():
    with TestClient(app) as client:
        payload = {
            "houses": [
                {
                    "MedInc": 3.5,
                    "HouseAge": 20,
                    "AveRooms": 5.0,
                    "AveBedrms": 1.0,
                    "Population": 500,
                    "AveOccup": 2.5,
                    "Latitude": 37.5,
                    "Longitude": -122.3
                },
                {
                    "MedInc": 8.0,
                    "HouseAge": 20.0,
                    "AveRooms": 6.0,
                    "AveBedrms": 1.5,
                    "Population": 1000.0,
                    "AveOccup": 3.0,
                    "Latitude": 34.0,
                    "Longitude": -118.0
                }
            ]
        }

        response = client.post("/lab/bulk-predict", json=payload)
        
        assert response.status_code == 200
        assert "predictions" in response.json()
        predictions = response.json()["predictions"]
        assert isinstance(predictions, list)
        assert len(predictions) == 2
        assert all(isinstance(pred, float) for pred in predictions)

def test_bulk_predict_single_house():
    with TestClient(app) as client:
        payload = {
            "houses": [
                {
                    "MedInc": 3.5,
                    "HouseAge": 20,
                    "AveRooms": 5.0,
                    "AveBedrms": 1.0,
                    "Population": 500,
                    "AveOccup": 2.5,
                    "Latitude": 37.5,
                    "Longitude": -122.3
                }
            ]
        }

        response = client.post("/lab/bulk-predict", json=payload)
        
        assert response.status_code == 200
        assert "predictions" in response.json()
        predictions = response.json()["predictions"]
        assert isinstance(predictions, list)
        assert len(predictions) == 1
        assert isinstance(predictions[0], float)

def test_bulk_predict_empty_list():
    with TestClient(app) as client:
        payload = {
            "houses": []
        }

        response = client.post("/lab/bulk-predict", json=payload)
        
        # This should either return an empty list of predictions or an error
        # Depending on how you decide to handle empty input lists
        if response.status_code == 200:
            assert response.json()["predictions"] == []
        else:
            assert response.status_code != 200

def test_bulk_predict_invalid_house():
    with TestClient(app) as client:
        payload = {
            "houses": [
                {
                    "MedInc": 3.5,
                    "HouseAge": 20,
                    "AveRooms": 5.0,
                    "AveBedrms": 1.0,
                    "Population": 500,
                    "AveOccup": 2.5,
                    "Latitude": 100.0,  # Invalid latitude
                    "Longitude": -122.3
                }
            ]
        }

        response = client.post("/lab/bulk-predict", json=payload)
        assert response.status_code != 200
        error_detail = response.json()["detail"][0]["msg"]
        assert "Invalid value for Latitude" in error_detail



# from fastapi.testclient import TestClient
#
# from src.main import app
#
# client = TestClient(app)
#
#
# def test_health():
#     response = client.get("/lab/health")
#     assert response.status_code == 200