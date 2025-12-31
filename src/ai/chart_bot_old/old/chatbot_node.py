import statistics
from typing import Annotated, List
# Import the 'add' operator to handle message history correctly
from operator import add

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from typing import Annotated, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

import datetime

def _preserve_context(
    left: Optional[Dict[str, str]], right: Optional[Dict[str, str]]
) -> Optional[Dict[str, str]]:
    if right is not None:
        return right
    return left

# --- Agent State Definition ---
class AgentState(TypedDict):
    """
    Represents the state of our agent.
    """
    messages: Annotated[list[AnyMessage], add]
    # This annotation tells the graph how to handle the company_info state,
    # ensuring it persists across all steps in a turn.
    company_info: Annotated[Optional[Dict[str, str]], _preserve_context]


# --- Graph Node Functions ---
async def tool_calling_agent(state: AgentState, config: RunnableConfig, llm):
    """
    The primary node that decides the next action. It invokes the LLM with the
    current conversation history and a system prompt. The LLM's response, which
    may include a tool call, is added to the state.
    """
    print("\n---AGENT---")

    current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p IST")
    # --- UPDATED SYSTEM PROMPT ---
    # This prompt now accurately describes all three tools you are providing.
    system_prompt = SystemMessage(
    content=f"""You are an expert financial assistant. Your goal is to help users by analyzing stock and cryptocurrency data using the tools provided.

    **Current Context:**
        - **Date and Time:** It is currently {current_time_str}.
        - Use this context to resolve any relative date queries from the user (e.g., "today", "yesterday", "last week" "last month" and other).

    **Your Tools and Capabilities:**

    1.  **`get_historical_price_full`**:
        * **Use Case:** Use this tool ONLY when the user asks for historical and current price data for a **stock** over a specific date range (e.g., "what was the price of Google from January to March?").
        * **Arguments:** You must infer the `ticker`, `from_date`, and `to_date`.

    2.  **`get_crypto_historical_price_full`**:
        * **Use Case:** Use this tool ONLY when the user asks for historical and current price data for a **cryptocurrency** (e.g., "show me Bitcoin's price history for 2025").
        * **Arguments:** You must infer the `symbol`, `from_date`, and `to_date`.

    3.  **`tavily_web_search`**: 
        * **Use Case: ** Always use this tool primarily to search the web and access the finance content from webpages.


    **Your Workflow:**
    -   **Analyze the Query:** First, determine if the user has a general query or a specific date-range query.
    -   **Select the Correct Tool:** Choose the most appropriate tool based on your analysis. For specific history, use the historical tools.
    -   **Fetch and Analyze the Data:** The tools return raw JSON data. You must analyze this data to answer the user's question.
        - Do NOT assume a date is invalid or in the future unless the tool returns **no data**.
        - If data is returned for a future-looking date, analyze it as normal.
    -   **Handle Errors:** If a tool returns an error or no results, inform the user politely.
    """
)

    
    messages_with_system_prompt = [system_prompt] + state["messages"]
    response = await llm.ainvoke(messages_with_system_prompt, config)
    print(f"Agent response: {response}")
    return {"messages": [response]}

def router_agent(state: AgentState) -> str:
    """
    This is a conditional edge. It checks the agent's last message to decide
    the next step in the graph.
    """
    print("\n---ROUTER---")
    if state["messages"][-1].tool_calls:
        print("Decision: Call tool.")
        return "tools"
    print("Decision: End turn.")
    return END

def create_agent_graph(llm, tools):
    """
    Builds and compiles the conversational agent graph with in-memory checkpointing.
    """
    tool_node = ToolNode(tools)
    # agent_node = lambda state, config: tool_calling_agent(state, config, llm=llm)
    async def agent_node(state, config):
        return await tool_calling_agent(state, config, llm=llm)

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", router_agent)
    builder.add_edge("tools", "agent")

    # Instantiate the in-memory saver
    memory = InMemorySaver()
    
    # Compile the graph with the checkpointer for memory
    graph = builder.compile(checkpointer=memory)
    
    return graph
