def merge_page_source_files(base_files: list[str], retrieved_files: list[str], max_extra: int = 5) -> list[str]:
    merged = []
    seen = set()

    for path in base_files:
        if path and path not in seen:
            merged.append(path)
            seen.add(path)

    extra_added = 0
    for path in retrieved_files:
        if not path or path in seen:
            continue
        merged.append(path)
        seen.add(path)
        extra_added += 1
        if extra_added >= max_extra:
            break

    return merged


def prioritize_page_source_files(file_paths: list[str], max_readme_files: int = 1) -> list[str]:
    prioritized = []
    readme_files = []
    other_docs = []
    code_files = []

    code_extensions = (
        '.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs',
        '.cpp', '.c', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
        '.kt', '.kts', '.scala', '.sh', '.sql'
    )

    for path in file_paths:
        normalized = (path or '').strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if 'readme' in lowered:
            readme_files.append(normalized)
        elif lowered.endswith(code_extensions):
            code_files.append(normalized)
        else:
            other_docs.append(normalized)

    prioritized.extend(code_files)
    prioritized.extend(readme_files[:max_readme_files])
    prioritized.extend(other_docs)

    seen = set()
    deduped = []
    for path in prioritized:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped
