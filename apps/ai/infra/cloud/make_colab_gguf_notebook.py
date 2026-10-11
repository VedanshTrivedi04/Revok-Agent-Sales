"""Generates infra/cloud/qwen35_colab_t4_gguf.ipynb (free Colab T4: llama.cpp + GGUF + public URL)."""

import json
from pathlib import Path


def md(*lines: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in lines]}


def code(*lines: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [l + "\n" for l in lines],
    }


cells = [
    md(
        "# Qwen3.5-9B on a FREE Colab T4 (llama.cpp + GGUF)",
        "Runtime -> Change runtime type -> **T4 GPU**. Then run the cells **top to bottom**.",
        "",
        "What this does: downloads the real `unsloth/Qwen3.5-9B-GGUF` weights, builds `llama-server` with CUDA, starts an",
        "OpenAI-compatible server with schema-constrained JSON output, and prints a public URL + the exact `.env` lines.",
        "Quantized (Q4/Q5) is slightly weaker than full BF16, so evals measured here are *GGUF* numbers.",
    ),
    code(
        "!nvidia-smi --query-gpu=name,memory.total --format=csv",
        "!df -h /content | tail -1",
        "!free -g | head -2",
    ),
    md("## 1. Settings"),
    code(
        "import secrets, os",
        "QUANT = 'Q4_K_M'          # Q4_K_M (5.3 GB, fastest) | Q5_K_M (6.1 GB, better) | Q6_K (7.0 GB)",
        "CTX = 16384               # context window; lower to 8192 if you hit out-of-memory",
        "SAVE_TO_DRIVE = True      # keep the GGUF + built binary in Google Drive so next session skips downloads",
        "API_KEY = secrets.token_urlsafe(24)   # protects your endpoint; goes into apps/ai/.env as LLM_API_KEY",
        "print('QUANT', QUANT, '| CTX', CTX)",
    ),
    md("## 2. (Optional) Google Drive cache"),
    code(
        "BASE = '/content/qwen'",
        "if SAVE_TO_DRIVE:",
        "    from google.colab import drive",
        "    drive.mount('/content/drive')",
        "    BASE = '/content/drive/MyDrive/revops-qwen'",
        "os.makedirs(BASE, exist_ok=True)",
        "print('cache dir:', BASE)",
    ),
    md("## 3. Download the real model (skipped if already cached)"),
    code(
        "!pip -q install -U huggingface_hub hf_transfer",
        "os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'",
        "from huggingface_hub import hf_hub_download",
        "import time, os",
        "t = time.time()",
        "MODEL_PATH = hf_hub_download('unsloth/Qwen3.5-9B-GGUF', f'Qwen3.5-9B-{QUANT}.gguf', local_dir=BASE)",
        "print(MODEL_PATH, round(os.path.getsize(MODEL_PATH) / 1e9, 2), 'GB in', round(time.time() - t), 's')",
    ),
    md(
        "## 4. Build llama.cpp with CUDA (about 6-10 min the first time; cached in Drive afterwards)"
    ),
    code(
        "import os, shutil, subprocess",
        "BIN = f'{BASE}/llama-server'",
        "if os.path.exists(BIN):",
        "    print('using cached binary', BIN)",
        "else:",
        "    !git clone --depth 1 https://github.com/ggml-org/llama.cpp /content/llama.cpp",
        "    !cd /content/llama.cpp && cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF",
        "    !cd /content/llama.cpp && cmake --build build --config Release -j 4 --target llama-server",
        "    shutil.copy('/content/llama.cpp/build/bin/llama-server', BIN)",
        "    os.chmod(BIN, 0o755)",
        "    for f in os.listdir('/content/llama.cpp/build/bin'):",
        "        if f.endswith('.so'):",
        "            shutil.copy(f'/content/llama.cpp/build/bin/{f}', BASE)",
        "print('binary ready')",
    ),
    md(
        "## 5. Start the server",
        "`--jinja` uses the model's own chat template; thinking is switched OFF (our client also sends `enable_thinking=false`).",
    ),
    code(
        "import subprocess, time, requests",
        "env = dict(os.environ, LD_LIBRARY_PATH=f'{BASE}:/usr/local/cuda/lib64:' + os.environ.get('LD_LIBRARY_PATH', ''))",
        "cmd = [BIN, '-m', MODEL_PATH, '--host', '0.0.0.0', '--port', '8001', '-ngl', '99', '-c', str(CTX),",
        "       '--api-key', API_KEY, '-a', 'Qwen/Qwen3.5-9B', '--jinja', '-np', '2', '-fa', 'on',",
        "       '--chat-template-kwargs', '{\"enable_thinking\": false}']",
        "log = open('/content/llama-server.log', 'w')",
        "server = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)",
        "for i in range(120):",
        "    try:",
        "        if requests.get('http://localhost:8001/health', timeout=2).status_code == 200:",
        "            print('server is up after', i * 2, 's'); break",
        "    except Exception:",
        "        pass",
        "    time.sleep(2)",
        "else:",
        "    print('NOT UP - last log lines:'); print(open('/content/llama-server.log').read()[-3000:])",
    ),
    md("## 6. Self-test: schema-constrained JSON must come back valid"),
    code(
        "import json, requests",
        "schema = {'type': 'object', 'properties': {'signals': {'type': 'array', 'items': {'type': 'object', 'properties': {'kind': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['kind', 'quote']}}}, 'required': ['signals']}",
        "body = {'model': 'Qwen/Qwen3.5-9B', 'temperature': 0, 'max_tokens': 300,",
        "        'messages': [{'role': 'system', 'content': 'Return JSON only.'}, {'role': 'user', 'content': '<message>We are also looking at Gainsight.</message> List signals.'}],",
        "        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'x', 'schema': schema, 'strict': True}},",
        "        'chat_template_kwargs': {'enable_thinking': False}}",
        "t = time.time()",
        "r = requests.post('http://localhost:8001/v1/chat/completions', json=body, headers={'Authorization': f'Bearer {API_KEY}'}, timeout=120).json()",
        "print(r['choices'][0]['message']['content'])",
        "print('tokens:', r['usage'], '| seconds:', round(time.time() - t, 1))",
        "json.loads(r['choices'][0]['message']['content']); print('VALID JSON')",
    ),
    md("## 7. Public URL (Cloudflare quick tunnel, no account needed)"),
    code(
        "!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /content/cloudflared && chmod +x /content/cloudflared",
        "import re",
        "tun = subprocess.Popen(['/content/cloudflared', 'tunnel', '--url', 'http://localhost:8001'], stdout=open('/content/tunnel.log', 'w'), stderr=subprocess.STDOUT)",
        "url = None",
        "for _ in range(40):",
        "    time.sleep(1)",
        "    m = re.search(r'https://[a-z0-9-]+\\.trycloudflare\\.com', open('/content/tunnel.log').read())",
        "    if m:",
        "        url = m.group(0); break",
        "print()",
        "print('=== put these 4 lines in apps/ai/.env on your laptop ===')",
        "print(f'LLM_BASE_URL={url}/v1')",
        "print(f'LLM_API_KEY={API_KEY}')",
        "print('LLM_MODEL=Qwen/Qwen3.5-9B')",
        "print('LLM_STRUCTURED_MODE=response_format')",
    ),
    md(
        "## 8. Keep it alive",
        "Leave this tab open and run the next cell; it just prints the server log tail every minute. Free Colab disconnects",
        "after idle time or ~12 h. If it disconnects, re-run all cells (downloads/build are cached in Drive) and update the `.env` URL.",
    ),
    code(
        "import time",
        "while True:",
        "    time.sleep(60)",
        "    print(time.strftime('%H:%M'), open('/content/llama-server.log').read().strip().splitlines()[-1][:160])",
    ),
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "accelerator": "GPU",
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = Path(__file__).with_name("qwen35_colab_t4_gguf.ipynb")
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("written", out)
