
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

class AgentRunRequest(BaseModel):
    prompt: str

    # Accept alias key 'input' or even a raw string body
    @model_validator(mode="before")
    @classmethod
    def coerce_prompt(cls, v):
        if isinstance(v, dict):
            if "prompt" in v:
                return v
            if "input" in v:
                v["prompt"] = v["input"]
                return v
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
