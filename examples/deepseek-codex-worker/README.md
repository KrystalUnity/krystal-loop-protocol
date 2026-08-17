# DeepSeek Codex Worker Example

This example turns a lower-cost DeepSeek model into one bounded KLP worker. It
uses a separate Codex home, an explicit Git workspace, standing worker
instructions, and one assignment file. It does not make the worker a critic or
give it integration authority.

## Prerequisites

- current `codex` and `git` commands on `PATH`;
- a DeepSeek API key already present as `DEEPSEEK_API_KEY`;
- a controller-reviewed assignment;
- a workspace inside a Git worktree, with its base revision recorded.

The launcher rejects non-Git workspaces so the controller can bind base and result
revisions to a Git worktree. DeepSeek documents `https://api.deepseek.com` as its OpenAI-compatible
base URL and `deepseek-v4-flash` as a current model identifier. Check the
provider's current documentation before pinning versions in a long-lived
system.

## Run

```bash
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
workspace="/path/to/git-worktree"
./examples/deepseek-codex-worker/run.sh \
  "$workspace" \
  "$PWD/examples/deepseek-codex-worker/assignment.example.md"
```

By default the launcher creates an ephemeral isolated Codex home and removes it
when the worker exits. Set `KLP_CODEX_HOME` to a dedicated directory only when
you deliberately want to retain that worker profile. The launcher never loads
a credential file and starts Codex with a scrubbed child environment.

## Boundary

The model endpoint supplies inference. The assignment, workspace sandbox,
standing instructions, controller checks, independent critic, and human
decision supply control. A cheaper model does not receive broader authority,
and a successful worker response is not an acceptance verdict.

The assignment's path allow-list is a controller and model instruction, not a
per-file sandbox. `workspace-write` restricts the worker to its workspace but
can still permit edits elsewhere inside that workspace. The controller must
inspect the exact changed-file set and diff before accepting a handover.

Continue with the
[OpenAI-compatible critic example](../openai-compatible-critic/README.md) after
the controller has captured the exact result revision and deterministic
evidence.
