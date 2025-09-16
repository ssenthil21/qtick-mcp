
from pydantic import BaseModel, model_validator

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
    output: str

class AgentTool(BaseModel):
    name: str
    description: str

class AgentToolsResponse(BaseModel):
    tools: list[AgentTool]
