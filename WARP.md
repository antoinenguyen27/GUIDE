# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Quick commands

- Python virtualenv (recommended)
  ```bash
  python -m venv .venv && source .venv/bin/activate
  ```
- Install runtime + test deps (per AGENTS.md)
  ```bash
  pip install google-genai opencv-python pyaudio pillow mss pytest
  ```
  - If running on Python < 3.11, the code imports backports used for asyncio TaskGroup/ExceptionGroup:
    ```bash
    pip install taskgroup exceptiongroup
    ```
- Run the live loop (set your key in the environment)
  ```bash
  export GOOGLE_API_KEY={{GOOGLE_API_KEY}}
  python -m gemini.gemini --mode camera   # modes: camera | screen | none
  ```
  Examples:
  ```bash
  python -m gemini.gemini --mode screen
  python -m gemini.gemini --mode none
  ```
- Run tests
  ```bash
  pytest -q
  ```
- Run a single test (file::test)
  ```bash
  pytest tests/test_process_graph.py::test_update_step -q
  ```
- Coverage (target ≥ 80%)
  ```bash
  coverage run -m pytest && coverage report --fail-under=80
  ```
- Optional formatting/lint (mentioned in AGENTS.md; install if needed)
  ```bash
  pip install ruff black
  ruff check . && ruff format .
  black .
  ```

Notes
- No build step; this repo is executed as a Python module.
- Use headphones to avoid echo/feedback when running live audio.
- Always consult up-to-date official documentation and current best practices for all dependencies, APIs, and tools before implementing or modifying functionality.

## Architecture overview

High level
- main.py: smoke test only. Production logic lives in gemini/.
- gemini/gemini.py: real-time audio/video client loop for Google’s Gemini Live API.
- gemini/process_graph.py and gemini/preference_service.py: reusable, lightweight directed graph utility (ProcessGraph) for modeling step transitions.
- gemini/object_dict.py: reserved for shared schemas (currently empty).

gemini/gemini.py (runtime loop)
- External deps: google-genai client, PyAudio (I/O), OpenCV (camera frames), mss (screen capture), Pillow (image encode).
- Configuration constants at top:
  - Audio: FORMAT=paInt16, CHANNELS=1, SEND_SAMPLE_RATE=16000, RECEIVE_SAMPLE_RATE=24000, CHUNK_SIZE=1024
  - Model: MODEL="models/gemini-2.0-flash-live-001"
  - Client: genai.Client(http_options={"api_version": "v1beta"})
  - Live session CONFIG includes response_modalities=["AUDIO"], system_instruction, and proactivity flags
- Concurrency model: asyncio + TaskGroup
  - Queues
    - out_queue: producer for outbound items to the model (microphone chunks, frames/screenshots)
    - audio_in_queue: inbound PCM audio from the model for local playback
  - Tasks
    - send_text: reads terminal input; sends to model (q quits)
    - listen_audio: reads microphone -> out_queue as audio/pcm chunks
    - get_frames / get_screen: capture camera or screen -> out_queue (uses to_thread to avoid blocking)
    - send_realtime: consumes out_queue; streams to live session
    - receive_audio: handles streamed model responses; enqueues audio for playback and prints text
    - play_audio: consumes audio_in_queue; writes to speaker stream
  - Orchestration: created inside an async with client.aio.live.connect(...); graceful cancellation on user exit
- CLI: --mode {camera,screen,none} selects video source; default camera.

Graph utilities (gemini/process_graph.py and gemini/preference_service.py)
- ProcessGraph: minimal directed graph API
  - add/remove/update steps; add/remove transitions
  - query predecessors/successors; string representation for inspection
- Intended for composing/inspecting processing pipelines alongside runtime agents.

## Repository conventions (from AGENTS.md)
- Keep new runtime agents/helpers inside gemini/ and mirror them under tests/ (create tests/ if missing).
- Install deps listed above; run the live loop via: `GOOGLE_API_KEY={{GOOGLE_API_KEY}} python -m gemini.gemini --mode camera` (swap `--mode` as needed).
- Use pytest for tests; use coverage with a ≥ 80% threshold before PRs.
- Style: PEP 8, type hints for public functions; keep constants (sample rates, chunk sizes, model IDs) at the top of each module; async function names verb-driven (e.g., send_text, listen_audio).
