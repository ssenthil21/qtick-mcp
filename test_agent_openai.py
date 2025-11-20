"""Compatibility helpers for LangChain's evolving agent APIs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Mapping, MutableMapping, Optional, Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage

# ---------------------------------------------------------------------------
# Agent type used by the rest of your code
# ---------------------------------------------------------------------------


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
    """Wrapper around a new-style agent graph to expose a ``.run()`` API."""

    graph: Any  # typically a Runnable graph
    base_callbacks: Sequence[BaseCallbackHandler]

    def run(
        self,
        prompt: str,
        callbacks: Optional[Sequence[BaseCallbackHandler]] = None,
    ) -> str:
        """Execute the agent graph with the provided prompt."""
        merged_callbacks: List[BaseCallbackHandler] = list(self.base_callbacks)
        if callbacks:
            merged_callbacks.extend(callbacks)

        config: MutableMapping[str, Any] = {}
        if merged_callbacks:
            config["callbacks"] = merged_callbacks

        # New-style agents usually expect {"input": "..."} and return {"output": "..."}
        result = self.graph.invoke({"input": prompt}, config=config or None)

        # Try common result shapes
        if isinstance(result, Mapping):
            if "output" in result:
                return str(result["output"])
            if "messages" in result:
                history = result.get("messages", [])
                if history:
                    return _extract_message_text(history[-1])

        if hasattr(result, "content"):
            return str(getattr(result, "content"))

        return str(result)


# ---------------------------------------------------------------------------
# Detect which LangChain agent API is available
# ---------------------------------------------------------------------------

# Legacy API: initialize_agent + AgentType enum
try:  # pragma: no cover
    from langchain.agents import initialize_agent as _legacy_initialize_agent
    from langchain.agents import AgentType as _LegacyAgentType

    _legacy_style_available = True
except ImportError:  # pragma: no cover
    _legacy_initialize_agent = None  # type: ignore
    _LegacyAgentType = None  # type: ignore
    _legacy_style_available = False

# New-style API (langchain-core 0.3+): create_react_agent + ChatPromptTemplate
try:  # pragma: no cover
    from langchain.agents import create_react_agent as _create_react_agent
    from langchain_core.prompts import ChatPromptTemplate

    _new_style_available = True
except ImportError:  # pragma: no cover
    _create_react_agent = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore
    _new_style_available = False


# ---------------------------------------------------------------------------
# Public initialize_agent used by your app and tests
# ---------------------------------------------------------------------------


def initialize_agent(
    *,
    tools: Optional[Sequence[Any]],
    llm: Any,
    agent: AgentType,
    verbose: bool = False,
    callbacks: Optional[Sequence[BaseCallbackHandler]] = None,
    **_: Any,
) -> Any:
    """Backwards-compatible initialize_agent.

    Preference order:
      1. Legacy ``langchain.agents.initialize_agent`` (most stable with your code)
      2. New-style ``create_react_agent`` (fallback if legacy is missing)
    """
    if agent is not AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION:
        raise ValueError(f"Unsupported agent type: {agent}")

    # --- Prefer legacy path if available -----------------------------------
    if _legacy_style_available and _legacy_initialize_agent is not None:
        lc_agent_type = _LegacyAgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION
        return _legacy_initialize_agent(
            tools=tools,
            llm=llm,
            agent=lc_agent_type,
            verbose=verbose,
            callbacks=callbacks,
        )

    # --- Fallback: new-style create_react_agent ----------------------------
    if _new_style_available and _create_react_agent is not None:
        # Prompt with all required variables for ReAct agents:
        # {input}, {tools}, {tool_names}, {agent_scratchpad}
        prompt = ChatPromptTemplate.from_template(
            """
You are QTick's virtual operations assistant.
Use the provided tools to manage appointments, leads, invoices, campaigns,
analytics, daily summaries, and date/time parsing. Think step by step and
call tools whenever they are helpful.

Available tools:
{tools}

Tool names: {tool_names}

Previous reasoning and tool results:
{agent_scratchpad}

User query:
{input}
            """.strip()
        )

        graph = _create_react_agent(
            llm,          # positional arg
            tools or [],  # tools
            prompt,       # ChatPromptTemplate
        )

        return _StructuredChatAgent(
            graph=graph,
            base_callbacks=list(callbacks or ()),
        )

    # --- No compatible API found -------------------------------------------
    raise ImportError(
        "Could not find a compatible LangChain agent factory.\n"
        "Tried:\n"
        "  • legacy:   langchain.agents.initialize_agent\n"
        "  • new-style: langchain.agents.create_react_agent\n\n"
        "Please upgrade/downgrade LangChain or adjust this file "
        "to the agent builder available in your installed version."
    )


__all__ = ["AgentType", "initialize_agent"]
