# Base Arguements to leverage across build stages
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

# Copy over the venv including any symbolic links, do not install development/testing libraries when install poetry dependencies
RUN python -m venv --copies ${APP_DIR}/venv
RUN . ${APP_DIR}/venv/bin/activate && poetry install --only main --no-root

# Stage 2: Create a smaller runtime image
FROM python:3.11-slim AS runtime
ARG APP_DIR

COPY --from=build ${APP_DIR}/venv ${APP_DIR}/venv/
ENV PATH=${APP_DIR}/venv/bin:$PATH

WORKDIR ${APP_DIR}/
COPY . ./

# Explicitly expose port 8000
EXPOSE 8000

# Command to start the FastAPI application using Poetry
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]



# # Base Arguements to leverage across build stages
# ARG APP_DIR=/app
#
# # Stage 1: Build the application
# FROM python:3.11-slim AS build
# ARG APP_DIR
#
# # Install necessary build dependencies
# RUN apt-get update && apt-get install -y \
#     curl \
#     libffi-dev \
#     && rm -rf /var/lib/apt/lists/*
#
# # Install Poetry
# ENV POETRY_VERSION=2.0.1
# RUN curl -sSL https://install.python-poetry.org | python -
# ENV PATH=/root/.local/bin:$PATH
#
# # Copy pyproject.toml and poetry.lock first for caching
# WORKDIR ${APP_DIR}
# COPY pyproject.toml poetry.lock* ./
#
# # Copy over the venv including any symbolic links, do not install development/testing libraries when install poetry dependencies
# RUN python -m venv --copies ${APP_DIR}/venv
# RUN . ${APP_DIR}/venv/bin/activate && poetry install --only main --no-root
#
#
# # Stage 2: Create a smaller runtime image
# FROM python:3.11-slim AS runtime
# ARG APP_DIR
#
# COPY --from=build ${APP_DIR}/venv ${APP_DIR}/venv/
# ENV PATH=${APP_DIR}/venv/bin:$PATH
#
# WORKDIR ${APP_DIR}/
# COPY  . ./
#
# # Command to start the FastAPI application using Poetry
# CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
#
# HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
#     CMD curl -f http://localhost:8000/lab/health || exit 1
