import importlib
import os
import sys
import threading

from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
import app.tools.agent as agent_module


class FastTool:
    def __init__(self) -> None:
        self.name = "fast_tool"
        self.description = "A fast tool for testing"
        self.called = False

    def __call__(self):
        self.called = True
        return "tool result"


class FakeAgent:
    def __init__(self, tool: FastTool) -> None:
        self.tool = tool
        self.thread_ident = None

    def run(self, prompt: str, callbacks=None) -> str:
        self.thread_ident = threading.get_ident()
        result = self.tool()
        return f"{prompt} -> {result}"


def test_agent_run_endpoint_uses_background_thread(monkeypatch):
    tool = FastTool()
    agent = FakeAgent(tool)
    loop_thread_ident = None

    def fake_get_agent(settings):
        nonlocal loop_thread_ident
        loop_thread_ident = threading.get_ident()
        return agent, [tool]

    monkeypatch.setattr(agent_module, "_get_agent", fake_get_agent)

    client = TestClient(app)
    response = client.post("/agent/run", json={"prompt": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["output"] == "hello -> tool result"
    assert payload["tool"] is None
    assert payload["dataPoints"] == []
    assert tool.called is True
    assert agent.thread_ident is not None
    assert loop_thread_ident is not None
    assert agent.thread_ident != loop_thread_ident


def test_agent_config_uses_runtime_port_default(monkeypatch):
    monkeypatch.delenv("QTICK_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("MCP_BASE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("QTICK_GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    import app.config as config_module
    import langchain_tools.qtick as qtick_module
    import app.tools.agent as agent_mod

    config_module = importlib.reload(config_module)
    qtick_module = importlib.reload(qtick_module)
    agent_mod = importlib.reload(agent_mod)

    assert qtick_module.MCP_BASE == "http://127.0.0.1:10000"

    captured = {}
    real_configure = agent_mod.configure

    def spy_configure(*, base_url: str) -> None:
        captured["base_url"] = base_url
        real_configure(base_url=base_url)

    monkeypatch.setattr(agent_mod, "configure", spy_configure)
    monkeypatch.setattr(agent_mod, "ChatGoogleGenerativeAI", lambda **_: object())
    monkeypatch.setattr(agent_mod, "initialize_agent", lambda **_: object())

    config_module.get_settings.cache_clear()
    agent_mod._get_agent_bundle.cache_clear()

    settings = config_module.Settings()
    agent_mod._get_agent(settings)

    assert captured["base_url"].startswith("http://127.0.0.1:10000")
    assert qtick_module.MCP_BASE == "http://127.0.0.1:10000"


def test_agent_config_local_default(monkeypatch):
    monkeypatch.delenv("QTICK_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("MCP_BASE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("QTICK_RUNTIME_HOST", raising=False)
    monkeypatch.delenv("QTICK_RUNTIME_SCHEME", raising=False)

    import app.config as config_module
    import langchain_tools.qtick as qtick_module

    config_module = importlib.reload(config_module)
    qtick_module = importlib.reload(qtick_module)

    assert config_module.runtime_default_mcp_base_url() == "http://localhost:8000"
    assert qtick_module.MCP_BASE == "http://localhost:8000"
