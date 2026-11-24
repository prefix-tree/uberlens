"""Arithmetic on spans of time. A span is [start, end] in seconds."""

from __future__ import annotations

Span = list[float]


def expand(span: Span, before: float = 0, after: float = 0) -> Span:
    """Widen a span by `before` seconds at its start and `after` at its end. Never starts before zero."""
    return [round(max(0.0, span[0] - before), 3), round(span[1] + after, 3)]


def merge(spans: list[Span], gap: float = 0) -> list[Span]:
    """Join spans that overlap or lie within `gap` seconds of each other. Returns them in time order."""
    out: list[Span] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def minus(span: Span, spans: list[Span]) -> list[Span]:
    """The parts of `span` that none of `spans` covers."""
    out, at = [], span[0]
    for start, end in merge(spans):
        if start > at:
            out.append([at, min(start, span[1])])
        at = max(at, end)
        if at >= span[1]:
            break
    if at < span[1]:
        out.append([at, span[1]])
    return [s for s in out if s[1] > s[0]]
