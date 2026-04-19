"""Re-export Pydantic models used by MCP tools.

These models mirror the definitions in api.api to avoid triggering FastAPI
app initialization side-effects during import.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class WikiPage(BaseModel):
    id: str
    title: str
    content: str
    filePaths: List[str]
    importance: str
    relatedPages: List[str]


class ProcessedProjectEntry(BaseModel):
    id: str
    owner: str
    repo: str
    name: str
    repo_type: str
    submittedAt: int
    language: str
    summary: Optional[str] = None
    note: Optional[str] = None


class WikiSection(BaseModel):
    id: str
    title: str
    pages: List[str]
    subsections: Optional[List[str]] = None


class WikiStructureModel(BaseModel):
    id: str
    title: str
    description: str
    pages: List[WikiPage]
    sections: Optional[List[WikiSection]] = None
    rootSections: Optional[List[str]] = None


__all__ = ["WikiPage", "WikiSection", "WikiStructureModel", "ProcessedProjectEntry"]
