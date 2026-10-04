# CLM plays 3D Tic-Tac-Toe

A fine-tuning demo built around **3D Tic-Tac-Toe** (a 6-face tic-tac-toe variant).
The repo contains the playable game, a match arena where different agents play it,
and the fine-tuning recipe that teaches a [CLM](https://github.com/Contrastive-LM/CLM)
head on top of a frozen Qwen3-8B encoder to play the game.

The contribution of this repo is the game, the arena, and the training/eval
recipes around it. The trainer itself is CLM's upstream `train/finetune.py`
(vendored, with one local patch — patch visible in `training/clm/finetune.py`).

## Layout

```
game/          game engine + rules (faces, board, controller, scoring)
ui/            pygame UI
main.py        play the game locally:  python main.py
arena/         match harness: engine adapter, agents (CLM, JEV, baselines),
               quiz + nuke probes, head-to-head runner, FastAPI match server
web/           browser UI served by arena/server.py
training/      dataset generator + CLM fine-tune package
  gen_3dttt_dataset.py    teacher-oracle dataset generator (jsonl)
  jsonl_to_parquet.py     trainer input conversion
  data/3dttt-v1/          stats + test split (train regenerable)
  clm/                    recovered fine-tune scripts: finetune.py (patched),
                          run_ft1.sh, pod_setup_clm.sh, setup2.sh
eval/          probe + series runners (being re-created; see eval/README.md)
results/       valid evidence only (ft1 metrics, probes, prompt-era series)
  invalid_bug_evidence/   the invalid Oct 1 ft1 series, kept as bug evidence
docs/          full training report + invalid-eval postmortem
```

## Status

- **ft1 done** (2026-10-01): CLM head (Qwen3-8B frozen encoder) trained on
  ~180k teacher-oracle questions. Test accuracy **0.8917** vs init 0.2925
  (majority 0.2973); per-question quiz: answer 0.7833, threat_check **1.0**;
  nuke double-threat probe: nuke prob 0.993 / confidence 0.991.
  See `results/ft1_summary.json`.
- **ft1 vs JEV — valid re-run (2026-10-04)**: recovered head served via ssh
  tunnel; 40 games across 10 seeds with the fail-fast runner (0 invalid moves):
  CLM **24W-13L-3D** overall and **20W-0L as X** (first player dominates;
  win-equiv 64%, 95% CI 48–77%). The Oct 1 series was invalid (stale server
  env → random fallback; kept in `results/invalid_bug_evidence/`). See
  `docs/INVALID_EVAL_POSTMORTEM.md`.
- **ft2**: next iteration. Known recipe caveats are listed in
  `docs/REPORT.md` §7 (soft targets are a no-op, boost ablation, weak teacher,
  model selection, missing win/block probe).

## Quickstart

```bash
pip install -r requirements.txt        # game + arena

python main.py                         # play the game (pygame)
uvicorn arena.server:app --port 8000   # browser arena at http://127.0.0.1:8000

# train (GPU pod): see training/clm/pod_setup_clm.sh + run_ft1.sh
# eval: see eval/README.md and docs/REPORT.md §8
```

## Weights

The fine-tuned ft1 head is hosted publicly on Hugging Face:

- **`best_head.pt`** — https://huggingface.co/DeKodez/3dttt-clm-ft1
  (75,557,470 B; md5 `911b68ca503fc6f1a326233b7107fac0`; sha256
  `c37c2534b80d4ab5aac6be0ff9323e3b6430f784770b3ef4c61d49a99b648934`) —
  the exact head behind the valid 40-game JEV series.

Agent configuration lives in `.env` (copy `.env.example`). The CLM agent needs a
live `CLM_BASE_URL`; the server must be restarted after changing it.
