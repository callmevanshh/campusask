import json
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
pat = re.compile(args[0], re.I)
src = args[1].lower() if len(args) > 1 else ""
snip, tables = "--snip" in sys.argv, "--tables" in sys.argv
n, places = 0, []
for line in open("data/processed/chunks_kept.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if (src and src not in r["source"].lower()) or (tables and not r.get("table")):
        continue
    m = pat.search(r["text"])
    if not m:
        continue
    n += 1
    if tables:
        print(f"{r['source']} p{r['page']}\n{r['text']}\n")
    elif snip:
        t = " ".join(r["text"][max(0, m.start() - 100): m.start() + 260].split())
        print(f"{r['source']} p{r['page']}: ...{t}...")
    elif len(places) < 8:
        places.append(f"{r['source'].split('-')[0]}:p{r['page']}")
print(f"{args[0]!r}: {n} chunk(s) {'' if (snip or tables) else places}")