import sys

import numpy as np

from app.retrieval import _bm25, _query_tokens, _rows, _scope_weights

q, src, page = sys.argv[1], sys.argv[2], int(sys.argv[3])
w = _scope_weights(q, None)
kw = _bm25.get_scores(_query_tokens(q, None))
final = kw * w
order = [int(i) for i in np.argsort(-final)]
print("query tokens:", _query_tokens(q, None))
print("\nTOP 8:")
for pos, i in enumerate(order[:8], 1):
    r = _rows[i]
    print(f"  #{pos} {r['source'].split('-')[0]}:p{r['page']} score={final[i]:.1f} section={r.get('section', '')!r}")
print(f"\nCHUNKS ON {src} page {page}:")
for i, r in enumerate(_rows):
    if r["source"] == src and r["page"] == page:
        print(f"  rank #{order.index(i) + 1} score={final[i]:.1f} section={r.get('section', '')!r}")
        print(f"     text: {r['text'][:140]!r}")