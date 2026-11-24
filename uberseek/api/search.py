"""`find` over the transcript: passages ranked by the words they share with the query.

This matches words, not meaning. A paraphrase finds nothing, and no result does not mean the moment is
absent. It returns candidates to look at, never answers.
"""

from __future__ import annotations

import math
import re
from collections import Counter

PAUSE = 0.6  # a gap this long between words ends a passage
LONGEST = 40  # words

_WORDS = (
    "a an and are as at be but by do does did for from had has have he her his how i in is it its of on or she so "
    "that the their them they this to was we were what when where which who why will with you your"
)
_STOP = frozenset(_WORDS.split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in _STOP]


def passages(words: list[list]) -> list[dict]:
    """Cut the transcript where a sentence ends, where the speaker stops, or when a passage gets long."""
    out, current = [], []
    for i, word in enumerate(words):
        current.append(word)
        following = words[i + 1] if i + 1 < len(words) else None
        ended = word[2].rstrip('"').endswith((".", "?", "!"))
        stopped = following is None or float(following[0]) - float(word[1]) >= PAUSE
        if ended or stopped or len(current) >= LONGEST:
            out.append({"start": float(current[0][0]), "end": float(current[-1][1]), "text": " ".join(w[2] for w in current)})
            current = []
    return out


def rank(found: list[dict], query: str, limit: int) -> list[dict]:
    """BM25 over the passages. Only passages that share a word with the query are returned."""
    wanted = _tokens(query)
    docs = [_tokens(p["text"]) for p in found]
    if not wanted or not docs:
        return []
    mean = sum(map(len, docs)) / len(docs) or 1
    seen_in = Counter(term for doc in docs for term in set(doc))
    scored = []
    for passage, doc in zip(found, docs, strict=True):
        counts, score = Counter(doc), 0.0
        for term in set(wanted):
            if counts[term]:
                rarity = math.log(1 + (len(docs) - seen_in[term] + 0.5) / (seen_in[term] + 0.5))
                score += rarity * counts[term] * 2.5 / (counts[term] + 1.5 * (0.25 + 0.75 * len(doc) / mean))
        if score > 0:
            scored.append(passage | {"score": round(score, 3), "how": "words"})
    return sorted(scored, key=lambda p: -p["score"])[:limit]
