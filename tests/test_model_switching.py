"""Regression tests for ACP model switching."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from acp.schema import SetSessionModelResponse

from acp_server.model_config import load_model_catalog
from acp_server.slash_commands import ACPCommandAgentServer


class _Agent:
    pass


class _Client:
    async def session_update(self, **kwargs: Any) -> None:
        pass


def _build_agent(context: Any) -> _Agent:
    agent = _Agent()
    agent.model = context.model
    return agent


class ModelSwitchingTests(unittest.IsolatedAsyncioTestCase):
    def test_anthropic_models_are_picker_only_not_subagent_router_candidates(self) -> None:
        env = {
            "ANTHROPIC_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
            "ACP_ENABLED_MODEL_PROVIDERS": "anthropic,openai",
        }
        with patch.dict("os.environ", env, clear=True):
            catalog = load_model_catalog()
            router_models = catalog.router_models

        self.assertTrue(router_models)
        self.assertEqual({model.provider for model in router_models}, {"openai"})
        self.assertTrue(catalog.subagent_base_model.startswith("openai:"))
        self.assertIn("anthropic:claude-sonnet-5", {model["value"] for model in catalog.acp_models})

    async def test_dedicated_model_rpc_switches_session_and_agent(self) -> None:
        models = [
            {"value": "anthropic:claude-sonnet-5", "name": "Claude Sonnet 5"},
            {"value": "openai:gpt-5.6-terra", "name": "GPT-5.6 Terra"},
        ]
        server = ACPCommandAgentServer(agent=_build_agent, models=models)
        server.on_connect(_Client())
        session = await server.new_session(cwd="/tmp")

        response = await server.set_session_model(
            model_id="openai:gpt-5.6-terra",
            session_id=session.session_id,
        )

        self.assertIsInstance(response, SetSessionModelResponse)
        self.assertEqual(server._session_models[session.session_id], "openai:gpt-5.6-terra")
        self.assertEqual(server._agent.model, "openai:gpt-5.6-terra")


if __name__ == "__main__":
    unittest.main()
