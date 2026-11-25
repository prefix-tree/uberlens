# UberSeek is installed: use it to measure and look inside video

`uberseek` is a command for working with video files: it measures the picture and the sound exactly, and shows
you any part of a video as one labelled picture. Reach for it before writing FFmpeg and Python by hand to find,
measure or look. Use FFmpeg freely for what it does not do (filters, restoration, a required output format).

Run it in the folder that holds the videos. Times are seconds, or `M:SS.mmm`.

| The job | Run |
| --- | --- |
| See what is in a clip | `uberseek observe clip.mp4 0 12` prints `Picture: <path>`. Open that file. Its title names the clip; every frame has its number and time |
| Compare many clips, order them, match them to descriptions | `uberseek overview '["1.mp4", "2.mp4", "3.mp4"]'`: one picture, a few frames of each clip, named. `uberseek videos` lists the clips |
| Check whether one clip follows another | `uberseek seam 3.mp4 5.mp4`: the end of the first beside the start of the second |
| Take an edit apart: what appears when, and where | `uberseek events clip.mp4`: every abrupt change with its `time`, its `frame`, and `where` in the frame as [left, top, right, bottom] fractions (a strip in the third of six columns is `[0.333, 0, 0.5, 1]`). `kind` is `part`, `whole` (a cut) or `flash`. Then `uberseek observe clip.mp4 0 4 --focus change` to see the frames on both sides of each |
| Remove a frozen or duplicated stretch | `uberseek freezes clip.mp4` gives each stretch's `start` and `end`. Mark the parts between them, then `clip` and `verify` (row below): that keeps every other frame exactly. Cutting by hand with `select` and `setpts` has failed the check |
| Look at part of the frame, larger | add `--region '[0, 0.5, 1, 1]'` (left, top, right, bottom as fractions) to `observe`, or `region=...` to `sheet` |
| A dense run of frames on one picture | `uberseek sheet clip.mp4 '[0.5, 0.6, 0.7, 0.8]'`, up to 48 times |
| How something moves, or the camera moves | `uberseek observe clip.mp4 2 6 --focus motion` |
| Find where something is said | `uberseek transcript talk.mp4` once, then `uberseek find talk.mp4 "aircraft carriers"` |
| Exact times of words, and a phrase said twice | `uberseek words talk.mp4 50 60`, `uberseek repeats talk.mp4 0 90` |
| Where a cut can go | `uberseek pauses talk.mp4 50 60` (silences), `uberseek gaps talk.mp4 50 60` (between words, works under music), `uberseek onsets talk.mp4` (beats) |
| Where the shots change | `uberseek cuts reel.mp4` and `uberseek shots reel.mp4` |
| Check one cut point or a join | `uberseek observe out.mp4 12.4 --focus boundary`: the frames on both sides and two seconds of sound |
| Keep or remove spans, frame-exact | `uberseek mark talk.mp4 0 54.9`, `uberseek mark talk.mp4 67.3 90` (the parts to keep), `uberseek clip out sel_000001 sel_000002`, `uberseek verify out`. `clip` prints `File: <path>`; `out.mp4` then opens by name. The file keeps the source's size |
| Several steps in one go | `uberseek run program.py`: Python with every operation as a function. See `uberseek guide` |
| Keep track in a long task | `uberseek brief "<the task, word for word>"`, `uberseek note obs_000003 "what it showed"`, `uberseek status` |

Every operation is a command with its arguments in order: `uberseek <operation> <arguments>`. A named argument
is `name=value` or `--name value`. `uberseek -h` lists them.

What keeps you right:

- **Open the picture.** The printed text says what was shown; only the picture shows it.
- **A number on a picture is that picture's number**, not a frame of the video. Read times from the labels.
- **You do not hear the sound.** It is drawn as a strip with silences shaded.
- **Word times are estimates**, good to a few tenths of a second. Where an edge must be exact, put it in a
  pause or a gap, then look with `--focus boundary`.
- **Nobody answers questions during the task.** Decide, say what you were unsure of, and deliver.

More: `uberseek guide` (the whole skill), `uberseek guide recipes` (worked programs), `uberseek guide limits`.
