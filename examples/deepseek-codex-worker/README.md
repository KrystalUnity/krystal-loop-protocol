# DeepSeek Codex Worker Example

This example turns a lower-cost DeepSeek model into one bounded KLP worker. It
uses a separate Codex home, an explicit workspace, standing worker
instructions, and one assignment file. It does not make the worker a critic or
give it integration authority.

## Prerequisites

- a current `codex` CLI on `PATH`;
- a DeepSeek API key already present as `DEEPSEEK_API_KEY`;
- a workspace and assignment reviewed by the controller.

DeepSeek documents `https://api.deepseek.com` as its OpenAI-compatible base URL
and `deepseek-v4-flash` as a current model identifier. Check the provider's
current documentation before pinning versions in a long-lived system.

## Run

```bash
read -rsp "DeepSeek API key: " DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY
./examples/deepseek-codex-worker/run.sh \
  "$PWD/example-workspace" \
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

Continue with the
[OpenAI-compatible critic example](../openai-compatible-critic/README.md) after
the controller has captured the exact result revision and deterministic
evidence.
