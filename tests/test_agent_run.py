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

    def run(self, prompt: str) -> str:
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
    assert response.json() == {"output": "hello -> tool result"}
    assert tool.called is True
    assert agent.thread_ident is not None
    assert loop_thread_ident is not None
    assert agent.thread_ident != loop_thread_ident
