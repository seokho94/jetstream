"""LLM synthesis (spec §4 stage 5 / §5.3) — grounded brief via the Claude Citations API.

KEY-GATED: returns None when ANTHROPIC_API_KEY is absent or the SDK isn't installed,
so callers fall back to the computed brief. Grounding is enforced structurally — the
brief is generated ONLY from the supplied source bodies, and every cited span is
hard-bound to a source document by the Citations API (CANON §9). Citations and
structured outputs can't combine, so the brief is a citations call (no output schema).

Model: SYNTHESIS_MODEL env (claude-sonnet-4-6 default per CANON §9; the project .env
may override, e.g. claude-haiku-4-5).
"""
from __future__ import annotations

import os
import re

from ..config import SYNTHESIS_MODEL

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore

BODY_CHARS = 9000  # ~2.5k tokens per source (CANON LLM_BODY_TOK)
MAX_SOURCES = 6


def available() -> bool:
    """True only when the SDK is installed and an API key is configured."""
    return bool(anthropic and os.environ.get("ANTHROPIC_API_KEY"))


def _split_brief(full: str) -> tuple[str, str]:
    """Split the model's two-paragraph output into (whatsHappening, whyItMatters)."""
    clean = re.sub(r"(?m)^\s*#+.*$", "", full).replace("**", "").strip()  # drop headers/bold
    paras = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]

    def strip_label(p: str) -> str:
        for lab in ("무엇이 일어나고 있는가", "왜 중요한가"):
            if p.startswith(lab):
                return p[len(lab):].lstrip(" :·-—").strip()
        return p

    paras = [strip_label(p) for p in paras]
    whats = paras[0] if paras else clean
    why = " ".join(paras[1:]) if len(paras) > 1 else ""
    return whats, why


def synthesize_brief(current_name: str, docs: list[dict]) -> dict | None:
    """docs: [{title, url, outlet, body}] → grounded brief dict, or None.

    Returns {whatsHappening, whyItMatters, citations:[{text,outlet,url,charStart,charEnd}]}.
    """
    if not available():
        return None
    sources = [d for d in docs if d.get("body")][:MAX_SOURCES]
    if not sources:
        return None

    client = anthropic.Anthropic()
    content: list[dict] = []
    for d in sources:
        title = f"{d.get('outlet', '')}: {d.get('title', '')}".strip(": ").strip()
        content.append(
            {
                "type": "document",
                "source": {"type": "text", "media_type": "text/plain", "data": d["body"][:BODY_CHARS]},
                "title": title or "source",
                "citations": {"enabled": True},
            }
        )
    content.append(
        {
            "type": "text",
            "text": (
                f"다음은 뉴스 흐름 '{current_name}'에 대한 출처 기사들이다. 오직 제공된 출처만 근거로 한국어로 "
                f"정확히 두 문단을 써라. 제목·머리말·마크다운 기호(#, *)·라벨 없이 평문으로. "
                f"첫 문단(2~3문장)은 무엇이 일어나고 있는지, 둘째 문단(1~2문장)은 왜 중요한지를 설명한다. "
                f"출처에 없는 사실은 절대 추가하지 마라. 각 주장은 인용으로 뒷받침되게 하라."
            ),
        }
    )

    model = os.environ.get("SYNTHESIS_MODEL") or SYNTHESIS_MODEL
    try:
        resp = client.messages.create(
            model=model, max_tokens=1024, messages=[{"role": "user", "content": content}]
        )
    except Exception:
        return None

    text_parts: list[str] = []
    citations: list[dict] = []
    for block in resp.content:
        if getattr(block, "type", None) != "text":
            continue
        text_parts.append(block.text)
        for c in getattr(block, "citations", None) or []:
            idx = getattr(c, "document_index", 0) or 0
            src = sources[idx] if 0 <= idx < len(sources) else {}
            citations.append(
                {
                    "text": getattr(c, "cited_text", "") or "",
                    "outlet": src.get("outlet", ""),
                    "url": src.get("url", ""),
                    "charStart": getattr(c, "start_char_index", 0) or 0,
                    "charEnd": getattr(c, "end_char_index", 0) or 0,
                }
            )

    full = "".join(text_parts).strip()
    if not full:
        return None
    whats, why = _split_brief(full)
    return {"whatsHappening": whats, "whyItMatters": why, "citations": citations}
