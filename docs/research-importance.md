# UberLens: research on deciding what to look at

None of the eight methods reviewed here should replace a part of UberLens, but five of them should feed or extend it, and each one sits in a different layer of the same stack. **Q-Gate** (arXiv:2604.17422, ACM MM '26, MIT), **FOCUS** (arXiv:2510.27280, Apache-2.0) and **APS** (arXiv:2611.24079, no licence) are training-free, one-shot frame selectors that score frames with BLIP before the VLM sees anything. That scoring pass costs about **1,600 BLIP passes per video hour for FOCUS and 3,600 for Q-Gate and APS**, against the 22–31 frames ForeSeek sends to its VLM for a whole question. **KeyScore** (arXiv:2510.06509), **HAS** (arXiv:2607.17994) and **HiVid** (arXiv:2602.14214, ICLR 2026) score importance, but none has usable public code, HAS needs a model's internal attention logits, and HiVid measures generic interestingness, not relevance to a question. **NEST** (arXiv:2606.19706, EMNLP 2026) shows that current VLMs cannot find narrative events on their own (7.98% trigger detection, 5.89% localization, 10.62% argument extraction) and that they localize to the most visually salient scene. Related work (Event-Causal RAG, Video-NaRA) gains 3–12 points by keeping events in a graph. What to take: APS's penalised partition, run over the activity profile at INIT; Q-Gate's weight-vector gating with a masked softmax for `prior_profile`; FOCUS's UCB-V radius as a `next_interval` feature; HiVid's windowed ratings, conditioned on the brief, as a highlight prior for edits; and an event-graph memory with a story-importance score. One finding shapes the design: the query-agnostic layers (activity profile, event graph) are computed once per video and reused for every question, while the query-aware scorers have to be paid again for each question. That is why the scorers belong behind a budget gate and not in the default first look.

## How the claims were checked and what stays unverified

Each source was read in its arXiv HTML full text (fetched 2026-11-22). Q-Gate, FOCUS and APS were also read at a pinned repository commit: Q-Gate `d6e6a7a`, FOCUS `d469757`, APS `03ba744`. KeyScore and HiVid have no public repository. HAS has one that holds demo pages only. NEST's repository returned 403 to this session. Several claims in the brief were wrong or imprecise. Their corrections are in the last numbered section, and claims not checked against a primary source are marked **[unverified]** where they appear. The remaining open points are these:

- FOCUS's ICLR 2026 acceptance comes only from APS's comparison table.
- HAS's ECCV 2026 acceptance comes only from the authors' README.
- NEST's EMNLP listing was read from a search result, not from the Anthology page.
- HiVid's code in the OpenReview supplementary material, and its licence, were not seen.
- Whether NEST's data has actually been released, and under what terms, could not be checked.
- The full texts of NA-VQA, Event-Causal RAG, NarraScene and Minimal Clips were not read; their claims below come from the abstracts.

UberLens context comes from [design.md](../docs/design.md), [activity-prior.md](../docs/activity-prior.md) and [research.md](../docs/research.md). This report does not repeat research.md's review of OmniAgent, ActiveForager, ForeSeek or System-1.

## Query-aware selection: three BLIP selectors that run before the VLM

### Q-Gate: an LLM picks the weights for three score streams

**Identity.** "Where to Focus: Query-Modulated Multimodal Keyframe Selection for Long Video Understanding", by Shaoguang Wang, Weiyu Guo, Ziyang Chen, Xuming Hu and Hui Xiong (HKUST Guangzhou). v1 was posted on 19 Apr 2026 and v3 on 13 Nov 2026. It was accepted at ACM MM '26 (DOI 10.1145/3767308.3835040), and the paper is CC BY ([arXiv](https://arxiv.org/html/2604.17422)). Code: [github.com/shaoguangwang/Q_Gate](https://github.com/shaoguangwang/Q_Gate), **MIT**. Its grounding stream is derived from T*, which is also MIT.

**Method.** Three per-frame score streams run over the 1 fps grid:

- YOLO-World detection confidence for entities that an LLM pulls out of the question;
- the BLIP ITM match probability;
- SBERT similarity between the question and the subtitle at that time, set to 0 where there is no subtitle.

Each stream is min–max scaled. A "masked temperature softmax" with τ = 0.5 is then applied over the positive positions only, so a missing modality contributes zeros and does not distort the others ([arXiv §3.1, Eq. 2–3](https://arxiv.org/html/2604.17422)). The gating is **not learned**. One GPT-4o call at temperature 0 reads the question and the answer options and returns JSON weights `{w_logic, w_relevance, w_narrative}` that sum to 1. Three hand-written rules drive it:

- narrative weight ≥ 0.5 for speech, quoted subtitles and why-questions;
- logic weight ≥ 0.4 for counting, colour and left/right questions;
- otherwise relevance weight ≥ 0.5.

The fused score is cut to its top K frames ([fuse_scores.py](https://github.com/shaoguangwang/Q_Gate/blob/main/fuse_scores.py)).

**Cost of the scoring pass.** BLIP scores **every second of video** ([calculate_relevance_score.py](https://github.com/shaoguangwang/Q_Gate/blob/main/score_producers/relevance_blip/calculate_relevance_score.py)). The grounding producer searches up to min(1000, 10% of frames), and GPT-4o makes two text calls (entity extraction and gating) ([interface_searcher.py](https://github.com/shaoguangwang/Q_Gate/blob/main/score_producers/grounding/lib/interface_searcher.py)). Over a video hour that comes to about 3,600 BLIP passes, SBERT on every subtitle, up to 360 YOLO frames and two LLM calls. The paper reports only a relative overhead, **"1.50% additional end-to-end time" over AKS**, and no absolute seconds ([arXiv §5.8](https://arxiv.org/html/2604.17422)).

**Results.** With Qwen3-VL-32B at K = 32, Q-Gate scores 61.19 on Video-MME Long against 54.79 for AKS, and 59.40 on LongVideoBench Long against 57.80. It does not win every cell: LVB Short at K = 8 is 68.24 against 71.76 for uniform ([arXiv Table 1](https://arxiv.org/html/2604.17422)). Two ablations matter for UberLens:

- **A hand-written keyword gater scored worse than static equal weights** (44.40 vs 47.70 on LVB Long, GPT-4o, K = 8).
- Removing the subtitle stream costs 5.3 points on LVB Long ([arXiv Tables 2–3](https://arxiv.org/html/2604.17422)).

Giving the gater the answer options is worth only 0.18 points ([arXiv §5.3](https://arxiv.org/html/2604.17422)).

**Black-box compatibility.** Yes. The gater is any chat LLM (Qwen3-VL-32B as gater costs 2–4 points), and the scorers are local open models.

### FOCUS: a bandit over 16 s clips, with an honest "<2%"

**Identity.** "FOCUS: Efficient Keyframe Selection for Long Video Understanding", by Zirui Zhu, Hailun Xu, Yang Luo, Yong Liu, Kanchan Sarkar, Zhenheng Yang and Yang You (NUS and TikTok). v2 was posted on 24 Nov 2025, and the paper is CC BY 4.0 ([arXiv](https://arxiv.org/html/2510.27280)). The venue is ICLR '26 according to APS's table only **[unverified from FOCUS itself]** ([APS Table 1](https://arxiv.org/html/2611.24079)). Code: [github.com/NUS-HPC-AI-Lab/FOCUS](https://github.com/NUS-HPC-AI-Lab/FOCUS), **Apache-2.0**.

**Method.** Fixed 16 s clips are bandit arms, and pulling an arm means BLIP-scoring one frame from it. The confidence radius is empirical-Bernstein in the UCB-V style, β = √(2σ̂² ln n / N_a) + 3 ln n / N_a, with no tunable exploration constant ([arXiv §2.3, Eq. 5–8](https://arxiv.org/html/2510.27280)). The batched version used in practice has two stages:

1. Score 3 frames per arm (the centre frame plus 2 random ones).
2. Rank arms by UCB and score the top 25% (α) densely at 1 fps.

Keyframes are then drawn from the best arms by softmax (temperature 0.06) over nearest-neighbour-interpolated scores ([focus.py](https://github.com/NUS-HPC-AI-Lab/FOCUS/blob/main/focus.py); [run_focus_example.sh](https://github.com/NUS-HPC-AI-Lab/FOCUS/blob/main/run_focus_example.sh)). Code and paper differ in two places. The code ranks the final arms by UCB, while the paper says the unbiased empirical mean. The code also takes 20% of K directly from the top-scored frames, which the paper does not describe.

**Cost of the scoring pass.** BLIP scores **1.6% of native-fps frames, 5.5 H100 GPU-hours over LongVideoBench**. AKS with a 1 fps pre-filter scores 3.7% (9.3 GPU-h), and AKS without one 100% (255 GPU-h, estimated). α = 0.1 gives 1.1%, and α = 0.5 gives 2.5% ([arXiv Tables 3–4](https://arxiv.org/html/2510.27280)). At the default settings that is about 0.19 fps (Stage I) plus about 0.25 fps (Stage II), so **roughly 1,600 BLIP passes per video hour, of which Stage I alone is 675**. That is 34–68 times ForeSeek's 10–20 skim frames. The unit is different, though: a BLIP pass is not a VLM frame.

**Results.** With LLaVA-Video-7B at 64 frames, FOCUS scores 63.5 on LongVideoBench and 65.4 on Video-MME, against 58.9 / 64.4 for uniform and 62.1 / 64.6 for AKS. On LVB videos longer than 20 minutes the gain over uniform is +11.9 ([arXiv Table 2](https://arxiv.org/html/2510.27280)). Removing the Bernstein radius costs 0.5–2.6 points, and BLIP beats CLIP (60.2) and SigLIP (60.9) as the scorer ([arXiv App. G](https://arxiv.org/html/2510.27280)). Under APS's protocol FOCUS **falls below uniform on Video-MME with InternVL3-8B (−0.7) and MiniCPM-V4 (−1.5)** ([APS Table 1](https://arxiv.org/html/2611.24079)). By the authors' own account, FOCUS misses 1–2 s events in videos with many cuts.

**Black-box compatibility.** Yes. Scoring is a local BLIP model, and any model can consume the selected frames.

### APS: an exact penalised partition, cheap once the scores exist

**Identity.** "APS: Adaptive Partitioning-Based Frame Selection for Long Video Understanding", by Junxiang Wen, Lijun Wang, Zhen Qin, Shuiguang Deng (Zhejiang University) and others. v1 was posted on 18 Nov 2026, and no venue is stated ([arXiv](https://arxiv.org/html/2611.24079)). Code: [github.com/Baibaione/APS](https://github.com/Baibaione/APS), with **no project licence**. Its [NOTICE.md](https://github.com/Baibaione/APS/blob/main/third_party/NOTICE.md) says a licence "has not yet been selected".

**Method.**

1. BLIP-score every 1 fps frame, min–max normalise, and smooth with a moving average of half-width h = 2.
2. Find the optimal partition by exact dynamic programming, D(t) = min_k D(k) + C([k+1, t]). Each segment is either constant or linear, with cost C(I) = min_m [RSS_m / 2σ² + λ p_m]. Here σ is a robust MAD of first differences (floor 0.03), λ = (η/2) log N with η = 0.5, and the minimum segment length is 3 bins.
3. Give each segment frames in proportion to (μ_j + ε)^α · L_j^β, with α = 1 and β = 0.4–0.6, and take its top-scored frames ([arXiv §3.3–3.4, Eq. 4–18](https://arxiv.org/html/2611.24079); [selector.py](https://github.com/Baibaione/APS/blob/main/src/aps/selector.py)).

**Cost of the scoring pass.** **About 13.7 s of BLIP feature extraction per LongVideoBench sample, against 0.045 s for the DP**. The DP is about 0.3% of the total ([arXiv Table 6](https://arxiv.org/html/2611.24079)). APS scores 3,600 frames per hour, so as a scorer it is the most expensive of the three. Only the partition is nearly free.

**Results.** With Qwen2.5-VL-7B at 32 frames, the average gain over uniform is **+5.77**, against +4.00 for AKS and +3.73 for FOCUS. APS is best or tied best in 8 of 9 cells ([arXiv Table 1](https://arxiv.org/html/2611.24079)). The ablations are small but point the same way. On Video-MME / LVB:

| Variant | Video-MME | LVB |
|---|---|---|
| Equal partition, same segment count | 61.59 | 62.23 |
| Relevance-only allocation | 61.93 | 63.50 |
| Full APS | 62.33 | 63.80 |

η is flat across 0.25–1.25 ([arXiv Tables 2–3](https://arxiv.org/html/2611.24079)).

**Black-box compatibility.** Yes. The DP works on any 1-D signal and needs no model at all.

## Importance scoring: three methods with no reusable code

### KeyScore: three cosine terms, with retrieval numbers inflated by the caption

**Identity.** "From Captions to Keyframes: KeyScore for Multimodal Frame Scoring and Video-Language Understanding", by Shih-Yao Lin, Sibendu Paul and Caren Chen (Amazon Prime Video). v2 is dated 10 Oct 2025. No venue is given, the paper carries the default arXiv licence, and **no code** was found ([arXiv](https://arxiv.org/html/2510.06509)).

**Method.** STACFP clusters HSV histograms plus a time term with K-means, choosing k by silhouette, which gives 5.6–11 proposal frames. Each proposal is then scored as α·cos(f_i, t) + β·cos(f_i, v) + γ·[cos(v, t) − cos(ṽ^(−i), t)], using Perception Encoder or CLIP embeddings. The three terms are semantic match to the text, typicality of the frame for the whole video, and the drop in video–text similarity when the frame is left out. **α, β, γ and the threshold are never reported** ([arXiv §3](https://arxiv.org/html/2510.06509)).

**Cost of the scoring pass.** Histograms on sampled frames, plus embeddings of the 6–11 proposals only. No timings are reported.

**Results.** MSR-VTT text-to-video R@1 is 63.9 with 2.5 frames, against 51.2 for PE core video ([arXiv Tables 2–3](https://arxiv.org/html/2510.06509)). These retrieval numbers are inflated: the paired ground-truth caption is used both to pick the frames and as the retrieval query. The paper also contradicts itself. DiDeMo R@1 is 80.7 in Table 2 but 60.4 in Table 3, and on TVSum KeyScore scores 0.539, below TRIPSS's 0.610, while the text claims it outperforms the baselines. **There are no long-video QA results.**

**Black-box compatibility.** The scorer is a local encoder. The model that consumes the frames can be anything.

### HAS: a soft prior written into attention logits

**Identity.** "HAS: Highlight-guided Attention Steering for Multimodal LLM Video Summarization", by Rui Chu and Yingjie Lao (Tufts). Posted on 20 Jul 2026 under CC BY 4.0 ([arXiv](https://arxiv.org/html/2607.17994)). ECCV 2026 per the authors' README only **[unverified]**. The [repo](https://github.com/CRcr0/HAS) has demo pages and no method code or licence.

**Method.** An unnamed external highlight module produces a curve h, which is smoothed and normalised. The term log(h + ε) is added to the **pre-softmax attention logits** from text queries to visual tokens, in a few selected heads of a frozen open MLLM, at every decoding step. A per-head gate and strength are fit with Adam on teacher-forced NLL of reference summaries ([arXiv §3.5](https://arxiv.org/html/2607.17994)).

**Cost of the scoring pass.** The highlight model scores the whole video, and the MLLM still takes the whole video as input. HAS saves no tokens, and no latency is reported.

**Results.** The gains are small. On TVSum, Kendall τ is 0.224 against 0.222 for V2Xum-LLaMA. On SumMe, Spearman ρ is 0.335, below V2Xum's 0.378. On VISTA, fine-tuned models score far higher (FactVC 75.41 against 50.11) ([arXiv Tables 1–3](https://arxiv.org/html/2607.17994)). The transferable lesson is in its coverage plot: **hard selection stops improving early as the budget grows, while soft weighting keeps gaining** ([arXiv Fig. 2](https://arxiv.org/html/2607.17994)).

**Black-box compatibility.** **No.** HAS needs attention internals and gradients for fitting.

### HiVid: an API model rates every second for generic interestingness

**Identity.** "HiVid: LLM-Guided Video Saliency For Content-Aware VOD And Live Streaming", by Jiahui Chen, Bo Peng, Lianchen Jia, Zeyu Zhang, Tianchi Huang and Lifeng Sun (Tsinghua and ANU). **ICLR 2026** per the arXiv comment, CC BY 4.0 ([arXiv](https://arxiv.org/html/2602.14214)). The only code is a ranking-module example in the OpenReview supplementary material, which was not seen **[unverified; licence unknown]**.

**Method.** HiVid rates the first frame of every 1 s chunk. Sliding windows of m frames carry a running story summary of at most 100 words, and each call returns 0–100 interestingness ratings in JSON (prompt in App. J). Ratings from different windows disagree, so an LLM-as-comparator merge sort re-ranks all chunks globally. The result is Gaussian-smoothed. A small forecaster, which has to be trained, predicts ratings for live video ([arXiv §3, App. J](https://arxiv.org/html/2602.14214)).

**Cost of the scoring pass.** On a 201 s video with GPT-4o at m = 10: 20 perception calls and 182 ranking calls, **$1.35 and 0.54 h**. Without the ranking stage: $0.13 and 0.054 h. Gemini-2-flash costs $0.03 ([arXiv Tables 2, 5](https://arxiv.org/html/2602.14214)). Extrapolated linearly, the windowed path costs about **$2.30 per hour of video with GPT-4o and about $0.50 with Gemini-2-flash**. This is our estimate, not the paper's. The ranking stage grows faster than linearly.

**Results.** PLCC on Mr.HiSum is 0.66, against 0.59 for the best baseline. Without ranking it is 0.611, and without smoothing 0.619. Open judges (InternVL3-14B, Qwen3-VL-8B) reach 0.60–0.64. Live forecasting is weak, at PLCC 0.20–0.29 ([arXiv Tables 1, 3–5, 14](https://arxiv.org/html/2602.14214)). The ground truth is replay counts and TVSum/SumMe annotations: **generic interestingness, not relevance to a question or a brief**.

**Black-box compatibility.** **Yes, by design.** It was tested with GPT-4o, Gemini, Grok and Claude-3-haiku.

## Narrative importance: VLMs cannot find story events, but graphs help

### NEST: 1,005 movies, and discovery scores below 11%

**Identity.** "NEST: Narrative Event Structures in Time for Long Video Understanding", by Ali Asgarov and others in Chris Thomas's group (Virginia Tech). v2 was posted on 5 Sep 2026. Listed at EMNLP 2026 main ([arXiv](https://arxiv.org/html/2606.19706v2); [ACL Anthology](https://aclanthology.org/2026.emnlp-main.2512/), from a listing only). Code and data are at [github.com/aliasgerovs/nest](https://github.com/aliasgerovs/nest); the release status was not checked.

**Data and tasks.** 1,005 movies (average 97.9 min) with **about 103 events per movie**: PropBank triggers and arguments, and six relation types (temporal, causal, precondition, hierarchical, coreference, no-relation). Events take the boundaries of the scene that contains them, because grounding models failed. The labels are LLM-generated (Grok-4.1 Fast, about 100B tokens) from audio-description tracks. The human GOLD set is only 5 movies, and **humans agree on relation types only 41% of the time** ([arXiv §3.2, A.9](https://arxiv.org/html/2606.19706v2)). Copyrighted movies are released as features only, "under a research-only agreement". Raw video is released only for a public-domain subset ([arXiv §8, A.3](https://arxiv.org/html/2606.19706v2)).

**Method and cost.** NEST is a benchmark, not a scorer. Its only training baseline is a LoRA fine-tune of Qwen3-Omni-30B. Building its labels took about 100B LLM tokens over 1,639 hours of video, which shows what offline graph construction costs at scale.

**Results.** These are the best zero-shot scores per task ([arXiv Table 4, Table 12](https://arxiv.org/html/2606.19706v2)):

| Task | What the model must do | Best zero-shot | Model | Note |
|---|---|---|---|---|
| ETD, trigger detection | name the story-level event | **7.98%** | LLaVA-Video 7B | |
| EL, localization | find the event's scene | **5.89%** | Qwen3-VL-30B | chance ≈ 0.6% |
| EAE, argument extraction | fill in who / what / where | **10.62%** | Ovis2.5 9B | CI [3.47, 13.37] on 5 movies |
| ERE, relation classification | classify a given pair of events | 34.23% macro-F1 | Qwen2.5-VL-32B | 49.20% fine-tuned (v2; v1 said 35.45% / 44.42%) |

Fine-tuning barely moves discovery (ETD 3.20 → 6.09, EL 0.44 → 0.45). More frames do not reliably help.

The error analysis is the useful part:

- 76.4% of ETD errors name the wrong event entirely.
- 97.6% of EAE errors are entity confusion.
- Models put events in **the most visually salient scene** and assign flashbacks to the narrative present.
- Four of five models predict no-relation for more than half of the related pairs ([arXiv Tables 16–17, A.8](https://arxiv.org/html/2606.19706v2)).

**Black-box compatibility.** As an evaluation set, yes. Only the features and the public-domain subset are usable, and only for research.

### Related event-structure work points the same way

Explicit structure beats long context on questions whose evidence is far apart.

- **Event-Causal RAG** segments a stream into events with visual and audio "sentinels". It stores each event as a pre-state → event → post-state transition in a vector-plus-graph memory, walks predecessors and successors at query time, and reports **+4.96 to +11.67 points** on its ECV-1H benchmark (150+ hours, 1,251 causal QA pairs). It is designed for streaming too ([arXiv:2605.06185](https://arxiv.org/abs/2605.06185)).
- **Video-NaRA** stores event chains in a structured memory and gains up to 3 points on far-range movie questions in NA-VQA ([arXiv:2603.19481](https://arxiv.org/abs/2603.19481)).
- **NarraScene** finds that standard scene boundaries follow visual cuts, not narrative ones, and are no better than uniform chunks as retrieval units ([arXiv:2608.28699](https://arxiv.org/abs/2608.28699)).
- **MF²** finds that models improve when the input is restricted to the content relevant to a claim, so selection is the bottleneck. Its films are open-licensed ([arXiv:2506.06275](https://arxiv.org/abs/2506.06275)).
- For importance labels, TV recaps (**TaleSumm/PlotSnap**, [arXiv:2405.11487](https://arxiv.org/abs/2405.11487)) and screenplay-derived reference clips (**Minimal Clips**: <6% of a movie carries a full summary, [arXiv:2512.11399](https://arxiv.org/abs/2512.11399)) are the only story-importance supervision found.

All of these are from abstracts **[full texts unread]**. No benchmark labels the importance of each event directly.

## Four layers with very different unit costs

The methods stack into four layers. They differ in cost by orders of magnitude, and in whether their output can be reused across questions. The table puts each method's scoring pass on a per-video-hour basis. Estimates are marked.

| Layer | Methods | Scoring cost per video hour | Query-aware? | Reusable across questions? | Feeds UberLens at |
|---|---|---|---|---|---|
| 0. Cheap file signals | activity prior (bitrate, keyframes, audio, tiny thumbnails); APS DP on top | packet headers + audio decode; "a few seconds" target, **unmeasured until M1**; DP ≈ 0.05 s | no | **yes, cached per file** | SKIM, INIT intervals, `next_interval` features, wake-ups |
| 1. Query-aware scorers | KeyScore terms; FOCUS bandit; APS on BLIP; Q-Gate fusion; HiVid ratings | KeyScore: ~6–11 embeddings after a histogram pass (measured on short clips only); FOCUS **~1,600 BLIP** (Stage I 675); APS **3,600 BLIP**; Q-Gate **3,600 BLIP + SBERT + ≤360 YOLO + 2 LLM calls**; HiVid ~360 LLM calls at m=10 without ranking (~$0.5–2.3, est.) | yes (HiVid only via the prompt) | no, paid per question | optional scan tool, `next_interval` features, edit highlight prior |
| 2. Agent belief and expectations | ForeSeek-style belief, System-1 decisions | ForeSeek: **22–31 VLM frames per question**, ~2 rounds ([ForeSeek](https://arxiv.org/html/2611.26024)) | yes | no | the loop itself |
| 3. Narrative / event graph | NEST schema, Event-Causal RAG, story importance | ~1 System-2 call per scene; NEST averages 160.6 scenes in 97.9 min, so **~100 scenes per hour (est.)** | no, once built | **yes** | memory, Recall, answering, cut selection |

The table points to a design. Layers 0 and 3 are paid once per video and amortised over every question, and layer 2 is the cheap loop that ForeSeek already shows works at 8B. Layer 1 is where all the published gains are, but it is also the only layer that is both expensive and paid again for every question. Its scoring pass needs **50 to 160 times more model passes than ForeSeek sends VLM frames**. A BLIP pass costs far less than a VLM frame, so the ratio overstates the real cost, but frame-count metrics hide it entirely. Two consequences follow.

First, layer 1 belongs in UberLens as a budget-gated tool or feature, not as the default first look, and every run should report scorer passes separately from VLM frames. Otherwise a comparison with ForeSeek's frame counts flatters UberLens.

Second, layer 1 has to justify itself inside an agent. **None of the six layer-0/1 methods has been tested inside an iterative loop or against an agent's own belief.** APS, FOCUS and Q-Gate were measured as one-shot pre-filters for a single VLM call, and KeyScore, HAS and HiVid were never measured on long-video QA at all.

Two cross-cutting lessons cut against the simplest designs. Q-Gate's keyword-gater result argues against the heuristic `prior_profile` that design.md §6 plans for its first build: **rules underperformed even static weights**. And NEST's salience bias, together with NarraScene's cut-vs-narrative result, says that busy or visually salient is not the same as important to the story. This is the same caution activity-prior.md already gives about "busy is not the same as relevant", one level up.

## Where the brief was wrong or imprecise

**FOCUS.** The "<2% of frames" claim is true **for the scoring pass too**: BLIP scores 1.6% of native frames, which is about 0.44 fps. But that is still **about 1,600 BLIP passes per video hour**, under half a 1 fps pass (3,600) and 50–70 times ForeSeek's per-question VLM frames. The venue (ICLR '26) is attested only by APS. Code and paper disagree on how the final arms are ranked.

**HAS.** It **needs model internals**: pre-softmax attention logits, plus gradients to fit the per-head gates on reference summaries. It does not work with API models, and it saves no tokens.

**HiVid.** It is **ICLR 2026**, not a systems venue. It measures **generic interestingness** against replay counts and summary labels, not relevance to a query or brief. Its live forecaster is weak (PLCC ≤ 0.29).

**NEST.** The "~10%" figure is **argument extraction (EAE, 10.62%)**. Trigger detection is **7.98%** and localization **5.89%**, near a 0.6% chance level. Relation classification on given pairs reaches 34.23% zero-shot and 49.20% fine-tuned (v2 figures). The data is research-only.

**Q-Gate.** Its "gating" is one prompted GPT-4o call with three hand-written rules. It is not a learned mixture of experts, and the prompt includes the answer options.

**APS.** It is not cheap end to end: it BLIP-scores every second. Only its partition costs almost nothing.

**KeyScore.** Its retrieval gains rely on the ground-truth caption, which is also the retrieval query.

**ForeSeek (repeated earlier error).** "2.5–4.4× fewer frames" is measured **against EVA only**, not against search agents in general ([research.md, ForeSeek](../docs/research.md#foreseek-one-expectation-a-label-belief-and-a-round-decay-reward); [ForeSeek Table 1](https://arxiv.org/html/2611.26024)). design.md §9 still says "than search agents".

**ActiveForager (repeated earlier error).** The tool reward is the **per-token log-likelihood gain of the gold answer under a frozen reference model**, with versus without the evidence. It is clipped to [0, 1], gated by correctness, and also covers Wait ([ActiveForager Eqs. 3–6](https://arxiv.org/pdf/2611.24267v2)). design.md §10 still says "a tool call is rewarded only if it raised P(correct)".

## Changes to design.md and activity-prior.md

### (a) Adopt

1. **APS-style penalised partition at INIT (activity-prior.md §5.2; design.md §4 step 1).**
   - Run exact DP segmentation over the combined activity curve a(t) on the 1 s grid. Each segment is constant or linear, with cost RSS/2σ² + λp; λ = (η/2) log N with η = 0.5; σ is a robust MAD of first differences with a floor; the minimum segment is 3 bins.
   - The segments become the first intervals. Snap their ends to the nearest cut within 2 s, replacing "gaps between skim frames, snapped to cuts" as the source of interval boundaries. Keep the uniform half of the skim. Place the activity half one frame per highest-activity segment, still respecting the T/(2N) spacing.
   - Use APS's allocation rule w = (μ + ε)^α · L^β, with α = 1 and β ≈ 0.5, when `seek_interval` splits its n frames across the sub-segments of one interval (activity-prior.md §5.4).
   - Re-implement from Eq. 4–18. APS has no licence.
   - The cost is negligible (≈0.05 s per video for the DP in APS's runs). Running it on activity rather than BLIP scores is untested; see (b).
2. **`prior_profile` becomes a weight vector, not a label (design.md §6; activity-prior.md §4 step 4 and §5.6).**
   - The decision point returns weights over {motion, speech, cuts, static/uniform} that sum to 1, as Q-Gate's gater does. It keeps "none of the above", which falls back to the default weights.
   - Replace a(t) = Σ wᵢ · max(zᵢ, 0) with Q-Gate's per-signal min–max scaling and masked temperature softmax (τ = 0.5). Signals switched off by the reliability checks then drop out as zeros rather than being renormalised by hand.
   - The first backend for this decision point is a small LM classifier returning JSON weights, not keyword overlap. Q-Gate's keyword gater lost to static weights. The heuristic backend returns the default weights unchanged.
   - Pass the answer options when the benchmark has them; they are worth only 0.18 points to Q-Gate, so this does not matter much.
   - Q-Gate's prompt and fusion code are MIT and can be adapted with attribution.
3. **UCB-V radius as a `next_interval` feature (design.md §6; activity-prior.md §5.3).**
   - Add `n_observed`, `mean_relevance` and `ucb_radius` to `IntervalActivity`, where β = √(2σ̂² ln n / N_a) + 3 ln n / N_a. Here N_a is the number of frames seen inside the interval, from the skim, a scan tool or `seek_interval`, and σ̂² is the variance of their relevance scores (System-1 or BLIP).
   - The bonus shrinks as an interval is looked at, which gives System-1 a numeric exploration term in place of a flat top-2-margin rule.
   - The formula is from FOCUS (Apache-2.0, reusable with NOTICE). Using it inside an agent belief is ours; see (b).
4. **Brief-conditioned highlight prior for edits (new section in design.md; uses `VisionLanguageModel`).**
   - For an edit task, rate one frame per second in windows of about 10, carrying a running summary of at most 100 words. Seed the summary with the edit brief instead of the title, as HiVid's App. J does with the title.
   - Gaussian-smooth the ratings, then choose shots by threshold or knapsack.
   - Skip the merge-sort ranking by default. It costs about 10 times more calls for +0.05 PLCC. Use a Gemini-flash-class or open 8–14B judge, at about $0.50 per hour of footage (est.).
   - Following HAS's coverage result, allocate frames or resolution in proportion to the curve; never drop low-rated stretches entirely.
   - Re-implement from the CC BY paper; no code is available.
5. **Event-graph memory and story-importance score (design.md §2, §3 Recall, §11 Q4).**
   - Add `Event` (trigger, args with entity ids, span at scene granularity, level atomic/narrative, source `MemoryEntry` ids) and `Relation` (temporal, causal, precondition, part-of, coreference) beside `memory`, plus a per-video entity table.
   - Build events during consolidation with one System-2 call per scene (~100 per hour, est.) and cache them per video.
   - Recall walks predecessors and successors (the Event-Causal RAG design) as well as doing similarity search. This answers §11 Q4 with "graph + text, embeddings optional".
   - A story-importance score per event (descendants over causal and precondition edges, plus recap or summary support) ranks clips for edits and long-range answers instead of visual salience.
   - Localize at scene level first and refine with `get_clip` only for exact cut points. NEST shows that direct VLM localization is near chance.
6. **Report scorer passes separately (design.md §9 metrics).** Count BLIP/SBERT/YOLO passes, LLM rating calls and VLM frames separately. Report probe time and graph-build calls per video hour as well, so that ForeSeek frame comparisons stay honest.
7. **Add a narrative evaluation track (design.md §9).**
   - MF² (open-licensed films, fact/fib pairs).
   - The NEST public-domain subset and GOLD annotations, for event and relation F1 against the agent's graph, reported by evidence distance and on flashbacks.
   - ECV-1H and NA-VQA once released.
   - For edits, recap- or screenplay-derived "keep" labels (PlotSnap, Minimal Clips).
8. **Factual fixes still open in design.md.** §9: "2.5–4.4× fewer frames than EVA" (one agent). §10 step 3: the frozen-reference log-likelihood gain, clipped, correctness-gated, covering Wait.

### (b) UberLens extensions: label and ablate

9. **APS partition on the activity profile instead of relevance scores.** Ablate against skim-gap intervals and cut-snapped gaps (activity-prior.md §9 variant 5), measuring evidence hit at skim and rounds to answer.
10. **A query-aware scan tool.** `scan_relevance(span)` runs FOCUS Stage I (3 BLIP frames per arm) with **cut-snapped intervals as arms** instead of fixed 16 s clips, budget-gated and offered only when System-1 asks. Ablate: off, Stage I only, and the full two-stage version, at equal VLM frames, reporting scorer passes. It costs about 675 BLIP passes per hour for Stage I.
11. **UCB-V over agent observations.** Ablate the `next_interval` ranking with and without the radius. FOCUS's 0.5–2.6 point gain was measured on BLIP rewards in a one-shot selector, not on an agent's belief.
12. **KeyScore terms as System-1 features.** Use cos(frame, question) and a leave-one-out drop computed against memory as `next_interval` and `sufficient` features. KeyScore's own gains came from caption leakage, so expect much less.
13. **HAS's soft prior expressed as frame density for API models.** Never tested by HAS. Ablate soft allocation against hard top-K at equal frames.
14. **Brief conditioning of HiVid ratings.** HiVid measured generic interestingness only. Compare brief-conditioned with generic ratings against editor choices on in-house footage.
15. **Graph memory and narrative importance.** Ablate flat memory against the event graph, similarity Recall against graph-walk Recall, and salience-ranked against story-importance-ranked clip selection. No published system combines an event graph with an importance score for editing.

### (c) Licence constraints

16. **Q-Gate: MIT.** The prompt, masked softmax and fusion code can be copied with the copyright notice. The grounding stream also carries T*'s MIT notice.
17. **FOCUS: Apache-2.0.** The arm statistics and UCB-V code can be reused, keeping the licence and NOTICE and marking changes.
18. **APS: no licence.** **Do not copy or adapt its code.** Re-implement from the paper's equations, and do not use the repo's AKS caches.
19. **KeyScore, HAS, HiVid: no usable code.** KeyScore has none. HAS's repo has demo pages and no licence. HiVid's supplementary code was not seen and its licence is unknown. Re-implement from the papers; HAS and HiVid papers are CC BY, KeyScore's is under the default arXiv licence.
20. **NEST data: research-only.** Copyrighted movies come as features under a research-only agreement, and only a public-domain subset includes raw video. Use NEST for internal evaluation only, never for training a product model or in a redistributed set, and confirm the actual release terms first **[unverified]**. MF²'s open-licensed films are the safer end-to-end choice.

## Conclusion

The literature answers "what is worth looking at" in two ways that do not meet. Selectors score frames against the question with BLIP and stop. Narrative work shows that importance lives in event structure that frame scores cannot see, and that VLMs cannot recover that structure zero-shot. UberLens can join the two because it already has both ends. The activity prior and an event graph are per-video assets that pay for themselves over many questions and edits. The belief loop is where query-aware evidence accumulates cheaply. Query-aware scorers fit between them as an optional instrument, with their passes counted, not as a new first stage.

The biggest risk is not choosing the wrong method. It is importing numbers measured in one-shot pre-filter setups and assuming they carry over into an agent loop. Every adoption above has to clear the same equal-budget test that activity-prior.md §9 sets for the prior itself.
