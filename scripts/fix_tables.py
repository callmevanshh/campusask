import re
from pathlib import Path

ROW = re.compile(r"^\s*\|.*\|\s*$")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def fmt(cs):
    return "| " + " | ".join(cs) + " |"


def is_sep(line):
    return "-" in line and bool(re.fullmatch(r"\|?[\s:\-|]+\|?", line.strip()))


def split_blocks(text):
    blocks, cur, kind = [], [], None
    for ln in text.split("\n"):
        k = "table" if ROW.match(ln) else "text"
        if k != kind and cur:
            blocks.append((kind, cur))
            cur = []
        kind = k
        cur.append(ln)
    if cur:
        blocks.append((kind, cur))
    return blocks


def try_merge(a, b):
    ra = [l for l in a if not is_sep(l)]
    rb = [l for l in b if not is_sep(l)]
    if len(ra) < 2 or len(rb) < 2:
        return None
    ha, hb = cells(ra[0]), cells(rb[0])
    if [c.lower() for c in ha] != [c.lower() for c in hb]:
        return None
    body_a, body_b = [cells(l) for l in ra[1:]], [cells(l) for l in rb[1:]]
    if body_b[0][0] != "" or not (len(body_a[-1]) == len(body_b[0]) == len(ha)):
        return None
    last = [(x + " " + y).strip() for x, y in zip(body_a[-1], body_b[0])]
    rows = body_a[:-1] + [last] + body_b[1:]
    return [fmt(ha), "|" + "|".join(["---"] * len(ha)) + "|"] + [fmt(r) for r in rows]


def merge(text):
    blocks, out, merged, i = split_blocks(text), [], 0, 0
    while i < len(blocks):
        kind, lines = blocks[i]
        if kind != "table":
            out.append(lines)
            i += 1
            continue
        j = i + 1
        while j + 1 < len(blocks):
            gap, nxt = blocks[j], blocks[j + 1]
            if gap[0] == "text" and all(not l.strip() for l in gap[1]) and nxt[0] == "table":
                m = try_merge(lines, nxt[1])
                if m is None:
                    break
                lines, merged, j = m, merged + 1, j + 2
            else:
                break
        out.append(lines)
        i = j
    return "\n".join(l for ls in out for l in ls), merged


for f in sorted(Path("data/tables").glob("*.md")):
    t = f.read_text(encoding="utf-8")
    if t.lstrip().startswith("<!--"):
        continue
    new, n = merge(t)
    if n:
        f.write_text(new, encoding="utf-8")
        print(f"{f.name}: merged {n} split table(s)")