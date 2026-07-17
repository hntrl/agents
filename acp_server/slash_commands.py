"""ACP slash command registration for the standalone agent server."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from acp.helpers import update_available_commands
from acp.schema import AvailableCommand, SetSessionModelResponse, TextContentBlock
from deepagents_acp.server import AgentServerACP
from langgraph.checkpoint.memory import MemorySaver

from .ci_middleware import WatchCIRequest

logger = logging.getLogger(__name__)

_CI_COMMAND = "ci"
_CI_COMMAND_TEXT = f"/{_CI_COMMAND}"


class ACPCommandAgentServer(AgentServerACP):
    """ACP adapter that advertises slash commands and threads command state."""

    async def new_session(self, *args: Any, **kwargs: Any):  # noqa: ANN201
        """Create a session, then publish ACP available commands."""
        response = await super().new_session(*args, **kwargs)
        asyncio.create_task(self._publish_available_commands(response.session_id))
        return response

    async def _publish_available_commands(self, session_id: str) -> None:
        await asyncio.sleep(0)
        try:
            await self._conn.session_update(
                session_id=session_id,
                update=update_available_commands(
                    [
                        AvailableCommand(
                            name=_CI_COMMAND,
                            description=(
                                "Wait for GitHub CI on the current PR/thread and summarize results."
                            ),
                        )
                    ]
                ),
                source="DeepAgent",
            )
        except Exception:
            logger.exception("Failed to publish ACP slash commands for session %s", session_id)

    async def prompt(self, prompt: list[Any], session_id: str, **kwargs: Any):  # noqa: ANN201
        """Thread ACP command state into the graph before normal prompt handling."""
        command = _parse_ci_command(prompt)
        if command is not None:
            await self._set_watch_ci_state(session_id=session_id, args=command)
        return await super().prompt(prompt=prompt, session_id=session_id, **kwargs)

    async def set_session_model(
        self,
        model_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModelResponse:
        """Handle ACP's dedicated model-switching RPC.

        ``deepagents-acp`` predates this RPC and implements model selection only
        through ``set_config_option``. Route both protocol surfaces through that
        implementation so validation, session state, and agent reset stay in sync.
        """
        await self.set_config_option(
            config_id="model",
            session_id=session_id,
            value=model_id,
            **kwargs,
        )
        return SetSessionModelResponse()

    async def _set_watch_ci_state(self, *, session_id: str, args: str) -> None:
        if self._agent is None:
            self._reset_agent(session_id)

        if self._agent is None:
            msg = "Agent initialization failed"
            raise RuntimeError(msg)

        if getattr(self._agent, "checkpointer", None) is None:
            self._agent.checkpointer = MemorySaver()  # Guarded by getattr check above

        await self._agent.aupdate_state(
            {"configurable": {"thread_id": session_id}},
            {"watch_ci": WatchCIRequest(args=args)},
        )


def _parse_ci_command(prompt: list[Any]) -> str | None:
    if not prompt or not isinstance(prompt[0], TextContentBlock):
        return None

    text = prompt[0].text.strip()
    if text == _CI_COMMAND_TEXT:
        return ""
    if text.startswith(f"{_CI_COMMAND_TEXT} "):
        return text.removeprefix(_CI_COMMAND_TEXT).strip()
    return None
