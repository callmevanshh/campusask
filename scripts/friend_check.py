import time
from pathlib import Path

from app.pipeline import REFUSAL, answer

QUESTIONS = [
    "How can I get my bonafide certificate?",
    "How can I get a provisional transcript?",
    "What is the rule to drop a course in between the semester?",
    "For what scholarships can a student apply?",
    "What if I have already finished 164 credits in 7th semester?",
    "Where do I complain about the IIITD cab driver?",
    "What are the hostel rules?",
    "What is the fee refund policy?",
    "What is the penalty for plagiarism or cheating in an exam?",
    "What are the requirements for a minor?",
    "Can I do an internship in my 8th semester?",
    "How many credits is the BTP?",
    "Can I get TA credits?",
    "What is the academic calendar for this semester?",
    "Who do I contact for a grievance or harassment complaint?",
]
out, n_ok = ["# Coverage check (answered with a citation is not the same as correct: read the answers)\n"], 0
for q in QUESTIONS:
    r = answer(q, [], "")
    a = r["answer"]
    if a.strip().startswith(REFUSAL):
        status = "REFUSED"
    elif a.startswith("The AI summary is unavailable"):
        status = "UNAVAILABLE"
    else:
        status, n_ok = "ANSWERED", n_ok + 1
    pages = ", ".join(f"{s['source']} p{s['page']}" for s in r["sources"]) or "-"
    print(f"{status:11} | {q}  [{pages}]")
    out.append(f"## {q}\n**{status}** | sources: {pages}\n\n{a[:700]}\n")
    time.sleep(5)
print(f"\nanswered {n_ok} of {len(QUESTIONS)}")
Path("eval/coverage.md").write_text("\n".join(out), encoding="utf-8")