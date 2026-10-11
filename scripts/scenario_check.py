import re
import time
from pathlib import Path

from app.pipeline import answer

BAD_MATH = re.compile(r"\\text|\\\(|\\\[|\$\$|\\frac|\\times|\\ge|\\le")
OVERCONFIDENT = ["you will meet", "you will graduate", "you will complete", "you will be able to graduate",
                 "you will definitely", "you are guaranteed"]
CAVEAT = ["confirm", "verify", "academic office", "degree audit"]

SCENARIOS = [
    ("facts without a question", [
        ("i have cgpa of 4.95 in 7th sem", {"asks": True}),
        ("i have completed 116 credits till 6th sem", {"asks": True}),
    ]),
    ("plan check", [
        ("i have cgpa of 4.95 in 7th sem", {"asks": True}),
        ("i have completed 116 credits till 6th sem", {"asks": True}),
        ("right now i have 116 credits, in 7th sem i will take 24 credits and in 8th sem 22. will i complete my degree?",
         {"any1": ["overload", "exceed"], "any2": ["156"], "caveat": True,
          "must_not": ["not fully specified", "not specified in the provided"]}),
    ]),
    ("SG and CW", [("do the 156 credits include SG and CW", {"any1": ["include"]})]),
    ("overload", [("my cgpa is 6.5, can I take 24 credits in one semester?", {"any1": ["8.0"], "any2": ["overload"]})]),
    ("honors", [
        ("i have cgpa 7.5, will i get honors?", {"any1": ["8.0"]}),
        ("what is the minimum cgpa for an honors degree", {"any1": ["8.0"]}),
    ]),
]

out_lines, bad = [], 0
for name, turns in SCENARIOS:
    history = []
    out_lines.append(f"\n## {name}")
    for q, exp in turns:
        a = answer(q, history[-12:], "")["answer"]
        low, problems = a.lower(), []
        if BAD_MATH.search(a):
            problems.append("raw LaTeX")
        problems += [f"overconfident: {s!r}" for s in OVERCONFIDENT if s in low]
        problems += [f"forbidden: {s!r}" for s in exp.get("must_not", []) if s in low]
        if exp.get("asks") and not ("?" in a and "[" not in a):
            problems.append("should ask a question without citations")
        for k in ("any1", "any2"):
            if exp.get(k) and not any(s in low for s in exp[k]):
                problems.append(f"none of {exp[k]} found")
        if exp.get("caveat") and not any(s in low for s in CAVEAT):
            problems.append("no 'confirm with office / degree audit' caveat")
        bad += bool(problems)
        print(("FAIL" if problems else "PASS"), "|", q)
        for p in problems:
            print("     !!", p)
        if problems:
            print("     ANSWER:", a)
        out_lines += [f"\n**Q:** {q}\n", f"**A:** {a}\n", f"**Problems:** {problems or 'none'}\n"]
        history += [{"role": "user", "text": q}, {"role": "assistant", "text": a[:800]}]
        time.sleep(5)

Path("eval/scenarios_out.md").write_text("\n".join(out_lines), encoding="utf-8")
print(f"\n{bad} scenario(s) with problems. Full answers in eval/scenarios_out.md")