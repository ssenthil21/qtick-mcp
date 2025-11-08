from langchain.chat_models import ChatOpenAI
from app.services.langchain_compat import AgentType, initialize_agent
from langchain_core.tools import Tool

# Import your QTick tools
from langchain_tools.qtick import (
    appointment_tool,
    campaign_tool,
    analytics_tool,
    daily_summary_tool,
)

# Setup tools list
tools = [appointment_tool(), campaign_tool(), analytics_tool(), daily_summary_tool()]

# Load LLM (OpenAI or local-compatible)
llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo", openai_api_key="sk-...")

# Initialize agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Example query
response = agent.run("Book a haircut appointment for Alex at ChillBreeze tomorrow at 5 PM.")
print("Response:", response)
