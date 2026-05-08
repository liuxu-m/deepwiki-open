from unittest.mock import MagicMock

from api.embed_retry import EMBED_MAX_RETRIES, embed_with_retry_sync


def _make_embedding_result(values):
    """Build a minimal object with .embeddings matching the adalflow shape."""
    return type("Result", (), {"embeddings": values})()


def test_embed_with_retry_sync_success_first_attempt():
    mock = MagicMock()
    mock.return_value = _make_embedding_result([[0.1, 0.2]])

    result = embed_with_retry_sync(mock, "hello")

    assert mock.call_count == 1
    assert result.embeddings == [[0.1, 0.2]]


def test_embed_with_retry_sync_retry_on_value_error_then_success():
    mock = MagicMock()
    mock.side_effect = [
        ValueError("transient embedding error"),
        _make_embedding_result([[0.1]]),
    ]

    result = embed_with_retry_sync(mock, "hello")

    assert mock.call_count == 2
    assert result.embeddings == [[0.1]]


def test_embed_with_retry_sync_exhausts_retries():
    mock = MagicMock(side_effect=ConnectionError("persistent network error"))

    try:
        embed_with_retry_sync(mock, "hello")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "retries" in str(e)

    assert mock.call_count == EMBED_MAX_RETRIES + 1


def test_embed_with_retry_sync_detects_all_empty_vectors():
    mock = MagicMock()
    mock.side_effect = [
        _make_embedding_result([[0.0, 0.0], [0.0, 0.0]]),
        _make_embedding_result([[0.1, 0.2]]),
    ]

    result = embed_with_retry_sync(mock, ["a", "b"])

    assert mock.call_count == 2
    assert result.embeddings == [[0.1, 0.2]]


def test_embed_with_retry_sync_does_not_retry_type_error():
    mock = MagicMock(side_effect=TypeError("unexpected argument type"))

    try:
        embed_with_retry_sync(mock, "hello")
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    assert mock.call_count == 1
