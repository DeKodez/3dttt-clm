# eval — probes and match series

These runners existed as ad-hoc scripts before the repo split. They are the
reproduction path for `results/`. `head_to_head.py` was re-created
2026-10-04; `nuke_probe.py` still needs its CLI.

## nuke_probe.py

Double-threat nuke probe: sets up the scenario where CLM can nuke a face to deny
a double threat, and scores nuke probability + confidence against a neutral
baseline. Library pieces already exist:

- `arena/probe.py` — scenario builders + scoring
- `arena/agents/text.py` — state/move formatting used by the CLM agent
- `arena/agents/clm_agent.py`

Outputs: `results/nuke_probe_double_threat*.json` (v0, coached, v2, v3, v4,
promptonly, ft1).

## head_to_head.py

Series runner (re-created 2026-10-04): `play_match` for N games on a seed, with
per-side stats and optional frames dump for the web UI.

```bash
PYTHONPATH=. python eval/head_to_head.py --agent-a jev --agent-b clm \
  --games 4 --seed 11 --out results/head_to_head_jev_vs_clm_ft1_valid.summary.json
```

Fail-fast: if any move has `invalid: true`, the series is written as
`<out>.FAILED.json` instead of a summary and the runner exits 2 — a stale
`CLM_BASE_URL` cannot silently become "evidence" again.

- Uses `arena/match.py`, `arena/stats.py`, `arena/agents/registry.py`
- Outputs: `results/head_to_head_*.summary.json`

## aggregate_head_to_head.py

Pools `.summary.json` files into W/L/D totals with Wilson 95% CIs, overall and
split by starting side.

```bash
PYTHONPATH=. python eval/aggregate_head_to_head.py --out results/<aggregate>.json \
  results/head_to_head_jev_vs_clm_ft1_valid*.summary.json results/rematch_batch/*.summary.json
```

- Outputs: `results/head_to_head_jev_vs_clm_ft1_valid_aggregate.json`

## Warning

Restart the arena server (or re-read `.env`) after pointing `CLM_BASE_URL` at a
new pod. A stale URL silently degrades CLM to random legal moves — the failure
mode that invalidated the Oct 1 ft1 series. See
`docs/INVALID_EVAL_POSTMORTEM.md`; treat `invalid: true` in match frames as
fatal for a series.
