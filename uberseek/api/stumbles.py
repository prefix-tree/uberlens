"""`stumbles` over the transcript: words said twice, lines restarted, fillers, and sound the transcript has no word for.

Everything here is a candidate to look at, never a decision. The transcript is an estimate, and Whisper
tidies speech: it often leaves out "um" and "uh" and sometimes writes a repeated word once. So the sound is
checked too: a stretch between two words that is not a pause holds something the transcript did not write.
"""

from __future__ import annotations

import re
from fractions import Fraction

from uberseek.api.search import STOP

FILLERS = frozenset(["um", "umm", "uh", "uhh", "uhm", "erm", "er", "err", "ah", "ahh", "eh", "hmm", "hm", "mm", "mmm", "mhm"])
# Words that join a phrase. A phrase made only of these said twice, a few words apart, is ordinary speech
# ("one of the best of the year"), not a restart.
GLUE = frozenset(["a", "an", "the", "of", "to", "in", "on", "at", "and", "or", "for", "with", "is", "it", "as", "by", "from", "that"])
# Short common words that start longer ones ("his history", "we went") are words, not fragments.
COMMON = GLUE | STOP
LONGEST = 4  # words in a repeated phrase
REACH = 3  # words that may come between a phrase and its restart
RESTART_SECONDS = Fraction(5, 2)  # a restart begins again within this long of the first try
SOUND = {"min_seconds": "0.2", "max_gap_seconds": "3"}  # sound between words worth reporting, and gaps too long to judge

Word = tuple[Fraction, Fraction, str]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9']", "", text.lower())


def _cut_off(text: str) -> bool:
    """A word broken off as it was said: Whisper writes it with a dash at the end ("wh-", "compa—")."""
    return bool(re.search(r"\w(-|—|–)$", text.strip()))


def _item(kind: str, start: Fraction, end: Fraction, text: str, cut: tuple[Fraction, Fraction]) -> dict:
    return {"kind": kind, "start": start, "end": end, "text": text, "cut": cut}


def from_words(words: list[Word]) -> list[dict]:
    """Repeats, restarts, cut-off words and fillers, found in the transcript alone.

    - repeat: the same word or phrase said twice in a row ("the the", "we had we had").
    - restart: a phrase begun, dropped and begun again a few words later ("we had no, we had nothing").
    - cut-off: a word broken off ("compa- company"), or a fragment the next word starts with.
    - filler: um, uh, erm and the like.

    "cut" is the span to remove to keep the second try: from the first try's start to the second's.
    """
    out: list[dict] = []
    tokens = [_norm(w[2]) for w in words]
    spoken = [i for i, t in enumerate(tokens) if t and t not in FILLERS]  # fillers do not break a repeat
    taken: set[int] = set()  # word positions already inside a reported repeat or restart

    def block(at: int, n: int) -> list[str]:
        return [tokens[spoken[at + m]] for m in range(n)]

    for k, i in enumerate(spoken):
        if i in taken:
            continue
        found = None
        for n in range(min(LONGEST, (len(spoken) - k) // 2), 0, -1):
            first = block(k, n)
            for gap in range(0, REACH + 1 if n > 1 else 1):
                j = k + n + gap
                if j + n > len(spoken):
                    break
                if block(j, n) != first:
                    continue
                if gap and all(t in GLUE for t in first):
                    continue
                if words[spoken[j]][0] - words[i][0] > RESTART_SECONDS:
                    continue
                found = (n, j, gap)
                break
            if found:
                break
        if not found:
            continue
        n, j, gap = found
        first = block(k, n)
        while not gap and j + 2 * n <= len(spoken) and block(j + n, n) == first:
            j += n  # "I I I": one stumble, keeping the last try
        a, b = words[i][0], words[spoken[j]][0]
        said = " ".join(w[2] for w in words[i : spoken[j + n - 1] + 1])
        out.append(_item("restart" if gap else "repeat", a, words[spoken[j + n - 1]][1], said, (a, b)))
        taken.update(range(i, spoken[j]))

    for k, i in enumerate(spoken[:-1]):
        if i in taken:
            continue
        here, following = tokens[i], tokens[spoken[k + 1]]
        fragment = len(here) >= 3 and here not in COMMON and following.startswith(here) and following != here
        if _cut_off(words[i][2]) or fragment:
            nxt = words[spoken[k + 1]]
            out.append(_item("cut-off", words[i][0], nxt[1], f"{words[i][2]} {nxt[2]}", (words[i][0], nxt[0])))
            taken.add(i)

    for i, t in enumerate(tokens):
        if t in FILLERS and i not in taken:
            out.append(_item("filler", words[i][0], words[i][1], words[i][2], (words[i][0], words[i][1])))

    return sorted(out, key=lambda item: item["start"])


def unworded(words: list[Word], pauses: list[tuple[Fraction, Fraction]], rule: dict = SOUND) -> list[dict]:
    """Sound between two words that the transcript has no word for, and that is not a pause.

    Often an "um" Whisper left out; sometimes a breath, a laugh or a word it missed. Gaps longer than
    `max_gap_seconds` are left alone: something else is going on there, and it needs a look, not a guess.
    """
    out, shortest, longest = [], Fraction(rule["min_seconds"]), Fraction(rule["max_gap_seconds"])
    for before, after in zip(words, words[1:], strict=False):
        a, b = before[1], after[0]
        if b - a < shortest or b - a > longest:
            continue
        at = a
        for p, q in pauses:
            if q <= at or p >= b:
                continue
            if p - at >= shortest:
                out.append(_item("sound", at, p, "", (at, p)))
            at = max(at, q)
        if b - at >= shortest:
            out.append(_item("sound", at, b, "", (at, b)))
    return out
