import logging
import os
from contextlib import asynccontextmanager
from typing import List

import numpy as np
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from joblib import load
from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis import asyncio

logger = logging.getLogger(__name__)
model = None

# Get Redis URL from environment variable or use localhost as default
LOCAL_REDIS_URL = "redis://localhost:6379/0"


@asynccontextmanager
async def lifespan_mechanism(app: FastAPI):
    logging.info("Starting up Lab3 API")

    # Load the Model on Startup
    global model
    model = load("model_pipeline.pkl")

    # Load the Redis Cache
    redis_url = os.getenv("REDIS_URL", "localhost")
    redis = asyncio.from_url(f"redis://{redis_url}:6379/0", encoding="utf8", decode_responses=True)

    # We initialize the connection to Redis and declare that all keys in the
    # database will be prefixed with w255-cache-predict. Do not change this
    # prefix for the submission.
    FastAPICache.init(RedisBackend(redis), prefix="w255-cache-prediction")

    yield
    # We don't need a shutdown event for our system, but we could put something
    # here after the yield to deal with things during shutdown
    logging.info("Shutting down Lab3 API")


sub_application_housing_predict = FastAPI(lifespan=lifespan_mechanism)


# Model definitions from Lab 2
class HousingInput(BaseModel):
    MedInc: float = Field(ge=0)  # Median income should be positive
    HouseAge: float = Field(ge=0)  # House age can't be negative
    AveRooms: float = Field(ge=0)  # Average rooms should be positive
    AveBedrms: float = Field(ge=0)  # Average bedrooms can't be negative
    Population: float = Field(ge=0)  # Population can't be negative
    AveOccup: float = Field(ge=0)  # Average occupancy should be positive
    Latitude: float
    Longitude: float

    # Pydantic v2 way of defining model config
    model_config = ConfigDict(extra="forbid")  

    @field_validator("Latitude")
    @classmethod
    def validate_latitude(cls, v):
        if v < -90 or v > 90:
            raise ValueError("Invalid value for Latitude")
        return v
    
    @field_validator("Longitude")
    @classmethod
    def validate_longitude(cls, v):
        if v < -180 or v > 180:
            raise ValueError("Invalid value for Longitude")
        return v
    
    def to_numpy(self):
        """Convert a single input to numpy array format"""
        return np.array([[
            self.MedInc, 
            self.HouseAge, 
            self.AveRooms,
            self.AveBedrms, 
            self.Population, 
            self.AveOccup,
            self.Latitude, 
            self.Longitude
        ]])


class HousingOutput(BaseModel):
    prediction: float


# New model for bulk predictions
class HousingInputBulk(BaseModel):
    houses: List[HousingInput]

    @field_validator("houses")
    @classmethod
    def validate_houses(cls, v):
        if not v:
            raise ValueError("Empty list of houses is not allowed")
        return v
                    
    def to_numpy(self):
        """Convert multiple HousingInput instances to a vectorized NumPy array"""
        return np.array([
            [
                house.MedInc,
                house.HouseAge,
                house.AveRooms,
                house.AveBedrms,
                house.Population,
                house.AveOccup,
                house.Latitude,
                house.Longitude
            ] 
            for house in self.houses  # Correctly iterate through all houses
        ])

class HousingOutputBulk(BaseModel):
    predictions: List[float]


# Endpoint from Lab 2
@sub_application_housing_predict.post("/predict", response_model=HousingOutput)
@cache()
async def predict(houses_input: HousingInput):
    # Convert input to model format using the to_numpy method
    features = houses_input.to_numpy()

    # Make prediction
    prediction = model.predict(features)[0]
    return HousingOutput(prediction=float(prediction))


# New bulk prediction endpoint for Lab 3
@sub_application_housing_predict.post("/bulk-predict")
@cache()
async def multi_predict(houses_input: HousingInputBulk):
    """
    Vectorized prediction on multiple inputs
    """
    # Check if the input list is empty and return empty predictions
    if len(houses_input.houses) == 0:
            return HousingOutputBulk(predictions=[])
    
    # Convert inputs to numpy format using the to_numpy method
    features = houses_input.to_numpy()
    
    # Make predictions on all inputs at once
    predictions = model.predict(features)
    
    # Convert numpy array to list of floats for the response
    return HousingOutputBulk(predictions=predictions.tolist())

# Health check endpoint from Lab 2
@sub_application_housing_predict.get("/health")
async def health():
    from datetime import datetime
    return {"time": datetime.utcnow().isoformat()}


# Hello endpoint from Lab 2
@sub_application_housing_predict.get("/hello")
async def hello(name: str):
    return {"message": f"Hello {name}"}


