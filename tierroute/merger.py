def merge(parts: list, answers: list) -> str:
    if len(answers) == 1:
        return answers[0]
    out = []
    for i, (p, a) in enumerate(zip(parts, answers), 1):
        title = p if len(p) <= 70 else p[:67] + "..."
        out.append(f"{i}. {title}\n{a}")
    return "\n\n".join(out)
