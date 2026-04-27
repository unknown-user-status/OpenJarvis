<div align="center">
  <img alt="OpenJarvis" src="assets/OpenJarvis_Horizontal_Logo.png" width="400">

  <p><i>Personal AI, On Personal Devices.</i></p>

  <p>
    <a href="https://scalingintelligence.stanford.edu/blogs/openjarvis/"><img src="https://img.shields.io/badge/project-OpenJarvis-blue" alt="Project"></a>
    <a href="https://open-jarvis.github.io/OpenJarvis/"><img src="https://img.shields.io/badge/docs-mkdocs-blue" alt="Docs"></a>
    <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
    <a href="https://discord.gg/YZZRxCAhmm"><img src="https://img.shields.io/badge/discord-join-7289da?logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

---

> **[Documentation](https://open-jarvis.github.io/OpenJarvis/)**
>
> **[Project Site](https://scalingintelligence.stanford.edu/blogs/openjarvis/)**
>
> **[Leaderboard](https://open-jarvis.github.io/OpenJarvis/leaderboard/)**
>
> **[Roadmap](https://open-jarvis.github.io/OpenJarvis/development/roadmap/)**

## Why OpenJarvis?

Personal AI agents are exploding in popularity, but nearly all of them still route intelligence through cloud APIs. Your "personal" AI continues to depend on someone else's server. At the same time, our [Intelligence Per Watt](https://www.intelligence-per-watt.ai/) research showed that local language models already handle 88.7% of single-turn chat and reasoning queries, with intelligence efficiency improving 5.3× from 2023 to 2025. The models and hardware are increasingly ready. What has been missing is the software stack to make local-first personal AI practical.

OpenJarvis is that stack. It is an opinionated framework for local-first personal AI, built around three core ideas: shared primitives for building on-device agents; evaluations that treat energy, FLOPs, latency, and dollar cost as first-class constraints alongside accuracy; and a learning loop that improves models using local trace data. The goal is simple: make it possible to build personal AI agents that run locally by default, calling the cloud only when truly necessary. OpenJarvis aims to be both a research platform and a production foundation for local AI, in the spirit of PyTorch.

## Installation

### Prerequisites

| Tool | Install |
|------|---------|
| **Python 3.10+** | [python.org](https://www.python.org/downloads/) |
| **uv** (Python package manager) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` — or `brew install uv` on macOS |
| **Rust** | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| **Git** | [git-scm.com](https://git-scm.com/) — or `brew install git` on macOS |

> **macOS users:** see the full [macOS Installation Guide](https://open-jarvis.github.io/OpenJarvis/getting-started/macos/) for a step-by-step walkthrough including Homebrew setup.

### Setup

```bash
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis
uv sync                           # core framework
uv sync --extra server             # + FastAPI server

# Build the Rust extension
uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml
```

> **Python 3.14+:** set `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` before the `maturin` command.

You also need a local inference backend: [Ollama](https://ollama.com), [vLLM](https://github.com/vllm-project/vllm), [SGLang](https://github.com/sgl-project/sglang), or [llama.cpp](https://github.com/ggerganov/llama.cpp). Alternatively, use the `cloud` engine with [OpenAI](https://openai.com), [Anthropic](https://anthropic.com), [Google Gemini](https://ai.google.dev), [OpenRouter](https://openrouter.ai), or [MiniMax](https://www.minimax.io) by setting the corresponding API key environment variable.

## Quick Start

```bash
# 1. Install and detect hardware
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis
uv sync
uv run jarvis init

# 2. Start Ollama and pull a model
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull qwen3:8b

# 3. Ask a question
uv run jarvis ask "What is the capital of France?"
```

`jarvis init` auto-detects your hardware and recommends the best engine. Run `uv run jarvis doctor` at any time to diagnose issues.

## Starter Configs

Install any preset with one command:

```bash
jarvis init --preset morning-digest-mac   # or any preset below
```

| Preset | Use Case | What it does |
|--------|----------|-------------|
| `morning-digest-mac` | Daily Briefing (Mac) | Spoken briefing from email, calendar, health, news with Jarvis voice |
| `morning-digest-linux` | Daily Briefing (Linux) | Same, with vLLM support for GPU servers |
| `morning-digest-minimal` | Daily Briefing (minimal) | Just Gmail + Calendar, runs on any machine |
| `deep-research` | Research Assistant | Multi-hop research across indexed docs with citations |
| `code-assistant` | Code Companion | Agent with code execution, file I/O, and shell access |
| `scheduled-monitor` | Persistent Monitor | Stateful agent that runs on a schedule with memory |
| `chat-simple` | Simple Chat | Lightweight conversation, no tools needed |

```bash
# Example: Morning Digest on Mac
jarvis init --preset morning-digest-mac
jarvis connect gdrive          # one OAuth flow covers Gmail, Calendar, Tasks
jarvis digest --fresh           # generate and play your first briefing

# Example: Deep Research
jarvis init --preset deep-research
jarvis memory index ./docs/    # index your documents
jarvis ask "Summarize all emails about Project X"
```

### Skills

Skills teach agents how to better use tools and improve their reasoning. Every skill is a tool — agents discover them from a catalog and invoke them on demand.

```bash
# Install skills from public sources
jarvis skill install hermes:arxiv
jarvis skill sync hermes --category research

# Use skills with any agent
jarvis ask "Use the code-explainer skill to explain this Python code: for i in range(5): print(i*2)"

# Optimize skills from your trace history
jarvis optimize skills --policy dspy

# Benchmark the impact
jarvis bench skills --max-samples 5 --seeds 42
```

Import from [Hermes Agent](https://github.com/NousResearch/hermes-agent) (~150 skills), [OpenClaw](https://github.com/openclaw/skills) (~13,700 community skills), or any GitHub repo. Skills follow the [agentskills.io](https://agentskills.io/specification) open standard.

See the [Skills User Guide](https://open-jarvis.github.io/OpenJarvis/user-guide/skills/) and [Skills Tutorial](https://open-jarvis.github.io/OpenJarvis/tutorials/skills-workflow/) for details.

### Built-in Agents

| Agent | Type | What it does |
|-------|------|-------------|
| `morning_digest` | Scheduled | Daily briefing from email, calendar, health, news — with TTS audio |
| `deep_research` | On-demand | Multi-hop research with citations across web and local docs |
| `monitor_operative` | Continuous | Long-horizon monitoring with memory, compression, and retrieval |
| `orchestrator` | On-demand | Multi-turn reasoning with automatic tool selection |
| `native_react` | On-demand | ReAct (Thought-Action-Observation) loop agent |
| `operative` | Continuous | Persistent autonomous agent with state management |
| `native_openhands` | On-demand | CodeAct — generates and executes Python code |
| `simple` | On-demand | Single-turn chat, no tools |

See the [User Guide](https://open-jarvis.github.io/OpenJarvis/user-guide/morning-digest/) and [Tutorials](https://open-jarvis.github.io/OpenJarvis/tutorials/) for detailed setup instructions.

Full documentation — including Docker deployment, cloud engines, development setup, and tutorials — at **[open-jarvis.github.io/OpenJarvis](https://open-jarvis.github.io/OpenJarvis/)**.

## Recent Improvements

### Intel NPU Integration with OpenVINO (2026-04)
Integrated Intel NPU/integrated GPU acceleration using OpenVINO framework with Hugging Face models:
- Added OpenVINO engine for Intel NPU/GPU acceleration with automatic device selection
- Implemented NPU-optimized models (Phi-3 Mini 4K, TinyLlama 1.1B, Gemma 2B, Llama 3.2 3B)
- Updated hardware detection to recommend OpenVINO for Intel GPUs
- Added intelligent model recommendation for NPU devices with INT8 quantization
- Created NPU configuration panel in Settings UI for device and model selection
- Achieved 50% memory reduction and 1.5-2x speed improvement with INT8 quantization
- Expected performance: 3-8 tokens/sec on Intel integrated GPU with shared memory

### Stanford Five-Primitive Architecture Implementation (2026-04)
Implemented Stanford's OpenJarvis five-primitive architecture across the entire stack:

- **Intelligence**: Added `/v1/intelligence/hardware` endpoint that detects system specs (RAM, GPU VRAM, CPU) and recommends appropriate model tiers. HardwarePanel UI component displays hardware info and model recommendations.
- **Engine**: Enhanced telemetry with energy/cost tracking in XRayFooter, added `/v1/telemetry/stats` endpoint for aggregate performance metrics.
- **Agents**: Added `/v1/agents` endpoint listing all available agents and AgentSelector component for switching between agent types in the chat UI.
- **Tools & Memory**: Added MCP server management endpoints (`/v1/mcp/servers` GET/POST/DELETE) and MCPPanel settings UI for managing external tools.
- **Learning**: Added `/v1/learning/status` and `/v1/learning/trigger` endpoints with LearningPanel dashboard component for optimization controls.

### Voice Mode v5 — Always On, Human-Like (2026-04)
`jarvis-voice.py` is now a true always-on assistant — no button pressing, no fixed recording windows.

- **Always listening in standby** — Jarvis silently monitors the microphone 24/7 and reacts the moment you speak.
- **Auto mic calibration** — measures ambient noise at startup and sets the detection threshold automatically.
- **Hands-free VAD** — detects when you start talking and stops recording 1 second after you go quiet. No timers.
- **Full machine control** — open/close any app, type text, click, scroll, take screenshots, set volume, control browser tabs, manage clipboard, search the web, and more — all by voice.
- **Conversation memory** — full session history sent to LLM on every turn for natural back-and-forth.
- **Standby until shutdown** — say *"shutdown Jarvis"* to stop. Otherwise Jarvis stays ready forever.
- Launch via `OpenJarvis-Voice.bat` (now uses `.venv\Scripts\python.exe` directly for reliability).

> **Tip:** if Jarvis false-triggers on background noise, raise `ENERGY_THRESHOLD` at the top of `jarvis-voice.py` (e.g. `0.025`).

### Model Download — Correct Qwen3 Tags + Engine Fix (2026-04)
- Fixed "Model pulling is only supported with the Ollama engine" error that appeared when any cloud API key was set alongside Ollama. The engine-detection now walks the full wrapper chain (`InstrumentedEngine → GuardrailsEngine → MultiEngine`).
- Corrected model catalogue: replaced nonexistent `qwen3.5:*` tags with the real Ollama tags — `qwen3:0.6b / 1.7b / 4b / 8b / 14b / 30b-a3b / 32b` — and added `qwen2.5vl` vision models.

### Data Sources — Upload & Document Management (2026-04)
- Drag-and-drop file upload zone with client-side file-type and 10 MB size validation.
- Uploaded documents panel: lists every ingested document (title, chunk count, type) with per-document delete.
- Backend: `GET /v1/connectors/upload/docs` and `DELETE /v1/connectors/upload/docs/{doc_id}` endpoints; 10 MB server-side guard.

### Chat — File Attachments via Paperclip (2026-04)
- Paperclip button in the chat input bar opens a file picker (txt, md, csv, py, js, json, and more).
- Selected files appear as chips above the input; their content is prepended to the message as fenced code blocks so the model can read them.
- Send button activates when attachments are present even with no typed text.

### Chat — Visible Error Messages (2026-04)
- Generation errors (e.g. model not found) now render as a red banner with a warning icon instead of appearing as a normal assistant message.

## Contributing

We welcome contributions! See the [Contributing Guide](CONTRIBUTING.md) for incentives, contribution types, and the PR process.

Quick start for contributors:

```bash
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis
uv sync --extra dev
uv run pre-commit install
uv run pytest tests/ -v
```

Browse the [Roadmap](https://open-jarvis.github.io/OpenJarvis/development/roadmap/) for areas where help is needed. Comment **"take"** on any issue to get auto-assigned.

## About

OpenJarvis is part of [Intelligence Per Watt](https://www.intelligence-per-watt.ai/), a research initiative studying the efficiency of on-device AI systems. The project is developed at [Hazy Research](https://hazyresearch.stanford.edu/) and the [Scaling Intelligence Lab](https://scalingintelligence.stanford.edu/) at [Stanford SAIL](https://ai.stanford.edu/).

## Sponsors

<p>
  <a href="https://www.laude.org/">Laude Institute</a> &bull;
  <a href="https://datascience.stanford.edu/marlowe">Stanford Marlowe</a> &bull;
  <a href="https://cloud.google.com/">Google Cloud Platform</a> &bull;
  <a href="https://lambda.ai/">Lambda Labs</a> &bull;
  <a href="https://ollama.com/">Ollama</a> &bull;
  <a href="https://research.ibm.com/">IBM Research</a> &bull;
  <a href="https://hai.stanford.edu/">Stanford HAI</a>
</p>

## Citation
```bibtex
@misc{saadfalcon2026openjarvis,
  title={OpenJarvis: Personal AI, On Personal Devices},
  author={Jon Saad-Falcon and Avanika Narayan and Herumb Shandilya and Hakki Orhun Akengin and Robby Manihani and Gabriel Bo and John Hennessy and Christopher R\'{e} and Azalia Mirhoseini},
  year={2026},
  howpublished={\url{https://scalingintelligence.stanford.edu/blogs/openjarvis/}},
}
```

## License

[Apache 2.0](LICENSE)
