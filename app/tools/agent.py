
import asyncio
from functools import lru_cache
import os
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.schemas.agent import AgentRunRequest, AgentRunResponse, AgentToolsResponse
from app.services.agent_logging import AgentLoggingCallbackHandler

from langchain.agents import AgentType, initialize_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_tools.qtick import (
    analytics_tool,
    appointment_list_tool,
    appointment_tool,
    campaign_tool,
    configure,
    datetime_tool,
    invoice_create_tool,
    lead_create_tool,
)

router = APIRouter()


def _cache_key(settings: Settings) -> Tuple[str, str, float]:
    return (str(settings.mcp_base_url), settings.agent_google_model, settings.agent_temperature)


def _build_tools() -> List:
    return [
        datetime_tool(),
        appointment_tool(),
        appointment_list_tool(),
        invoice_create_tool(),
        lead_create_tool(),
        campaign_tool(),
        analytics_tool(),
    ]


@lru_cache(maxsize=1)
def _get_agent_bundle(cache_key: Tuple[str, str, float]):
    settings = get_settings()
    configure(base_url=str(settings.mcp_base_url))
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    elif not os.getenv("GOOGLE_API_KEY"):
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set on server")

    #api_key = "AIzaSyDUucupw9yBarvslvctDJ_SraQfAuN0H78"
    #llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0,google_api_key=api_key)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    tools = _build_tools()
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        callbacks=[AgentLoggingCallbackHandler()],
    )
    return agent, tools


def _get_agent(settings: Settings) -> Tuple[object, List]:
    cache_key = _cache_key(settings)
    return _get_agent_bundle(cache_key)


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    settings: Settings = Depends(get_settings),
):
    try:
        agent, _ = _get_agent(settings)
        output = await asyncio.to_thread(agent.run, req.prompt)
        return AgentRunResponse(output=output)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc


@router.get("/run", response_model=AgentRunResponse)
async def run_agent_get(
    prompt: str = Query(..., description="Your natural language instruction"),
    settings: Settings = Depends(get_settings),
):
    return await run_agent(AgentRunRequest(prompt=prompt), settings)


@router.get("/tools", response_model=AgentToolsResponse)
async def list_agent_tools(settings: Settings = Depends(get_settings)):
    _, tools = _get_agent(settings)
    return AgentToolsResponse(
        tools=[{"name": tool.name, "description": tool.description} for tool in tools]
    )
