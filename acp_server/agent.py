"""Demo coding agent using ACP."""

import asyncio
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
from deepagents_acp.server import AgentServerACP, AgentSessionContext
from deepagents_code.tools import fetch_url
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_quickjs import CodeInterpreterMiddleware
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import Checkpointer, CompiledStateGraph

from .auto_model import AutoModelMiddleware, ModelChoice
from .local_context import LocalContextMiddleware


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

    # Project-local skills relative to the ACP session cwd. Keep this last so
    # repo-specific skills override global skills with the same name.
    sources.append(("skills/", "Project"))
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
    load_dotenv()

    checkpointer: Checkpointer = MemorySaver()

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

        # Override the built-in general-purpose subagent so it picks its own
        # model per session via `AutoModelMiddleware`. The router runs once on
        # the first model call (using the subagent's configured model) and
        # then locks in one of the candidates below for the rest of the
        # session, based on each candidate's `when_to_use` hint.
        auto_router = AutoModelMiddleware(
            models=[
                ModelChoice(
                    model=init_chat_model("anthropic:claude-haiku-4-5"),
                    name="haiku",
                    when_to_use=(
                        "Short, simple questions, quick lookups, and "
                        "single-file reads where speed matters more than "
                        "deep reasoning."
                    ),
                ),
                ModelChoice(
                    model=init_chat_model("anthropic:claude-sonnet-4-6"),
                    name="sonnet",
                    when_to_use=(
                        "Everyday coding and research tasks: multi-step "
                        "searches, moderate refactors, summarizing a few "
                        "files. The default balanced choice."
                    ),
                ),
                ModelChoice(
                    model=init_chat_model("anthropic:claude-opus-4-8"),
                    name="opus",
                    when_to_use=(
                        "Hard reasoning, large refactors spanning many "
                        "files, architectural analysis, or anything "
                        "requiring careful multi-step planning."
                    ),
                ),
            ],
            default="sonnet",
        )

        general_purpose = SubAgent(
            {
                **GENERAL_PURPOSE_SUBAGENT,
                # The router itself runs through this model on the first call,
                # then `AutoModelMiddleware` swaps in the selected candidate.
                "model": "anthropic:claude-haiku-4-5",
                "middleware": [auto_router],
                "skills": skill_sources,
            }
        )

        return create_deep_agent(
            # Falls back to Deep Agent default model if not provided
            model=context.model,
            tools=[fetch_url],
            checkpointer=checkpointer,
            backend=backend,
            interrupt_on=interrupt_config,
            middleware=[
                LocalContextMiddleware(backend=backend),
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

    # Define available models for dynamic switching
    baseten_models = [
        {"value": "baseten:moonshotai/Kimi-K2.6", "name": "Kimi-K2.6"},
        {"value": "baseten:zai-org/GLM-5", "name": "GLM-5"},
        {"value": "baseten:zai-org/GLM-5.2", "name": "GLM-5.2"},
    ]
    anthropic_models = [
        {"value": "anthropic:claude-opus-4-8", "name": "Claude Opus 4.8"},
        {"value": "anthropic:claude-opus-4-7", "name": "Claude Opus 4.7"},
        {"value": "anthropic:claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        {"value": "anthropic:claude-haiku-4-5", "name": "Claude Haiku 4.5"},
    ]
    openai_models = [
        {"value": "openai:gpt-5.5", "name": "GPT-5.5"},
        {"value": "openai:gpt-5.4-pro", "name": "GPT-5.4 Pro"},
        {"value": "openai:gpt-5.3-codex", "name": "GPT-5.3 Codex"},
    ]
    models = baseten_models + anthropic_models + openai_models

    acp_agent = AgentServerACP(agent=build_agent, modes=modes, models=models)
    await run_acp_agent(acp_agent)


def main() -> None:
    """Run the demo agent."""
    asyncio.run(_serve_example_agent())


if __name__ == "__main__":
    main()
