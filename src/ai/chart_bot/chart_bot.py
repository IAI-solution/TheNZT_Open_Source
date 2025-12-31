import datetime
import asyncio
import calendar


from typing import List
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from .tools.financial_tool import fetch_crypto_price_history, fetch_stock_price_history
from .tools.tavily_search import search_financial_web_content
from src.ai.llm.model import get_llm
from src.ai.llm.config import FastAgentConfig
from src.ai.chart_bot.prompt.prompt_Vz import SYSTEM_PROMPT


fc = FastAgentConfig()
tools = [
    fetch_stock_price_history,
    fetch_crypto_price_history,
    search_financial_web_content,
]

llm = get_llm(fc.MODEL, fc.TEMPERATURE, fc.MAX_TOKENS).bind_tools(tools)

# --- Project-Specific Imports (Updated as per your new structure) ---
# Assuming your files are in a package named 'chart_bot' or similar.
# If your structure is different, you may need to adjust these paths.

async def start_chat_session(name: str, user_input: str, ticker: str, exchange: str, context_data: List[dict], messages: List):
    """
    Starts an interactive chat session for a specific stock or cryptocurrency.
    It first establishes the context and then enters a loop for the conversation.

    Args:
        name: The name of the company or cryptocurrency.
        ticker: The ticker symbol (e.g., 'AAPL') or crypto symbol (e.g., 'BTCUSD').
        exchange: The exchange it trades on (e.g., 'NASDAQ' or 'Crypto').
        graph: The compiled LangGraph agent.
        config: The configuration dictionary for the graph's memory.
    """
    # print(f"\nHello! I'm your financial assistant for {name}. Ask me anything. Type 'exit' to quit.")

    # --- ESTABLISH CONTEXT ONCE (as per your suggestion) ---
    # This base context is created one time when the session starts.
    # current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    # --- UPDATED SYSTEM PROMPT ---
    # This prompt now accurately describes all three tools you are providing.
    
    # current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    current_date = datetime.datetime.now()
    current_time_str = f"{calendar.day_name[current_date.weekday()]}, {current_date.strftime('%B %d, %Y at %I:%M %p')}"


    BASE_SYSTEM_PROMPT = SYSTEM_PROMPT.format(current_time_str=current_time_str)
    system_prompt = SystemMessage(
        content=BASE_SYSTEM_PROMPT
    )

    # --- 3. Create the async ReAct agent ---
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt
    )
    
    current_date = datetime.datetime.now()
    current_time_str = f"{calendar.day_name[current_date.weekday()]}, {current_date.strftime('%B %d, %Y')}"

    
    if exchange.upper() == "CRYPTO":
        base_context = f"""
\n<context>
**CONTEXT FOR THIS QUERY**
- Crypto currency name: {name}
- Crypto symbol: {ticker}
- Current Date: {current_time_str}
</context>\n
---
"""
    else:
        base_context = f"""
\n<context>
**CONTEXT FOR THIS QUERY**
- Company Name: {name}
- Ticker: {ticker}
- Exchange: {exchange}
- Current Date: {current_time_str}
</context>\n
---
"""
    
    base_context = base_context + f"""
**Other numerical data you need to consider (which may include prediction results for next 5 days):**
{context_data}
---

## Guide to Responding to Queries About Stock Price and Cryptocurrency Price Prediction Models. Only respond in this manner if the user explicitly asks for information on the stock or cryptocurrency price prediction model used in this app.

What you should respond: 'We fit a SARIMA model (`SARIMAX` with order `(1,1,1)` and seasonal order `(1,1,1,5)`) on the last 120 scaled closing-price data points and forecast the next 5 days. The forecast is then adjusted using a sentiment rating—derived from LLM analysis and web search of the relevant company or country—through a quadratic scaling process. If sentiment is above 50, prices are nudged upward; if below 50, they are lowered. The further sentiment is from neutral (50%), the stronger the adjustment, growing faster near the extremes (0 or 100) by squaring the distance from 50% and applying it proportionally to the forecast range. The prediction error typically ranges from 5% to 10%.'
"""

    
    prev_chat_hist = ""

    if messages:
        prev_chat_hist = "\n---\n<chat_history>\nTHIS IS THE PREVIOUS CHAT HISTORY BETWEEN THE USER AND YOU : **(Key Note: oldest message listed first and newest and latest messages listed last)**\n"

        for i, m in enumerate(messages, 1):
            prev_chat_hist += f"{i}. USER Query: {m[0]}\n"
            prev_chat_hist += f"   AI Response: {m[1]}\n"

        prev_chat_hist+= "</chat_history>\n---\n"


    # Build prompt and run ONCE
    user_input = f"<user_query>\n# You have to answer the current user's query: **{user_input}**.\n</user_query>\n\n---\n"
    full_prompt = user_input + base_context + prev_chat_hist

    print(f"Full Prompt\n{full_prompt}")

    final_content = None
    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": full_prompt}]},
        stream_mode="updates"
    ):
        print(f"chunk: {chunk}")
        if "agent" in chunk and "messages" in chunk["agent"]:
            for msg in chunk["agent"]["messages"]:
                content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
                if content and content.strip():
                    final_content = content

    if final_content:
        print(final_content)
        return final_content
    else:
        return ""



async def main():
    # """Main async function to set up and run the chatbot."""
    # print("Setting up the Stock Analysis Chatbot...")

    # # 1. Define the tools
    # tools = [
    #     fetch_stock_price_history,
    #     fetch_crypto_price_history,
    #     search_financial_web_content,
    # ]

    # # 2. Configure the LLM
    # fc = FastAgentConfig()
    # llm = get_llm(fc.MODEL, fc.TEMPERATURE, fc.MAX_TOKENS).bind_tools(tools)

    # # 3. Create the graph
    # graph = create_agent_graph(llm, tools)
    
    # # 4. Define a unique ID for the conversation thread

    # --- Start a chat session ---
    output = await start_chat_session(
        name="Tesla Inc",
        user_input="What was my last two questions?",
        ticker="TSLA",
        exchange="NASDAQ",
        context_data=[{"predicted_value_day1":54.8}, {"predicted_value_day2":78.2}],
        messages= [
            ["What’s the weather in New York today?", 
            "The current temperature in New York is 78°F with partly cloudy skies and light winds."],
            
            ["Tell me a joke", 
            "Why did the computer go to the doctor? Because it caught a virus!"],
            
            ["Summarize the book 'To Kill a Mockingbird'", 
            "'To Kill a Mockingbird' is a novel by Harper Lee that explores themes of racial injustice, moral growth, and compassion, set in the 1930s American South."],
            
            ["Amazon stock price on July 10, 2025", 
            "On July 10, 2025, Amazon's stock opened at $221.55, reached a high of $222.79, a low of $219.70, and closed at $222.26."],
        ],
    )
    print(f"Final output: {output}")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())



    
