# Status

Current posture:

- working beta
- GitHub packaging candidate
- swarm runtime verified locally
- live Phase 3 mission completed successfully

What is implemented:

- isolated daemon bootstrap
- headless Gemini doctor checks
- rolling multi-round context
- recursive `NEW_TASK` spawning
- shared `HIVE_MIND.md` memory
- zombie worker reaping
- queue-status repair from durable worker state

What still deserves real-world shakeout:

- long-running multi-worker contention under heavy task fan-out
- larger public install documentation polish
- broader Linux path and shell validation

## Interplay with Legion

Legion Plugin is now the Claude-side control layer for this runtime.
The plugin enqueues Atlas/Gemini work into the daemon queue and reads back durable task state from the daemon's runtime files.

Operational split:

- Codex HAL/TARS blueprint: Codex execution environment and operator posture
- Gemini Unchained daemon: headless Gemini swarm execution engine
- Legion Plugin: Claude-facing dispatcher and routing layer

## Cluster readiness

- Codex HAL/TARS blueprint: docs-first, private beta, ready for controlled multi-node replication
- Gemini Unchained daemon: live local beta, queue/state model verified, ready for bounded clustered experiments
- Legion Plugin: first backend live through Atlas, ready for plugin-level integration testing before broader cluster rollout
