from app.planner import _label, _plan, mixes, new_cgpa, required_sgpa

req = required_sgpa(4.95, 116, 5.0, 20)
assert abs(req - 5.29) < 1e-9, req
ok, no = mixes(req, 5)
print("enough:", _label(ok[1]), "avg", ok[0] / 5)
print("short :", _label(no[1]), "avg", no[0] / 5)
assert ok[1] == (5, 5, 5, 6, 6) and no[1] == (5, 5, 5, 5, 6)
assert abs(new_cgpa(4.95, 116, 20, 5.4) - 5.0162) < 1e-3
assert required_sgpa(9.0, 116, 9.5, 20) > 10

# several targets are each computed on their own
assert abs(required_sgpa(4.95, 116, 5.2, 20) - 6.65) < 1e-9
assert abs(required_sgpa(4.95, 116, 5.3, 20) - 7.33) < 1e-9

# one course already has a D: the other four must average about 5.61
text = " ".join(_plan(4.95, 116, 5.0, 20, 5, [4]))
assert "at least" in text and "5.61" in text, text
ok2, no2 = mixes((5.29 * 5 - 4) / 4, 4)
assert ok2[1] == (5, 6, 6, 6) and no2[1] == (5, 5, 6, 6), (ok2, no2)
assert "3 courses at C (6 points)" in text and "1 course at C- (5 points)" in text, text

# unreachable targets, alone or with a known grade
assert "NOT reachable" in " ".join(_plan(9.0, 116, 9.5, 20, 5, []))
assert "NOT reachable" in " ".join(_plan(5.0, 116, 5.7, 20, 5, [4]))
print("ALL PASS")