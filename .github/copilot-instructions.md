# Copilot instructions — HA-Log-Debugger-AI

> Canonical standards live in the `dev-standards` repo on SOUNDWAVE/Gitea.
> Read by Copilot chat **and** inline suggestions.

## What this repo is

A **standalone Dockerised Python web app** that ingests Home Assistant logs and
does AI-assisted analysis (with a web UI + log database + web search). It is
**not** a Home Assistant custom component — there's no `custom_components/`. It
complements the `HA-Log-Debugger` component (which *is* an HA integration).

## Repo shape

- `src/` — `main.py`, `ai_analyzer.py`, `log_monitor.py`, `database.py`,
  `models.py`, `web_interface.py`, `web_search.py`.
- `static/` — web UI (`index.html`, `script.js`, `style.css`).
- `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `run.py`,
  `requirements.txt`, `examples/`.
- `.github/workflows/build-and-publish.yml` — builds + publishes the image.

## Conventions

- Python web service: **no `manifest.json`/`hassfest`/HACS** — the HA component
  pipeline does NOT apply here.
- Ship changes as a rebuilt Docker image (the workflow publishes it).
- AI provider keys + any HA log access are configured via env/compose — never
  commit keys or tokens.

## Never

- Don't commit AI API keys, HA tokens, or other secrets.
