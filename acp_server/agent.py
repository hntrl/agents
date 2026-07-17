"""Demo coding agent using ACP."""

import asyncio
import logging
import os
from pathlib import Path

from acp import (
    run_agent as run_acp_agent,
)
from acp.schema import (
    SessionMode,
    SessionModeState,
)
from deepagents import SubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, LocalShellBackend, StateBackend
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from deepagents_acp.server import AgentSessionContext
from deepagents_code.mcp_tools import resolve_and_load_mcp_tools
from deepagents_code.tools import fetch_url
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.tools import BaseTool
from langchain_quickjs import CodeInterpreterMiddleware
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import Checkpointer, CompiledStateGraph

from .auto_model import AutoModelMiddleware, ModelChoice
from .ci_middleware import WaitForCIMiddleware
from .local_context import LocalContextMiddleware
from .model_config import load_model_catalog
from .slash_commands import ACPCommandAgentServer

logger = logging.getLogger(__name__)


# Skills shipped with this codebase, located at `<repo root>/skills/`. Resolved
# relative to this source file so it works regardless of the process working
# directory or the ACP session cwd.
_BUNDLED_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# MCP server config shipped with this codebase, located at `<repo root>/.mcp.json`.
# Resolved relative to this source file so it works regardless of the process
# working directory or the ACP session cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUNDLED_MCP_CONFIG = _REPO_ROOT / ".mcp.json"
_BUNDLED_ENV_FILE = _REPO_ROOT / ".env"


def _init_chat_model(model_id: str):
    """Initialize a chat model with provider-specific defaults."""
    if model_id.startswith("openai:"):
        return init_chat_model(
            model_id,
            use_responses_api=True,
            output_version="responses/v1",
        )
    return init_chat_model(model_id)


async def _load_mcp_tools() -> list[BaseTool]:
    """Resolve MCP tools from the bundled ``.mcp.json`` config.

    Loaded once at server startup (inside the async event loop) so the
    synchronous per-session agent factory can close over the resulting tools.
    OAuth-backed servers are skipped with a warning until the user authenticates
    via ``dcode mcp login <server>``; the remaining servers still load. Any
    failure here is non-fatal: the agent simply starts without MCP tools.
    """
    config_path = str(_BUNDLED_MCP_CONFIG) if _BUNDLED_MCP_CONFIG.exists() else None
    try:
        tools, _session_manager, server_infos = await resolve_and_load_mcp_tools(
            explicit_config_path=config_path,
            # This config ships with the repo, so trust it rather than gating it
            # behind dcode's untrusted-project-MCP approval flow.
            trust_project_mcp=True,
        )
    except Exception:
        logger.exception("Failed to load MCP tools; starting without them.")
        return []

    for info in server_infos:
        if info.status == "ok":
            logger.info("MCP server '%s' loaded (%d tools).", info.name, len(info.tools))
        elif info.status == "unauthenticated":
            logger.warning(
                "MCP server '%s' needs authentication. Run `dcode mcp login %s`.",
                info.name,
                info.name,
            )
        elif info.status != "disabled":
            logger.warning(
                "MCP server '%s' unavailable (%s): %s",
                info.name,
                info.status,
                info.error,
            )

    return tools


def _get_skill_sources() -> list[str | tuple[str, str]]:
    """Return global and project skill sources in increasing precedence order."""
    home = Path.home()
    sources: list[str | tuple[str, str]] = []

    # User/global skills shared with other agent tools. These correspond to the
    # client-side `file://skills/` skills resource when provided globally.
    for path, label in [
        (home / ".deepagents" / "agent" / "skills", "User Deepagents"),
        (home / ".agents" / "skills", "User Agents"),
        (home / ".claude" / "skills", "User Claude"),
    ]:
        if path.exists():
            sources.append((str(path), label))

    # Skills bundled with this codebase. Keep this last so repo-specific skills
    # override global skills with the same name.
    sources.append((str(_BUNDLED_SKILLS_DIR), "Project"))
    return sources


def _get_interrupt_config(mode_id: str) -> dict:
    """Get interrupt configuration for a given mode."""
    mode_to_interrupt = {
        "ask_before_edits": {
            "edit_file": {"allowed_decisions": ["approve", "reject"]},
            "write_file": {"allowed_decisions": ["approve", "reject"]},
            "write_todos": {"allowed_decisions": ["approve", "reject"]},
            "execute": {"allowed_decisions": ["approve", "reject"]},
        },
        "accept_edits": {
            "write_todos": {"allowed_decisions": ["approve", "reject"]},
            "execute": {"allowed_decisions": ["approve", "reject"]},
        },
        "accept_everything": {},
    }
    return mode_to_interrupt.get(mode_id, {})


async def _serve_example_agent() -> None:
    """Run example agent from the root of the repository with ACP integration."""
    # Load server-local env first so editor cwd does not hide this repo's .env.
    # Values already present in the process environment still win.
    load_dotenv(_BUNDLED_ENV_FILE)
    load_dotenv()

    checkpointer: Checkpointer = MemorySaver()

    # Resolve MCP tools once here, inside the running event loop, so the sync
    # per-session factory below can close over them.
    mcp_tools = await _load_mcp_tools()

    def build_agent(context: AgentSessionContext) -> CompiledStateGraph:
        """Agent factory based in the given root directory."""
        _root_dir = context.cwd
        interrupt_config = _get_interrupt_config(context.mode)
        skill_sources = _get_skill_sources()

        ephemeral_backend = StateBackend()
        shell_env = os.environ.copy()

        # Use CLIShellBackend for filesystem + shell execution.
        # Provides `execute` tool via FilesystemMiddleware with per-command
        # timeout support.
        shell_backend = LocalShellBackend(
            root_dir=_root_dir,
            inherit_env=True,
            env=shell_env,
        )
        backend = CompositeBackend(
            default=shell_backend,
            routes={
                "/memories/": ephemeral_backend,
                "/conversation_history/": ephemeral_backend,
            },
        )

        model_catalog = load_model_catalog()

        # Override the built-in general-purpose subagent so it picks its own
        # model per session via `AutoModelMiddleware`. The router runs once on
        # the first model call (using the subagent's configured base model) and
        # then locks in one configured candidate for the rest of the session,
        # based on each candidate's `when_to_use` hint.
        auto_router = AutoModelMiddleware(
            models=[
                ModelChoice(
                    model=_init_chat_model(model.value),
                    name=model.key,
                    when_to_use=model.when_to_use,
                )
                for model in model_catalog.router_models
            ],
            default=model_catalog.effective_router_default,
        )

        general_purpose = SubAgent(
            {
                **GENERAL_PURPOSE_SUBAGENT,
                # The router itself runs through this model on the first call,
                # then `AutoModelMiddleware` swaps in the selected candidate.
                "model": model_catalog.subagent_base_model,
                "middleware": [auto_router],
                "skills": skill_sources,
            }
        )

        agent_model = context.model or model_catalog.default_agent_model

        return create_deep_agent(
            # Use an explicit fallback instead of Deep Agent's internal default
            # when the ACP client does not provide a selected model.
            model=_init_chat_model(agent_model),
            tools=[fetch_url, *mcp_tools],
            checkpointer=checkpointer,
            backend=backend,
            interrupt_on=interrupt_config,
            middleware=[
                LocalContextMiddleware(backend=backend),
                WaitForCIMiddleware(),
                CodeInterpreterMiddleware(ptc=["read_file", "glob", "grep"]),
            ],
            subagents=[general_purpose],
            skills=skill_sources,
        )

    modes = SessionModeState(
        current_mode_id="accept_edits",
        available_modes=[
            SessionMode(
                id="ask_before_edits",
                name="Ask before edits",
                description="Ask permission before edits, writes, shell commands, and plans",
            ),
            SessionMode(
                id="accept_edits",
                name="Accept edits",
                description="Auto-accept edit operations, but ask before shell commands and plans",
            ),
            SessionMode(
                id="accept_everything",
                name="Accept everything",
                description="Auto-accept all operations without asking permission",
            ),
        ],
    )

    acp_agent = ACPCommandAgentServer(
        agent=build_agent,
        modes=modes,
        models=load_model_catalog().acp_models,
    )
    await run_acp_agent(acp_agent)


def main() -> None:
    """Run the demo agent."""
    asyncio.run(_serve_example_agent())


if __name__ == "__main__":
    main()
