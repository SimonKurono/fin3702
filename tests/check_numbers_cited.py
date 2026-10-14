"""Hallucination screen: every number in an LLM justification should appear in the data it was given.
Usage: python tests/check_numbers_cited.py PROMPT_FILE ANSWER_FILE"""
import re
import sys

NUM = re.compile(r"-?\d+(?:\.\d+)?")
prompt, answer = open(sys.argv[1]).read(), open(sys.argv[2]).read()
data = prompt[prompt.index("MODEL OUTPUT START"):prompt.index("MODEL OUTPUT END")]


def variants(tok):
    """Allowed spellings of a number from the data: as written, as a percent, rounded."""
    out = set()
    x = float(tok)
    out.add(tok)
    for d in range(0, 7):
        out.add(f"{x:.{d}f}"); out.add(f"{abs(x):.{d}f}")
        out.add(f"{x * 100:.{d}f}"); out.add(f"{abs(x) * 100:.{d}f}")
    return out


allowed = set()
for t in NUM.findall(data):
    allowed |= variants(t)
allowed |= {"1", "2", "3", "4", "5", "7", "12", "48", "2021", "2024", "2025", "2024-12-31", "31", "12"}   # list numbers, A, months, years
cited = [t for t in NUM.findall(answer) if t.lstrip("-") not in {a.lstrip("-") for a in allowed}]
print(f"numbers in answer: {len(NUM.findall(answer))}; not found in the data: {len(cited)}")
for c in sorted(set(cited), key=cited.index):
    print("  NOT IN DATA:", c)
print("CLEAN" if not cited else "REVIEW")
