from langchain_core.messages import HumanMessage,SystemMessage
import asyncio
from src.ai.tools.finance_data_tools import get_stock_data

# 2. Import your LLM and configuration
from src.ai.llm.model import get_llm
#from src.ai.llm.config import FastAgentConfig
from src.ai.llm.config import  FastAgentConfig

# 3. Import the graph builder from the new node file
from .chatbot_node import create_agent_graph
from ..financial_tool import fetch_crypto_price_history, fetch_stock_price_history
from ..tavily_search import search_financial_web_content


from langchain_core.messages import HumanMessage
import datetime

# --- Project-Specific Imports (Updated as per your new structure) ---
# Assuming your files are in a package named 'chart_bot' or similar.
# If your structure is different, you may need to adjust these paths.

async def start_chat_session(name: str, user_input: str, ticker: str, exchange: str, graph, config: dict):
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
    current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    if exchange.upper() == "CRYPTO":
        base_context = f"""
        **CONTEXT FOR THIS QUERY**
        - Crypto currency name: {name}
        - Crypto symbol: {ticker}
        - Current Date: {current_time_str}
        ---
        User's Question: """
    else:
        base_context = f"""
        **CONTEXT FOR THIS QUERY**
        - Company Name: {name}
        - Ticker: {ticker}
        - Exchange: {exchange}
        - Current Date: {current_time_str}
        ---
        User's Question: """

    while True:
        # user_input = await asyncio.to_thread(input, " You: ")
        # if user_input.lower() in ["exit", "quit"]:
        #     print(" Goodbye!")
        #     break
        
        # The user's input is now appended to the pre-made context string.
        full_prompt = base_context + user_input
        
        # The context and user question are combined into a single, rich HumanMessage.
        messages = [HumanMessage(content=full_prompt)]
        
        final_answer = None
        # The graph now receives the combined message.
        async for event in graph.astream({"messages": messages}, config):
            if "agent" in event:
                final_answer = event["agent"]["messages"][-1]

        if final_answer:
            print(f"\n Assistant: {final_answer.content}\n")



async def main():
    """Main async function to set up and run the chatbot."""
    print("Setting up the Stock Analysis Chatbot...")

    # 1. Define the tools
    tools = [
        fetch_stock_price_history,
        fetch_crypto_price_history,
        search_financial_web_content,
    ]

    # 2. Configure the LLM
    fc = FastAgentConfig()
    llm = get_llm(fc.MODEL, fc.TEMPERATURE, fc.MAX_TOKENS).bind_tools(tools)

    # 3. Create the graph
    graph = create_agent_graph(llm, tools)
    
    # 4. Define a unique ID for the conversation thread
    config = {"configurable": {"thread_id": "user-main-thread"}}

    # --- Start a chat session ---
    await start_chat_session(
        name="dogecoin",
        user_input="What is the current price of Dogecoin?",
        ticker="DOGEUSD",
        exchange="Crypto",
        graph=graph,
        config=config
    )

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())



    
