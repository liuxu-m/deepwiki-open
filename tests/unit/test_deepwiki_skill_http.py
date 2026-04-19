from urllib.parse import urlparse


def parse_repo_url(repo_url: str):
    if repo_url.startswith("github:"):
        repo_url = "https://github.com/" + repo_url[len("github:"):]
    elif repo_url.startswith("gitlab:"):
        repo_url = "https://gitlab.com/" + repo_url[len("gitlab:"):]

    parsed = urlparse(repo_url)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError("invalid repo_url")
    owner = parts[0]
    repo = "/".join(parts[1:]).removesuffix(".git")
    repo_type = "gitlab" if "gitlab" in host else "github"
    return owner, repo, repo_type


def shape_wiki_structure(cache_payload: dict):
    wiki_structure = cache_payload.get("wiki_structure")
    if wiki_structure is None:
        raise ValueError("wiki not generated")
    return wiki_structure


def shape_page_result(cache_payload: dict, page_id: str | None = None):
    pages = cache_payload.get("generated_pages") or {}
    if page_id is None:
        return list(pages.values())[:10]
    if page_id not in pages:
        raise KeyError("page not found")
    return pages[page_id]


def test_parse_repo_url_supports_github_prefix():
    assert parse_repo_url("github:foo/bar") == ("foo", "bar", "github")


def test_parse_repo_url_supports_gitlab_https():
    assert parse_repo_url("https://gitlab.com/foo/bar") == ("foo", "bar", "gitlab")


def test_parse_repo_url_strips_dot_git_suffix():
    assert parse_repo_url("https://github.com/foo/bar.git") == ("foo", "bar", "github")


def test_shape_wiki_structure_raises_when_missing():
    try:
        shape_wiki_structure({"wiki_structure": None})
        assert False
    except ValueError as exc:
        assert str(exc) == "wiki not generated"


def test_shape_page_result_limits_to_10():
    payload = {"generated_pages": {f"p{i}": {"id": f"p{i}"} for i in range(15)}}
    result = shape_page_result(payload)
    assert len(result) == 10


def test_shape_page_result_returns_specific_page():
    payload = {"generated_pages": {"p1": {"id": "p1", "title": "Page 1"}}}
    result = shape_page_result(payload, "p1")
    assert result["title"] == "Page 1"


def test_shape_page_result_handles_missing_generated_pages():
    assert shape_page_result({}) == []
