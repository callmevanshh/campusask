import sys

import app.pipeline as p

QA = "What is the penalty for plagiarism or cheating in an exam?"
QB = "What is the dress code in the college?"
ok_all, calls = True, []


def check(name, ok):
    global ok_all
    ok_all &= bool(ok)
    print("PASS" if ok else "FAIL", "|", name)


def refuse_then_answer(question, chunks, history=None, branch="", verified="", exclude=(), budget=None):
    calls.append(tuple(exclude))
    return (p.REFUSAL, "model-a") if not exclude else ("The penalty is set out in the policy [1].", "model-b")


p.model_count = lambda: 2
p.generate_ex = refuse_then_answer
p._cache.clear()
r = p.answer(QA, [], "")
check("a refusal gets a second opinion from the other model",
      r["answer"].startswith("The penalty") and r["sources"] and calls == [(), ("model-a",)])
check("an answered question is cached", len(p._cache) == 1)
calls.clear()
p.answer(QA, [], "")
check("the cached answer needs no model call", calls == [])

p._cache.clear()
p.generate_ex = lambda *a, **k: (p.REFUSAL, "model-x")
r = p.answer(QB, [], "")
check("two refusals stay a refusal and are not cached", r["answer"] == p.REFUSAL and not p._cache)

p.SECOND_OPINION = False
calls.clear()
p.generate_ex = refuse_then_answer
r = p.answer(QB, [], "")
check("the switch turns the second opinion off", r["answer"] == p.REFUSAL and calls == [()])
print("ALL PASS" if ok_all else "SOME FAILED")
sys.exit(0 if ok_all else 1)