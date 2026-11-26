# How Is This Hook Built?

`/workspace/materials/hook.mp4` is a short vertical video that opens on one moving picture. Narrow vertical strips of other pictures then appear one at a time, each in its own column, until they cover the frame; most pop in, some fade in. Somewhere after that a white shape flashes over the middle for a moment, and the video then cuts to a title card.

I want to rebuild this opening on my own footage, so I need its timing exactly: when each strip appears and
where, and when the flash happens.

## What to deliver

`/workspace/output/answer.json`, in exactly this shape:

```json
{
  "strips": [{"t": 0.25, "column": 0}, {"t": 0.5, "column": 3}],
  "flash": 1.1,
  "title": 2.5
}
```

- `strips`: one entry per picture strip, in the order they appear. `t` is the time in seconds of the first
  frame that shows it. `column` is where it sits: the strips divide the width into equal columns, counted
  from 0 at the left.
- `flash`: the time in seconds of the first frame of the flash, or `null` if there is none.
- `title`: the time in seconds of the first frame of the title card, or `null` if there is none.

Times count from the first frame of the video and are judged to within 0.02 seconds, about one frame. For a strip that fades in, its time is the first frame where any of it shows.

## Environment

CPU only, about 15 minutes. Work in `/workspace/work/`. Nobody will answer questions during the task.
