"""Callback handlers that log agent activity for observability."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

logger = logging.getLogger("app.agent")
logger.setLevel(logging.INFO)


class AgentLoggingCallbackHandler(BaseCallbackHandler):
    """Logs the internal decisions the agent makes while running."""

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        for index, prompt in enumerate(prompts, start=1):
            logger.info("LLM prompt %s: %s", index, prompt)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not response.generations:
            return
        generations = response.generations[0]
        if not generations:
            return
        generation = generations[0]
        text = getattr(generation, "text", None)
        if text is None and getattr(generation, "message", None) is not None:
            text = getattr(generation.message, "content", None)
        logger.info("LLM response: %s", text if text is not None else generation)

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        logger.exception("LLM error: %s", error)

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        logger.info(
            "Agent selected tool '%s' with input: %s", action.tool, action.tool_input
        )

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        logger.info("Agent finished with output: %s", finish.return_values)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name") if isinstance(serialized, dict) else None
        logger.info("Tool '%s' started with input: %s", tool_name, input_str)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        logger.info("Tool finished with output: %s", output)

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        logger.exception("Tool error: %s", error)

