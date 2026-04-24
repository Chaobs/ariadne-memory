"""
Session Summarizer — LLM-driven extraction of structured observations
from tool-use events and conversation transcripts.

This is the heart of the "automatic memory capture" feature, mirroring
Claude-Mem's SDKAgent + ResponseProcessor pipeline.

Key differences from Claude-Mem:
- Uses Ariadne's existing LLMFactory (9 providers: DeepSeek, OpenAI, Anthropic, Qwen, Gemini, Grok, Kimi, MiniMax, GLM)
- XML parsing adapted for Python (no TypeScript SDK)
- Fully synchronous (no Worker daemon required)
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Tuple

from ariadne.session.models import (
    Observation,
    ObservationType,
    SessionRecord,
    SessionSummary,
)
from ariadne.session.privacy import strip_private_tags

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XML Parser (mirrors Claude-Mem's parser.ts)
# ---------------------------------------------------------------------------

_OBS_PATTERN = re.compile(
    r"<observation>(.*?)</observation>",
    re.DOTALL | re.IGNORECASE,
)
_SUMMARY_PATTERN = re.compile(
    r"<session_summary>(.*?)</session_summary>",
    re.DOTALL | re.IGNORECASE,
)


def _extract_tag(text: str, tag: str) -> str:
    """Extract content of a named XML tag (first match)."""
    m = re.search(r"<" + tag + r">(.*?)</" + tag + r">", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_list(text: str, tag: str) -> List[str]:
    """Extract a newline / comma-separated list from an XML tag."""
    raw = _extract_tag(text, tag)
    if not raw:
        return []
    # Support both newline and comma separation
    items = re.split(r"[,\n]+", raw)
    return [i.strip() for i in items if i.strip()]


def parse_observations(llm_response: str, session_id: str) -> List[Observation]:
    """
    Parse <observation> blocks from an LLM response into Observation objects.

    Expected XML format:
        <observation>
          <type>bugfix|feature|refactor|change|discovery|decision|security_alert</type>
          <summary>One-line description</summary>
          <detail>Optional detailed notes</detail>
          <files>file1.py, file2.py</files>
          <concepts>concept1, concept2</concepts>
        </observation>
    """
    observations = []
    for match in _OBS_PATTERN.finditer(llm_response):
        block = match.group(1)
        try:
            raw_type = _extract_tag(block, "type").lower()
            try:
                obs_type = ObservationType(raw_type)
            except ValueError:
                obs_type = ObservationType.GENERAL

            summary = _extract_tag(block, "summary")
            if not summary:
                continue  # Skip empty observations

            obs = Observation.new(
                session_id=session_id,
                obs_type=obs_type,
                summary=summary,
                detail=_extract_tag(block, "detail") or None,
                files=_extract_list(block, "files"),
                concepts=_extract_list(block, "concepts"),
            )
            observations.append(obs)
        except Exception as e:
            logger.warning(f"Failed to parse observation block: {e}")

    return observations


def parse_session_summary(llm_response: str, session_id: str) -> Optional[SessionSummary]:
    """
    Parse a <session_summary> block from an LLM response.

    Expected XML format:
        <session_summary>
          <narrative>Multi-sentence description of what happened</narrative>
          <key_decisions>decision1, decision2</key_decisions>
          <files_changed>file1.py, file2.py</files_changed>
          <concepts_covered>concept1, concept2</concepts_covered>
        </session_summary>
    """
    m = _SUMMARY_PATTERN.search(llm_response)
    if not m:
        return None

    block = m.group(1)
    narrative = _extract_tag(block, "narrative")
    if not narrative:
        # Try to use the whole block as narrative
        narrative = block.strip()

    return SessionSummary(
        session_id=session_id,
        narrative=narrative,
        key_decisions=_extract_list(block, "key_decisions"),
        files_changed=_extract_list(block, "files_changed"),
        concepts_covered=_extract_list(block, "concepts_covered"),
    )


# ---------------------------------------------------------------------------
# Prompt Templates (mirrors Claude-Mem's prompts.ts)
# ---------------------------------------------------------------------------

_OBSERVATION_PROMPT = """You are an intelligent assistant analyzing a software development tool-use event.
Extract a structured observation from the following tool call.

Tool name: {tool_name}
Tool input: {tool_input}
Tool output: {tool_output}
Project path: {project_path}

Analyze this tool usage and produce ONE <observation> block.
If the event is trivial (e.g., listing files with no significant change), output nothing.

Format:
<observation>
  <type>bugfix|feature|refactor|change|discovery|decision|security_alert|general</type>
  <summary>One clear sentence describing what happened</summary>
  <detail>Optional: additional context, reasoning, or impact</detail>
  <files>Comma-separated list of affected files (if any)</files>
  <concepts>Comma-separated key concepts or topics (if any)</concepts>
</observation>

Respond ONLY with the observation block or nothing. No other text."""


_SUMMARIZE_PROMPT = """You are an intelligent assistant summarizing a development session.
Review the following observations from this session and create a comprehensive summary.

Session observations:
{observations_text}

Project: {project_path}

Produce a <session_summary> block capturing the key events of this session.

Format:
<session_summary>
  <narrative>2-4 sentences describing what was accomplished in this session</narrative>
  <key_decisions>Decision1, Decision2 (important architectural or design choices made)</key_decisions>
  <files_changed>file1.py, file2.py (most significant files modified)</files_changed>
  <concepts_covered>concept1, concept2 (main topics, technologies, or patterns discussed)</concepts_covered>
</session_summary>

Respond ONLY with the session_summary block. No other text."""


_CONTEXT_INJECT_PROMPT = """You are reviewing prior work context for a new session.
Below are observations and summaries from previous sessions working on this project.

Your task: produce a concise context injection that will help the AI assistant
understand what has been done before, without overwhelming the context window.

Prior sessions (most recent first):
{sessions_text}

Format the context as:
<ariadne-context>
## Prior Work Context

### What was done
[2-3 bullet points of key accomplishments]

### Important decisions
[1-2 bullet points of key decisions that affect current work]

### Files of interest
[key files that were actively worked on]
</ariadne-context>

Keep it under 500 tokens. Focus on actionable context."""


# ---------------------------------------------------------------------------
# SessionSummarizer
# ---------------------------------------------------------------------------


class SessionSummarizer:
    """
    LLM-powered summarizer for session observations.

    Works with any provider supported by Ariadne's LLMFactory:
    DeepSeek, OpenAI, Anthropic, Qwen, Gemini, Grok, Kimi, MiniMax, GLM.
    """

    def __init__(self, llm=None):
        """
        Args:
            llm: BaseLLM instance. If None, loads from Ariadne config.
        """
        self._llm = llm

    def _get_llm(self):
        if self._llm:
            return self._llm
        try:
            from ariadne.config import get_config
            cfg = get_config()
            return cfg.create_llm()
        except Exception as e:
            logger.warning(f"Could not load LLM from config: {e}")
            return None

    def analyze_tool_use(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        project_path: str = "",
    ) -> List[Observation]:
        """
        Ask LLM to extract observations from a single tool-use event.

        Returns empty list if the event is trivial or LLM is unavailable.
        """
        llm = self._get_llm()
        if llm is None:
            # Fallback: create a basic observation from raw data
            return self._fallback_observation(session_id, tool_name, tool_input, tool_output)

        # Strip private content before sending to LLM
        clean_output = strip_private_tags(tool_output or "")
        clean_input = json.dumps(tool_input, ensure_ascii=False, default=str)[:500]

        prompt = _OBSERVATION_PROMPT.format(
            tool_name=tool_name,
            tool_input=clean_input[:500],
            tool_output=clean_output[:1000],
            project_path=project_path or "(unknown)",
        )

        try:
            response = llm.chat(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)
            observations = parse_observations(raw_text, session_id)

            # Attach tool metadata to each observation
            for obs in observations:
                obs.tool_name = tool_name
                obs.tool_input = tool_input

            return observations

        except Exception as e:
            logger.warning(f"LLM observation analysis failed: {e}")
            return self._fallback_observation(session_id, tool_name, tool_input, tool_output)

    def summarize_session(
        self,
        session: SessionRecord,
        observations: List[Observation],
    ) -> Optional[SessionSummary]:
        """
        Generate a narrative summary for a completed session.

        Args:
            session: The session being summarized.
            observations: All observations from this session.

        Returns:
            SessionSummary, or None if LLM is unavailable.
        """
        if not observations:
            return None

        llm = self._get_llm()
        if llm is None:
            logger.warning("LLM not available for session summarization")
            return self._fallback_summary(session, observations)

        # Format observations for the prompt
        obs_lines = []
        for i, obs in enumerate(observations[:30], 1):  # Limit to 30 to avoid token overflow
            line = f"{i}. [{obs.obs_type.value.upper()}] {obs.summary}"
            if obs.detail:
                line += f"\n   Detail: {obs.detail[:200]}"
            if obs.files:
                line += f"\n   Files: {', '.join(obs.files[:5])}"
            obs_lines.append(line)

        prompt = _SUMMARIZE_PROMPT.format(
            observations_text="\n".join(obs_lines),
            project_path=session.project_path,
        )

        try:
            response = llm.chat(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)
            summary = parse_session_summary(raw_text, session.id)
            return summary or self._fallback_summary(session, observations)

        except Exception as e:
            logger.warning(f"LLM session summarization failed: {e}")
            return self._fallback_summary(session, observations)

    def build_context_injection(
        self,
        sessions: List[SessionRecord],
        recent_observations: List[Observation],
        max_tokens: int = 500,
    ) -> str:
        """
        Build context text to inject at the start of a new session.

        Returns plain text (not wrapped in tags) — the caller wraps it.
        """
        if not sessions and not recent_observations:
            return ""

        llm = self._get_llm()
        if llm is None:
            return self._fallback_context(sessions, recent_observations)

        # Build sessions text (last 5 sessions)
        sessions_parts = []
        for s in sessions[:5]:
            part = f"Session {s.started_at[:10]}"
            if s.summary:
                part += f":\n{s.summary[:500]}"
            else:
                # Find observations for this session from recent_observations
                session_obs = [o for o in recent_observations if o.session_id == s.id]
                if session_obs:
                    summaries = "; ".join(o.summary for o in session_obs[:5])
                    part += f":\n{summaries}"
            sessions_parts.append(part)

        prompt = _CONTEXT_INJECT_PROMPT.format(
            sessions_text="\n\n".join(sessions_parts)
        )

        try:
            response = llm.chat(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            # Strip the ariadne-context wrapper if LLM included it
            raw = re.sub(r"</?ariadne[-_]context>", "", raw, flags=re.IGNORECASE).strip()
            return raw

        except Exception as e:
            logger.warning(f"LLM context building failed: {e}")
            return self._fallback_context(sessions, recent_observations)

    # ------------------------------------------------------------------
    # Fallbacks (no LLM needed)
    # ------------------------------------------------------------------

    def _fallback_observation(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
    ) -> List[Observation]:
        """Create a basic GENERAL observation without LLM."""
        # Skip very trivial tools
        trivial = {"ls", "pwd", "echo", "cat"}
        if tool_name in trivial:
            return []

        summary = f"Used tool: {tool_name}"
        if "path" in tool_input:
            summary += f" on {tool_input['path']}"
        elif "file" in tool_input:
            summary += f" on {tool_input['file']}"

        return [Observation.new(
            session_id=session_id,
            obs_type=ObservationType.GENERAL,
            summary=summary,
            tool_name=tool_name,
            tool_input=tool_input,
        )]

    def _fallback_summary(
        self,
        session: SessionRecord,
        observations: List[Observation],
    ) -> SessionSummary:
        """Build a minimal summary without LLM."""
        summaries = [o.summary for o in observations[:10]]
        narrative = "Session included: " + "; ".join(summaries[:5])

        all_files: List[str] = []
        all_concepts: List[str] = []
        for obs in observations:
            all_files.extend(obs.files)
            all_concepts.extend(obs.concepts)

        return SessionSummary(
            session_id=session.id,
            narrative=narrative,
            files_changed=list(dict.fromkeys(all_files))[:10],
            concepts_covered=list(dict.fromkeys(all_concepts))[:10],
        )

    def _fallback_context(
        self,
        sessions: List[SessionRecord],
        observations: List[Observation],
    ) -> str:
        """Build a minimal context injection without LLM."""
        parts = ["## Prior Work Context\n"]

        if sessions:
            parts.append("### Recent sessions")
            for s in sessions[:3]:
                if s.summary:
                    parts.append(f"- {s.started_at[:10]}: {s.summary[:200]}")

        if observations:
            parts.append("\n### Recent observations")
            for obs in observations[:5]:
                parts.append(f"- [{obs.obs_type.value}] {obs.summary}")

        return "\n".join(parts)
