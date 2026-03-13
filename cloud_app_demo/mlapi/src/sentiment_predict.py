import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from pydantic import BaseModel, ConfigDict
from redis import asyncio
from redis.exceptions import ConnectionError, RedisError
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
from typing import List
import torch  

# Global variable for the classifier
_classifier = None
logger = logging.getLogger(__name__)
LOCAL_REDIS_URL = "redis://localhost:6379"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _classifier
    logging.info("Starting up MLAPI Sentiment Analysis")
    
    # Load model once on startup
    model_path = "./distilbert-base-uncased-finetuned-sst2"
    try:
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model.eval()  # Set to evaluation mode
        torch.set_grad_enabled(False)  # Add this line to disable gradient calculation
        _classifier = pipeline(
            task="text-classification",
            model=model,
            tokenizer=tokenizer,
            device=-1,
            top_k=None,
            batch_size=32  # Increased batch size for better performance
        )
    except Exception as e:
        logging.error(f"Error loading model: {str(e)}")
        raise
    
    # Load the Redis Cache
    try:
        redis_url = os.getenv("REDIS_URL", "localhost")
        redis = asyncio.from_url(f"redis://{redis_url}:6379/0", encoding="utf8", decode_responses=True)
        # Initialize Redis cache with the same prefix
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache-project")
    except Exception as e:
        logging.error(f"Error initializing Redis cache: {str(e)}")
        # Continue without Redis cache rather than failing
    
    yield
    
    logging.info("Shutting down MLAPI Sentiment Analysis")

sub_application_sentiment_predict = FastAPI(lifespan=lifespan)

# Single input model
class SingleSentimentRequest(BaseModel):
    text: str  # Single text string
    
    model_config = ConfigDict(extra="forbid")

# Bulk input model
class BulkSentimentRequest(BaseModel):
    text: List[str]  # List of text strings
    
    model_config = ConfigDict(extra="forbid")

class Sentiment(BaseModel):
    label: str
    score: float

# Single prediction response
class SingleSentimentResponse(BaseModel):
    prediction: List[Sentiment]  # Single prediction with positive/negative sentiments

# Bulk prediction response
class BulkSentimentResponse(BaseModel):
    predictions: List[List[Sentiment]]  # List of sentiment lists

@sub_application_sentiment_predict.post(
    "/predict", response_model=SingleSentimentResponse
)
async def predict(sentiment: SingleSentimentRequest):
    try:
        # Try with cache decorator
        return await cached_predict(sentiment)
    except (ConnectionError, RedisError) as e:
        # Log Redis error but continue without caching
        logging.error(f"Redis error in predict endpoint: {str(e)}")
        return await predict_without_cache(sentiment)
    except Exception as e:
        # Log any other errors but still try to process
        logging.error(f"Error in predict endpoint: {str(e)}")
        return await predict_without_cache(sentiment)

@cache()
async def cached_predict(sentiment: SingleSentimentRequest):
    return await predict_without_cache(sentiment)

async def predict_without_cache(sentiment: SingleSentimentRequest):
    if not sentiment.text:
        return SingleSentimentResponse(prediction=[])
    
    # Process a single text
    prediction = _classifier(sentiment.text)[0]
    
    # Format prediction
    formatted_prediction = [
        Sentiment(label="POSITIVE", score=next((pred["score"] for pred in prediction if pred["label"] == "POSITIVE"), 0.0)),
        Sentiment(label="NEGATIVE", score=next((pred["score"] for pred in prediction if pred["label"] == "NEGATIVE"), 0.0))
    ]
    
    return SingleSentimentResponse(prediction=formatted_prediction)

@sub_application_sentiment_predict.post(
    "/bulk-predict", response_model=BulkSentimentResponse
)
async def bulk_predict(sentiments: BulkSentimentRequest):
    try:
        # Try with cache decorator
        return await cached_bulk_predict(sentiments)
    except (ConnectionError, RedisError) as e:
        # Log Redis error but continue without caching
        logging.error(f"Redis error in bulk_predict endpoint: {str(e)}")
        return await bulk_predict_without_cache(sentiments)
    except Exception as e:
        # Log any other errors but still try to process
        logging.error(f"Error in bulk_predict endpoint: {str(e)}")
        return await bulk_predict_without_cache(sentiments)

@cache()
async def cached_bulk_predict(sentiments: BulkSentimentRequest):
    return await bulk_predict_without_cache(sentiments)

async def bulk_predict_without_cache(sentiments: BulkSentimentRequest):
    texts = sentiments.text
    if not texts:
        return BulkSentimentResponse(predictions=[])
    
    # Process all texts at once in a batch - using vectorized approach
    batch_predictions = _classifier(texts)
    
    all_predictions = []
    for preds in batch_predictions:
        # Format each prediction correctly
        predictions_by_label = {}
        for pred in preds:
            predictions_by_label[pred["label"]] = pred["score"]
        
        formatted_predictions = [
            Sentiment(label="POSITIVE", score=predictions_by_label.get("POSITIVE", 0.0)),
            Sentiment(label="NEGATIVE", score=predictions_by_label.get("NEGATIVE", 0.0))
        ]
        
        all_predictions.append(formatted_predictions)
    
    return BulkSentimentResponse(predictions=all_predictions)

@sub_application_sentiment_predict.get("/health")
async def health():
    # Simple health check that doesn't depend on other components
    return {"status": "healthy"}