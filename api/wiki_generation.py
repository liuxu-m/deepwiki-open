from typing import Optional
import re


def build_repo_file_url(repo_url: str, file_path: str, branch: str = "main") -> str:
    if not repo_url:
        return ""

    normalized_repo_url = repo_url.rstrip("/")
    normalized_file_path = file_path.replace("\\", "/")
    hostname = normalized_repo_url.split("//", 1)[-1].split("/", 1)[0].lower()

    if hostname == "github.com" or "github" in hostname:
        return f"{normalized_repo_url}/blob/{branch}/{normalized_file_path}"
    if hostname == "gitlab.com" or "gitlab" in hostname:
        return f"{normalized_repo_url}/-/blob/{branch}/{normalized_file_path}"
    if hostname == "bitbucket.org" or "bitbucket" in hostname:
        return f"{normalized_repo_url}/src/{branch}/{normalized_file_path}"
    return ""


def build_repo_citation_url(repo_url: str, file_path: str, start_line: str, end_line: Optional[str] = None, branch: str = "main") -> str:
    base_file_url = build_repo_file_url(repo_url, file_path, branch)
    if not base_file_url:
        return ""

    hostname = repo_url.split("//", 1)[-1].split("/", 1)[0].lower() if repo_url else ""
    if hostname == "bitbucket.org" or "bitbucket" in hostname:
        return f"{base_file_url}#lines-{start_line}{f':{end_line}' if end_line else ''}"
    return f"{base_file_url}#L{start_line}{f'-L{end_line}' if end_line else ''}"


def normalize_source_citation_links(markdown: str, repo_url: str, branch: str = "main") -> str:
    return re.sub(
        r"\[([^\]\n]+?):(\d+)(?:-(\d+))?\]\(([^)]*)\)",
        lambda match: _rewrite_citation_match(match, repo_url, branch),
        markdown,
    )


def _rewrite_citation_match(match: re.Match[str], repo_url: str, branch: str = "main") -> str:
    file_path, start_line, end_line, href = match.groups()
    normalized_file_path = file_path.replace("\\", "/")
    normalized_url = build_repo_citation_url(repo_url, normalized_file_path, start_line, end_line, branch)
    if not normalized_url:
        return match.group(0)

    trimmed_href = href.strip()
    should_rewrite = (
        not trimmed_href
        or trimmed_href == "#"
        or trimmed_href.startswith("#source:")
        or normalized_file_path not in trimmed_href.replace("\\", "/")
        or ("#L" not in trimmed_href and "#lines-" not in trimmed_href)
    )
    if not should_rewrite:
        return match.group(0).replace(file_path, normalized_file_path)

    line_suffix = f"-{end_line}" if end_line else ""
    return f"[{normalized_file_path}:{start_line}{line_suffix}]({normalized_url})"


def validate_generated_wiki_page(markdown: str, file_paths: list[str]) -> tuple[bool, str]:
    if '<details>' not in markdown or 'Relevant source files' not in markdown:
        return False, 'Missing Relevant source files details block'
    source_lines = [line for line in markdown.splitlines() if line.strip().startswith('Sources:')]
    if not source_lines:
        return False, 'Missing Sources citations'
    if len(source_lines) < 2:
        return False, 'At least two Sources citations are required in the body'
    matched_files = [file_path for file_path in file_paths if file_path in markdown]
    if file_paths and len(matched_files) < min(2, len(file_paths)):
        return False, 'Generated page must reference multiple selected source files'
    return True, ''


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
    file_tree = "\n".join(repo_files) if repo_files else "(no files available)"

    base = f"""Analyze this GitHub repository {owner}/{repo} and create a wiki structure for it.

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
- Data Management/Flow: If applicable, how data is stored, processed, accessed, and managed (e.g., database schema, data pipelines, state management).
- Frontend Components (UI elements, if applicable.)
- Backend Systems (server-side components)
- Model Integration (AI model connections)
- Deployment/Infrastructure (how to deploy, what's the infrastructure like)
- Extensibility and Customization: If the project architecture supports it, explain how to extend or customize its functionality (e.g., plugins, theming, custom modules, hooks).

Each section should contain relevant pages. For example, the "Frontend Components" section might include pages for "Home Page", "Repository Wiki Page", "Ask Component", etc.

Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <sections>
    <section id=\"section-1\">
      <title>[Section title]</title>
      <pages>
        <page_ref>page-1</page_ref>
        <page_ref>page-2</page_ref>
      </pages>
      <subsections>
        <section_ref>section-2</section_ref>
      </subsections>
    </section>
    <!-- More sections as needed -->
  </sections>
  <pages>
    <page id=\"page-1\">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
        <!-- More file paths as needed -->
      </relevant_files>
      <related_pages>
        <related>page-2</related>
        <!-- More related page IDs as needed -->
      </related_pages>
      <parent_section>section-1</parent_section>
    </page>
    <!-- More pages as needed -->
  </pages>
</wiki_structure>
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
        <!-- More file paths as needed -->
      </relevant_files>
      <related_pages>
        <related>page-2</related>
        <!-- More related page IDs as needed -->
      </related_pages>
    </page>
    <!-- More pages as needed -->
  </pages>
</wiki_structure>
"""

    base += f"""
IMPORTANT FORMATTING INSTRUCTIONS:
- Return ONLY the valid XML structure specified above
- DO NOT wrap the XML in markdown code blocks (no ``` or ```xml)
- DO NOT include any explanation text before or after the XML
- Ensure the XML is properly formatted and valid
- Start directly with <wiki_structure> and end with </wiki_structure>

IMPORTANT:
1. Create {'8-12' if is_comprehensive else '4-6'} pages that would make a {'comprehensive' if is_comprehensive else 'concise'} wiki for this repository
2. Each page should focus on a specific aspect of the codebase (e.g., architecture, key features, setup)
3. The relevant_files should be actual files from the repository that would be used to generate that page
4. Return ONLY valid XML with the structure specified above, with no markdown code block delimiters
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

You will be given:
1. The "[WIKI_PAGE_TOPIC]" for the page you need to create.
2. A list of "[RELEVANT_SOURCE_FILES]" from the project that you MUST use as the sole basis for the content. You have access to the full content of these files. You MUST use AT LEAST 5 relevant source files for comprehensive coverage - if fewer are provided, search for additional related files in the codebase.

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a `<details>` block listing ALL the `[RELEVANT_SOURCE_FILES]` you used to generate the content. There MUST be AT LEAST 5 source files listed - if fewer were provided, you MUST find additional related files to include.
Format it exactly like this:
<details>
<summary>Relevant source files</summary>

Remember, do not provide any acknowledgements, disclaimers, apologies, or any other preface before the `<details>` block. JUST START with the `<details>` block.
The following files were used as context for generating this wiki page:

{chr(10).join(details_lines)}
<!-- Add additional relevant files if fewer than 5 were provided -->
</details>

Immediately after the `<details>` block, the main title of the page should be a H1 Markdown heading: `# {page_title}`.

The repository base URL is `{repo_url}` and the default branch is `{default_branch}`.
Use those values when constructing every source citation link.
Keep the visible citation text concise as `file_path:line` or `file_path:start-end`, but make every markdown link target point to the original repository file and line range.

Source file contents:
{chr(10).join(source_contents) if source_contents else '  (source file contents unavailable)'}

Based ONLY on the content of the `[RELEVANT_SOURCE_FILES]`:

1. **Introduction:** Start with a concise introduction (1-2 paragraphs) explaining the purpose, scope, and high-level overview of "{page_title}" within the context of the overall project.
2. **Detailed Sections:** Break down "{page_title}" into logical sections using H2 (`##`) and H3 (`###`) Markdown headings.
3. **Mermaid Diagrams:** EXTENSIVELY use Mermaid diagrams derived from the source files.
4. **Tables:** Use Markdown tables to summarize key information when useful.
5. **Code Snippets (ENTIRELY OPTIONAL):** Include short, relevant code snippets from the source files.
6. **Source Citations (EXTREMELY IMPORTANT):**
   - For EVERY piece of significant information, explanation, diagram, table entry, or code snippet, you MUST cite the specific source file(s) and relevant line numbers from which the information was derived.
   - Use the exact format: `Sources: [filename.ext:start_line-end_line](full_repository_url_to_file#Lstart-Lend)` for a range, or `Sources: [filename.ext:line_number](full_repository_url_to_file#Lline)` for a single line.
   - The visible citation text MUST stay concise as the file path and line numbers only.
   - IMPORTANT: You MUST cite AT LEAST 5 different source files throughout the wiki page to ensure comprehensive coverage.
7. **Technical Accuracy:** All information must be derived SOLELY from the `[RELEVANT_SOURCE_FILES]`.
8. **Clarity and Conciseness:** Use clear, professional, and concise technical language.
9. **Conclusion/Summary:** End with a brief summary paragraph if appropriate.

IMPORTANT: Generate the content in {language_label} language.

Remember:
- Ground every claim in the provided source files.
- Prioritize accuracy and direct representation of the code's functionality and structure.
- Structure the document logically for easy understanding by other developers.
"""
