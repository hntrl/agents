# acp-server

A standalone [Agent Client Protocol (ACP)](https://agentclientprotocol.com/overview/introduction)
server that runs a Python [Deep Agent](https://docs.langchain.com/oss/python/deepagents/overview)
inside any ACP-compatible editor (such as [Zed](https://zed.dev/)).

The ACP bridge itself is **not** reimplemented here — it uses the published
[`deepagents-acp`](https://pypi.org/project/deepagents-acp/) package
(`deepagents_acp.server.AgentServerACP`). This project just wires up an agent
and serves it over stdio, so you get HITL permission prompts, model/mode
switching, multimodal input, and MCP support for free.

## Layout

```
acp-server/
├── acp_server/
│   ├── __init__.py          # re-exports AgentServerACP/AgentSessionContext from deepagents-acp
│   ├── __main__.py          # python -m acp_server
│   ├── agent.py             # builds a coding Deep Agent + serves it
│   ├── auto_model.py        # subagent model-router middleware
│   └── model_config.py      # shared ACP/router model catalog
├── run_agent.sh             # entrypoint for editors (e.g. Zed)
├── .env.example
└── pyproject.toml
```

## Getting started

Make sure you have [`uv`](https://docs.astral.sh/uv/) installed, then from this
directory:

```sh
uv sync
cp .env.example .env   # then add the provider API keys you want to use
```

Provider credentials are read by the LangChain integrations from environment
variables. Add only the keys for providers you plan to use:

- `ANTHROPIC_API_KEY` for Claude models
- `OPENAI_API_KEY` for OpenAI models
- `BASETEN_API_KEY` for Baseten model APIs or dedicated deployments

Run it directly (it speaks ACP over stdio):

```sh
uv run python -m acp_server
```

## Model configuration

The server ships with a shared model catalog for the ACP model picker and the
bundled general-purpose subagent router. The catalog tracks current and recent
Anthropic, OpenAI, and Baseten frontier/coding/reasoning models, including older
compatibility entries such as Claude Sonnet 4.6 and GPT-5.5.

By default, the ACP picker shows the full built-in catalog so you can manually
select a specific current or older model. The subagent router is OpenAI-only by
default (`gpt-5.6-terra`, `gpt-5.6-sol`, and `gpt-5.6-luna`) so you
can explicitly opt other providers into routing only when needed.

Useful environment overrides:

- `ACP_DEFAULT_MODEL=openai:gpt-5.6-terra` changes the top-level agent fallback
  used when the ACP client does not provide an explicit selected model.
- `ACP_ENABLED_MODEL_PROVIDERS=anthropic,openai` filters the default catalog by
  provider. Supported default provider keys are `anthropic`, `openai`, and
  `baseten`.
- `ACP_ROUTER_DEFAULT=openai_terra` changes the auto-router fallback model key.
- `ACP_SUBAGENT_BASE_MODEL=openai:gpt-5.6-terra` changes the model used for
  the router's first call before a session model is selected. If unset, the
  server uses the effective router default after provider credential filtering.
  `ACP_ROUTER_MODEL` is accepted as a backwards-readable alias when
  `ACP_SUBAGENT_BASE_MODEL` is unset.
- `ACP_DISABLE_DEFAULT_MODELS=true` starts with no built-in models. Use this with
  `ACP_MODEL_CONFIG` for a fully custom catalog.
- `ACP_MODEL_CONFIG` replaces the built-in catalog with JSON. It may be a list of
  model entries or an object with `models`, `default_agent_model`,
  `router_default`, and `subagent_base_model` keys.

Example `ACP_MODEL_CONFIG`:

```json
{
  "default_agent_model": "openai:gpt-5.6-terra",
  "router_default": "sonnet",
  "subagent_base_model": "anthropic:claude-sonnet-5",
  "models": [
    {
      "value": "anthropic:claude-sonnet-5",
      "name": "Claude Sonnet 5",
      "provider": "anthropic",
      "key": "sonnet",
      "requires_env": "ANTHROPIC_API_KEY",
      "show_in_picker": true,
      "auto_route": true,
      "when_to_use": "Balanced default for coding, research, and multi-step work."
    },
    {
      "value": "anthropic:claude-fable-5",
      "name": "Claude Fable 5",
      "provider": "anthropic",
      "key": "fable",
      "requires_env": "ANTHROPIC_API_KEY",
      "show_in_picker": true,
      "auto_route": true,
      "when_to_use": "Hard long-running agentic coding, architecture, and synthesis tasks."
    },
    {
      "value": "openai:gpt-5.6-sol",
      "name": "GPT-5.6 Sol",
      "provider": "openai",
      "key": "sol",
      "requires_env": "OPENAI_API_KEY",
      "show_in_picker": true,
      "auto_route": true,
      "when_to_use": "OpenAI flagship for complex professional reasoning and coding."
    },
    {
      "value": "baseten:moonshotai/Kimi-K2.7-Code",
      "name": "Kimi K2.7 Code on Baseten",
      "provider": "baseten",
      "key": "kimi_code",
      "requires_env": "BASETEN_API_KEY",
      "show_in_picker": true,
      "auto_route": true,
      "when_to_use": "Fast open-weight coding and long-context repository tasks."
    }
  ]
}
```

Set `show_in_picker` to expose or hide a model in ACP clients. Set `auto_route`
to control whether the general-purpose subagent router may select it. Entries
without `when_to_use` are never used by the subagent auto-router.

### Use it in Zed

Add to your Zed `settings.json` (use the absolute path):

```json
{
  "agent_servers": {
    "ACP Server": {
      "type": "custom",
      "command": "/absolute/path/to/agents/acp-server/run_agent.sh"
    }
  }
}
```

Make sure the entrypoint is executable:

```sh
chmod +x run_agent.sh
```

## Serve your own agent

`AgentServerACP` comes from the published `deepagents-acp` package and accepts
either a compiled agent or a factory
`Callable[[AgentSessionContext], CompiledStateGraph]` (so the agent can be
rooted at the client's working directory — see `acp_server/agent.py`).

```python
import asyncio

from acp import run_agent
from deepagents import create_deep_agent
from deepagents_acp.server import AgentServerACP
from langgraph.checkpoint.memory import MemorySaver


async def main() -> None:
    agent = create_deep_agent(
        system_prompt="You are a helpful assistant",
        checkpointer=MemorySaver(),
    )
    await run_agent(AgentServerACP(agent))


if __name__ == "__main__":
    asyncio.run(main())
```
