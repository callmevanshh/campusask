import itertools
import json
import re
from collections import Counter

from app.llm import extract_json

# grade points as listed in the UG Regulations grading table (section 6.3); F is not used for planning
POINTS = {10: "A or A+", 9: "A-", 8: "B", 7: "B-", 6: "C", 5: "C-", 4: "D"}
LETTER = {"A+": 10, "A": 10, "A-": 9, "B": 8, "B-": 7, "C": 6, "C-": 5, "D": 4}

PROMPT = (
    "From the conversation below, extract the numbers for a CGPA target problem. Return ONLY a JSON object with "
    'exactly these keys, using null when the student did not say: {"current_cgpa": number, "credits_done": number, '
    '"target_cgpas": [every CGPA target the student mentions, as numbers], '
    '"next_credits": number (total credits of the coming semester), '
    '"courses": number (how many courses in the coming semester), "credits_per_course": number, '
    '"fixed_grades": [letter grades that some of the coming courses already have or will certainly get, '
    'one entry per course, for example ["D"]]}. '
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


def _plan(cgpa, done, target, nxt, n, fixed):
    """Lines for one target. `fixed` holds the grade points of courses whose grade is already known."""
    total, have = target * (done + nxt), cgpa * done
    req = required_sgpa(cgpa, done, target, nxt)
    out = [
        f"Target CGPA {target:g}:",
        f"  Points needed at the end = {target:g} x ({done:g} + {nxt:g}) = {total:.2f}; "
        f"already earned = {cgpa:g} x {done:g} = {have:.2f}; needed in the coming semester = {total - have:.2f}.",
        f"  Required SGPA = {total - have:.2f} / {nxt:g} = {req:.2f}.",
    ]
    if req > 10:
        out.append("  NOT reachable in one semester: the required SGPA is above 10.")
        return out
    if not n or not (1 <= n <= 8):
        return out
    k = len(fixed)
    if k >= n:
        avg = sum(fixed[:n]) / n
        out.append(f"  With all {n} grades known the SGPA would be {avg:.2f} and the CGPA about "
                   f"{new_cgpa(cgpa, done, nxt, avg):.3f}; that {'reaches' if avg >= req - 1e-9 else 'does not reach'} the target.")
        return out
    if k > 0:
        rem = n - k
        r2 = (req * n - sum(fixed)) / rem
        out.append(f"  Known grades: {k} course(s) worth {sum(fixed)} points in total. The other {rem} course(s) must "
                   f"average at least ({req:.2f} x {n} - {sum(fixed)}) / {rem} = {r2:.2f}.")
        if r2 > 10:
            out.append("  NOT reachable: even straight A grades in the other courses would not be enough.")
            return out
        ok, no = mixes(r2, rem)
        if ok:
            avg = (sum(fixed) + ok[0]) / n
            out.append(f"  Smallest sufficient mix for the other {rem} courses: {_label(ok[1])}; SGPA {avg:.2f}, "
                       f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, avg):.3f}.")
        if no:
            avg = (sum(fixed) + no[0]) / n
            out.append(f"  One step lower is NOT enough: {_label(no[1])}; SGPA {avg:.2f}, "
                       f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, avg):.3f}.")
        return out
    ok, no = mixes(req, n)
    if ok:
        out.append(f"  Smallest sufficient mix of {n} whole courses: {_label(ok[1])}; average {ok[0] / n:.2f}, "
                   f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, ok[0] / n):.3f}.")
    if no:
        out.append(f"  One step lower is NOT enough: {_label(no[1])}; average {no[0] / n:.2f}, "
                   f"giving a CGPA of about {new_cgpa(cgpa, done, nxt, no[0] / n):.3f}.")
    return out


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
    courses = _num(data.get("courses"), 1, 12)
    per = _num(data.get("credits_per_course"), 1, 12)
    nxt = _num(data.get("next_credits"), 1, 60) or (courses * per if courses and per else None)
    raw_targets = data.get("target_cgpas") or [data.get("target_cgpa")]
    if not isinstance(raw_targets, list):
        raw_targets = [raw_targets]
    targets = []
    for t in raw_targets:
        v = _num(t, 0, 10)
        if v is not None and v not in targets:
            targets.append(v)
    targets = targets[:4]
    if None in (cgpa, done, nxt) or not targets:
        return ""
    n = int(courses) if courses else (int(round(nxt / per)) if per and abs(nxt / per - round(nxt / per)) < 1e-9 else None)
    if courses and per and courses * per != nxt:
        n = None
    fixed = []
    fg = data.get("fixed_grades") or []
    for g in (fg if isinstance(fg, list) else []):
        p = LETTER.get(str(g).strip().upper().replace(" ", ""))
        if p:
            fixed.append(p)
    lines = [f"Current CGPA {cgpa:g} on {done:g} credits; credits in the coming semester {nxt:g}"
             + (f" ({n} courses)." if n else ".")]
    for t in targets:
        lines += _plan(cgpa, done, t, nxt, n, fixed)
    lines.append("Grade points used: " + ", ".join(f"{v} {k}" for k, v in sorted(POINTS.items(), reverse=True)) + ".")
    lines.append("CGPA is treated as the credit-weighted average over all credits done; dropping worst grades or SG/CW credits can change the real figure.")
    return ("VERIFIED CALCULATION (done by code and correct; copy these numbers exactly, never recompute or round differently):\n"
            + "\n".join(lines) + "\n\n")