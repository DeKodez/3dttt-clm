# results

Evidence from all evaluation runs. Two tiers:

## Valid evidence

- `ft1_summary.json` — ft1 training outcome (test acc 0.8917 vs init 0.2925,
  majority 0.2973; quiz answer 0.7833 / threat_check 1.0; 20 epochs, 51.18 min).
- `ft1_history.tsv`, `ft1_log_reconstructed.txt` — per-epoch history, merged from
  the training log tails captured before the ft1 pod disk was lost. All 20 epochs
  present. Provenance: upstream CLM + local patch (see `finetune.py`).
- `nuke_probe_double_threat*.json` — probe series across CLM variants (v0,
  coached, v2–v4, promptonly, ft1) and `probe_*.json` understanding probes.
- `head_to_head_*.summary.json` — match series for prompt-era and coached
  variants. These ran against live models and were audited.
- `head_to_head_jev_vs_clm_ft1_valid.summary.json` (seed 11),
  `..._valid_seed23.summary.json` (seed 23), `rematch_batch/seed*.summary.json`
  (seeds 31–38) — the valid ft1-vs-JEV re-run (2026-10-04): 40 games, 0 invalid
  moves, CLM **24W-13L-3D** overall and **20W-0L as X**. Pooled stats:
  `head_to_head_jev_vs_clm_ft1_valid_aggregate.json`. Runner:
  `../eval/head_to_head.py`; aggregator: `../eval/aggregate_head_to_head.py`.

## invalid_bug_evidence/

The Oct 1 ft1 series, invalidated by a stale `CLM_BASE_URL`: the CLM agent
silently fell back to random legal moves, so the games measure random play.
Kept only because the bug is instructive — see `../docs/INVALID_EVAL_POSTMORTEM.md`.

- `head_to_head_jev_vs_clm_ft1.summary.json`, `..._seed23.summary.json`,
  `coached_ft1_comparison.json`

Do not cite these numbers as results; frame files (`.frames.jsonl`) were
intentionally excluded for the same reason.
