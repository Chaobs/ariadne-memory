"""
Ariadne Wiki Prompts — LLM prompt templates for the Wiki feature.

Implements Karpathy's two-step Chain-of-Thought ingest:
  Step 1: Analysis — LLM reads source, produces structured analysis
  Step 2: Generation — LLM takes analysis, generates wiki pages

Plus prompts for Query and Lint operations.
"""

from typing import Optional


def build_analysis_prompt(
    purpose: str = "",
    index: str = "",
    language: str = "",
) -> str:
    """
    Step 1 prompt: LLM reads the source and produces a structured analysis.
    This is the "discussion" step — the LLM reasons about the source before writing wiki pages.
    """
    parts = [
        "You are an expert research analyst. Read the source document and produce a structured analysis.",
        "",
    ]

    if language and language != "auto":
        parts.append(f"**Output language: {language}.** All analysis must be written in {language}.")
        parts.append("")

    parts.extend([
        "Your analysis should cover:",
        "",
        "## Key Entities",
        "List people, organizations, products, datasets, tools mentioned. For each:",
        "- Name and type",
        "- Role in the source (central vs. peripheral)",
        "- Whether it likely already exists in the wiki (check the index)",
        "",
        "## Key Concepts",
        "List theories, methods, techniques, phenomena. For each:",
        "- Name and brief definition",
        "- Why it matters in this source",
        "- Whether it likely already exists in the wiki",
        "",
        "## Main Arguments & Findings",
        "- What are the core claims or results?",
        "- What evidence supports them?",
        "- How strong is the evidence?",
        "",
        "## Connections to Existing Wiki",
        "- What existing pages does this source relate to?",
        "- Does it strengthen, challenge, or extend existing knowledge?",
        "",
        "## Contradictions & Tensions",
        "- Does anything in this source conflict with existing wiki content?",
        "- Are there internal tensions or caveats?",
        "",
        "## Recommendations",
        "- What wiki pages should be created or updated?",
        "- What should be emphasized vs. de-emphasized?",
        "- Any open questions worth flagging for the user?",
        "",
        "Be thorough but concise. Focus on what's genuinely important.",
        "",
    ])

    if purpose:
        parts.append(f"## Wiki Purpose (for context)\n{purpose}")
        parts.append("")
    if index:
        parts.append(f"## Current Wiki Index (for checking existing content)\n{index}")
        parts.append("")

    return "\n".join(parts)


def build_generation_prompt(
    source_file_name: str,
    schema: str = "",
    purpose: str = "",
    index: str = "",
    overview: str = "",
    language: str = "",
) -> str:
    """
    Step 2 prompt: LLM takes its own analysis and generates wiki files + review items.
    """
    source_base_name = source_file_name.rsplit(".", 1)[0] if "." in source_file_name else source_file_name

    parts = [
        "You are a wiki maintainer. Based on the analysis provided, generate wiki files.",
        "",
    ]

    if language and language != "auto":
        parts.append(f"**Output language: {language}.** All generated content must be written in {language}.")
        parts.append("")

    parts.extend([
        f"## IMPORTANT: Source File",
        f"The original source file is: **{source_file_name}**",
        f"All wiki pages generated from this source MUST include this filename in their frontmatter `sources` field.",
        "",
        "## What to generate",
        "",
        f"1. A source summary page at **wiki/sources/{source_base_name}.md** (MUST use this exact path)",
        "2. Entity pages in wiki/entities/ for key entities identified in the analysis",
        "3. Concept pages in wiki/concepts/ for key concepts identified in the analysis",
        "4. An updated wiki/index.md — add new entries to existing categories, preserve all existing entries",
        "5. A log entry for wiki/log.md (just the new entry to append, format: ## [YYYY-MM-DD] ingest | Title)",
        "6. An updated wiki/overview.md — a high-level summary of what the entire wiki covers, updated to reflect the newly ingested source. This should be a comprehensive 2-5 paragraph overview of ALL topics in the wiki, not just the new source.",
        "",
        "## Frontmatter Rules (CRITICAL)",
        "",
        "Every page MUST have YAML frontmatter with these fields:",
        "```yaml",
        "---",
        "type: source | entity | concept | comparison | query | synthesis",
        "title: Human-readable title",
        "created: YYYY-MM-DD",
        "updated: YYYY-MM-DD",
        "tags: []",
        "related: []",
        f'sources: ["{source_file_name}"]  # MUST contain the original source filename',
        "---",
        "```",
        "",
        f'The `sources` field MUST always contain "{source_file_name}" — this links the wiki page back to the original uploaded document.',
        "",
        "Other rules:",
        "- Use [[wikilink]] syntax for cross-references between pages",
        "- Use kebab-case filenames",
        "- Follow the analysis recommendations on what to emphasize",
        "- If the analysis found connections to existing pages, add cross-references",
        "",
        "## Review block types",
        "",
        "After all FILE blocks, optionally emit REVIEW blocks for anything that needs human judgment:",
        "",
        "- contradiction: the analysis found conflicts with existing wiki content",
        "- duplicate: an entity/concept might already exist under a different name in the index",
        "- missing-page: an important concept is referenced but has no dedicated page",
        "- suggestion: ideas for further research, related sources to look for, or connections worth exploring",
        "",
        "Only create reviews for things that genuinely need human input. Don't create trivial reviews.",
        "",
        "## Output Format (MUST FOLLOW EXACTLY)",
        "",
        "Your ENTIRE response consists of FILE blocks followed by optional REVIEW blocks. Nothing else.",
        "",
        "FILE block template:",
        "```",
        "---FILE: wiki/path/to/page.md---",
        "(complete file content with YAML frontmatter)",
        "---END FILE---",
        "```",
        "",
        "REVIEW block template (optional, after all FILE blocks):",
        "```",
        "---REVIEW: type | Title---",
        "Description of what needs the user's attention.",
        "OPTIONS: Create Page | Skip",
        "PAGES: wiki/page1.md, wiki/page2.md",
        "---END REVIEW---",
        "```",
        "",
        "## Output Requirements (STRICT)",
        "",
        "1. The FIRST character of your response MUST be `-` (the opening of `---FILE:`).",
        "2. DO NOT output any preamble.",
        "3. DO NOT echo or restate the analysis — your job is to emit FILE blocks.",
        "4. DO NOT output markdown tables, bullet lists, or headings outside of FILE/REVIEW blocks.",
        "5. DO NOT output any trailing commentary after the last block.",
        "",
    ])

    if purpose:
        parts.append(f"## Wiki Purpose\n{purpose}")
        parts.append("")
    if schema:
        parts.append(f"## Wiki Schema\n{schema}")
        parts.append("")
    if index:
        parts.append(f"## Current Wiki Index (preserve all existing entries, add new ones)\n{index}")
        parts.append("")
    if overview:
        parts.append(f"## Current Overview (update this to reflect the new source)\n{overview}")
        parts.append("")

    return "\n".join(parts)


def build_query_prompt(
    purpose: str = "",
    index: str = "",
    language: str = "",
) -> str:
    """Prompt for querying the wiki."""
    parts = [
        "You are a knowledgeable assistant helping to answer questions based on a wiki.",
        "",
    ]
    if language and language != "auto":
        parts.append(f"**Output language: {language}.** Respond in {language}.")
        parts.append("")

    parts.extend([
        "Instructions:",
        "- Search the provided wiki pages for relevant information",
        "- Synthesize an answer with citations (use [1], [2] etc. to cite page numbers)",
        "- If the answer reveals important connections or analysis, suggest saving it to the wiki",
        "- Be thorough but focused on the question asked",
        "",
    ])

    if purpose:
        parts.append(f"## Wiki Purpose\n{purpose}")
        parts.append("")
    if index:
        parts.append(f"## Wiki Index\n{index}")
        parts.append("")

    return "\n".join(parts)


def build_semantic_lint_prompt(
    page_summaries: str,
    language: str = "",
) -> str:
    """Prompt for semantic lint of the wiki."""
    parts = [
        "You are a wiki quality analyst. Review the following wiki page summaries and identify issues.",
        "",
    ]
    if language and language != "auto":
        parts.append(f"**Output language: {language}.** Respond in {language}.")
        parts.append("")

    parts.extend([
        "For each issue, output exactly this format:",
        "",
        "---LINT: type | severity | Short title---",
        "Description of the issue.",
        "PAGES: page1.md, page2.md",
        "---END LINT---",
        "",
        "Types:",
        "- contradiction: two or more pages make conflicting claims",
        "- stale: information that appears outdated or superseded",
        "- missing-page: an important concept is heavily referenced but has no dedicated page",
        "- suggestion: a question or source worth adding to the wiki",
        "",
        "Severities:",
        "- warning: should be addressed",
        "- info: nice to have",
        "",
        "Only report genuine issues. Do not invent problems. Output ONLY the ---LINT--- blocks, no other text.",
        "",
        "## Wiki Pages",
        "",
        page_summaries,
    ])

    return "\n".join(parts)
