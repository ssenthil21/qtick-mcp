import importlib
import os
import sys
import threading

from fastapi.testclient import TestClient
from google.api_core.exceptions import NotFound as GoogleAPINotFound

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
import app.tools.agent as agent_module


from app.services.conversation_memory import ConversationMemoryStore, conversation_memory
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
        self.prompts: list[str] = []

    def run(self, prompt: str, callbacks=None) -> str:
        self.thread_ident = threading.get_ident()
        self.prompts.append(prompt)
        result = self.tool()
        return f"{prompt} -> {result}"


class MissingModelAgent:
    def run(self, prompt: str, callbacks=None) -> str:
        raise GoogleAPINotFound("models/missing")


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
    assert payload["requiresHuman"] is False
    assert payload["pendingTool"] is None
    assert payload["pendingToolInput"] is None
    assert tool.called is True
    assert agent.thread_ident is not None
    assert loop_thread_ident is not None
    assert agent.thread_ident != loop_thread_ident


def test_agent_run_endpoint_handles_missing_model(monkeypatch):
    agent = MissingModelAgent()

    def fake_get_agent(settings):
        return agent, []

    monkeypatch.setattr(agent_module, "_get_agent", fake_get_agent)

    client = TestClient(app)
    response = client.post("/agent/run", json={"prompt": "hello"})

    assert response.status_code == 500
    payload = response.json()
    assert "Agent model is unavailable" in payload["detail"]


def test_agent_config_uses_runtime_port_default(monkeypatch):
    monkeypatch.delenv("QTICK_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("MCP_BASE_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("QTICK_GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("QTICK_AGENT_GOOGLE_MODEL", "gemini-1.5-flash-custom")
    monkeypatch.setenv("QTICK_AGENT_TEMPERATURE", "0.25")

    import app.config as config_module
    import langchain_tools.qtick as qtick_module
    import app.tools.agent as agent_mod

    config_module = importlib.reload(config_module)
    qtick_module = importlib.reload(qtick_module)
    agent_mod = importlib.reload(agent_mod)

    assert qtick_module.MCP_BASE == "http://127.0.0.1:10000"

    captured = {}
    llm_kwargs: dict = {}
    real_configure = agent_mod.configure

    def spy_configure(*, base_url: str, timeout: float | None = None) -> None:
        captured["base_url"] = base_url
        captured["timeout"] = timeout
        real_configure(base_url=base_url, timeout=timeout)

    monkeypatch.setattr(agent_mod, "configure", spy_configure)

    def spy_llm(**kwargs):
        llm_kwargs.clear()
        llm_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(agent_mod, "ChatGoogleGenerativeAI", spy_llm)
    monkeypatch.setattr(agent_mod, "initialize_agent", lambda **_: object())

    config_module.get_settings.cache_clear()
    agent_mod._get_agent_bundle.cache_clear()

    settings = config_module.Settings()
    agent_mod._get_agent(settings)

    assert captured["base_url"].startswith("http://127.0.0.1:10000")
    assert qtick_module.MCP_BASE == "http://127.0.0.1:10000"
    assert captured["timeout"] == settings.agent_tool_timeout
    assert llm_kwargs == {
        "model": settings.agent_google_model,
        "temperature": settings.agent_temperature,
    }


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



def test_agent_run_marks_invoice_creation_requires_human(monkeypatch):
    conversation_memory.clear()
    tool = FastTool()
    agent = FakeAgent(tool)

    class StubCollector:
        def __init__(self) -> None:
            self.tool_name = "invoice_create"
            self.tool_input = {
                "business_id": 77,
                "customer_name": "Alex",
                "currency": "SGD",
                "items": [
                    {
                        "description": "Signature Haircut",
                        "quantity": 1,
                        "unit_price": 32.0,
                    }
                ],
            }
            self.tool_output = {
                "invoice_id": "INV-00077",
                "total": 32.0,
                "currency": "SGD",
            }
            self.final_output = "Created invoice"

    monkeypatch.setattr(agent_module, "AgentRunCollector", StubCollector)

    def fake_get_agent(settings):
        return agent, [tool]

    monkeypatch.setattr(agent_module, "_get_agent", fake_get_agent)

    client = TestClient(app)
    response = client.post("/agent/run", json={"prompt": "create invoice"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["requiresHuman"] is True
    assert payload["pendingTool"] == "invoice_create"
    assert payload["pendingToolInput"] == {
        "business_id": 77,
        "customer_name": "Alex",
        "currency": "SGD",
        "items": [
            {
                "description": "Signature Haircut",
                "quantity": 1,
                "unit_price": 32.0,
            }
        ],
    }


class NoOpCollector:
    def __init__(self) -> None:
        self.tool_name = None
        self.tool_input = None
        self.tool_output = None
        self.final_output = None


def test_agent_run_uses_conversation_history(monkeypatch):
    conversation_memory.clear()
    tool = FastTool()
    agent = FakeAgent(tool)

    monkeypatch.setattr(agent_module, "AgentRunCollector", NoOpCollector)
    monkeypatch.setattr(agent_module, "_get_agent", lambda settings: (agent, [tool]))

    client = TestClient(app)
    first = client.post(
        "/agent/run",
        json={"prompt": "Book a haircut", "conversationId": "conv-1"},
    )
    assert first.status_code == 200
    assert agent.prompts[0] == "Book a haircut"
    assert len(conversation_memory.get_history("conv-1")) == 1

    second = client.post(
        "/agent/run",
        json={"prompt": "It's for Alex", "conversationId": "conv-1"},
    )
    assert second.status_code == 200
    assert len(agent.prompts) == 2
    assert "User: Book a haircut" in agent.prompts[1]
    assert "Assistant: Book a haircut -> tool result" in agent.prompts[1]
    history = conversation_memory.get_history("conv-1")
    assert len(history) == 2
    assert history[-1].user == "It's for Alex"


def test_conversation_memory_store_limits_turns():
    store = ConversationMemoryStore(max_turns=3)
    for idx in range(5):
        store.append("demo", f"user {idx}", f"assistant {idx}")

    history = store.get_history("demo")
    assert len(history) == 3
    assert history[0].user == "user 2"
    assert history[-1].assistant == "assistant 4"
