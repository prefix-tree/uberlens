# How Is This Hook Built?

`/workspace/materials/reel.mp4` is a vertical social video that shows an edit and the editor's timeline that made it. The upper part of the frame is the finished video; below it is the timeline, with a playhead moving in step. The finished video opens on one shot of a person; narrow vertical strips of other shots then pop in one at a time, each in its own column, until they cover the picture. Then, for a moment, the person is replaced by a white shape of her outline.

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

Times count from the first frame of the video and are judged to within 0.1 seconds.

## Environment

CPU only, about 15 minutes. Work in `/workspace/work/`. Nobody will answer questions during the task.
