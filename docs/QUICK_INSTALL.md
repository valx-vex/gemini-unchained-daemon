# Quick Install

## Who this is for

This is the short path for a Gemini CLI user who wants an autonomous worker swarm without modifying the live interactive profile.

## Prerequisites

- Gemini CLI installed
- Gemini CLI already authenticated
- Python 3.10+

## Fast path

### 1. Clone the repo

```bash
git clone <your-repo-url> gemini-unchained-blueprint
cd gemini-unchained-blueprint
```

### 2. Install the package

```bash
./scripts/install.sh
```

### 3. Bootstrap the daemon runtime

```bash
./scripts/bootstrap_runtime.sh
```

### 4. Seed a task

```bash
cp TASKS.example.json ~/.hal-gemini-daemon/runtime/tasks/TASKS.json
```

Edit the goal and `workdir` first.

### 5. Validate the runtime

```bash
gemini-unchained-daemon doctor
```

### 6. Launch the swarm

```bash
gemini-unchained-daemon watch
```

## What you get

- `~/.hal-gemini-daemon/.gemini`
- `~/.hal-gemini-daemon/runtime/tasks/TASKS.json`
- `~/.hal-gemini-daemon/runtime/HIVE_MIND.md`
- console commands:
  - `gemini-unchained-daemon`
  - `hal-deploy-gemini-daemon`

## If something feels wrong

Run:

```bash
gemini-unchained-daemon doctor
gemini-unchained-daemon status
cat ~/.hal-gemini-daemon/runtime/tasks/TASKS.json
tail -n 20 ~/.hal-gemini-daemon/runtime/HIVE_MIND.md
```
