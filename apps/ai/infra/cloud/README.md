# Running the real Qwen3.5-9B on a cloud GPU

The laptop (7.7 GB RAM, no NVIDIA GPU) cannot run the 9B model, so the model is served from a GPU machine
and this repo talks to it over an OpenAI-compatible URL.

1. Start a GPU machine (>= 24 GB VRAM, or 2 x 16 GB). Open a terminal / notebook cell there.
2. `git clone` this repo (or upload `serve_qwen.sh`) and run `LLM_API_KEY=<your key> bash serve_qwen.sh`.
   First run downloads ~18 GB of weights (resumable), then starts vLLM on port 8001.
3. Expose the port (RunPod: the proxy URL; Colab/Kaggle: `cloudflared tunnel --url http://localhost:8001`).
4. On the laptop put it in `apps/ai/.env`:
   ```
   LLM_BASE_URL=https://<your-tunnel>/v1
   LLM_API_KEY=<same key>
   LLM_MODEL=Qwen/Qwen3.5-9B
   ```
5. Verify: `uv run python scripts/smoke_structured.py --n 5`

Notes
- Qwen3.5 needs a recent vLLM. If `vllm serve` rejects a flag, upgrade vLLM; if structured output fails set
  `LLM_STRUCTURED_MODE` to `structured_outputs` or `guided_json` (the smoke script reports which works).
- Thinking mode is controlled by `LLM_ENABLE_THINKING` (sent as `chat_template_kwargs.enable_thinking`).
- The API key protects the endpoint; do not share the tunnel URL publicly. No customer data is ever sent: all
  data in this repo is synthetic.

---
## Free Colab T4 route (GGUF, recommended for a first real run)
Notebook: `qwen35_colab_t4_gguf.ipynb` (regenerate with `python infra/cloud/make_colab_gguf_notebook.py`).
1. colab.research.google.com -> File -> Upload notebook -> pick the .ipynb.
2. Runtime -> Change runtime type -> T4 GPU -> Save.
3. Run cells top to bottom. Cell 2 asks to mount Google Drive (keeps the 5.7 GB model and the built binary for next time).
4. Cell 7 prints 4 lines (`LLM_BASE_URL`, `LLM_API_KEY`, ...). Paste them into `apps/ai/.env` on the laptop.
5. Laptop: `uv run python scripts/smoke_structured.py --n 20`, then `uv run pytest -m live tests/live -q`.
Model is Q4_K_M (quantized): numbers are GGUF numbers, not BF16. Switch `QUANT` to Q5_K_M for better quality.
