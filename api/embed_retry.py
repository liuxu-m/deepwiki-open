import logging
import time

logger = logging.getLogger(__name__)

EMBED_MAX_RETRIES = 3
EMBED_RETRY_BASE_DELAY = 2  # seconds, exponential backoff

# Only retry recoverable errors — programming errors (TypeError, AttributeError)
# should fail fast so they are visible during development.
_RETRYABLE_ERRORS = (ConnectionError, TimeoutError, OSError, ValueError)


def embed_with_retry_sync(embedder_instance, texts):
    """Embedding call with retry and exponential backoff for recoverable failures.

    Targets timeout, connection loss, and empty-vector responses from embedding
    providers.  Programming errors (TypeError, AttributeError, etc.) are not
    retried and propagate immediately.
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
        except _RETRYABLE_ERRORS as e:
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
