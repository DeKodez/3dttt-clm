#!/bin/bash
exec > /root/setup.log 2>&1
set -x
echo "=== setup start $(date -u) ==="

pip install --no-cache-dir --break-system-packages --ignore-installed vllm contrastive-lm
echo "=== pip done rc=$? $(date -u) ==="

python -c "import vllm; print('vllm', vllm.__version__)"
python -c "import clm; print('clm import ok')"

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
echo "=== health ==="
curl -s http://127.0.0.1:8700/health
echo
echo "=== setup done $(date -u) ==="
