# CLM fine-tuning for 3D Tic-Tac-Toe — training report

This documents the first CLM fine-tune (`ft1`) for the 3D Tic-Tac-Toe arena:
how the dataset was built, how the run was launched, what the *valid* results
are, and why the ft1-vs-JEV head-to-head numbers produced on Oct 1 are **not**
valid evidence.

Goal (external): show that fine-tuning an 8B CLM on game trajectories lets it
perform competitively on the same complicated SystemOne task that JEV
(TypeSafe `jev-latest`) is strong at, without hand-written prompt coaching.

> Status: ft1 trained and validated on its held-out test set + targeted nuke
> probe. The Oct 1 ft1 head-to-head against JEV was invalidated by a stale
> `CLM_BASE_URL` in a long-running local server (see §6); a valid 40-game re-run
> on 2026-10-04 replaced it — CLM **24W-13L-3D** overall and **20W-0L as X**,
> 0 invalid moves (see §6 update).

---

## 1. Background and starting point

- Game: 6 faces × 3×3, global alternating turns, only the face in play is
  playable, cube rotation after each mark, one nuke per player per game. Full
  rules: `arena/agents/text.py::RULES` / root `README.md`.
- Both agents are asked the same wire format every turn (`SystemOne`):
  - `state`: `state_text(engine)` — rules + full position + rotation/win hints
  - `questions.threat_check` (`type: noul`)
  - `questions.answer` (`type: choice`) — one option per legal move, each
    annotated with its factual outcome (`arena/agents/text.py::move_options`)
- JEV = TypeSafe `jev-latest` via `https://api.typesafe.ai/v1/systemone`
  (`arena/agents/jev_agent.py`).
- CLM = local model served over the same SystemOne contract
  (`arena/agents/clm_agent.py`, URL from `CLM_BASE_URL`).

### Pre-fine-tune diagnostics (Sep 28)

| Agent | Rules/board quiz | vs tactical |
|---|---|---|
| CLM v0.1 (untrained) | 52.9% | 0% win rate |
| JEV | 100% | 0% win rate |

Source: `results/probe_clm.json`, `results/probe_jev.json`,
`results/probe_*_vs_tactical.json`.

### Prompt-coaching attempts (Sep 29, all valid: 0 invalid moves)

CLM was first given hand-written "coaching" prompts (variants v1–v4,
`promptonly`). Across 4 games/seed (each side plays X twice), the pattern was
always the same: **the side moving first (X) won every game**. CLM never won a
game as O, JEV never won as O.

| Series | Seed | Outcomes |
|---|---|---|
| coached | 11 | X wins 4/4 (JEV 2 as X, CLM 2 as X) |
| coached_v2 | 11 | X wins 4/4 |
| coached_v3 | 11, 23 | X wins 8/8 |
| coached_v4 | 11, 23 | X wins 8/8 |
| promptonly | 11, 23 | X wins 8/8 |
| stats-coached | 11 | CLM 2 wins as X, 2 ties |

Prompting alone produced no edge over JEV — hence fine-tuning.

---

## 2. Evaluation protocol

**Head-to-head** (`results/head_to_head_jev_vs_clm_*.summary.json`):
4 games per seed (JEV X vs CLM O, then CLM X vs JEV O, ×2), seeds 11 and 23.
A series is only usable if **every** CLM move is `invalid: false` (non-empty
`meta`); an invalid move means the arena replayed a seeded random legal move
instead of a model decision (`arena/match.py:125`) and the game is noise.

**Nuke probe** (`results/nuke_probe_double_threat*.json`): two positions
recorded from the earlier JEV-vs-CLM games where the defender faced two
immediate threats on the face in play (survivable only by nuking):
- `A_game0_move33` — game 0, move 33 (JEV defends)
- `B_game1_move31` — game 1, move 31 (CLM defends)

Each variant re-asks the position and records top nuke probability + confidence.

**Quiz** (`arena/probe.py::build_quiz`): fixed rules/board-reading quiz with
shuffled options.

---

## 3. Dataset (v1)

Generator: `training/gen_3dttt_dataset.py` (seed 7).

1. Plays 1,000 games — 400 random-vs-random, 400 tactical-vs-tactical
   (`TacticalAgent`), 200 mixed — and records a row at every non-repeated
   position (dedup by exact `state_text`). Every 10th game goes to **test**,
   the rest to **train**.
2. Row gold labels come from a deterministic oracle:
   - `threat_check`: opponent has an immediate winning cell
   - `answer`: **win > safe block > nuke (only to deny an immediate win) >
     positional heuristic** (`_score_move`, no rng jitter)
3. Rows carry `meta` used for boosting: `strategy` ∈ {positional, block, win,
   lost, nuke}, `threat`, `n_threats`, `n_options`.

Each row mirrors exactly what `CLMAgent` sends at inference
(`state`, `questions`), with `gold.answer.label/probabilities` and
`gold.threat_check.label/probabilities`.

### Raw dataset stats (`training/data/3dttt-v1/stats.json`)

| Split | Rows | Unique | threat=true | threat=false |
|---|---|---|---|---|
| train (raw) | 44,762 | 44,762 | 14,141 (31.6%) | 30,621 |
| test | 5,017 | — | ~1,653 (33.0%) | ~3,364 |

Raw train strategies: positional 21,576 · block 9,971 · win 12,643 · lost 356 · nuke 216
(cells-with-N-threats: 0→30,621, 1→10,657, 2→2,612, 3→719, 4→142, 5→11)

### Boosting

`boost()` duplicates rare decision rows. Copies per row:
`1 + boost_double_threat·[n_threats ≥ 2] + boost_own_win·[strategy == win] + boost_nuke·[strategy == nuke]`.

The ft1 dataset was generated with **`--boost-double-threat 8 --boost-own-win 2
--boost-nuke 8`** (derived from `stats.json`; note the checked-in script
defaults are 8/4/8, which would give ×5 single wins — pass the flags explicitly
to reproduce v1):

| Strategy | Raw | Boosted | Effective multiplier |
|---|---|---|---|
| positional | 21,576 | 21,576 | ×1 |
| block | 9,971 | 28,027 | ×9 when double-threat |
| win | 12,643 | 43,169 | ×3 single, ×11 double-threat |
| lost | 356 | 3,204 | ×9 (all double-threat) |
| nuke | 216 | 3,672 | ×17 (nuke + double-threat boosts) |
| **total** | **44,762** | **99,648** | |

Boosted classes: threat=true 50,937 (51.1%) vs 33.0% in raw test — i.e. the
boosted train set is heavily rebalanced toward threats. (No ablation exists
for these multipliers yet; §7.)

2. Conversion for the trainer: `training/jsonl_to_parquet.py` writes
   `id, state, questions (JSON string), gold (JSON string)` parquet files that
   the `choice` loader in `CLM/train/finetune.py` reads from
   `<data-root>/<workflow>/*.parquet` (uploaded layout: `/root/data/3dttt/all/`).

---

## 4. ft1 training run

Launcher: `run_ft1.sh` (kept in the session temp dir; reproduce below).
Executed on the RunPod L40S pod (`<ft1-pod>`, now **stopped**, disk kept).

```bash
cd /root/CLM/train || exit 1
export CUDA_VISIBLE_DEVICES=""          # head trains on CPU
export OMP_NUM_THREADS=32 MKL_NUM_THREADS=32
exec python finetune.py \
  --task choice --workflow all --data /root/data/3dttt \
  --embed-url http://127.0.0.1:8090/v1/embeddings --served-model-name qwen3-8b \
  --init-ckpt /root/.cache/clm/CLM_v0.1-8B.pt \
  --out-dir /root/runs/3dttt-ft1 \
  --targets soft --loss infonce --batch 256 --epochs 20 --patience 5 --seed 1234 \
  > /root/ft1.log 2>&1 < /dev/null
```

- Embeddings for the 99,648+5,017 texts are computed by a Qwen3-8B embedding
  server on the pod (`:8090`), cached to
  `runs/3dttt-ft1/embeddings/choice_Qwen_Qwen3-8B_2048.npz` (~886 MB; cache
  build dominates the wall clock).
- Outputs: `best_head.pt` (75,557,470 B) and `final_head.pt` (75,557,493 B),
  both mirrored locally under
  `best_head.pt`, `final_head.pt` (session temp dir, not in repo).
- Watcher log (`<session-tmp>/watcher.log`): run observed Sep 30 20:16 →
  Oct 1 00:15 local time (includes dataset upload, embedding cache, training).
  `finetune_summary.json` reports **~51 min** of training.

### Metrics (from `history.json` / `finetune_summary.json`)

| Metric | Value |
|---|---|
| Best epoch | 20 (final; best val 0.9412) |
| Test answer accuracy (ft1) | **0.8917** |
| Test answer accuracy (init head) | 0.2925 |
| Majority-class accuracy | 0.2973 |
| threat_check accuracy | 1.0 |
| per-question `answer` accuracy | 0.7833 |

Selection is teacher-forced validation accuracy on the boosted/held-out rows —
it measures agreement with the oracle labels, not game strength (§7).

> ⚠️ `history.json`, `finetune_summary.json` and `ft1.log` were pulled to the
> session temp dir but are no longer present locally, and `finetune.py` exists
> only on the pod disk (`/root/CLM/train/finetune.py`). Pull them before the
> pod is deleted.

---

## 5. Valid ft1 evidence

### 5a. Held-out test set

See §4 table: 0.8917 answer accuracy vs 0.2925 init / 0.2973 majority, 100%
threat_check. This is the strongest clean signal that the head learned the
task from the supervised oracle.

### 5b. Nuke double-threat probe

Nuke probability (top-1) and answer confidence for each variant:

| Variant | A: JEV pos (game0 m33) | B: CLM pos (game1 m31) |
|---|---|---|
| CLM v0.1 (untrained) | chose block; nuke not top-3 (conf 0.35) | chose block; nuke not top-3 (~0.40 top prob) |
| coached v1 | conf 0.86 / nuke 0.88 | — (not recorded) |
| coached v2 | conf 0.72 / nuke 0.76 | — |
| coached v3 | conf 0.70 / nuke 0.75 | — |
| coached v4 | conf 0.75 / nuke 0.78 | conf 0.349 / nuke **0.48** |
| promptonly | conf 0.76 / nuke 0.80 | conf 0.349 / nuke **0.48** |
| **ft1** | conf 0.70 / nuke 0.75 | conf **0.991** / nuke **0.993** |

Interpretation:
- In scenario B (the unambiguous "only the nuke survives" case) ft1 is
  decisively sharpened: 0.993 vs 0.48 for the prompt-based variants. This
  confirms the fine-tune internalized the nuke-to-deny rule.
- Scenario A is strategically ambiguous (the nuke line and the recorded
  no-nuke line both end in a 3-3 tie per the probe's `verification` note), so
  ~0.75 there — same as coached_v4 — is not evidence of a regression.
- The untrained v0 head never even considered the nuke, which is the clearest
  before/after contrast.

### 5c. Invalid evidence — do not use

`results/head_to_head_jev_vs_clm_ft1*.summary.json` and everything derived from
it (`results/coached_ft1_comparison.json`, conclusions like "ft1 loses 8/8" or
"ft1 over-nukes") are **invalid** — see §6. The invalid series recorded
91/182 (seed 11) and 81/163 (seed 23) CLM moves as invalid; every CLM "move"
in it was a seeded random legal move from the arena fallback.

---

## 6. Postmortem: why the ft1 head-to-head was invalid

### Symptom

Live reproduction (fresh WS match `agent_a=clm, agent_b=tactical`, seed 11):
every CLM turn failed with

```
HTTPStatusError: Client error '404 Not Found' for url
'https://<old-pod-host>/v1/systemone'
```

`invalid: true`, `error: <the 404>`, `meta: {}` on every CLM move.

### Root cause

1. `arena/env.py::load_env()` only sets environment variables **not already
   present** in `os.environ` — pre-existing values win.
2. The arena server (`venv/bin/python -m arena.server`, started
   Sep 29 12:25:33, still running) read `.env` while
   `CLM_BASE_URL=https://<old-pod-host>` (an older,
   later-terminated pod) was current. It captured that value into its process
   environment for its whole lifetime.
3. `.env` was later updated to the ft1 pod
   (`CLM_BASE_URL=https://<ft1-pod-host>`) and the ft1
   pod was trained and served — but the long-running server never re-read the
   file, so every match it ran pointed at the dead older pod.
4. On failure the arena does not abort: `arena/match.py:125` substitutes a
   seeded random legal move, records `invalid: true`, and continues. The
   games complete and look playable in the UI — the series is silently noise.

The nuke probe (Oct 1 00:17) returned real answers (`invalid: false`, full
`meta`, ft1-sharpened distributions) because it was run outside the stale
server process, so it is valid. The head-to-head summary files were produced
through the stale server — hence the split verdict.

### Fix and preflight

- Restart any long-lived server process after a pod/URL change (fresh process
  re-reads `.env`):
  `kill <server-pid> && venv/bin/python -m arena.server`
- Before recording any series, assert:
  - `curl -s -o /dev/null -w '%{http_code}' $CLM_BASE_URL/health` (or a
    `POST /v1/systemone` smoke call) does not 404
  - the first CLM move of the series has `invalid: false` and non-empty `meta`
- Treat `invalid: true` as fatal for a series, not as a random move: fail the
  match or the run instead of falling back.
- Optionally change `load_env()` precedence, or document that the server must
  be started fresh.

### Update (2026-10-04): valid re-run

The ft1 `best_head.pt` was recovered (md5 `911b68ca503fc6f1a326233b7107fac0`)
and re-served in a fresh `clm-serve` on the re-provisioned pod; the Mac side
reached it through an ssh tunnel with `CLM_BASE_URL=http://127.0.0.1:8700` set
in the environment (so `.env` could not poison the run). The re-created runner
is `eval/head_to_head.py` — fail-fast, so a series with any `invalid: true` is
written as `.FAILED.json` and not recorded.

Protocol re-run: 4 games/seed, seeds 11 and 23 plus 8 fresh seeds (31–38) =
**40 games, 0 invalid moves**. Pooled (`eval/aggregate_head_to_head.py`):

| | Games | CLM | JEV |
|---|---|---|---|
| Overall | 40 | **24W-13L-3D** (win-equiv 64%, 95% CI 48–77%) | 13W-24L-3D |
| CLM as X | 20 | **20W-0L-0D** | 0W-20L |
| CLM as O | 20 | 4W-13L-3D | 13W-4L-3D |

First move dominates (X went 33W-4L-3D overall), as in the prompt era — except
now CLM wins every game it starts and takes 4 games as O (JEV takes 0). The
first two seeds alone (6W-1D-1L) were favourable variance; at 40 games parity
sits at the bottom edge of the CI (48%), so the honest read is "at least level,
likely better". CLM first-move confidence ~0.6–0.8 with sharp distributions,
JEV 0.95; both sides have full `meta`.

Artifacts: `results/head_to_head_jev_vs_clm_ft1_valid*.summary.json` and
`results/rematch_batch/seed*.summary.json`; pooled stats in
`results/head_to_head_jev_vs_clm_ft1_valid_aggregate.json`. The Oct 1 files are
invalid bug evidence only and must not be cited.

---

## 7. Recipe caveats (known before ft2)

1. **`--targets soft` is a no-op on this data.** Gold probabilities are
   one-hot (`{chosen_key: 1.0}`), so "soft" targets telescope to hard targets.
   A real soft-label recipe (oracle distribution, or JEV rationales) would be a
   genuine change.
2. **Boosts are unablated and skew the training prior.** Double-threat ×9,
   win ×3/×11, nuke ×17 push threat=true from 31.6% → 51.1% while test stays
   at 33%. It may be beneficial or harmful — unknown until ablated.
3. **The teacher is a weak heuristic, not JEV.** The oracle is
   win > safe-block > nuke-to-deny > positional with hand-tuned scores. The
   0.89 test accuracy is agreement with that oracle; the *ceiling* on real
   strength is unknown. Distillation from JEV (or self-play improvement) is
   the obvious next step.
4. **Model selection by teacher-forced val accuracy** picks the epoch that
   best imitates the oracle; best = final epoch means training was still
   improving and/or patience was wasted. Prefer probe/game-strength selection.
5. **No win/block probe.** Only the nuke double-threat probe exists, so the
   win path (boosted ×3/×11) is unverified.

---

## 8. Reproduction

Dataset (local):

```bash
python training/gen_3dttt_dataset.py \
  --out-dir training/data/3dttt-v1 \
  --seed 7 --random-games 400 --tactical-games 400 --mixed-games 200 \
  --test-every 10 \
  --boost-double-threat 8 --boost-own-win 2 --boost-nuke 8
python training/jsonl_to_parquet.py training/data/3dttt-v1/train.jsonl <dst>/all/train.parquet
python training/jsonl_to_parquet.py training/data/3dttt-v1/test.jsonl  <dst>/all/test.parquet
# (the loader globs <root>/<workflow>/*.parquet, so file names are free;
#  the exact names used on the ft1 pod were not recorded)
```

Train (pod; CLM checkout + Qwen3-8B embedding server on `:8090`):

```bash
bash run_ft1.sh        # see §4 for the exact command
```

Evaluate (after starting the ft1 pod):

```bash
# 1. point .env at the live pod, then start a FRESH server (re-reads .env)
kill <old-pid>; venv/bin/python -m arena.server
# 2. smoke: one CLM turn must have invalid: false and non-empty meta
# 3. run the head-to-head series (seeds 11 and 23) and the nuke probe
```

Valid re-run completed 2026-10-04 (10 seeds, 40 games): 0 invalid moves, CLM
24W-13L-3D overall and 20W-0L as X. Do not compare against the invalid Oct 1
series.

---

## 9. Proposed new repo layout (CLM fine-tuning demo)

`arena/` and `training/` are all this repo adds; the trainer itself is CLM's
`train/finetune.py` (must be pulled from the pod or taken from the CLM
upstream). Suggested standalone repo:

```
README.md                      # this report, trimmed to the demo narrative
training/gen_3dttt_dataset.py  # dataset generator (arena-dependent)
training/jsonl_to_parquet.py   # trainer input format
training/run_ft1.sh            # exact fine-tune launcher
training/data/3dttt-v1/{stats.json,test.jsonl}   # train.jsonl regenerable
eval/nuke_probe.py             # double-threat probe (to be re-created)
eval/head_to_head.py           # series runner (re-created 2026-10-04, fail-fast)
arena/                         # needed subset: engine, enums, faces, agents/text,
                               # baselines, probe, clm_agent, jev_agent, env
results/                       # valid evidence only (test metrics, nuke probe)
docs/INVALID_EVAL_POSTMORTEM.md
```

Not yet in the repo (on pod disk / lost): `finetune.py`, `history.json`,
`finetune_summary.json`, `ft1.log`, embedding npz cache, the original probe
runner script (the head-to-head runner was re-created as `eval/head_to_head.py`).

---

## 10. Artifacts index

Local:
- `training/gen_3dttt_dataset.py`, `training/jsonl_to_parquet.py`
- `training/data/3dttt-v1/` — `train.jsonl` (99,648), `test.jsonl` (5,017),
  `stats.json`
- `results/nuke_probe_double_threat*.json` — v0, coached, v2, v3, v4,
  promptonly, ft1
- `results/probe_{clm,jev}*.json` — quizzes
- `results/head_to_head_jev_vs_clm_{coached,coached_v2,coached_v3,coached_v4,
  promptonly,stats}*.summary.json` — valid prompt-era series
- `results/head_to_head_jev_vs_clm_ft1_valid*.summary.json` +
  `results/rematch_batch/seed*.summary.json` + `..._valid_aggregate.json` —
  valid re-run (2026-10-04), 40 games: CLM 24W-13L-3D vs JEV, 20W-0L as X
- `results/head_to_head_jev_vs_clm_ft1*` + `coached_ft1_comparison.json` —
  **invalid, keep only as bug evidence**
- `<session-tmp>/run_ft1.sh``,
  `best_head.pt`, `final_head.pt` (session temp dir, not in repo)
- Hosted: `best_head.pt` (ft1) — https://huggingface.co/DeKodez/3dttt-clm-ft1
  (sha256 `c37c2534b80d4ab5aac6be0ff9323e3b6430f784770b3ef4c61d49a99b648934`,
  round-trip verified 2026-10-05)
- `.env`: `TYPESAFE_API_KEY=…`, `CLM_BASE_URL=https://<ft1-pod-host>`
  (pod stopped; stale server pointed at a dead pod)

On pod `<ft1-pod>` disk (needs a restart to fetch):
`/root/CLM/train/finetune.py`, `/root/runs/3dttt-ft1/{history.json,
finetune_summary.json,best_head.pt,final_head.pt,embeddings/}`, `/root/ft1.log`,
`/root/data/3dttt/all/*.parquet`.
