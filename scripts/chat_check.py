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

print("\nALL PASS" if not fails else f"\n{fails} FAILED")