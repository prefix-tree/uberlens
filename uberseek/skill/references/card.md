# UberSeek is installed: use it to measure and look inside video

`uberseek` is a command for working with video files: it measures the picture and the sound exactly, and shows
you any part of a video as one labelled picture. Reach for it before writing FFmpeg and Python by hand to find,
measure or look. Use FFmpeg freely for what it does not do (filters, restoration, a required output format).

Run it in the folder that holds the videos. Times are seconds, or `M:SS.mmm`.

| The job | Run |
| --- | --- |
| See what is in a clip | `uberseek observe clip.mp4 0 12` prints `Picture: <path>`. Open that file. Its title names the clip; every frame has its number and time |
| Compare many clips | One `uberseek observe N.mp4 0 <length>` per clip: each picture carries the clip's name, so they cannot be mixed up. `uberseek videos` lists the clips and their lengths |
| See chosen instants of a video on one picture | `uberseek sheet talk.mp4 '[5, 20, 61.5]'` |
| How something moves, or the camera moves | `uberseek observe clip.mp4 2 6 --focus motion` |
| Find where something is said | `uberseek transcript talk.mp4` once, then `uberseek find talk.mp4 "aircraft carriers"` |
| Exact times of words and silences | `uberseek words talk.mp4 50 60` and `uberseek pauses talk.mp4 50 60` |
| Where the shots change | `uberseek cuts reel.mp4` and `uberseek shots reel.mp4` |
| Flash frames, frozen frames, a strip or corner changing on its own | `uberseek flashes reel.mp4`, `uberseek freezes reel.mp4`, `uberseek part_changes reel.mp4`; frame by frame, `uberseek change reel.mp4 10 14` |
| Check one cut point or a join | `uberseek observe out.mp4 12.4 --focus boundary`: the frames on both sides and two seconds of sound |
| Keep or remove spans, frame-exact | `uberseek mark talk.mp4 0 54.9`, `uberseek mark talk.mp4 67.3 90` (the parts to keep), `uberseek clip out sel_000001 sel_000002`, `uberseek verify out`. `clip` prints `File: <path>` |
| Several steps in one go | `uberseek run program.py`: Python with every operation as a function. See `uberseek guide` |
| Keep track in a long task | `uberseek brief "<the task, word for word>"`, `uberseek note obs_000003 "what it showed"`, `uberseek status` |

Every operation is a command with its arguments in order: `uberseek <operation> <arguments>`. `uberseek -h`
lists them.

What keeps you right:

- **Open the picture.** The printed text says what was shown; only the picture shows it.
- **A number on a picture is that picture's number**, not a frame of the video. Read times from the labels.
- **You do not hear the sound.** It is drawn as a strip with silences shaded. `pauses` gives them exactly.
- **Word times are estimates**, good to a few tenths of a second. Where an edge must be exact, put it inside
  a silence: run `pauses` around the word and cut in the pause, then look with `--focus boundary`.
- **Nobody answers questions during the task.** Decide, say what you were unsure of, and deliver.

More: `uberseek guide` (the whole skill), `uberseek guide recipes` (worked programs), `uberseek guide limits`.
