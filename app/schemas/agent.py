
import json

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


def _stringify_prompt_segments(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        role = value.get("role")
        content = value.get("content")
        if isinstance(role, str) and isinstance(content, str):
            return f"{role.strip()}: {content.strip()}".strip()
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        parts = [
            segment
            for segment in (
                _stringify_prompt_segments(item)
                for item in value
                if item not in (None, "")
            )
            if segment
        ]
        return "\n\n".join(parts)
    return str(value)

class AgentRunRequest(BaseModel):
    prompt: str

    # Accept alias key 'input' or even a raw string body
    @model_validator(mode="before")
    @classmethod
    def coerce_prompt(cls, v):
        if isinstance(v, dict):
            if "prompt" in v:
                prompt_value = v["prompt"]
                if isinstance(prompt_value, (list, tuple, dict)):
                    v["prompt"] = _stringify_prompt_segments(prompt_value)
                return v
            if "input" in v:
                prompt_value = v["input"]
                if isinstance(prompt_value, (list, tuple, dict)):
                    v["prompt"] = _stringify_prompt_segments(prompt_value)
                else:
                    v["prompt"] = prompt_value
                return v
            if "role" in v and "content" in v:
                return {"prompt": _stringify_prompt_segments(v)}
        elif isinstance(v, (list, tuple, dict)):
            return {"prompt": _stringify_prompt_segments(v)}
        elif isinstance(v, str):
            return {"prompt": v}
        return v

class AgentRunResponse(BaseModel):
    """HTTP response model for agent execution results."""

    model_config = ConfigDict(populate_by_name=True)

    output: str
    tool: Optional[str] = None
    data_points: List[Dict[str, Any]] = Field(default_factory=list, alias="dataPoints")

class AgentTool(BaseModel):
    name: str
    description: str

class AgentToolsResponse(BaseModel):
    tools: list[AgentTool]
