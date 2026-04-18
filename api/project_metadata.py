import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def get_metadata_path() -> Path:
    root = Path(os.environ.get("ADALFLOW_ROOT", Path.home() / ".adalflow"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "project_metadata.json"


def make_project_key(repo_type: str, owner: str, repo: str, language: str) -> str:
    return f"{repo_type}:{owner}:{repo}:{language}"


def load_metadata() -> dict[str, dict[str, Any]]:
    path = get_metadata_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_metadata(data: dict[str, dict[str, Any]]) -> None:
    path = get_metadata_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_project_note(repo_type: str, owner: str, repo: str, language: str) -> Optional[str]:
    metadata = load_metadata()
    key = make_project_key(repo_type, owner, repo, language)
    entry = metadata.get(key) or {}
    note = entry.get("note")
    return note if isinstance(note, str) and note.strip() else None


def upsert_project_note(repo_type: str, owner: str, repo: str, language: str, note: str) -> Optional[str]:
    metadata = load_metadata()
    key = make_project_key(repo_type, owner, repo, language)
    cleaned = note.strip()
    if cleaned:
        metadata[key] = {
            "note": cleaned,
            "updated_at": int(time.time() * 1000),
        }
    else:
        metadata.pop(key, None)
    save_metadata(metadata)
    return cleaned or None


def delete_project_note(repo_type: str, owner: str, repo: str, language: str) -> None:
    metadata = load_metadata()
    key = make_project_key(repo_type, owner, repo, language)
    if key in metadata:
        metadata.pop(key, None)
        save_metadata(metadata)
