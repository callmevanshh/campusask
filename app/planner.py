import itertools
import json
import re
from collections import Counter

from app.llm import extract_json

# grade points as listed in the UG Regulations grading table (section 6.3); F is not used for planning
POINTS = {10: "A or A+", 9: "A-", 8: "B", 7: "B-", 6: "C", 5: "C-", 4: "D"}

PROMPT = (
    "From the conversation below, extract the numbers for a CGPA target problem. Return ONLY a JSON object with "
    'exactly these keys, using null when the student did not say: {"current_cgpa": number, "credits_done": number, '
    '"target_cgpa": number, "next_credits": number (total credits of the coming semester), '
    '"courses": number (how many courses in the coming semester), "credits_per_course": number}. '
    "Do not compute anything and do not guess.\n\nCONVERSATION:\n"
)


def required_sgpa(cgpa, done, target, nxt):
    return (target * (done + nxt) - cgpa * done) / nxt


def new_cgpa(cgpa, done, nxt, avg):
    return (cgpa * done + avg * nxt) / (done + nxt)


def mixes(req, n):
    """Smallest mix of whole courses whose average reaches req, and the best mix that falls short."""
    best_ok = best_no = None
    for combo in itertools.combinations_with_replacement(sorted(POINTS), n):  # combos are ascending
        s, spread = sum(combo), combo[-1] - combo[0]
        if s / n >= req - 1e-9:
            if best_ok is None or (s, spread) < best_ok[0]:
                best_ok = ((s, spread), combo)
        elif best_no is None or (-s, spread) < best_no[0]:
            best_no = ((-s, spread), combo)
    ok = (sum(best_ok[1]), best_ok[1]) if best_ok else None
    no = (sum(best_no[1]), best_no[1]) if best_no else None
    return ok, no


def _label(combo):
    parts = []
    for p, k in sorted(Counter(combo).items(), reverse=True):
        parts.append(f"{k} course{'s' if k > 1 else ''} at {POINTS[p]} ({p} points)")
    return " and ".join(parts)


def _num(x, lo, hi):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def verified(question, history):
    """A block of correct numbers for the model to copy, or '' when the numbers cannot be extracted."""
    convo = "\n".join(t["text"] for t in (history or []) if t["role"] == "user") + "\n" + question
    try:
        raw = extract_json(PROMPT + convo[-1500:])
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception as e:
        print("[planner] extraction failed:", repr(e))
        return ""
    cgpa = _num(data.get("current_cgpa"), 0, 10)
    done = _num(data.get("credits_done"), 1, 300)
    target = _num(data.get("target_cgpa"), 0, 10)
    courses = _num(data.get("courses"), 1, 12)
    per = _num(data.get("credits_per_course"), 1, 12)
    nxt = _num(data.get("next_credits"), 1, 60) or (courses * per if courses and per else None)
    if None in (cgpa, done, target, nxt):
        return ""
    total, have = target * (done + nxt), cgpa * done
    req = required_sgpa(cgpa, done, target, nxt)
    lines = [
        f"Current CGPA {cgpa:g} on {done:g} credits; target CGPA {target:g}; credits in the coming semester {nxt:g}.",
        f"Points needed at the end = {target:g} x ({done:g} + {nxt:g}) = {total:.2f}.",
        f"Points already earned = {cgpa:g} x {done:g} = {have:.2f}.",
        f"Points needed in the coming semester = {total:.2f} - {have:.2f} = {total - have:.2f}.",
        f"Required SGPA = {total - have:.2f} / {nxt:g} = {req:.2f}.",
    ]
    if req > 10:
        lines.append("This target is NOT reachable in one semester: the required SGPA is above 10.")
    else:
        n = int(courses) if courses else (int(round(nxt / per)) if per and abs(nxt / per - round(nxt / per)) < 1e-9 else None)
        if courses and per and courses * per != nxt:
            n = None
        if n and 1 <= n <= 8:
            ok, no = mixes(req, n)
            if ok:
                lines.append(f"Smallest sufficient mix of {n} whole courses: {_label(ok[1])}; average {ok[0] / n:.2f}, "
                             f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, ok[0] / n):.3f}.")
            if no:
                lines.append(f"One step lower is NOT enough: {_label(no[1])}; average {no[0] / n:.2f}, "
                             f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, no[0] / n):.3f}.")
    lines.append("Grade points used: " + ", ".join(f"{v} {k}" for k, v in sorted(POINTS.items(), reverse=True)) + ".")
    lines.append("CGPA is treated as the credit-weighted average over all credits done; dropping worst grades or SG/CW credits can change the real figure.")
    return "VERIFIED CALCULATION (done by code and correct; copy these numbers exactly, never recompute or round differently):\n" + "\n".join(lines) + "\n\n"