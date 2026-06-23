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
│   └── example_agent.py     # builds a coding Deep Agent + serves it
├── run_agent.sh             # entrypoint for editors (e.g. Zed)
├── .env.example
└── pyproject.toml
```

## Getting started

Make sure you have [`uv`](https://docs.astral.sh/uv/) installed, then from this
directory:

```sh
uv sync
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

Run it directly (it speaks ACP over stdio):

```sh
uv run python -m acp_server
```

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
rooted at the client's working directory — see `acp_server/example_agent.py`).

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
