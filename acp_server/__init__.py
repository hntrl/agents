"""A standalone ACP server that runs a Deep Agent via the published deepagents-acp.

The ACP bridge itself lives in the published ``deepagents-acp`` package
(``deepagents_acp.server.AgentServerACP``). This project only wires up an agent
and serves it. Those names are re-exported here for convenience.
"""

from deepagents_acp.server import AgentServerACP, AgentSessionContext

__all__ = ["AgentServerACP", "AgentSessionContext"]
