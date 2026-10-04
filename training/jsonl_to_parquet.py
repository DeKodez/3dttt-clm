"""Convert SystemOne JSONL rows (gen_3dttt_dataset.py output) to parquet.

The choice loader in ``train/finetune.py`` expects ``<root>/<workflow>/*.parquet``
with ``id``, ``state``, ``questions`` and ``gold`` columns (questions/gold may be
JSON-encoded strings, which the adapter decodes).

Usage: python jsonl_to_parquet.py IN.jsonl[.gz] OUT.parquet
"""

from __future__ import annotations

import gzip
import json
import sys

import pyarrow as pa
import pyarrow.parquet as pq


def read_rows(path: str) -> list[dict]:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    rows = read_rows(src)
    table = pa.table(
        {
            "id": [row["id"] for row in rows],
            "state": [row["state"] for row in rows],
            "questions": [json.dumps(row["questions"]) for row in rows],
            "gold": [json.dumps(row["gold"]) for row in rows],
        }
    )
    pq.write_table(table, dst, compression="zstd")
    print(f"{src} -> {dst}: {len(rows)} rows")


if __name__ == "__main__":
    main()
