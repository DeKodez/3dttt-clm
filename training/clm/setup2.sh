#!/bin/bash
# Re-provision the wiped ft1 pod for another fine-tune batch.
# Uploads expected at /root/: finetune.py (patched), jsonl_to_parquet.py,
# data/train.jsonl.gz, data/test.jsonl.gz
exec > /root/setup2.log 2>&1
set -x
echo "=== setup2 start $(date -u) ==="

mkdir -p /root/data/3dttt/all /root/.cache/clm /root/runs

if [ ! -d /root/CLM/.git ]; then
  git clone --depth 1 https://github.com/Contrastive-LM/CLM.git /root/CLM
fi
cp /root/finetune.py /root/CLM/train/finetune.py
md5sum /root/CLM/train/finetune.py

echo "=== pip install $(date -u) ==="
pip install --no-cache-dir --break-system-packages --ignore-installed vllm contrastive-lm pyarrow
echo "=== pip done rc=$? $(date -u) ==="
python -c "import vllm, clm, pyarrow; print('imports ok')"

echo "=== parquet conversion $(date -u) ==="
gunzip -kf /root/data/train.jsonl.gz
gunzip -kf /root/data/test.jsonl.gz
python /root/jsonl_to_parquet.py /root/data/train.jsonl /root/data/3dttt/all/train.parquet
python /root/jsonl_to_parquet.py /root/data/test.jsonl /root/data/3dttt/all/test.parquet
ls -la /root/data/3dttt/all/

echo "=== CLM head download $(date -u) ==="
bash /root/CLM/download_head.sh
cp -n /root/CLM/checkpoints/CLM_v0.1-8B.pt /root/.cache/clm/CLM_v0.1-8B.pt
ls -la /root/.cache/clm/

echo "=== starting vllm encoder $(date -u) ==="
nohup vllm serve Qwen/Qwen3-8B \
  --served-model-name qwen3-8b \
  --runner pooling \
  --max-model-len 2048 \
  --port 8090 > /root/vllm.log 2>&1 &
echo $! > /root/vllm.pid

up=0
for i in $(seq 1 240); do
  if curl -sf http://127.0.0.1:8090/v1/models >/dev/null 2>&1; then
    echo "=== vllm up after $((i*10))s $(date -u) ==="
    up=1
    break
  fi
  sleep 10
done
[ "$up" = 1 ] || echo "=== vllm did not come up within 40min ==="

echo "=== starting clm-serve $(date -u) ==="
nohup clm-serve > /root/clm.log 2>&1 &
echo $! > /root/clm.pid

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8700/health >/dev/null 2>&1; then
    echo "=== clm-serve up after $((i*5))s $(date -u) ==="
    break
  fi
  sleep 5
done
curl -s http://127.0.0.1:8700/health
echo
echo "=== setup2 done $(date -u) ==="
