"""
Pipeline module for ml_lib.

Provides:
- get_pipeline(model_name) - Get pipeline and metadata
- list_models() - List all available models
- PIPELINE_REGISTRY - Direct access to registry
"""
from .pipeline_registry import (
    get_pipeline,
    list_models,
    PIPELINE_REGISTRY
)

__all__ = [
    'get_pipeline',
    'list_models',
    'PIPELINE_REGISTRY'
]
