#!/bin/bash
# Launch ft1 choice-head finetune on the pod. Training logs to /root/ft1.log.
# Per-epoch checkpoints land in /root/runs/3dttt-ft1/ (best_head.pt, final_head.pt);
# the embedding cache is saved every 2000 texts to runs/3dttt-ft1/embeddings/.
cd /root/CLM/train || exit 1
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export OMP_WAIT_POLICY=PASSIVE
export KMP_BLOCKTIME=0
exec python finetune.py \
  --task choice --workflow all --data /root/data/3dttt \
  --embed-url http://127.0.0.1:8090/v1/embeddings --served-model-name qwen3-8b \
  --init-ckpt /root/.cache/clm/CLM_v0.1-8B.pt \
  --out-dir /root/runs/3dttt-ft1 \
  --targets soft --loss infonce --batch 256 --epochs 20 --patience 5 --seed 1234 \
  > /root/ft1.log 2>&1 < /dev/null
