import sys

from app.pipeline import answer

result = answer(" ".join(sys.argv[1:]))
print(result["answer"])
for s in result["sources"]:
    print(f"[{s['n']}] {s['source']} p.{s['page']}")