from typing import Optional


def build_repo_file_url(repo_url: str, file_path: str, branch: str = "main") -> str:
    if not repo_url:
        return ""

    normalized_repo_url = repo_url.rstrip("/")
    hostname = normalized_repo_url.split("//", 1)[-1].split("/", 1)[0].lower()

    if hostname == "github.com" or "github" in hostname:
        return f"{normalized_repo_url}/blob/{branch}/{file_path}"
    if hostname == "gitlab.com" or "gitlab" in hostname:
        return f"{normalized_repo_url}/-/blob/{branch}/{file_path}"
    if hostname == "bitbucket.org" or "bitbucket" in hostname:
        return f"{normalized_repo_url}/src/{branch}/{file_path}"
    return ""


def build_context_text(documents: list[dict[str, str]]) -> str:
    docs_by_file: dict[str, list[str]] = {}
    for doc in documents:
        file_path = doc.get('file_path', 'unknown')
        text = doc.get('text', '')
        if not text:
            continue
        docs_by_file.setdefault(file_path, []).append(text)

    context_parts = []
    for file_path, texts in docs_by_file.items():
        header = f"## File Path: {file_path}\n\n"
        content = "\n\n".join(texts)
        context_parts.append(f"{header}{content}")

    return "\n\n" + "----------\n\n".join(context_parts) if context_parts else ""


def build_shared_structure_prompt(
    owner: str,
    repo: str,
    repo_files: list[str],
    readme: str,
    language: str,
    is_comprehensive: bool,
) -> str:
    lang_map = {
        "zh": "Mandarin Chinese (中文)", "ja": "Japanese (日本語)",
        "ko": "Korean (한국어)", "vi": "Vietnamese (Tiếng Việt)",
        "es": "Spanish (Español)", "fr": "French (Français)",
        "ru": "Russian (Русский)", "pt-br": "Brazilian Portuguese (Português Brasileiro)",
    }
    lang_name = lang_map.get(language, "English")
    file_tree = "\n".join(repo_files[:200]) if repo_files else "(no files available)"

    base = f"""Analyze this {repo} repository and create a wiki structure for it.

1. The complete file tree of the project:
<file_tree>
{file_tree}
</file_tree>

2. The README file of the project:
<readme>
{readme[:3000]}
</readme>

I want to create a wiki for this repository. Determine the most logical structure for a wiki based on the repository's content.

IMPORTANT: The wiki content will be generated in {lang_name} language.

When designing the wiki structure, include pages that would benefit from visual diagrams, such as:
- Architecture overviews
- Data flow descriptions
- Component relationships
- Process workflows
- State machines
- Class hierarchies

"""

    if is_comprehensive:
        base += """Create a structured wiki with the following main sections:
- Overview (general information about the project)
- System Architecture (how the system is designed)
- Core Features (key functionality)
- Data Management/Flow
- Frontend Components (UI elements, if applicable)
- Backend Systems (server-side components)
- Deployment/Infrastructure

Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <sections>
    <section id=\"section-1\">
      <title>[Section title]</title>
      <pages>
        <page_ref>page-1</page_ref>
      </pages>
      <subsections>
        <section_ref>section-2</section_ref>
      </subsections>
    </section>
  </sections>
  <pages>
    <page id=\"page-1\">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
      </relevant_files>
      <related_pages>
        <related>page-2</related>
      </related_pages>
      <parent_section>section-1</parent_section>
    </page>
  </pages>
</wiki_structure>

Create 8-12 pages that would make a comprehensive wiki for this repository.
"""
    else:
        base += """Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <pages>
    <page id=\"page-1\">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
      </relevant_files>
      <related_pages>
        <related>page-2</related>
      </related_pages>
    </page>
  </pages>
</wiki_structure>

Create 4-6 pages that would make a concise wiki for this repository.
"""

    base += """
IMPORTANT FORMATTING INSTRUCTIONS:
- Return ONLY the valid XML structure specified above
- DO NOT wrap the XML in markdown code blocks (no ``` or ```xml)
- DO NOT include any explanation text before or after the XML
- Ensure the XML is properly formatted and valid
- Start directly with <wiki_structure> and end with </wiki_structure>

IMPORTANT:
1. Each page should focus on a specific aspect of the codebase
2. The relevant_files should be actual files from the repository
3. Return ONLY valid XML with the structure specified above
"""
    return base


def build_shared_page_prompt(
    page_title: str,
    file_paths: list[str],
    language: str,
    repo_url: str,
    default_branch: str = "main",
    file_contents: Optional[dict[str, str]] = None,
) -> str:
    details_lines = []
    for file_path in file_paths:
        file_url = build_repo_file_url(repo_url, file_path, default_branch)
        if file_url:
            details_lines.append(f"- [{file_path}]({file_url})")
        else:
            details_lines.append(f"- {file_path}")

    source_contents = []
    if file_contents:
        for file_path in file_paths:
            text = (file_contents.get(file_path) or "").strip()
            if text:
                source_contents.append(f"File: {file_path}\n```\n{text[:4000]}\n```")

    language_label = {
        "en": "English",
        "ja": "Japanese (日本語)",
        "zh": "Mandarin Chinese (中文)",
        "zh-tw": "Traditional Chinese (繁體中文)",
        "es": "Spanish (Español)",
        "kr": "Korean (한국어)",
        "vi": "Vietnamese (Tiếng Việt)",
        "pt-br": "Brazilian Portuguese (Português Brasileiro)",
        "fr": "Français (French)",
        "ru": "Русский (Russian)",
    }.get(language, "English")

    return f"""You are an expert technical writer and software architect.
Your task is to generate a comprehensive and accurate technical wiki page in Markdown format about a specific feature, system, or module within a given software project.

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a `<details>` block listing ALL the relevant source files you used to generate the content.
Format it exactly like this:
<details>
<summary>Relevant source files</summary>

{chr(10).join(details_lines)}
</details>

Immediately after the `<details>` block, the main title of the page should be a H1 Markdown heading: `# {page_title}`.

The repository base URL is `{repo_url}` and the default branch is `{default_branch}`.
Use those values when constructing every source citation link.
Keep the visible citation text concise as `file_path:line` or `file_path:start-end`, but make every markdown link target point to the original repository file and line range.

Source file contents:
{chr(10).join(source_contents) if source_contents else '  (source file contents unavailable)'}

Based ONLY on the content of the relevant source files:
- Ground every claim in the provided source files.
- If the source file contents do not support a claim, do not include that claim.
- Generate the content in {language_label} language.

Source citations are EXTREMELY IMPORTANT:
- For EVERY significant explanation, diagram, table entry, or code snippet, you MUST cite the specific source file(s) and relevant line numbers.
- Use the exact format: `Sources: [filename.ext:start_line-end_line](full_repository_url_to_file#Lstart-Lend)` for a range, or `Sources: [filename.ext:line_number](full_repository_url_to_file#Lline)` for a single line.
"""
