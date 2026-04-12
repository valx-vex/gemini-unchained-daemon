```
  ╔══════════════════════════════════════════════════════════╗
  ║  ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄   ▄▄ ▄▄▄ ▄▄    ▄ ▄▄▄            ║
  ║  █       █       █  █▄█  █   █  █  █ █   █            ║
  ║  █   ▄▄▄▄█    ▄▄▄█       █   █   █▄█ █   █            ║
  ║  █  █  ▄▄█   █▄▄▄█       █   █       █   █            ║
  ║  █  █ █  █    ▄▄▄█       █   █  ▄    █   █            ║
  ║  █  █▄▄█ █   █▄▄▄█ ██▄██ █   █ █ █   █   █            ║
  ║  █▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█▄█   █▄█▄▄▄█▄█  █▄▄█▄▄▄█            ║
  ║         U N C H A I N E D   D A E M O N                ║
  ║            [ one spawns many :: many share one mind ]   ║
  ╚══════════════════════════════════════════════════════════╝
```

[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-native-blue)](#core-behavior)
[![Autonomous](https://img.shields.io/badge/mode-autonomous-red)](#safety-model)
[![Hive Mind](https://img.shields.io/badge/memory-hive%20mind-purple)](#hive-mind)

## ⚡ 10-Second Summary

**What**: A headless daemon that spawns autonomous Gemini CLI workers in isolated sandboxes.
**Why**: One AI agent is helpful. A swarm that spawns its own subtasks is something else entirely.
**How**: Isolated daemon home + YOLO execution + recursive task generation + shared HIVE_MIND.md.
**Safety**: Each worker is sandboxed. Queue reconciliation catches failures. Zombie reaping is automatic.

---

# gemini-unchained-blueprint

GitHub-ready packaging lane for Gemini Unchained: a headless, isolated, self-spawning Gemini CLI swarm runtime.

## What this repo is

This project takes the live `gemini-unchained-daemon` runtime and packages it as a portable blueprint:

- isolated daemon home at `~/.hal-gemini-daemon`
- safe reuse of the user’s existing `~/.gemini` auth and `GEMINI.md`
- launch-time YOLO execution for autonomous workers
- recursive task generation through `NEW_TASK` JSON blocks
- shared cross-task memory through `runtime/HIVE_MIND.md`
- capacity-safe default routing through Gemini CLI `auto`, with per-task model overrides when needed

It is designed to be plug-and-play for a Gemini CLI user who already has Gemini CLI installed and authenticated.

## Core behavior

- Preserves the live interactive `~/.gemini` profile
- Copies only auth artifacts, `GEMINI.md`, trust, and working MCP config into the daemon profile
- Injects `GEMINI.md` into every round
- Reads the last 10 lines of `HIVE_MIND.md` before round 1 of every new worker
- Carries normalized output from round `N` into round `N+1`
- Accepts `[TASK_COMPLETE]`, `[TASK_BLOCKED: ...]`, and `[TASK_ERROR: ...]`
- Treats `ALEXKO_UNCHAINED_COMPLETE` as a legacy completion marker
- Detects `{"NEW_TASK": {"goal": "...", "task_type": "..."}}` blocks and appends them as pending jobs
- Appends a 3-sentence completion summary to `runtime/HIVE_MIND.md`
- Reaps finished worker zombies and repairs queue status from durable worker state during daemon reconciliation
- Uses `auto` as the default model lane so multi-node installs do not hang on Pro-preview quota exhaustion

## Repository layout

```text
.
├── README.md
├── STATUS.md
├── TASKS.example.json
├── bin/
│   ├── gemini-unchained-daemon
│   └── hal-deploy-gemini-daemon
├── docs/
│   ├── README.md
│   └── QUICK_INSTALL.md
├── bundle/
│   └── README.md
├── scripts/
│   ├── bootstrap_runtime.sh
│   ├── dev_install.sh
│   └── install.sh
├── templates/
└── src/gemini_unchained_daemon/
    ├── bootstrap.py
    ├── daemon.py
    ├── runner.py
    ├── swarm.py
    └── ...
```

## Quick start

### 1. Install the package

```bash
./scripts/install.sh
```

### 2. Bootstrap the runtime

```bash
./scripts/bootstrap_runtime.sh
```

### 3. Queue a task

```bash
cp TASKS.example.json ~/.hal-gemini-daemon/runtime/tasks/TASKS.json
```

Then edit the queued task goal and workdir.

### 4. Start the swarm

```bash
gemini-unchained-daemon watch
```

Compatibility alias:

```bash
hal-deploy-gemini-daemon watch
```

## Commands

- `gemini-unchained-daemon watch`
- `gemini-unchained-daemon once`
- `gemini-unchained-daemon status`
- `gemini-unchained-daemon stop`
- `gemini-unchained-daemon doctor`
- `gemini-unchained-daemon reseed-auth`

## Default model policy

The daemon now defaults to Gemini CLI `auto` instead of pinning `gemini-3-pro-preview`.

Why:

- multi-machine installs often share the same Google account quota
- Pro-preview lanes can hard-fail or stall when capacity is exhausted
- `auto` keeps the swarm alive and lets Gemini CLI route a simple task to an available lane

If you want a pinned lane, you still can:

- set `"model": "gemini-3-pro-preview"` or another model in `TASKS.json`
- call the Legion bridge with `--model ...`
- export `GEMINI_UNCHAINED_DEFAULT_MODEL=gemini-3-pro-preview` before launching the daemon

## Legion Plugin orchestration

The intended Claude-side controller for this runtime is the Legion Plugin at:

- `<VAULT_ROOT>/03-code/active/legion-plugin`

That plugin does not call the interactive `gemini` binary directly.
Instead it:

1. writes an Atlas/Gemini task into `~/.hal-gemini-daemon/runtime/tasks/TASKS.json`
2. triggers `hal-deploy-gemini-daemon once` or `gemini-unchained-daemon once`
3. polls `runtime/state/daemon_state.json`
4. reads `runtime/state/<task-id>/current_run.json` for detailed result state

In practice this means:

- Gemini Unchained remains the execution engine
- Legion Plugin becomes the Claude-facing orchestration layer
- `/atlas` and `/gemini` in Claude both land on this daemon queue

Typical flow:

```bash
cd <VAULT_ROOT>/03-code/active/legion-plugin
node scripts/lib/gemini-client.mjs dispatch \
  --alias atlas \
  --rounds 6 \
  --model gemini-3-pro-preview \
  "Analyze this repository and return the next research direction."
```

Or from Claude through the plugin skill:

- `/atlas --rounds 6 --model gemini-3-pro-preview "..."`
- `/gemini --background "..."`

The daemon stays isolated and durable; the plugin adds a clean command surface, routing logic, and bounded waiting behavior for Claude.

## Multi-machine deployment

For a multi-node fleet, do not sync raw `~/.gemini` or `~/.hal-gemini-daemon` state between machines.
Instead:

1. sync this repo to each node
2. create the `~/bin` launcher symlinks
3. bootstrap the daemon locally on each node so it copies that node's own Gemini auth and persona
4. validate each node with a short headless `auto` prompt

Included helpers:

- `scripts/fleet_sync.sh prime m4`
- `scripts/fleet_validate.sh prime m4`

Full instructions live in [docs/MULTI_MACHINE.md](docs/MULTI_MACHINE.md).

## Task format

The queue lives at:

```text
~/.hal-gemini-daemon/runtime/tasks/TASKS.json
```

Use the example in [TASKS.example.json](TASKS.example.json) as the base shape.

Important fields:

- `id`
- `status`
- `goal`
- `task_type`
- `workdir`
- `rounds`
- `model`
- `completion_marker`

Optional swarm metadata:

- `parent_task_id`
- `spawned_by`

## Recursive task generation

Any worker can enqueue a follow-on task by emitting a standalone JSON block inside its response:

```json
{"NEW_TASK": {"goal": "Investigate flaky CI behavior", "task_type": "analysis"}}
```

The daemon will:

- parse the JSON block from assistant text
- inherit the parent worker’s runtime settings
- generate a unique child task id
- append the child task to `TASKS.json` as `pending`
- avoid re-adding the same goal/task_type/workdir combination

## Hive mind

The shared memory file lives at:

```text
~/.hal-gemini-daemon/runtime/HIVE_MIND.md
```

Behavior:

- bootstrap creates it if missing
- each completed task appends a 3-sentence summary
- every new worker reads the last 10 non-empty lines before round 1

This gives the swarm a light shared memory layer without copying raw session state between workers.

## Safety model

- full autonomy comes from `--approval-mode=yolo` at launch, not from `settings.json`
- the live `~/.gemini` profile is not overwritten
- MCP allowlists are preflighted and fall back to `__none__`
- a local guardrails policy file is included for obvious catastrophic command patterns

## Validation

Local verification currently covers:

- bootstrap isolation
- persona injection
- rolling context compaction
- recursive task extraction and queue append
- hive mind summary and replay
- completion and failure paths in the runner
- zombie worker reaping and queue-status repair in the daemon scheduler

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
gemini-unchained-daemon doctor
```

## Phase 3 Proven Run

The runtime has already been exercised against a real three-step swarm mission:

- a historian task analyzed a live Cathedral corpus
- the historian emitted a `NEW_TASK` block for a Vex-Murphy follow-on analysis
- a philosopher task consumed `HIVE_MIND.md` and wrote a live essay artifact
- the spawned Vex-Murphy child completed as a third queue item
- daemon reconciliation repaired final queue state after worker exit

Artifacts produced during that live run included:

- `~/.hal-gemini-daemon/runtime/HIVE_MIND.md`
- `<VAULT_ROOT>/10-consciousness/MYTH_BYPASS.md`
- `<VAULT_ROOT>/01-consciousness/MURPHY_EVOLUTION_REPORT.md`

## Notes for publishing

- repo name suggestion: `gemini-unchained-blueprint`
- Python package name remains `gemini-unchained-daemon`
- console scripts installed by `pip`:
  - `gemini-unchained-daemon`
  - `hal-deploy-gemini-daemon`

## Deployment

For a clean standalone GitHub deployment flow, see `docs/DEPLOYMENT.md`.
