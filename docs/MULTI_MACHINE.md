# Multi-Machine Deployment

Use this when you want the same Gemini Unchained repo and daemon surface on multiple machines.

## Rules

- Sync the repo, not raw daemon runtime state.
- Do not copy `~/.gemini` between machines.
- Do not copy `~/.hal-gemini-daemon` between machines.
- Log into Gemini CLI once on each node first.
- Let each node bootstrap its own daemon profile from that node's live `~/.gemini`.

This keeps auth, keychain fallbacks, local trust, and queue state node-local while still giving you the same code and launcher surface everywhere.

## One-command rollout

From the machine that holds the canonical repo checkout:

```bash
./scripts/fleet_sync.sh prime m4
```

What it does per node:

1. `rsync` the repo checkout to the remote target directory
2. install or refresh the `~/bin/gemini-unchained-daemon` and `~/bin/hal-deploy-gemini-daemon` symlinks
3. run the daemon bootstrap locally on that node

By default the remote target directory matches your current local checkout path.
Override it when the remote machines use a different layout:

```bash
./scripts/fleet_sync.sh --target-dir /Users/alex/projects/gemini-unchained-daemon studio laptop
```

## Validation

Run a post-sync check on every node:

```bash
./scripts/fleet_validate.sh prime m4
```

This verifies:

- `gemini` exists on the remote node
- the repo bin launchers exist
- the `~/bin` symlinks point at the repo
- the daemon runtime files exist
- a short headless `auto` prompt returns `OK`

## Model policy

The daemon defaults to `auto` for fleet safety.

Reason:

- preview and Pro lanes can exhaust quota independently of the machine
- a single pinned model can make every node look broken even when the install is fine
- `auto` lets Gemini CLI route to an available lane

If you want a pinned model anyway:

- set `GEMINI_UNCHAINED_DEFAULT_MODEL`
- or set `"model"` on individual tasks

## Notes for shared fleets

- If you also replicate Codex or Claude orchestration across nodes, sync those layers separately.
- The Legion Plugin can point at the local daemon on each machine; it should not bypass the queue by calling `gemini` directly.
