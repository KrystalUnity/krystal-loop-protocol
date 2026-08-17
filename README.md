# Krystal Loop Protocol

Use fast AI agents for the grunt work. Use a lead agent and real checks to keep
the project coherent, working, and under your control.

AI coding agents can produce a lot of code quickly. The harder problem begins
after the first impressive demo: agents lose context, overlap each other's
changes, trust confident summaries, reopen solved problems, and quietly break
features that worked yesterday.

Krystal Loop Protocol (KLP) is a practical operating pattern for continuing to
build with multiple AI agents without handing them control of the project.

## The 90-Second Version

1. **Scope it.** Write down the outcome, allowed files, forbidden actions,
   checks, budget, and stop conditions.
2. **Split it.** Give each worker one small outcome that can be judged on its
   own.
3. **Build it.** The worker returns the exact revision and a factual handover,
   not its own pass verdict.
4. **Check it.** Run tests, linters, builds, or other deterministic checks
   before asking another model what it thinks.
5. **Critique it.** A fresh, read-only critic reviews the exact revision against
   the original task and direct evidence.
6. **Repair it.** Fix blocking findings within a declared time, cost, and round
   limit. Stop when the scope changes.
7. **Integrate it.** Treat the combined system as a new artifact and check it
   again.
8. **Decide it.** A person decides whether anything is merged, released,
   deployed, purchased, or activated.

## What This Prevents

| Common agent failure | KLP response |
| --- | --- |
| Two agents edit the same shared file. | Give each worker an explicit file and action boundary. |
| A worker says its own work is complete. | Separate factual handover from independent acceptance. |
| A critic reviews an outdated build. | Bind every verdict to an exact artifact revision. |
| Agents keep looping without improvement. | Stop on repeated findings, exhausted budgets, or a plateau. |
| Unit changes pass but break when combined. | Review integration as a new artifact. |
| A test or agent message is treated as permission to deploy. | Keep live actions behind an explicit human decision. |

## Start With One Prompt

Give this to the lead agent before a multi-agent build:

```text
Work under Krystal Loop Protocol Core.

Before changing files, write a bounded task contract containing:
- the exact outcome;
- allowed and protected paths;
- forbidden actions and live side effects;
- deterministic checks and required evidence;
- time, cost, and repair-round limits;
- conditions that require stopping for human review.

Split the task into independently judgeable work units. Workers must return
factual handovers tied to exact revisions and must not certify their own work.
Run deterministic checks before independent, read-only criticism. Treat the
integrated result as a new artifact. Never interpret an agent result, message,
test, or receipt as permission to merge, deploy, spend, contact customers, or
change a live system.
```

KLP does not require a special model, database, vector store, or message bus.
You can start with Git and Markdown files, then add durable coordination when
the project needs it.

## Read Next

- [KLP Core protocol](PROTOCOL.md)
- [Instructions for AI agents and orchestrators](AI_AGENT_INTEGRATION.md)
- [Optional runtime profiles](RUNTIME_PROFILES.md)
- [Safety and limits](SAFETY_AND_LIMITS.md)
- [Hermes Kanban adapter example](adapters/hermes-kanban.md)

## What KLP Is Not

KLP is not an autonomous software factory, deployment platform, model router,
or claim that tests prove a product has no defects. It is a portable way to
bound multi-agent work, retain useful evidence, and make uncertainty visible.

KLP is inspired by public builder/critic systems such as the
[Gauntlet Loop](https://somethingbig.ai/gauntlet-loop). It does not claim to
invent multi-agent coding, independent review, or automated testing. Its focus
is what happens after the demo, when a real project must remain understandable
and working across many changes.

## Project Status

This repository is an early documentation-first reference draft. Portable
schemas, executable fixtures, and a synthetic fail-review-repair example are
planned before a stable KLP Core release.

## License

Krystal Loop Protocol is licensed under the
[GNU Affero General Public License v3.0 only](LICENSE) (`AGPL-3.0-only`).
