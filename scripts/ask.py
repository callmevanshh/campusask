import sys

from app.llm import generate
from app.retrieval import search

SEM_MIN = 0.35  # starting guess; we tune this in Day 5

question = " ".join(sys.argv[1:])
chunks = search(question, k=4)

if max(c["sem"] for c in chunks) < SEM_MIN:
    print("I could not find this in the documents.")
    sys.exit()

print(generate(question, chunks))
print("\nSources:")
for i, c in enumerate(chunks, 1):
    print(f"[{i}] {c['source']} p.{c['page']}")