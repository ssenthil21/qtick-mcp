
# test_agent_gemini.py
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType

os.environ.setdefault("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))

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

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

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
        reponseValue = agent.run(prompt)
        print(reponseValue)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    # Make sure: uvicorn app.main:app --reload
    #run_case("Create Lead", "Create a new lead for business 11 named Priya N. phone +6581234567 email priya@example.com source whatsapp.")
    #run_case("List Lead", "List leads for business 11 ")
    run_case("Daily summary", "Generate daily summary for business 119 for 10 Oct 2025")
    #run_case("Datetime Parse", "Convert 'tomorrow 5 PM Singapore' to ISO 8601 (just return the timestamp).")
    #run_case("Book Appointment", "Book a haircut for Alex at business 'chillbreeze' tomorrow 5 PM SGT. Service is 'haircut'.")
    #run_case("List Appointments", "List confirmed appointments for business 'chillbreeze' between 2025-09-01 and 2025-09-14, page size 10.")
    #run_case("Create Invoice", "Create an invoice for 'chillbreeze' for customer Alex: 1x Haircut 25 SGD (8% tax) and 2x Hair serum 12.5 SGD each (no tax).")
    #run_case("Create Lead", "Create a new lead for business 'chillbreeze' named Priya N. phone +65 8123 4567 email priya@example.com source walk-in.")
    ##run_case("Send WhatsApp Campaign", "Send WhatsApp to Priya N. at +65 8123 4567: 'September special: 15% off any treatment!' code SEP15 expires 2025-09-30.")
    #run_case("Analytics Report", "Show footfall and revenue metrics for business 'chillbreeze' for the last week.")
