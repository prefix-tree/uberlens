# What UberSeek cannot do

Know these before you promise a result or trust one.

## It cannot hear

You are never given sound. It reaches you two ways: as measurements (words with timings, pauses,
loudness) and as a drawn strip. So you cannot judge tone of voice, whether a word is slurred, whether music
drowns speech, whether a breath or a click is audible at a cut, or what a sound is. When a decision rests
on any of these, say it is **not heard** and should be checked by ear.

## It searches words, not meaning and not pictures

- `find` ranks passages of the transcript by the words they share with your query. "Where does she admit
  the company almost failed" finds nothing unless words like those are said. Rephrase with likely spoken
  words; try several.
- There is no search by what is shown. To find a picture (a red car, a handshake) you look: a map of the
  whole video, then closer where it could be. `shots` tells you where to look, one shot at a time.
- `find(like=...)` exists in the signature and is not built. It says so.
- A video with no speech gives `find` nothing to search.

## Its measurements can be wrong

- **Cuts.** Hard cuts are found. Flashes to white, fades and dissolves are often missed, so two shots can
  be reported as one. Fast action or a camera flash can be reported as a cut. A change in part of the frame
  is not a cut: `events` finds those.
- **Events and freezes.** They compare each frame with the one before, at a small size. A slow wipe or a
  fade is many small changes and may give no event. A still picture is reported as a freeze, whether or not
  it is a fault.
- **Transcript.** It is produced by a speech model. Names and rare words are often wrong; a word's time
  can be off by a tenth of a second or more; overlapping speakers are merged; it does not say who speaks.
- **Pauses.** A pause is a stretch quieter than a fixed level for a quarter of a second. Under music or
  room noise there may be no "pause" even where nobody speaks. `gaps` gives the gaps between words from the
  transcript instead: it works under music, and is an estimate.
- **Repeats.** `repeats` reads the transcript, and a speech model often leaves a stutter or a false start
  out. Finding nothing does not mean nothing was repeated.

## A look is a sample

A wide span shows a few frames of many. The text says how far apart they are. Something shorter than that
gap can be missed entirely. Focus `change` picks the frames where the picture changes most, so a fast
event is not stepped over. `overview` and `seam` show several videos on one picture; they show a few
instants of each, not the whole of any.

## It cuts, and does no more than cut

- `clip` joins chosen spans with hard cuts, frame-exact. There are no transitions, captions, speed changes,
  layers, crops in the output, or music. Those belong to an editor.
- It records what you looked at and why (`purpose`), and what you concluded when you write it with `note`.
  A conclusion you did not note is gone when the picture leaves your context.

## The first time is slow

The first `find` or `words` on a video transcribes all of it (about a quarter of its length, on a CPU).
The first `cuts` or `shots` scans the whole picture (a few seconds per ten minutes), and so does the first
`change`, `events`, `freezes` or look with focus `change`. Each happens once per file and is kept.
