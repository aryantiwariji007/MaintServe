#!/bin/bash
# Start vLLM server for MaintServe
# --max-model-len 32768  : supports long PDF/image embeddings (up to ~16k token inputs)
# --gpu-memory-utilization 0.95 : use 95% of VRAM for KV cache (safe on 48GB)

cd ~/qwen3-vllm || { echo "ERROR: ~/qwen3-vllm not found"; exit 1; }
source .venv/bin/activate

nohup vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --max-model-len 32768 \
  --max-num-seqs 12 \
  --gpu-memory-utilization 0.95 \
  --limit-mm-per-prompt.video 0 \
  > vllm.log 2>&1 &

echo "vLLM started with PID $!"
echo "Tail logs: tail -f ~/qwen3-vllm/vllm.log"
echo "Health check: curl -s http://localhost:8001/health"
