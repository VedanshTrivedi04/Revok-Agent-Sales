#!/usr/bin/env bash
# Serve Qwen/Qwen3.5-9B with vLLM on a cloud GPU (Colab Pro L4/A100, Kaggle 2xT4, RunPod, Lambda...).
# Downloads the real weights (~18 GB) from Hugging Face on first run.
#
#   export LLM_API_KEY=dev-llm-key   # same value you put in apps/ai/.env
#   bash serve_qwen.sh
#
# VRAM guide: >=24 GB (L4/A10/4090/A100)  -> BF16 on one GPU
#             2 x 16 GB (Kaggle T4 x2)    -> fp16 with tensor parallel 2 (T4 has no bf16)
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen3.5-9B}"
PORT="${PORT:-8001}"
API_KEY="${LLM_API_KEY:-dev-llm-key}"
MAXLEN="${MAXLEN:-16384}"

NGPU=$(nvidia-smi -L | wc -l)
VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
DTYPE=auto
if [ "$VRAM_MB" -lt 20000 ] && [ "$NGPU" -ge 2 ]; then DTYPE=half; fi
echo "GPUs=$NGPU vram_per_gpu=${VRAM_MB}MB dtype=$DTYPE model=$MODEL"

pip -q install -U vllm huggingface_hub hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1
huggingface-cli download "$MODEL"            # resumable real download

exec vllm serve "$MODEL" \
  --host 0.0.0.0 --port "$PORT" --api-key "$API_KEY" \
  --dtype "$DTYPE" --tensor-parallel-size "$NGPU" \
  --max-model-len "$MAXLEN" --gpu-memory-utilization 0.90 \
  --enable-prefix-caching --served-model-name "$MODEL"
