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
