"""Compatibility helpers for LangChain's evolving agent APIs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Mapping, MutableMapping, Optional, Sequence

def _ensure_pydantic_v1() -> None:
    """Provide ``langchain_core.pydantic_v1`` if the distribution omits it."""

    try:  # pragma: no cover - only executed on newer langchain builds
        import langchain_core.pydantic_v1  # type: ignore
        return
    except ImportError:
        pass

    import sys
    import types

    from pydantic import v1 as pydantic_v1

    module = types.ModuleType("langchain_core.pydantic_v1")
    module.BaseModel = pydantic_v1.BaseModel
    module.Field = pydantic_v1.Field
    module.ValidationError = pydantic_v1.ValidationError
    module.root_validator = pydantic_v1.root_validator
    module.validator = pydantic_v1.validator
    module.__all__ = [
        "BaseModel",
        "Field",
        "ValidationError",
        "root_validator",
        "validator",
    ]

    sys.modules.setdefault("langchain_core.pydantic_v1", module)


_ensure_pydantic_v1()

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage


class AgentType(str, Enum):
    """Subset of historical ``AgentType`` enum values that we rely on."""

    STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION = (
        "structured-chat-zero-shot-react-description"
    )


def _extract_message_text(message: BaseMessage) -> str:
    """Return a readable string from a LangChain message instance."""

    content: Any = getattr(message, "content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, Sequence):
        parts: List[str] = []
        for item in content:
            if isinstance(item, Mapping):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        if parts:
            return "".join(parts)

    return str(content)


@dataclass
class _StructuredChatAgent:
    """Minimal wrapper that mimics the legacy agent executor interface."""

    graph: Any
    base_callbacks: Sequence[BaseCallbackHandler]

    def run(self, prompt: str, callbacks: Optional[Sequence[BaseCallbackHandler]] = None) -> str:
        """Execute the agent graph with the provided prompt."""

        messages = {"messages": [HumanMessage(content=prompt)]}
        merged_callbacks: List[BaseCallbackHandler] = list(self.base_callbacks)
        if callbacks:
            merged_callbacks.extend(callbacks)

        config: MutableMapping[str, Any] = {}
        if merged_callbacks:
            config["callbacks"] = merged_callbacks

        result: Mapping[str, Any] = self.graph.invoke(messages, config=config or None)
        history = result.get("messages", [])
        if not history:
            return ""

        return _extract_message_text(history[-1])


def initialize_agent(
    *,
    tools: Optional[Sequence[Any]],
    llm: Any,
    agent: AgentType,
    verbose: bool = False,
    callbacks: Optional[Sequence[BaseCallbackHandler]] = None,
    **_: Any,
) -> _StructuredChatAgent:
    """Backwards compatible ``initialize_agent`` helper."""

    if agent is not AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION:
        raise ValueError(f"Unsupported agent type: {agent}")

    graph = create_agent(model=llm, tools=tools or None)

    return _StructuredChatAgent(graph=graph, base_callbacks=list(callbacks or ()))


__all__ = ["AgentType", "initialize_agent"]

