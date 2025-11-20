# test_agent_openai.py
import os
# 1. CHANGED: Import OpenAI Chat wrapper
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType

# 2. CHANGED: Ensure OPENAI_API_KEY is set
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not found in environment variables.")
    # os.environ["OPENAI_API_KEY"] = "sk-..." # You can hardcode here for testing if needed

# Keep your existing custom tools imports exactly the same
from langchain_tools.qtick import (
    appointment_tool,
    appointment_list_tool,
    invoice_create_tool,
    lead_create_tool,
    lead_list_tool,
    campaign_tool,
    analytics_tool,
    daily_summary_tool,
    datetime_tool,
)

tools = [
    datetime_tool(),
    appointment_tool(),
    appointment_list_tool(),
    invoice_create_tool(),
    lead_create_tool(),
    lead_list_tool(),
    campaign_tool(),
    analytics_tool(),
    daily_summary_tool(),
]

# 3. CHANGED: Initialize OpenAI LLM
# 'gpt-4o-mini' is currently the most cost-effective model (cheaper than gpt-3.5-turbo)
llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0
)

# Agent initialization remains the same
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

def run_case(title: str, prompt: str):
    print("\n" + "="*88)
    print(f"{title}\nPrompt: {prompt}\n")
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        responseValue = agent.run(prompt)
        print(responseValue)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    # Make sure: uvicorn app.main:app --reload
    
    # run_case("Create Lead", "Create a new lead for business 11 named Priya N. phone +6581234567 email priya@example.com source whatsapp.")
    # run_case("List Lead", "List leads for business 11 ")
    run_case("Daily summary", "Generate daily summary for business 119 for 10 Oct 2025")
    # run_case("Datetime Parse", "Convert 'tomorrow 5 PM Singapore' to ISO 8601 (just return the timestamp).")
    # run_case("Book Appointment", "Book a haircut for Alex at business 'chillbreeze' tomorrow 5 PM SGT. Service is 'haircut'.")