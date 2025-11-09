# Repository Guidelines

## Project Structure & Module Organization
- Root `main.py` is just a smoke-test; all production logic lives in `gemini/`.
- `gemini/gemini.py` hosts the Live API audio/video loop, while `process_graph.py` and `preference_service.py` expose reusable graph utilities; `object_dict.py` is reserved for upcoming shared schemas.
- Keep new runtime agents or helpers beside these modules, and mirror their layout inside `tests/` (create it if missing). Assets such as recorded prompts belong in `assets/` to avoid polluting source directories.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — provision an isolated env; PyAudio especially requires this to pull the correct native wheels.
- `pip install google-genai opencv-python pyaudio pillow mss pytest` — install runtime + test dependencies defined in `gemini.py`.
- `GOOGLE_API_KEY=<token> python -m gemini.gemini --mode camera` — run the core loop; swap `--mode screen` or `--mode none` per scenario.
- `pytest -q` — execute the suite; use `coverage run -m pytest && coverage report --fail-under=80` before opening a PR.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents, informative snake_case filenames, and CapWords classes (see `ProcessGraph`); keep constants (sample rates, chunk sizes, model IDs) near the top of each module.
- Favor type hints and docstrings for public functions, and keep asynchronous function names verb-driven (`send_text`, `listen_audio`). Formatters such as `ruff format` or `black` are welcome but do not commit mixed styles.

## Testing Guidelines
- House tests in `tests/` with files named `test_<module>.py` and functions `test_<behavior>()`.
- Use pytest fixtures or monkeypatching to fake microphone, camera, and Google client objects; assert queue back-pressure, cancellation, and CLI parsing paths.
- Document any hardware-specific assumptions (sample rates, audio devices) inside the test docstrings.

## Documentation & Best Practices
- Always consult up-to-date official documentation and current best practices for dependencies, APIs, and tools before implementing or modifying functionality.

## Commit & Pull Request Guidelines
- History currently uses short imperative subject lines (“Initial commit”); follow the same, optionally prefixed with a scope (`agent: add screen mode support`), and keep bodies for context or issue refs.
- Each PR description must cover motivation, testing evidence (paste the `pytest` or coverage summary), and any configuration/API-key changes. Include screenshots or logs when the console UX shifts.
- Rebase before requesting review, ensure CI-equivalent commands pass locally, and avoid mixing unrelated refactors with feature work.
