import json
from pathlib import Path


def test_default_openai_embedder_batch_size_is_reduced():
    config_path = Path('D:/my_code/python_code/deepwiki-open/api/config/embedder.json')
    data = json.loads(config_path.read_text(encoding='utf-8'))

    assert data['embedder']['batch_size'] <= 100
