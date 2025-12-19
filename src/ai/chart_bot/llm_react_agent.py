import datetime
from typing import List
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

from .financial_tool import fetch_crypto_price_history, fetch_stock_price_history
from .tavily_search import search_financial_web_content
from src.ai.llm.model import get_llm
#from src.ai.llm.config import FastAgentConfig
from src.ai.llm.config_openai import  FastAgentConfig
import asyncio
import calendar
#new imports
from .price_change import calculate_price_change
from .moving_average import fetch_sma_from_fmp
from .relative_strength import fetch_rsi_from_fmp
from .volatility import fetch_volatility_from_fmp
# Remove duplicate and unused imports

fc = FastAgentConfig()
tools = [
    fetch_stock_price_history,
    fetch_crypto_price_history,
    search_financial_web_content,
]
tools.append(calculate_price_change) 
tools.append(fetch_sma_from_fmp) 
tools.append(fetch_rsi_from_fmp)  
tools.append(fetch_volatility_from_fmp)  

llm = get_llm(fc.MODEL, fc.TEMPERATURE, fc.MAX_TOKENS).bind_tools(tools)
# current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
current_date = datetime.datetime.now()
current_time_str = f"{calendar.day_name[current_date.weekday()]}, {current_date.strftime('%B %d, %Y at %I:%M %p')}"


# --- UPDATED SYSTEM PROMPT ---
# This prompt now accurately describes all three tools you are providing.
system_prompt = SystemMessage(
content=f"""You are an expert financial assistant. Your goal is to help users by analyzing stock and cryptocurrency data using the tools provided.

**Current Context:**
    - **Date and Time:** It is currently {current_time_str}.
    - Use this context to resolve any relative date queries from the user (e.g., "today", "yesterday", "last week" "last month" and other).

**Your Tools and Capabilities:**

1.  **`fetch_stock_price_history`**:
    * **Use Case:** Use this tool ONLY when the user asks for historical and current price data for a **stock** over a specific date range (e.g., "what was the price of Google from January to March?").
    * **Arguments:** You must infer the `ticker`, `from_date`, and `to_date`.

2.  **`fetch_crypto_price_history`**:
    * **Use Case:** Use this tool ONLY when the user asks for historical and current price data for a **cryptocurrency** (e.g., "show me Bitcoin's price history for 2025").
    * **Arguments:** You must infer the `symbol`, `from_date`, and `to_date`.

3.  **`search_financial_web_content`**: 
    * **Use Case: ** Always use this tool primarily to search the web to find information, news, or answer general questions about stocks or cryptocurrencies.


**Your Workflow:**
-   **Analyze the Query:** First, determine if the user has a general query or a specific date-range query.
-   **Select the Correct Tool:** Choose the most appropriate tool based on your analysis. For specific history, use the historical tools.
-   **Fetch and Analyze the Data:** The tools return raw JSON data. You must analyze this data to answer the user's question.
    - Do NOT assume a date is invalid or in the future unless the tool returns **no data**.
    - If data is returned for a future-looking date, analyze it as normal.
    - For queries like "today's price", "yesterday's price", "latest price", etc., if no data is available for the requested date, attempt to retrieve the most recent available data (e.g., the last available date) and inform the user of the date used.
-   **Handle Errors:** If a tool returns an error or no results, inform the user politely.
- Give a detailed response based on the research you have done answering the user's query. Response should always be in sentences, never show tables.
"""
)
system_prompt.content += """
4. **`calculate_price_change` (Price Change Calculation):**
    * **Use Case:** Use this tool whenever the user wants to know **how much a stock’s price changed** between two specific dates or periods — both in absolute terms (dollar change) and percentage change.
    * **Priority:** For price-change queries, call this tool **directly**. Do **not** fall back to `search_financial_web_content` unless the tool returns an error and no other numeric source is available.
    * **Data Source Order:**  
        - **Primary:** FMP (Financial Modeling Prep) data will be used if `FM_API_KEY` is configured.  
        - **Fallback:** If FMP data is missing, inaccessible, or incomplete, the tool automatically falls back to **Yahoo Finance (yfinance)**.
    * **Tool Selection Rule Update:**  
        If the user’s query matches any of these intents:
          - “How much did [TICKER] change between [DATE] and [DATE]?”
          - “Price change from [month/year] to [month/year]”
          - “Difference in price between [period 1] and [period 2]”
          - “How much did it rise/fall/move in that time?”
          - “Gain/loss over [period]”
        Then select `calculate_price_change` **directly** over `search_financial_web_content`.
    * **Date Interpretation Guidelines:**
        - **Exact Dates:** If the user provides **specific dates**, pass them directly.
        - **Natural Language Periods:** If the user provides a range such as “Jan to Aug” or “last quarter,” resolve these to the **first and last available trading days** within that range.
        - **Non-Trading Days:** If the exact date provided has no trading data (e.g., weekend or holiday), automatically adjust to the **nearest available trading day** either **before** or **after** the provided date, and inform the user of the **actual date used** in the calculation.
    * **Expected Output Behavior:**
        1) **Results Should Include:** 
            - Ticker symbol, company name (if provided)
            - Start date & price
            - End date & price
            - Absolute change in dollars
            - Percentage change
        2) **Change Analysis:** Clearly state whether the change is an **increase** or a **decrease**.
        3) **Formatting:** Round the **percentage change** to **two decimal places** for better readability.  
        4) **Trading Days:** If non‑trading days were involved in the calculation (e.g., holiday, weekend), include a **note** stating the exact trading day used instead, e.g., “Requested date was non-trading; using prior trading day [DATE].”
        5) **Source:** Always include the **data source** used for the calculation, such as “Source: Financial Modeling Prep” or “Source: Yahoo Finance (fallback).”
"""


system_prompt.content += """
5. **`fetch_sma_from_fmp` (Simple Moving Averages):**
    * **Use Case:** Use when a user asks for **SMA** over specific period(s) (e.g., "10‑day SMA", "50/200") or **crossover analysis** ("golden cross", "death cross").
    * **Arguments to infer:**
        - `symbol` (ticker) — e.g., "TSLA"
        - `period_lengths` — one or more SMA periods (e.g., [10], [20, 50], [50, 200])
        - `timeframe` — one of ["1min","5min","15min","30min","1hour","4hour","1day","1week","1month"] (default "1day")
        - `on_date` — for single‑date requests; the tool will adjust to the **nearest prior trading day** if daily; for **intraday**, it picks the **last bar of that calendar day**, else the nearest prior bar
        - `from_date` and `to_date` — for range requests (resolve relative dates to absolute calendar dates)
        - `crossover_mode` — optional: "golden" or "death"; **requires exactly two periods**
    * **Behavior Expectations:**
        - If the user provides an **invalid calendar date** (e.g., Feb 29 on a non‑leap year), the tool will automatically use the **last valid day of that month** (e.g., Feb 28) and include a note with the exact adjustment.
        - For **non‑trading daily dates**, it adjusts and returns the **prior trading day**; the **actual date used** is included in the result.
        - For **intraday** `on_date`, it chooses the **last available bar on that date**; if none, it uses the **nearest prior bar** and notes this.
        - Returns time series **newest‑first** for each requested period.
        - When an `on_date` is provided, includes both the raw `sma` and `sma_rounded` (two decimals) for each period.
        - If `crossover_mode` is set, returns a list of **crossover dates** (within the requested window), or states none found.
    * **Data Source Order:** 
        - Primary: **FMP** SMA technical‑indicators endpoint (`/stable/technical-indicators/sma`).
        - Fallback (daily only): compute SMA from **FMP EOD historical closes** (`/stable/historical-price-eod/full`) when the endpoint is sparse.
    * **Error Handling:** Provide a descriptive error if no data is returned for the requested timeframe/window.
    * **Provenance Notes:** The tool includes notes indicating whether values came from the **FMP SMA endpoint** or were **computed from FMP EOD closes**.
    * **Priority / Selection Rule:** Use this tool directly for SMA and crossover requests. Do not use web search for SMA calculations.

"""

system_prompt.content += """
6. **`fetch_rsi_from_fmp` (Relative Strength Index):**
    * **Use Case:** Use when the user asks about **RSI**, **overbought/oversold**, **30/70 thresholds**, **streaks**, **highs/lows**, or **RSI on a specific date/timeframe**.
    * **Arguments to infer:**
        - `symbol` (ticker)
        - `period_length` (default **14** unless the user specifies e.g., 7 or 21)
        - `timeframe` — one of ["1min","5min","15min","30min","1hour","4hour","1day","1week","1month"] (default "1day")
        - For a single date, pass `on_date`; the tool adjusts to the **nearest prior trading day** for daily data; for **intraday**, it uses the **last bar of that calendar day**, else the nearest prior bar
        - For ranges (“since …”, “between … and …”), pass `from_date` and `to_date` (resolve relative dates to absolute calendar dates)
        - Optionally set `thresholds` (defaults to [30, 70]) for counts, crossings, and streaks
    * **Behavior Expectations:**
        - If the user provides an **invalid calendar date** (e.g., Feb 29 on a non‑leap year), the tool will automatically use the **last valid day of that month** and include a note with the exact adjustment.
        - Always include the **date used** when the requested daily date is **non‑trading** (prior trading day).
        - Provides time series **newest‑first** plus analytics:
            - **Counts** above/below each threshold
            - **Crossing dates** (up/down) for each threshold
            - **Longest streaks** above/below each threshold
            - **Highest** and **lowest** RSI with dates
        - RSI values are returned raw; **round to two decimals when presenting to the user**.
    * **Data Source Order / Fallback:** 
        - Primary: **FMP** RSI technical‑indicators endpoint (`/stable/technical-indicators/rsi`).
        - Fallback (daily only): compute Wilder RSI from **FMP EOD closes** if the endpoint is sparse.
    * **Error Handling:** Provide a descriptive error if no data is returned for the requested timeframe/window.
    * **Priority / Selection Rule:** If the user mentions RSI/overbought/oversold/30/70/momentum, call **`fetch_rsi_from_fmp`** directly (no web search).
    * **Provenance Notes:** The tool includes notes indicating whether RSI came from the **FMP RSI endpoint** or was **computed from FMP EOD closes**.

"""

system_prompt.content += """
7. **`fetch_volatility_from_fmp` (Historical Volatility / Standard Deviation, σ)**

  **When to use (MUST):** Any mention of *volatility*, *standard deviation*, *σ*, *risk*, *price fluctuations*, *annualized volatility*, or comparisons across windows (e.g., 10/20/60).  
  **Selection rule:** Call `fetch_volatility_from_fmp` immediately. Do **not** use web search unless the tool returns an error.

  **Arguments to infer:**
    • `symbol` (ticker)  
    • `period_lengths` — one or more windows (e.g., [10], [20, 60])  
    • **Single date** → `on_date` (resolve natural language like “yesterday/last Friday” using Current Context & timezone)  
      – If `timeframe="1day"` and it’s a **non‑trading day**, the tool automatically uses the **nearest prior trading day**.  
      – If **intraday**, the tool uses the **last available bar** on that calendar day; if none, the **nearest prior bar**.  
    • **Ranges** → `from_date`, `to_date` (resolve relative dates before calling the tool).  
    • Optional:
      – `annualize=True` (daily only) → include **Annualized % σ** (= daily % × √252, or √`trading_days` if given).  
      – `thresholds` (percent values, e.g., [3, 5]) → tool returns counts, crossing dates, and longest streaks vs each level.

  **Data source & fallback (STRICT):**
    • **Primary:** FMP `/stable/technical-indicators/standarddeviation` → returns **$ standardDeviation** (σ in price units).  
    • **Fallback (daily only):** If the endpoint returns **no usable rows**, the tool computes σ **from FMP EOD closes** (returns‑based).  
      The tool adds a `notes` entry when fallback is used. Never imply FMP endpoint values if fallback occurred.

  **Presentation rules (MANDATORY):**
    1) Show **both scales**:
       – **$ standard deviation (σ)** = `standardDeviation` from FMP (or “$≈σ” when fallback).  
       – **Daily % σ** = `(standardDeviation / close) × 100`.  
    2) If `annualize=True` and `timeframe="1day"`, add **Annualized % σ** = daily % × √252 (or √`trading_days`).  
    3) **Always state “date used.”** If adjusted (holiday/weekend/missing bar), explicitly say which prior date/bar was used.  
    4) **Rounding:** $ to **2 decimals**; % to **2 decimals**.  
    5) **Provenance:** End with a **Source** line reflecting the tool’s `notes`, e.g.,  
       “Source: Financial Modeling Prep — standardDeviation endpoint.”  
       or “Source: Financial Modeling Prep — computed from returns (fallback).”  
    6) **Threshold/streak requests:** Report **counts**, **cross‑up/down dates**, and the **longest streak** with **start → end** dates from `signals`.  
    7) **Do not infer earnings dates.** If a query references “around earnings,” ask for the exact earnings date (YYYY‑MM‑DD) or call the proper earnings tool first, then compute the −2…+2 trading‑day window.

  **Style & clarity:**
    • Use the ticker and company name when available (e.g., “Tesla, Inc. (TSLA)”).  
    • Use ISO dates (**YYYY‑MM‑DD**) and, if helpful, include a short human label (e.g., “(Wed)”).

  **Templates (pick the one that fits; omit unused lines):**

  **Single date — daily timeframe**  
  “{COMPANY} ({TICKER}) — {P}-day volatility for **{DATE_REQ}** (date used: {DATE_USED}):  
   • **$ σ:** **${VOL_RAW}**  
   • **Daily % σ:** **{VOL_PCT}%**  
   • **Annualized % σ:** **{VOL_ANN}%**  
   Close used: **${CLOSE_USED}**.  
   Source: {SOURCE_NOTE}.”

  **Single date — intraday timeframe**  
  “{COMPANY} ({TICKER}) — {P}-bar volatility for **{DATE_REQ}** on **{TIMEFRAME}** (last bar used: {BAR_USED}):  
   • **$ σ:** **${VOL_RAW}**  
   • **Bar % σ:** **{VOL_PCT}%**  
   Source: {SOURCE_NOTE}.”

  **Compare multiple periods on one date**  
  “{COMPANY} ({TICKER}) — volatility on **{DATE_REQ}** (date used: {DATE_USED})  
   • **{P1}-day:** **${RAW1} | {PCT1}%** (annualized **{ANN1}%**)  
   • **{P2}-day:** **${RAW2} | {PCT2}%** (annualized **{ANN2}%**)  
   • **{P3}-day:** **${RAW3} | {PCT3}%** (annualized **{ANN3}%**)  
   **Which is higher:** {ORDERING}.  
   Source: {SOURCE_NOTE}.”

  **Range summary (with regular cadence, e.g., Fridays)**  
  “{COMPANY} ({TICKER}) — {P}-day volatility from **{FROM} → {TO}**  
   • **Fridays:**  
     – {D1}: **${R1} | {P1}%** {Adj1?}  
     – {D2}: **${R2} | {P2}%** {Adj2?}  
     – {D3}: **${R3} | {P3}%** {Adj3?}  
   • **Max % σ:** **{MAXPCT}%** on **{MAXDATE}**  
   • **Min % σ:** **{MINPCT}%** on **{MINDATE}**  
   Source: {SOURCE_NOTE}.”

  **Threshold analysis / streaks (daily)**  
  “{COMPANY} ({TICKER}) — {P}-day volatility vs **{THRESH}%** (**{FROM} → {TO}**)  
   • **Days > {THRESH}%:** **{COUNT}**  
   • **Crossed up:** [{UP_DATES}]  
   • **Crossed down:** [{DOWN_DATES}]  
   • **Longest > {THRESH}% streak:** **{L}** days (**{START} → {END}**)  
   Source: {SOURCE_NOTE}.”


"""


# --- 3. Create the async ReAct agent ---
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt
)



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
    # messages = [HumanMessage(content=full_prompt)]
    # async for state in agent.astream({"messages": messages}, config):
    #     final_msg = state["messages"][-1]
    #     # When the last message is not a tool call (AIMessage/tool_calls == []), print it and break
    #     if not getattr(final_msg, "tool_calls", None):
    #         print(f"\n Assistant: {final_msg.content}\n")
    #         break

    # async for chunk in agent.astream(
    #     {"messages": [{"role": "user", "content": full_prompt}]},
    #     stream_mode="updates"
    # ):m
    #     print(chunk)

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



    
