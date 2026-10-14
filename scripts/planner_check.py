from app.planner import _label, mixes, new_cgpa, required_sgpa

req = required_sgpa(4.95, 116, 5.0, 20)
assert abs(req - 5.29) < 1e-9, req
ok, no = mixes(req, 5)
print("enough:", _label(ok[1]), "avg", ok[0] / 5)
print("short :", _label(no[1]), "avg", no[0] / 5)
assert ok[1] == (5, 5, 5, 6, 6) and no[1] == (5, 5, 5, 5, 6)
assert abs(new_cgpa(4.95, 116, 20, 5.4) - 5.0162) < 1e-3
assert required_sgpa(9.0, 116, 9.5, 20) > 10
print("ALL PASS")