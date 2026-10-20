from app.pipeline import resolve


def run(name, turns):
    print(f"\n== {name}")
    msgs, bad = [], 0
    for q, exp in turns:
        r = resolve(q, msgs[-12:], "")
        if "reply" in r:
            ok = exp.get("reply", "") in r["reply"] and "reply" in exp
            shown = r["reply"][:45]
        else:
            sq = r["search_q"].lower()
            ok = "reply" not in exp
            if "branch" in exp:
                ok &= r["branch"] == exp["branch"]
            if "followup" in exp:
                ok &= r["use_hist"] == exp["followup"]
            ok &= all(s in sq for s in exp.get("has", []))
            ok &= all(s not in sq for s in exp.get("not", []))
            shown = f"branch={r['branch']!r} followup={r['use_hist']} search={r['search_q']!r}"
        bad += not ok
        print(("PASS" if ok else "FAIL"), "|", q, "->", shown)
        msgs += [{"role": "user", "text": q}, {"role": "assistant", "text": "ok"}]
    return bad


fails = run("program not set, switching branches", [
    ("what are the first semester courses", {"reply": "Which program"}),
    ("CSB", {"branch": "csb", "followup": True, "has": ["first semester courses", "csb"]}),
    ("for cse", {"branch": "cse", "has": ["first semester courses", "cse"], "not": ["csb"]}),
    ("what about ece", {"branch": "ece", "has": ["first semester courses", "ece"], "not": ["csb", "cse"]}),
    ("what about cse", {"branch": "cse", "has": ["first semester courses", "cse"], "not": ["ece", "csb"]}),
    ("table ?", {"followup": True, "has": ["first semester courses"]}),
    ("make a table", {"followup": True, "has": ["first semester courses"]}),
])
fails += run("topic change and follow-up", [
    ("what is the attendance rule", {"followup": False, "branch": ""}),
    ("what happens if i fall below it", {"followup": True, "has": ["attendance rule"]}),
    ("CSE 1st semester courses", {"followup": False, "branch": "cse", "not": ["attendance"]}),
    ("who won the world cup", {"followup": False, "not": ["cse"]}),
])
fails += run("personal statements", [
    ("i have cgpa of 4.95 in 7th sem", {"reply": "What would you like to know"}),
    ("i have completed 116 credits till 6th sem", {"reply": "What would you like to know"}),
    ("will i get honors?", {"followup": False}),
])
fails += run("long self-contained questions", [
    ("If I have completed 160 total credits by the end of 8th sem, but 8 of those credits were 'F' or 'E' grades in core courses, can the 8-credit worst grade exclusion rule automatically drop them so I can graduate, or must I repeat those exact courses?",
     {"followup": False}),
    ("If I took a semester leave in my 4th semester due to medical reasons and cleared 2 SG credits during summer term, does that semester leave count towards the 8-semester minimum duration requirement for B.Tech completion?",
     {"followup": False, "not": ["160 total credits"]}),
    ("I did a branch transfer from CSE to CSB after my 2nd semester. Do the extra discipline credits I completed in 1st year count towards the 12 additional discipline credits required for Graduating with Honors in CSB, or do they only count as open electives?",
     {"followup": False, "branch": "csb", "not": ["semester leave"]}),
])

h = [{"role": "user", "text": "i have 116 credits by the end of 6th sem and a cgpa of 4.95, in 7th sem i have 5 courses of 4 credits each, how much grade should i get in each minimum to get to 5 cgpa in 7th sem"},
     {"role": "assistant", "text": "What are the individual course credits and current grade points earned so far?"}]
r = resolve("each course credit is 4", h, "")
ok = r.get("use_hist") is True and "cgpa" in r["search_q"].lower() and "grade points" in r["extra"]
print("PASS" if ok else "FAIL", "| a reply to the bot's own question is joined to that question")
fails += not ok

from app.pipeline import _drop_empty_tables

sample = "Answer\n\n```text\n|   |   |\n| --- | --- |\n|   |   |\n\n| A | B |\n| --- | --- |\n| 1 | 2 |"
res = _drop_empty_tables(sample)
ok = "| A | B |" in res and "| --- | --- |" in res and "```" not in res and "|   |" not in res
print("PASS" if ok else "FAIL", "| empty tables and code fences are removed, real tables are kept")
fails += not ok

from app.pipeline import _fix_br, _scrub

s = _fix_br(_scrub("| a<br>b | c |\n<br>Intro line\nAccording to the UG Regulations (Oct 2025)..."))
ok = "| a<br>b | c |" in s and "<br>" not in s.replace("a<br>b", "") and "..." not in s
print("PASS" if ok else "FAIL", "| stray <br> and ellipsis lines are cleaned, table cells keep <br>")
fails += not ok

from app.pipeline import _finish

r = resolve("What is the minimum CGPA required for graduating with Honors?", [], "")
ok = r["extra"] == "" and not r["planning"]
print("PASS" if ok else "FAIL", "| a plain 'minimum CGPA' question does not trigger CGPA-planning retrieval")
fails += not ok

plan_q = ("i have 116 credits by the end of 6th sem and a cgpa of 4.95, in 7th sem i have 5 courses of 4 credits each, "
          "how much grade should i get in each minimum to get to 5 cgpa in 7th sem")
r = resolve(plan_q, [], "")
ok = r["planning"] and "grading scheme" in r["extra"]
print("PASS" if ok else "FAIL", "| a personal CGPA target question is planning")
fails += not ok

r = resolve("each course credit is 4",
            [{"role": "user", "text": plan_q}, {"role": "assistant", "text": "What are the individual course credits?"}], "")
ok = r["use_hist"] and r["planning"]
print("PASS" if ok else "FAIL", "| the reply to the bot's question keeps the planning context")
fails += not ok

text, cited = _finish("A fact [2].\n[1]")
ok = text == "A fact [2]." and cited == {1, 2}
print("PASS" if ok else "FAIL", "| a lone trailing citation line is removed but still counted")
fails += not ok

r = resolve("i have 116 credits and cgpa 4.95, 5 courses of 4 credits next sem, one course will be a D, what do i need in the rest to reach 5 cgpa", [], "")
ok = r["planning"]
print("PASS" if ok else "FAIL", "| a question with a known grade is planning")
fails += not ok

r = resolve("i have 116 credits and cgpa 4.95, 5 courses of 4 credits next sem, what sgpa do i need to reach 5.2 and 5.3 cgpa", [], "")
ok = r["planning"]
print("PASS" if ok else "FAIL", "| a question with two targets is planning")
fails += not ok

text, cited = _finish("A fact [2].\n\n[1], [4]")
ok = text == "A fact [2]." and cited == {1, 2, 4}
print("PASS" if ok else "FAIL", "| a trailing line like '[1], [4]' is removed but still counted")
fails += not ok

import sys

print("\nALL PASS" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)