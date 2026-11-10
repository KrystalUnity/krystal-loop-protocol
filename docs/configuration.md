# Configuration

`klp init` writes two files. Your own settings go in
`~/.config/klp/config.json`. The repository gets a `klp.json` with its checks
and critical triggers.

## Your config: models, limits and sandbox

```json
{
  "worker": {
    "name": "deepseek-flash", "family": "deepseek",
    "base_url": "https://api.deepseek.com", "api_key_env": "DEEPSEEK_API_KEY",
    "params": {"max_tokens": 16384, "thinking": {"type": "enabled"}, "reasoning_effort": "high"}
  },
  "critic": {
    "name": "gpt-6.1-sol", "family": "openai",
    "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY",
    "params": {"max_completion_tokens": 16384, "prompt_cache_options": {"mode": "explicit"}}
  },
  "limits": {"cost_usd": 2.0, "max_steps": 100, "repair_steps": 40, "repair_rounds": 2, "time_seconds": 3600},
  "review": {"acceptance": false},
  "sandbox": {"read_only_paths": [], "path": "", "network": false}
}
```

| Key | What it sets |
| --- | --- |
| `worker`, `critic` | One model route each. `family` is what the independence rule compares: the two must differ. |
| `base_url`, `api_key_env` | Any OpenAI-compatible endpoint, including a local one, and the name of the environment variable that holds its key. The key itself is never written to a file. |
| `api` | `"chat"` (the default) for `/chat/completions`, `"responses"` for OpenAI's `/responses`, `"command"` for a local agent CLI. |
| `params` | Passed to the provider as they are. |
| `limits` | Cost per task in USD, worker steps, repair steps, repair rounds and wall-clock seconds. |
| `review.acceptance` | The critic also writes an acceptance test file from the task statement. Same as `--acceptance`. |
| `sandbox.read_only_paths` | Host paths to show inside the sandbox read-only, such as a virtualenv outside the repository. |
| `sandbox.path` | Directories to put first on `PATH` inside the sandbox. |
| `sandbox.network` | Leave `false` unless the checks themselves need the network. |

Use another file with `--config <file>` or the `KLP_CONFIG` environment
variable.

## A critic on a subscription you already hold

A critic route can be an agent CLI that you are signed in to. The review then
adds no metered cost.

```json
"critic": {
  "name": "gemini-4-argon-high", "family": "google", "api": "command",
  "command": ["agy", "--print", "{prompt}", "--mode", "plan", "--model", "gemini-4-argon-high", "--output-format", "json"],
  "reply": "json:response"
}
```

- `command` is the CLI's one-shot invocation. `{prompt}` is replaced with the
  review packet; without it the packet goes to standard input.
- `reply` says where the answer is in the CLI's output: `"text"`,
  `"json:<field>"` or `"ndjson:<field>"`.
- The runner starts the CLI in an empty directory with a minimal environment
  and records its calls as unmetered. Give the CLI its read-only or plan mode
  where it has one.

[`bench/models.json`](../bench/models.json) has working entries for the
Antigravity, Kimi and Qwen CLIs. On the benchmark, Gemini 4 Argon through the
Antigravity CLI matched the metered frontier critic's solve count.

## The repository's `klp.json`

```json
{
  "checks": ["python -m pytest -q"],
  "critical_triggers": ["changes to the billing ledger schema", "authentication or session handling"]
}
```

- `checks` are the commands that must pass when you give no `--check`.
- `critical_triggers` are the project's protected areas in plain words. The
  critic assesses every change against them, and a match ends the run as
  `critical_trigger` for the [Critical path](../EXECUTION_PROFILES.md).

A repository's `klp.json` cannot set model routes, limits or sandbox mounts.
Those come from your own config, so a cloned repository cannot redirect your
keys or open the sandbox.

## Command line

```text
klp init [--config FILE]
klp run "<what should change>" [--task-file FILE] [--check CMD]... [--cap USD]
        [--acceptance] [--no-review] [--json] [--config FILE]
```

| Option | Effect |
| --- | --- |
| `--check CMD` | A command that must pass. Repeat it for several. |
| `--task-file FILE` | Read the task from a file. |
| `--cap USD` | Cost limit for this run. |
| `--acceptance` | Add the acceptance test file to the first review. |
| `--no-review` | Worker only, for comparison. |
| `--json` | Print one result object on standard output for a calling agent. |

Each run writes `.klp/runs/<time>-<task>/` with `receipt.md`, `receipt.json`,
`candidate.patch` and `ledger.jsonl`. The exit code is `0` for `completed` and
`2` for any other state.

## Prices

Costs are calculated from the token usage each provider reports, at the rates
in [`klp/prices.json`](../klp/prices.json). A model with off-peak pricing lists
both tiers and its peak hours, and each call is priced by the hour it ran. A
model missing from the file is reported as unpriced. Add your own models there.
