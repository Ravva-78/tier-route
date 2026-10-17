"""Splits a multi-part request into independent sub-tasks (rule-based v1)."""
import re

ITEM_RE = re.compile(r"^\s*(\d+[\.\)]|[-*\u2022])\s+")
INLINE_SPLIT = re.compile(r"(?<=[.?!])\s+(?=(?:Also|Then|Next|Finally|Additionally|Second|Third)\b)|;\s+|\s+and then\s+",
                          re.I)


def split_request(text: str, min_len: int = 12) -> list:
    lines = [l for l in text.splitlines() if l.strip()]
    items = [ITEM_RE.sub("", l).strip() for l in lines if ITEM_RE.match(l)]
    if len(items) >= 2:
        context = " ".join(l.strip() for l in lines if not ITEM_RE.match(l))
        return [(context + " " + it).strip() if context else it for it in items]
    parts = [p.strip() for p in INLINE_SPLIT.split(text) if p and p.strip()]
    merged = []
    for p in parts:
        if merged and len(p) < min_len:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged if len(merged) >= 2 else [text.strip()]
