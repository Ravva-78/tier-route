"""Cheap sanity check on a model's answer. A failed check escalates the part to the next tier."""
import re

UNSURE = ["i'm not sure", "i am not sure", "i cannot", "i can't", "as an ai", "i don't know",
          "i do not know", "unable to", "not able to", "cannot determine"]


def verify(prompt: str, answer: str, task_type: str, error=None):
    if error:
        return False, f"provider error: {error[:80]}"
    a = (answer or "").strip()
    if not a:
        return False, "empty answer"
    low = a.lower()
    if any(p in low for p in UNSURE):
        return False, "answer signals uncertainty"
    words = re.findall(r"\w+", low)
    if len(words) > 30 and len(set(words)) / len(words) < 0.30:
        return False, "repetitive / degenerate output"
    if task_type == "code" and not re.search(r"def |function|return|class|\{|;", a):
        return False, "no code found in a code task"
    return True, "ok"
