"""AutoModelMiddleware: pick a session model from the initial input.

`AutoModelMiddleware` takes a list of candidate chat models, each paired with
a natural-language ``when_to_use`` hint. On the first model call of a session
it asks the *current* model to read the initial user input and choose the best
candidate. That choice is stored in agent state and reused for the rest of the
session, so the router runs at most once per thread.

Example:
    ```python
    from langchain.chat_models import init_chat_model
    from deepagents_acp.auto_model import AutoModelMiddleware, ModelChoice

    middleware = AutoModelMiddleware(
        models=[
            ModelChoice(
                model=init_chat_model("anthropic:claude-haiku-4"),
                name="haiku",
                when_to_use="Short, simple questions and quick lookups.",
            ),
            ModelChoice(
                model=init_chat_model("anthropic:claude-opus-4-6"),
                name="opus",
                when_to_use="Hard reasoning, large refactors, multi-step plans.",
            ),
        ],
    )

    agent = create_deep_agent(model="anthropic:claude-sonnet-4", middleware=[middleware])
    ```

The middleware needs a current model to route with — it does not require any
particular provider. The candidate models can span providers; the chosen
model instance is supplied by the caller and never serialized.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command
from pydantic import BaseModel, Field, create_model

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AnyMessage

logger = logging.getLogger(__name__)


def _keep_first(existing: str | None, new: str | None) -> str | None:
    """State reducer: lock in the first non-null selection for the session.

    Once a model has been chosen for a thread, later updates are ignored so
    the session does not flip models mid-conversation.
    """
    return existing if existing is not None else new


class AutoModelState(AgentState):
    """Agent state extended with the auto-selected model key.

    `selected_model` holds the `name` of the chosen `ModelChoice`. It is set
    once (guarded by `_keep_first`) and then read on every subsequent model
    call. Storing the *name* — not the model instance — keeps the value
    checkpoint-serializable.
    """

    selected_model: Annotated[str | None, _keep_first]


@dataclass
class ModelChoice:
    """A candidate model paired with guidance on when to route to it.

    Attributes:
        model: The chat model instance to use when this choice is selected.
        name: Stable identifier for the choice. Surfaced to the router and
            stored in state, so it must be unique within a middleware.
        when_to_use: Natural-language description of the inputs this model is
            best suited for. Shown verbatim to the routing model.
    """

    model: BaseChatModel
    name: str
    when_to_use: str


DEFAULT_ROUTER_PROMPT = (
    "You are a model router. Read the user's initial request and choose the "
    "single best model to handle the entire session from the options below. "
    "Weigh each option's 'when to use' guidance against the request.\n\n"
    "Options:\n{options}"
)


def _first_human_text(messages: Sequence[AnyMessage]) -> str:
    """Return the text of the first human message, or empty string.

    The router decides from the *initial* input, which is the first human
    turn in the thread. Non-text content blocks are flattened to their text.
    """
    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            # Multimodal content: concatenate any text parts.
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            return "\n".join(parts)
    return ""


class AutoModelMiddleware(AgentMiddleware[AutoModelState, Any, Any]):
    """Choose a session model from the initial input using the current model.

    On the first model call of a thread, the middleware asks the current
    (configured) model to pick the best candidate for the user's initial
    request, given each candidate's `when_to_use` hint. The choice is written
    to `selected_model` in state and reused for every later call, so routing
    happens at most once per session.

    If routing cannot produce a selection — empty input, a router exception,
    or (defensively) an unrecognized reply — the middleware falls back to
    `default` (or the first candidate) for the current call but does **not**
    persist that selection. The next turn gets another chance to route, so a
    transient failure does not pin the thread to the default for the rest of
    the session.
    """

    state_schema = AutoModelState

    def __init__(
        self,
        models: Sequence[ModelChoice],
        *,
        default: str | None = None,
        router_prompt: str = DEFAULT_ROUTER_PROMPT,
    ) -> None:
        """Initialize the middleware.

        Args:
            models: Candidate models with `when_to_use` guidance. Must be
                non-empty, with unique `name` values.
            default: `name` of the choice to fall back to when routing cannot
                produce a valid selection. Defaults to the first candidate.
            router_prompt: Template for the router system prompt. Must contain
                an `{options}` placeholder.

        Raises:
            ValueError: If `models` is empty, names are not unique, `default`
                is not a known name, or `router_prompt` lacks `{options}`.
        """
        super().__init__()
        if not models:
            msg = "AutoModelMiddleware requires at least one ModelChoice"
            raise ValueError(msg)
        by_name: dict[str, ModelChoice] = {}
        for choice in models:
            if choice.name in by_name:
                msg = f"Duplicate ModelChoice name: {choice.name!r}"
                raise ValueError(msg)
            by_name[choice.name] = choice
        if default is not None and default not in by_name:
            msg = f"default {default!r} is not one of {sorted(by_name)}"
            raise ValueError(msg)
        if "{options}" not in router_prompt:
            msg = "router_prompt must contain an '{options}' placeholder"
            raise ValueError(msg)

        self._choices = list(models)
        self._by_name = by_name
        self._default = default or self._choices[0].name
        self._router_prompt = router_prompt
        self._router_schema = self._build_router_schema()

    def _build_router_schema(self) -> type[BaseModel]:
        """Build a structured-output schema constraining the router's choice.

        The `choice` field is a `Literal` over the known choice names, so a
        provider that honors structured output cannot return an out-of-set
        value and no free-text parsing is needed.
        """
        names = tuple(self._by_name)
        choice_type = Literal[names]  # type: ignore[valid-type]
        return create_model(
            "RouterDecision",
            choice=(
                choice_type,
                Field(description="Name of the single best model to use."),
            ),
        )

    def _options_block(self) -> str:
        """Render the candidate list for the router prompt."""
        return "\n".join(f"- {c.name}: {c.when_to_use}" for c in self._choices)

    def _route_messages(self, initial_input: str) -> list[AnyMessage]:
        """Build the messages handed to the router model."""
        system = self._router_prompt.format(options=self._options_block())
        return [
            SystemMessage(content=system),
            HumanMessage(content=f"Initial request:\n{initial_input}"),
        ]

    def _route(self, model: BaseChatModel, initial_input: str) -> str:
        """Ask the model to choose a candidate via structured output.

        Returns the chosen name. A `Literal`-constrained schema guarantees the
        result is one of the known names.
        """
        structured = model.with_structured_output(self._router_schema)
        decision = structured.invoke(self._route_messages(initial_input))
        return self._decision_name(decision)

    async def _aroute(self, model: BaseChatModel, initial_input: str) -> str:
        """Async variant of `_route`."""
        structured = model.with_structured_output(self._router_schema)
        decision = await structured.ainvoke(self._route_messages(initial_input))
        return self._decision_name(decision)

    def _decision_name(self, decision: Any) -> str:
        """Extract the chosen name from a structured router decision."""
        if isinstance(decision, dict):
            return str(decision["choice"])
        return str(decision.choice)

    def _resolve(self, name: str | None) -> ModelChoice:
        """Return the chosen `ModelChoice`, falling back to the default.

        An unknown `name` should be unreachable in normal use — the router's
        `Literal`-constrained schema rejects out-of-set values, and persisted
        names came from a prior successful route. Reaching the fallback here
        therefore indicates either a provider that ignored structured output
        or state from an older middleware configuration; log it loudly so the
        silent default isn't invisible.
        """
        if name is not None and name in self._by_name:
            return self._by_name[name]
        if name is not None:
            logger.warning(
                "AutoModelMiddleware: unknown selected_model %r; using default %r. Known names: %s",
                name,
                self._default,
                sorted(self._by_name),
            )
        return self._by_name[self._default]

    def _selected_from_state(self, request: ModelRequest) -> str | None:
        """Read a previously stored selection from the request's state."""
        state = request.state
        if isinstance(state, dict):
            value = state.get("selected_model")
            return value if isinstance(value, str) else None
        return None

    def _apply(
        self,
        request: ModelRequest,
        selected_name: str,
    ) -> ModelRequest:
        """Override the request's model with the resolved choice."""
        choice = self._resolve(selected_name)
        return request.override(model=choice.model)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | ExtendedModelResponse:
        """Route on first call, then reuse the session's chosen model.

        Returns:
            The downstream `ModelResponse`. When routing actually succeeds,
            the response is wrapped in an `ExtendedModelResponse` carrying a
            `Command` that persists the selection to state. If routing is
            skipped (no input) or fails (router exception), the current call
            uses the default but nothing is persisted — the next turn gets
            another chance to route.
        """
        existing = self._selected_from_state(request)
        if existing is not None:
            return handler(self._apply(request, existing))

        initial_input = _first_human_text(request.messages)
        if not initial_input:
            logger.debug("No initial human input found; using default %r", self._default)
            return handler(self._apply(request, self._default))

        try:
            selected_name = self._route(request.model, initial_input)
        except Exception:  # routing must never crash the call
            logger.exception(
                "AutoModelMiddleware routing failed; using default %r without "
                "persisting (next turn will retry routing)",
                self._default,
            )
            return handler(self._apply(request, self._default))

        response = handler(self._apply(request, selected_name))
        return _persist(response, selected_name)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse | ExtendedModelResponse:
        """Async variant of `wrap_model_call`.

        Returns:
            The downstream `ModelResponse`, wrapped with a persistence
            `Command` only when routing actually succeeded. See
            `wrap_model_call` for the failure-handling rationale.
        """
        existing = self._selected_from_state(request)
        if existing is not None:
            return await handler(self._apply(request, existing))

        initial_input = _first_human_text(request.messages)
        if not initial_input:
            logger.debug("No initial human input found; using default %r", self._default)
            return await handler(self._apply(request, self._default))

        try:
            selected_name = await self._aroute(request.model, initial_input)
        except Exception:  # routing must never crash the call
            logger.exception(
                "AutoModelMiddleware routing failed; using default %r without "
                "persisting (next turn will retry routing)",
                self._default,
            )
            return await handler(self._apply(request, self._default))

        response = await handler(self._apply(request, selected_name))
        return _persist(response, selected_name)


def _persist(
    response: ModelResponse,
    selected_name: str,
) -> ExtendedModelResponse:
    """Wrap a response with a `Command` that records the model selection.

    The `_keep_first` reducer on `selected_model` ensures only the initial
    selection sticks for the session.
    """
    return ExtendedModelResponse(
        model_response=response,
        command=Command(update={"selected_model": selected_name}),
    )
