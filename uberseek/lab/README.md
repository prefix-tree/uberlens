# The lab

Pieces from building real clips, copied here to play with before any of them becomes an operation. Nothing in this
package is part of UberSeek's API, and anything here may change or go.

They come from one job: an interview clip in a kinetic-type style, built with
[UberScene](https://github.com/prefix-tree/uberscene), where the finding and preparing was done by hand around the
editor. That hand work is what is here.

## What is here

| | What it does | Tested |
|---|---|---|
| `fetch.py` | A few seconds out of a very large remote video, by byte range, from the file's index | by test, on a file made for it; and on a 12.8 GB file |
| `beats.py` | The beats and tempo of music | by test, on click tracks from 72 to 180 BPM and a kick-and-hat pattern; not on recorded music |
| `loudness.py` | Integrated loudness and true peak of a file | by test |
| `matte.py` | A person cut out of their background, as a matte or over green | by hand, on the interview |
| `matte_compare.py` | Several matting models on the same frames: a sheet and numbers | by hand, on the interview |
| `sounds.py` | A music bed, synthesized, and key clicks for text that types in | the typing by test; the music by hand |
| `interview/` | The film: its UberScene file, its manifest and transcript, and a script that prepares its media | by hand, from nothing, then rendered |
| `notes/` | What was learned: the cut-out decision with seven models measured, UberScene's backlog, and the craft pages of UberScene's agent skill | |

Each module's docstring says how to run it. They need `numpy` (`uv sync --extra lab`); the matting ones need more,
which their docstrings name.

## The interview film

```sh
uv sync --extra lab
bash uberseek/lab/interview/prepare.sh     # about ten minutes on four CPU cores, most of it the cut-out
```

Then render `interview/video.tsx` with UberScene (`npx uberscene uberseek/lab/interview/video.tsx --out interview.mp4`,
from a project with `uberscene` installed). The film is 38 seconds: a cold open on the speaker's strongest line, then
the answer with every title anchored to a word he says.

## How these map onto UberSeek

Where each would land if it earns its place. None is decided.

| Piece | Would become |
|---|---|
| `fetch.py` | A way to open a source by span: `Project` takes a URL and the seconds wanted |
| `beats.py` | A `beats()` signal beside `pauses` and `cuts`. The roadmap already asks for sound onsets or beats |
| `loudness.py` | Part of `verify`: the file is what was asked for, and loud enough |
| `matte.py` | An operation that makes a matte, and from it where the person is over time, for a reframe |
| `matte_compare.py` | A measurement in `bench/` |
| `interview/` | The first test of an export to UberScene: a selection becoming a `video.tsx` and a manifest with its words |
| `notes/craft/` | Recipes in the skill, each once a real run has shown it helps choose a moment |

Not here, because they are not built yet: the export to an UberScene file, and UberScene's checks (`lint`,
`--check-layout`, `--check-motion`) as a review step.

## Sources and licences

- **This package's code** is UberSeek's, MPL-2.0. `beats.py` is a port of UberScene's detector, and the notes and the
  film are copied from UberScene (MIT), each marked with the commit it came from.
- **Footage** the script fetches: Dr. Joe Westlake and the Voyager b-roll, NASA's Scientific Visualization Studio
  ([svs.gsfc.nasa.gov/15111](https://svs.gsfc.nasa.gov/15111/)), public domain. NASA does not endorse this project.
- **Key sounds**: Kenney's Interface Sounds, CC0, fetched from the [soundcn](https://github.com/kapishdima/soundcn)
  repository.
- **RobustVideoMatting** (Lin et al.), GPL-3.0: the script downloads it and its weights. Neither is in this
  repository, and nothing it makes is either.
