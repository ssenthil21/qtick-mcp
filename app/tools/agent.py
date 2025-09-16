
from fastapi import APIRouter, HTTPException, Query
from app.schemas.agent import AgentRunRequest, AgentRunResponse, AgentToolsResponse

import os
from typing import Optional, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType

from langchain_tools.qtick import (
    appointment_tool,
    appointment_list_tool,
    invoice_create_tool,
    lead_create_tool,
    campaign_tool,
    analytics_tool,
    datetime_tool,
)

router = APIRouter()

_AGENT = None
_TOOLS = None

def _build_tools():
    return [
        datetime_tool(),
        appointment_tool(),
        appointment_list_tool(),
        invoice_create_tool(),
        lead_create_tool(),
        campaign_tool(),
        analytics_tool(),
    ]

def _build_agent():
    global _AGENT, _TOOLS
    if _AGENT is not None:
        return _AGENT
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set on server")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    _TOOLS = _build_tools()
    _AGENT = initialize_agent(
        tools=_TOOLS,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )
    return _AGENT

@router.post("/run", response_model=AgentRunResponse)
def run_agent(req: AgentRunRequest):
    try:
        agent = _build_agent()
        output = agent.run(req.prompt)
        return AgentRunResponse(output=output)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

# Optional GET for quick browser testing: /agent/run?prompt=...
@router.get("/run", response_model=AgentRunResponse)
def run_agent_get(prompt: str = Query(..., description="Your natural language instruction")):
    return run_agent(AgentRunRequest(prompt=prompt))

@router.get("/tools", response_model=AgentToolsResponse)
def list_agent_tools():
    agent = _build_agent()
    tools = _TOOLS or []
    return AgentToolsResponse(
        tools=[{"name": t.name, "description": t.description} for t in tools]
    )
