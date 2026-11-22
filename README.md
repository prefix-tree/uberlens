# UberLens

An agent that watches video and answers questions about it, looking only where it matters.

UberLens decides where to look instead of watching every frame. On a long recording it predicts what each stretch
holds, checks the most promising ones, and rules stretches out when a prediction fails. On a live stream it chooses,
moment to moment, to answer, look closer, recall something earlier, or wait. A fast, cheap model makes the small
choices; a large one is called only when the fast one is unsure, and to write the answer.

It is the companion to [UberScene](https://github.com/prefix-tree/uberscene): UberScene makes video as code, UberLens
understands it.

> [!WARNING]
> **Design stage.** There is no code yet. [docs/design.md](docs/design.md) describes the architecture, the
> evaluation plan and the milestones.

## License

[Mozilla Public License 2.0](LICENSE).
