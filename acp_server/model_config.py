"""Model catalog and routing configuration for the ACP agent.

The agent has two model-selection surfaces:

* ACP's model picker, which lets the client choose the top-level agent model.
* ``AutoModelMiddleware``, which lets the bundled general-purpose subagent route
  each session to the best configured model.

This module keeps both surfaces backed by the same plain-data catalog. The
catalog intentionally contains only provider/model identifiers and routing hints;
API keys remain provider environment variables consumed by LangChain's provider
integrations.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")
_ALLOWED_PROVIDERS = {"anthropic", "openai", "baseten"}


@dataclass(frozen=True)
class ModelSpec:
    """A configured model exposed by the ACP server.

    Attributes:
        value: LangChain model identifier, usually ``provider:model-name``.
        display_name: Human-readable name shown in ACP clients.
        provider: Provider key used for grouping and env-var filtering.
        key: Stable short identifier for auto-router state.
        when_to_use: Natural-language routing hint. Empty values exclude the
            model from auto-routing.
        enabled: Whether this entry is active.
        requires_env: Optional provider API-key env var. If set, auto-routing
            will only use the model when that env var is present, unless the
            model catalog is explicitly overridden.
        show_in_picker: Whether to expose this model in the ACP model picker.
        auto_route: Whether the general-purpose subagent router may select this
            model when `when_to_use` is also set.
    """

    value: str
    display_name: str
    provider: str
    key: str
    when_to_use: str = ""
    enabled: bool = True
    requires_env: str | None = None
    show_in_picker: bool = True
    auto_route: bool = True

    @property
    def routable(self) -> bool:
        """Return whether this model has enough metadata for auto-routing."""
        return self.enabled and self.auto_route and bool(self.when_to_use)

    def to_acp_model(self) -> dict[str, str]:
        """Return ACP model-picker shape."""
        return {"value": self.value, "name": self.display_name}


@dataclass(frozen=True)
class ModelCatalog:
    """Resolved model configuration for the server."""

    models: tuple[ModelSpec, ...]
    router_default: str
    subagent_base_model: str
    default_agent_model: str

    @property
    def acp_models(self) -> list[dict[str, str]]:
        """Models exposed to ACP clients."""
        return [
            model.to_acp_model()
            for model in self.models
            if model.enabled and model.show_in_picker
        ]

    @property
    def router_models(self) -> list[ModelSpec]:
        """Models that the auto-router may select."""
        return _router_models_for_env(self.models)

    @property
    def effective_router_default(self) -> str:
        """Router fallback key adjusted to the credential-filtered candidates."""
        router_models = self.router_models
        router_keys = {model.key for model in router_models}
        if self.router_default in router_keys:
            return self.router_default
        return router_models[0].key


DEFAULT_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        value="anthropic:claude-sonnet-5",
        display_name="Claude Sonnet 5",
        provider="anthropic",
        key="anthropic_sonnet",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Best Anthropic balance of speed and intelligence for everyday coding, "
            "multi-step research, moderate refactors, and technical writing."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-fable-5",
        display_name="Claude Fable 5",
        provider="anthropic",
        key="anthropic_fable",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Anthropic's most capable widely released model. Use for the hardest "
            "long-running agentic coding, architecture, and synthesis tasks."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-opus-4-8",
        display_name="Claude Opus 4.8",
        provider="anthropic",
        key="anthropic_opus",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Complex agentic coding and enterprise work where strong reasoning is "
            "needed but Fable-level cost or latency is not warranted."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        key="anthropic_haiku",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Fastest Anthropic model. Use for short questions, quick lookups, and "
            "single-file reads where speed matters more than deep reasoning."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        provider="anthropic",
        key="anthropic_sonnet_4_6",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Previous Sonnet generation for compatibility, regression checks, or "
            "when you explicitly want the older balanced Claude behavior."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-opus-4-7",
        display_name="Claude Opus 4.7",
        provider="anthropic",
        key="anthropic_opus_4_7",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
        when_to_use=(
            "Previous Opus generation for compatibility or comparison against "
            "Claude Opus 4.8 and Fable 5."
        ),
    ),
    ModelSpec(
        value="anthropic:claude-mythos-5",
        display_name="Claude Mythos 5 (limited availability)",
        provider="anthropic",
        key="anthropic_mythos",
        requires_env="ANTHROPIC_API_KEY",
        auto_route=False,
    ),
    ModelSpec(
        value="openai:gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
        provider="openai",
        key="openai_sol",
        requires_env="OPENAI_API_KEY",
        when_to_use=(
            "OpenAI flagship for complex professional work, hard reasoning, and "
            "coding. Prefer when maximum OpenAI capability is needed."
        ),
    ),
    ModelSpec(
        value="openai:gpt-5.6-terra",
        display_name="GPT-5.6 Terra",
        provider="openai",
        key="openai_terra",
        requires_env="OPENAI_API_KEY",
        when_to_use=(
            "Balanced OpenAI model for intelligence and cost. Use for routine "
            "coding, research, code review, and multi-step technical work."
        ),
    ),
    ModelSpec(
        value="openai:gpt-5.6-luna",
        display_name="GPT-5.6 Luna",
        provider="openai",
        key="openai_luna",
        requires_env="OPENAI_API_KEY",
        when_to_use=(
            "Cost-sensitive OpenAI model for high-volume, simpler edits, quick "
            "summaries, and straightforward Q&A."
        ),
    ),
    ModelSpec(
        value="openai:gpt-5.5",
        display_name="GPT-5.5",
        provider="openai",
        key="openai_gpt_5_5",
        requires_env="OPENAI_API_KEY",
        auto_route=False,
        when_to_use=(
            "Previous OpenAI frontier model for compatibility, regression checks, "
            "or when you explicitly want GPT-5.5 behavior."
        ),
    ),
    ModelSpec(
        value="openai:gpt-5.4-pro",
        display_name="GPT-5.4 Pro",
        provider="openai",
        key="openai_gpt_5_4_pro",
        requires_env="OPENAI_API_KEY",
        auto_route=False,
        when_to_use=(
            "Previous OpenAI pro model for comparison or compatibility with older "
            "workflows."
        ),
    ),
    ModelSpec(
        value="openai:gpt-5.3-codex",
        display_name="GPT-5.3 Codex",
        provider="openai",
        key="openai_gpt_5_3_codex",
        requires_env="OPENAI_API_KEY",
        auto_route=False,
        when_to_use=(
            "Previous OpenAI Codex-family model for compatibility with older "
            "coding workflows."
        ),
    ),
    ModelSpec(
        value="baseten:deepseek-ai/DeepSeek-V4-Pro",
        display_name="DeepSeek V4 Pro on Baseten",
        provider="baseten",
        key="baseten_deepseek_v4_pro",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Baseten-hosted reasoning model with reasoning enabled by default. Use "
            "for hard coding, analysis, and agentic open-model workflows."
        ),
    ),
    ModelSpec(
        value="baseten:moonshotai/Kimi-K2.7-Code",
        display_name="Kimi K2.7 Code on Baseten",
        provider="baseten",
        key="baseten_kimi_k2_7_code",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Latest Baseten Kimi code model. Use for code generation, repository "
            "edits, tool-heavy tasks, and long-context code understanding."
        ),
    ),
    ModelSpec(
        value="baseten:nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B",
        display_name="Nemotron Ultra on Baseten",
        provider="baseten",
        key="baseten_nemotron_ultra",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Largest Baseten Nemotron reasoning model. Use for demanding open-model "
            "reasoning, planning, and synthesis when latency is less important."
        ),
    ),
    ModelSpec(
        value="baseten:nvidia/Nemotron-120B-A12B",
        display_name="Nemotron Super on Baseten",
        provider="baseten",
        key="baseten_nemotron_super",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Baseten Nemotron reasoning model for strong open-model analysis, code "
            "review, and general technical tasks."
        ),
    ),
    ModelSpec(
        value="baseten:openai/gpt-oss-120b",
        display_name="GPT OSS 120B on Baseten",
        provider="baseten",
        key="baseten_gpt_oss_120b",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Open-weight GPT OSS model on Baseten for general reasoning, coding, "
            "and structured-output workflows."
        ),
    ),
    ModelSpec(
        value="baseten:zai-org/GLM-5.2",
        display_name="GLM 5.2 on Baseten",
        provider="baseten",
        key="baseten_glm_5_2",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Strong Baseten GLM reasoning model with reasoning enabled by default. "
            "Use for balanced coding, analysis, and multilingual tasks."
        ),
    ),
    ModelSpec(
        value="baseten:zai-org/GLM-5.1",
        display_name="GLM 5.1 on Baseten",
        provider="baseten",
        key="baseten_glm_5_1",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Baseten GLM model for routine reasoning, code review, and summaries "
            "when GLM 5.2 is not needed."
        ),
    ),
    ModelSpec(
        value="baseten:moonshotai/Kimi-K2.6",
        display_name="Kimi K2.6 on Baseten",
        provider="baseten",
        key="baseten_kimi_k2_6",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Baseten Kimi model for fast open-weight coding and agentic tasks, "
            "especially where long-context code understanding is useful."
        ),
    ),
    ModelSpec(
        value="baseten:zai-org/GLM-5",
        display_name="GLM 5 on Baseten",
        provider="baseten",
        key="baseten_glm_5",
        requires_env="BASETEN_API_KEY",
        auto_route=False,
        when_to_use=(
            "Cost-conscious Baseten fallback for routine code review, search, and "
            "summarization tasks."
        ),
    ),
)

DEFAULT_ROUTER_DEFAULT = "openai_terra"
DEFAULT_SUBAGENT_BASE_MODEL: str | None = None
DEFAULT_AGENT_MODEL = "openai:gpt-5.6-terra"


def load_model_catalog() -> ModelCatalog:
    """Load model configuration from defaults plus environment overrides.

    Environment variables:
        ACP_MODEL_CONFIG: JSON list of model objects, or an object with
            ``models``, ``router_default``, and ``subagent_base_model`` keys.
            Supplying this replaces the built-in default model list.
        ACP_ENABLED_MODEL_PROVIDERS: Comma-separated provider allowlist applied
            after defaults/config are loaded, e.g. ``anthropic,openai``.
        ACP_DISABLE_DEFAULT_MODELS: If true, starts with no built-in models. Use
            with ``ACP_MODEL_CONFIG`` to provide a fully custom catalog.
        ACP_DEFAULT_MODEL: Top-level agent model to use when the ACP client does
            not provide an explicit selected model.
        ACP_ROUTER_DEFAULT: Router model key to use as fallback.
        ACP_SUBAGENT_BASE_MODEL / ACP_ROUTER_MODEL: Model used for the router's
            first call before ``AutoModelMiddleware`` swaps in a selected model.
    """
    use_defaults = not _env_flag("ACP_DISABLE_DEFAULT_MODELS")
    models = list(DEFAULT_MODELS if use_defaults else ())
    default_agent_model = os.getenv("ACP_DEFAULT_MODEL", DEFAULT_AGENT_MODEL)
    router_default = os.getenv("ACP_ROUTER_DEFAULT", DEFAULT_ROUTER_DEFAULT)
    subagent_base_model = os.getenv("ACP_SUBAGENT_BASE_MODEL") or os.getenv(
        "ACP_ROUTER_MODEL"
    )

    raw_config = os.getenv("ACP_MODEL_CONFIG")
    if raw_config:
        parsed = _parse_model_config(raw_config)
        models = list(parsed.get("models", models))
        if "default_agent_model" in parsed and parsed["default_agent_model"] is not None:
            default_agent_model = str(parsed["default_agent_model"])
        if "router_default" in parsed and parsed["router_default"] is not None:
            router_default = str(parsed["router_default"])
        if "subagent_base_model" in parsed:
            value = parsed["subagent_base_model"]
            subagent_base_model = str(value) if value is not None else None

    models = _filter_enabled_providers(models)
    models = _dedupe_model_keys(models)

    if not models:
        msg = "No ACP models are configured"
        raise ValueError(msg)
    if not any(model.routable for model in models):
        msg = "At least one ACP model must include when_to_use so the subagent router can run"
        raise ValueError(msg)

    router_keys = {model.key for model in models if model.routable}
    if router_default not in router_keys:
        fallback = next((model.key for model in models if model.routable), models[0].key)
        logger.warning(
            "Configured ACP_ROUTER_DEFAULT %r is not routable; using %r instead.",
            router_default,
            fallback,
        )
        router_default = fallback

    router_models = _router_models_for_env(models)
    router_models_by_key = {model.key: model for model in router_models}
    effective_router_default = (
        router_default if router_default in router_models_by_key else router_models[0].key
    )
    if subagent_base_model is None:
        subagent_base_model = router_models_by_key[effective_router_default].value

    return ModelCatalog(
        models=tuple(models),
        router_default=router_default,
        subagent_base_model=subagent_base_model,
        default_agent_model=default_agent_model,
    )


def _parse_model_config(raw_config: str) -> dict[str, Any]:
    """Parse ``ACP_MODEL_CONFIG`` as plain JSON configuration."""
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        msg = "ACP_MODEL_CONFIG must be valid JSON"
        raise ValueError(msg) from exc

    if isinstance(parsed, list):
        return {"models": [_model_from_mapping(item) for item in parsed]}
    if isinstance(parsed, dict):
        result: dict[str, Any] = {}
        if "models" in parsed:
            models = parsed["models"]
            if not isinstance(models, list):
                msg = "ACP_MODEL_CONFIG.models must be a list"
                raise ValueError(msg)
            result["models"] = [_model_from_mapping(item) for item in models]
        if "default_agent_model" in parsed:
            result["default_agent_model"] = parsed["default_agent_model"]
        if "router_default" in parsed:
            result["router_default"] = parsed["router_default"]
        if "subagent_base_model" in parsed:
            result["subagent_base_model"] = parsed["subagent_base_model"]
        return result

    msg = "ACP_MODEL_CONFIG must be a JSON list or object"
    raise ValueError(msg)


def _model_from_mapping(item: Any) -> ModelSpec:
    """Build a ``ModelSpec`` from a JSON object."""
    if not isinstance(item, dict):
        msg = "Each ACP model config entry must be an object"
        raise ValueError(msg)

    value = _required_str(item, "value")
    provider = str(item.get("provider") or value.split(":", 1)[0])
    if provider not in _ALLOWED_PROVIDERS:
        msg = f"ACP model config provider must be one of {sorted(_ALLOWED_PROVIDERS)}"
        raise ValueError(msg)
    display_name = str(item.get("name") or item.get("display_name") or value)
    key = str(item.get("key") or _make_model_key(provider, value))
    requires_env = item.get("requires_env")
    if requires_env is not None and not isinstance(requires_env, str):
        msg = "ACP model config requires_env must be a string or null"
        raise ValueError(msg)

    return ModelSpec(
        value=value,
        display_name=display_name,
        provider=provider,
        key=key,
        when_to_use=str(item.get("when_to_use") or ""),
        enabled=bool(item.get("enabled", True)),
        requires_env=requires_env,
        show_in_picker=_bool_from_config(item, "show_in_picker", True),
        auto_route=_bool_from_config(item, "auto_route", True),
    )


def _bool_from_config(item: dict[str, Any], key: str, default: bool) -> bool:
    value = item.get(key, default)
    if isinstance(value, bool):
        return value
    msg = f"ACP model config entry {key!r} must be a boolean"
    raise ValueError(msg)


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        msg = f"ACP model config entry requires a non-empty {key!r} string"
        raise ValueError(msg)
    return value


def _make_model_key(provider: str, value: str) -> str:
    raw = value.split(":", 1)[1] if ":" in value else value
    normalized = _MODEL_NAME_RE.sub("_", raw).strip("_").lower()
    return f"{provider}_{normalized}" if normalized else provider


def _router_models_for_env(models: tuple[ModelSpec, ...] | list[ModelSpec]) -> list[ModelSpec]:
    """Return routable models, avoiding providers without visible credentials."""
    routable = [model for model in models if model.routable]
    configured = [model for model in routable if _env_is_present(model.requires_env)]

    # When at least one provider credential is present, avoid auto-routing to
    # providers that cannot authenticate. If no credentials are visible at all,
    # keep every routable model so startup behavior stays transparent and users
    # still get the provider's normal missing-key error on first use.
    if configured:
        return configured
    return routable


def _filter_enabled_providers(models: list[ModelSpec]) -> list[ModelSpec]:
    raw = os.getenv("ACP_ENABLED_MODEL_PROVIDERS")
    if not raw:
        return models
    allowed = {provider.strip().lower() for provider in raw.split(",") if provider.strip()}
    if not allowed:
        return models
    return [model for model in models if model.provider.lower() in allowed]


def _dedupe_model_keys(models: list[ModelSpec]) -> list[ModelSpec]:
    seen: set[str] = set()
    deduped: list[ModelSpec] = []
    for model in models:
        if model.key in seen:
            msg = f"Duplicate ACP model key: {model.key!r}"
            raise ValueError(msg)
        seen.add(model.key)
        deduped.append(model)
    return deduped


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def _env_is_present(name: str | None) -> bool:
    return name is None or bool(os.getenv(name))
