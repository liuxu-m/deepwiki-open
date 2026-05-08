import asyncio
import logging
import time

import adalflow as adal

from api.config import configs, get_embedder_type

logger = logging.getLogger(__name__)

EMBED_MAX_RETRIES = 3
EMBED_RETRY_BASE_DELAY = 2  # seconds, exponential backoff


async def embed_with_retry(embedder_instance, texts, **kwargs):
    """Wrap embedding calls with retry for timeout and empty-vector resilience."""
    last_error = None
    for attempt in range(EMBED_MAX_RETRIES + 1):
        try:
            # Run the embedding call (adalflow Embedder is synchronous)
            result = await asyncio.wait_for(
                asyncio.to_thread(lambda: embedder_instance(input=texts)),
                timeout=60,
            )
            # Check for empty vectors
            if hasattr(result, 'embeddings'):
                empty_count = sum(
                    1 for e in result.embeddings
                    if not e or all(v == 0 for v in e)
                )
                if empty_count == len(result.embeddings):
                    raise ValueError("All embeddings returned empty vectors")
                if empty_count > 0:
                    logger.warning(
                        f"Embedding batch: {empty_count}/{len(result.embeddings)} "
                        f"empty vectors (attempt {attempt + 1})"
                    )
            return result
        except (asyncio.TimeoutError, ValueError) as e:
            last_error = str(e)
            if attempt < EMBED_MAX_RETRIES:
                delay = EMBED_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Embedding retry {attempt + 1}/{EMBED_MAX_RETRIES} "
                    f"after {delay}s: {last_error}"
                )
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"Embedding failed after {EMBED_MAX_RETRIES} retries: {last_error}"
    )


def embed_with_retry_sync(embedder_instance, texts):
    """Synchronous wrapper for embedding with retry and exponential backoff.

    Designed for call sites that run inside a sync context (e.g. RAG.call,
    single_string_embedder closure) where asyncio.run would collide with an
    already-running event loop.
    """
    last_error = None
    for attempt in range(EMBED_MAX_RETRIES + 1):
        try:
            result = embedder_instance(input=texts)
            # Check for empty vectors
            if hasattr(result, 'embeddings'):
                empty_count = sum(
                    1 for e in result.embeddings
                    if not e or all(v == 0 for v in e)
                )
                if empty_count == len(result.embeddings):
                    raise ValueError("All embeddings returned empty vectors")
                if empty_count > 0:
                    logger.warning(
                        f"Embedding batch: {empty_count}/{len(result.embeddings)} "
                        f"empty vectors (attempt {attempt + 1})"
                    )
            return result
        except Exception as e:
            last_error = str(e)
            if attempt < EMBED_MAX_RETRIES:
                delay = EMBED_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Embedding retry {attempt + 1}/{EMBED_MAX_RETRIES} "
                    f"after {delay}s: {last_error}"
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Embedding failed after {EMBED_MAX_RETRIES} retries: {last_error}"
    )


def get_embedder(is_local_ollama: bool = False, use_google_embedder: bool = False, embedder_type: str = None) -> adal.Embedder:
    """Get embedder based on configuration or parameters.
    
    Args:
        is_local_ollama: Legacy parameter for Ollama embedder
        use_google_embedder: Legacy parameter for Google embedder  
        embedder_type: Direct specification of embedder type ('ollama', 'google', 'bedrock', 'openai')
    
    Returns:
        adal.Embedder: Configured embedder instance
    """
    # Determine which embedder config to use
    if embedder_type:
        if embedder_type == 'ollama':
            embedder_config = configs["embedder_ollama"]
        elif embedder_type == 'google':
            embedder_config = configs["embedder_google"]
        elif embedder_type == 'bedrock':
            embedder_config = configs["embedder_bedrock"]
        else:  # default to openai
            embedder_config = configs["embedder"]
    elif is_local_ollama:
        embedder_config = configs["embedder_ollama"]
    elif use_google_embedder:
        embedder_config = configs["embedder_google"]
    else:
        # Auto-detect based on current configuration
        current_type = get_embedder_type()
        if current_type == 'bedrock':
            embedder_config = configs["embedder_bedrock"]
        elif current_type == 'ollama':
            embedder_config = configs["embedder_ollama"]
        elif current_type == 'google':
            embedder_config = configs["embedder_google"]
        else:
            embedder_config = configs["embedder"]

    # --- Initialize Embedder ---
    model_client_class = embedder_config["model_client"]
    if "initialize_kwargs" in embedder_config:
        model_client = model_client_class(**embedder_config["initialize_kwargs"])
    else:
        model_client = model_client_class()
    
    # Create embedder with basic parameters
    embedder_kwargs = {"model_client": model_client, "model_kwargs": embedder_config["model_kwargs"]}
    
    embedder = adal.Embedder(**embedder_kwargs)
    
    # Set batch_size as an attribute if available (not a constructor parameter)
    if "batch_size" in embedder_config:
        embedder.batch_size = embedder_config["batch_size"]
    return embedder
