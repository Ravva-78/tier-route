"""Gold-free helpers that work on a prompt and a model output only (no grader, no gold, no tests)."""
import ast
import builtins
import re
import unicodedata

ANSWER_RE = re.compile(r"answer\s*:\s*(.+)", re.I)


def wants_answer_format(prompt: str) -> bool:
    return bool(re.search(r"Answer:", prompt))


def is_code_prompt(prompt: str) -> bool:
    return "```python" in prompt


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)\s*```", text or "", re.DOTALL)
    return m.group(1) if m else (text or "")


def final_answer(prompt: str, text: str) -> str:
    """Normalised final answer used to compare samples. '' means missing/malformed."""
    text = text or ""
    if is_code_prompt(prompt):
        try:
            return ast.dump(ast.parse(extract_code(text)))
        except (SyntaxError, ValueError):
            return ""
    m = ANSWER_RE.findall(text)
    if not m:
        return ""
    a = unicodedata.normalize("NFKC", m[-1]).lower().replace("*", "").strip().strip("\"'.` ")
    return re.sub(r"\s+", " ", a).replace(",", "")


def _self_contained(assert_line: str, fn) -> bool:
    """True if the assert only uses literals, builtins and the target function (no free example variables)."""
    try:
        tree = ast.parse(assert_line)
    except SyntaxError:
        return False
    ok_names = set(dir(builtins)) | {fn}
    return all(n.id in ok_names for n in ast.walk(tree) if isinstance(n, ast.Name))


def prompt_examples(prompt: str):
    """Example asserts that literally appear inside the prompt. Returns (func_name or None, [assert lines])."""
    asserts = [l.strip() for l in prompt.splitlines() if l.strip().startswith("assert ")]
    fn = None
    m = re.search(r"^\s*def\s+(\w+)\s*\(", prompt, re.M)
    if m:
        fn = m.group(1)
    elif asserts:
        m2 = re.match(r"assert\s+(?:not\s+)?\(?\s*(\w+)\s*\(", asserts[0])
        fn = m2.group(1) if m2 else None
    if fn:
        # docstring examples:  name(args) ==> expected   |   name(args) == expected   |   >>> name(args) \n expected
        for line in prompt.splitlines():
            m3 = re.match(rf"^\s*(?:>>>\s*)?({fn}\(.*?\))\s*(?:==>|=>|==|->)\s*(.+?)\s*$", line)
            if m3:
                call, exp = m3.groups()
                try:
                    ast.parse(call, mode="eval")
                    ast.parse(exp, mode="eval")
                except SyntaxError:
                    continue
                asserts.append(f"assert {call} == ({exp})")
        lines = prompt.splitlines()
        for i, line in enumerate(lines[:-1]):
            m4 = re.match(rf"^\s*>>>\s*({fn}\(.*\))\s*$", line)
            if m4 and lines[i + 1].strip() and not lines[i + 1].strip().startswith(">>>"):
                exp = lines[i + 1].strip()
                try:
                    ast.parse(exp, mode="eval")
                except SyntaxError:
                    continue
                asserts.append(f"assert {m4.group(1)} == ({exp})")
    return fn, [a for a in dict.fromkeys(asserts) if _self_contained(a, fn)]
