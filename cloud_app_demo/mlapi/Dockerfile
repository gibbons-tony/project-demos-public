# Base Arguments to leverage across build stages
ARG APP_DIR=/app

# Stage 1: Build the application
FROM python:3.11-slim AS build
ARG APP_DIR

# Install necessary build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.0.1
RUN curl -sSL https://install.python-poetry.org | python -
ENV PATH=/root/.local/bin:$PATH

# Copy pyproject.toml and poetry.lock first for caching
WORKDIR ${APP_DIR}
COPY pyproject.toml poetry.lock* ./

# Install dependencies inside a virtual environment
RUN python -m venv --copies ${APP_DIR}/venv
RUN . ${APP_DIR}/venv/bin/activate && poetry install --only main --no-root
RUN rm -rf /root/.cache /root/.config /root/.local/share/pip

# Stage 2: Create a smaller runtime image
FROM python:3.11-slim AS runtime
ARG APP_DIR

WORKDIR ${APP_DIR}/

# COPY --from=build ${APP_DIR}/venv ${APP_DIR}/venv/
# ENV PATH=${APP_DIR}/venv/bin:$PATH

COPY --from=build ${APP_DIR}/venv ${APP_DIR}/venv/
ENV PATH=${APP_DIR}/venv/bin:$PATH

# Set environment variables for faster model loading
ENV TRANSFORMERS_OFFLINE=1
ENV TOKENIZERS_PARALLELISM=true
ENV TORCH_NUM_THREADS=4
ENV OMP_NUM_THREADS=4


# Copy model files first (these rarely change)
# COPY ./distilbert-base-uncased-finetuned-sst2 ./distilbert-base-uncased-finetuned-sst2/
# COPY ../distilbert-base-uncased-finetuned-sst2 ./distilbert-base-uncased-finetuned-sst2/
COPY ./distilbert-base-uncased-finetuned-sst2/config.json ./distilbert-base-uncased-finetuned-sst2/
COPY ./distilbert-base-uncased-finetuned-sst2/pytorch_model.bin ./distilbert-base-uncased-finetuned-sst2/
COPY ./distilbert-base-uncased-finetuned-sst2/tokenizer_config.json ./distilbert-base-uncased-finetuned-sst2/
COPY ./distilbert-base-uncased-finetuned-sst2/vocab.txt ./distilbert-base-uncased-finetuned-sst2/
COPY ./distilbert-base-uncased-finetuned-sst2/tokenizer.json ./distilbert-base-uncased-finetuned-sst2/


# Copy application code
# COPY . ./
COPY src/ ./src/
# COPY tests/ ./tests/
# COPY example.py ./


# Explicitly expose port 8000
EXPOSE 8000

# Command to start the FastAPI application using uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--timeout-keep-alive", "60"]
