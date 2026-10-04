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

---

### Update (2026-10-04): valid re-run

The invalid series was replaced by a valid re-run: the ft1 head
(`best_head.pt`, md5 `911b68ca503fc6f1a326233b7107fac0`) was re-served in a
fresh `clm-serve` on a re-provisioned pod, reached through an ssh tunnel with
`CLM_BASE_URL=http://127.0.0.1:8700` set in the environment. Runner:
`../eval/head_to_head.py` (fail-fast on any `invalid: true`). Result over
**40 games / 10 seeds: CLM 24W-13L-3D vs JEV, 0 invalid moves** — including
20W-0L as first player and 4W-13L-3D as second. The Oct 1 files stay here as
bug evidence only.
