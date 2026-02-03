# Related Queries Language Issue - Fix Documentation

## Issue Description

Related queries were being generated in Hindi instead of English, even when the user's original query was in English. This was observed particularly for Indian stocks like "Jyoti Limited".

---

## Root Cause Analysis

Two locations in the codebase were responsible for generating related queries, and both had language-related issues:

### 1. `src/ai/agents/utils.py` - `get_related_queries_util()`

**Problem:** The prompt explicitly instructed the LLM to generate queries in the same language as the **AI response**, not the user query.

```python
# OLD PROMPT (Line 217)
"Generate the queries same language as the response generasted by the AI."
```

**Why this was wrong:** If the AI response contained Hindi content (from data sources, company information, financial data, etc.), the related queries would be generated in Hindi regardless of what language the user asked in.

### 2. `src/ai/chart_bot/chart_bot_utils/generate_related_qn.py` - `chart_bot_related_query()`

**Problem:** The prompt had **no language instruction at all**.

```python
# OLD PROMPT (Line 29-31)
system_prompt = """
Generate 4 questions regarding stock chart or crypto chart for the following information.
"""
```

**Why this was wrong:** Without explicit language guidance, the LLM would default based on context. For Indian companies like "Jyoti Limited", the model might choose Hindi based on the company name or context data.

---

# Stage 1 Changes (2026-02-03) - FAILED

## Approach
Added prompt instructions telling the LLM to match the language of the user query.

---

### Stage 1 - Change 1: `src/ai/agents/utils.py` (Line 216-218)

**Before:**
```python
def get_related_queries_util(previous_messages: dict) -> List[str]:
    input = """
    You are given a list of user search queries and corresponding AI responses from a past interaction, ordered from oldest to latest. Your task is to generate four related search queries that a user might ask next or that are semantically similar to the original queries, taking into account both the user query and the AI response. All generated queries must focus on financial or economic aspects related to the topic of the original query and response. The queries should be concise, relevant, and designed to explore financial implications, economic impacts, or business-related angles. Generate the queries same language as the response generasted by the AI.
    """
```

**After:**
```python
def get_related_queries_util(previous_messages: dict) -> List[str]:
    input = """
    You are given a list of user search queries and corresponding AI responses from a past interaction, ordered from oldest to latest. Your task is to generate four related search queries that a user might ask next or that are semantically similar to the original queries, taking into account both the user query and the AI response. All generated queries must focus on financial or economic aspects related to the topic of the original query and response. The queries should be concise, relevant, and designed to explore financial implications, economic impacts, or business-related angles.

    **IMPORTANT**: Generate the queries in the same language as the User Query. If the User Query is in English, generate queries in English. If the User Query is in Hindi, generate queries in Hindi. Always match the language of the User Query, NOT the AI response.
    """
```

**Reason:** Changed instruction from "same language as AI response" to "same language as User Query" with explicit examples for clarity.

---

### Stage 1 - Change 2: `src/ai/chart_bot/chart_bot_utils/generate_related_qn.py` (Line 20-31)

**Before:**
```python
async def chart_bot_related_query(name: str, ticker: str, exchange: str, context_data: List[dict]) -> List[str]:
    """
    Args:
        name: The name of the company or cryptocurrency.
        ticker: The ticker symbol (e.g., 'AAPL') or crypto symbol (e.g., 'BTCUSD').
        exchange: The exchange it trades on (e.g., 'NASDAQ' or 'Crypto').
    """

    system_prompt = """
    Generate 4 questions regarding stock chart or crypto chart for the following information.
    """
```

**After:**
```python
async def chart_bot_related_query(name: str, ticker: str, exchange: str, context_data: List[dict], user_query: str = "") -> List[str]:
    """
    Args:
        name: The name of the company or cryptocurrency.
        ticker: The ticker symbol (e.g., 'AAPL') or crypto symbol (e.g., 'BTCUSD').
        exchange: The exchange it trades on (e.g., 'NASDAQ' or 'Crypto').
        user_query: The user's original query to match language.
    """

    system_prompt = f"""
    Generate 4 questions regarding stock chart or crypto chart for the following information.

    **IMPORTANT**: Generate all questions in the same language as the user's original query: "{user_query}". If the user query is in English, generate questions in English. If in Hindi, generate in Hindi. Do not switch languages based on company names or context data.
    """
```

**Reason:**
1. Added `user_query` parameter to receive the user's original query
2. Added explicit language instruction that references the user's query
3. Changed to f-string to include the actual user query in the prompt

---

### Stage 1 - Change 3: `src/backend/api/session.py` (Line 938-950)

**Before:**
```python
        realtime = chart.get("realtime", {})
        historical = chart.get("historical", {})
        name = realtime.get("name", "")
        ticker = realtime.get("symbol", "")
        exchange = realtime.get("exchange", "")
        context_data = [realtime, historical]

        queries = await chart_bot_related_query(
            name=name,
            ticker=ticker,
            exchange=exchange,
            context_data=context_data
        )
```

**After:**
```python
        realtime = chart.get("realtime", {})
        historical = chart.get("historical", {})
        name = realtime.get("name", "")
        ticker = realtime.get("symbol", "")
        exchange = realtime.get("exchange", "")
        context_data = [realtime, historical]
        user_query = message_log.human_input.get("user_query", "") if message_log.human_input else ""

        queries = await chart_bot_related_query(
            name=name,
            ticker=ticker,
            exchange=exchange,
            context_data=context_data,
            user_query=user_query
        )
```

**Reason:**
1. Extract the user's original query from `message_log.human_input`
2. Pass it to `chart_bot_related_query()` so the function can use it for language matching

---

## Stage 1 - Why It Failed

- Gemini (the LLM being used) ignored the language instruction when it saw Indian company names/context
- The instruction was placed at the BEGINNING of the prompt, where it got overshadowed by later content (guidelines, examples)
- The LLM still defaulted to Hindi for Indian companies like "Jyoti Limited"

---

# Stage 2 Changes (2026-02-03) - CURRENT FIX

## Approach
Programmatic language detection + stronger prompt instructions placed at the END of the prompt.

**Key insight:** Instead of relying on the LLM to detect and respect language, we detect language programmatically and give explicit, forceful instructions at the end where LLMs pay more attention.

---

### Stage 2 - Change 1: Added `detect_query_language()` function

**Added to both `src/ai/agents/utils.py` and `src/ai/chart_bot/chart_bot_utils/generate_related_qn.py`:**

```python
def detect_query_language(text: str) -> str:
    """
    Detect if text is primarily English or Hindi based on character analysis.
    Returns 'english' or 'hindi'.
    """
    if not text:
        return 'english'

    # Count Devanagari characters (Hindi script range: U+0900 to U+097F)
    devanagari_count = sum(1 for char in text if '\u0900' <= char <= '\u097F')
    # Count ASCII letters
    ascii_count = sum(1 for char in text if char.isascii() and char.isalpha())

    # If more than 10% of alphabetic characters are Devanagari, consider it Hindi
    total_alpha = devanagari_count + ascii_count
    if total_alpha > 0 and (devanagari_count / total_alpha) > 0.1:
        return 'hindi'
    return 'english'
```

**Reason:** Programmatic detection is reliable - no LLM interpretation needed.

---

### Stage 2 - Change 2: `src/ai/agents/utils.py` - Updated `get_related_queries_util()`

**Changes made:**

1. Removed the `**IMPORTANT**` language instruction from the BEGINNING of the prompt

2. Added language detection after extracting user query:
```python
    # Extract user query for language detection
    user_query_text = ""
    for msg in previous_messages['messages'][-1:]:
        user_query_text = msg[0]
        input += f" User Query: {msg[0]}\n"
        input += f" AI Answer: {msg[1]}\n"

    # Detect language of user query
    detected_language = detect_query_language(user_query_text)

    print(f"Detected language: {detected_language} (from query: {user_query_text})")
```

3. Added CRITICAL language instruction at the END of the prompt (after guidelines, before schema):
```python
    # Add explicit language instruction at the END (more effective position)
    if detected_language == 'english':
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: The User Query is in ENGLISH. You MUST generate ALL 4 related queries in ENGLISH ONLY.
    Do NOT use Hindi, Devanagari script, or any other language. Every single query must be written entirely in English.
    """
    else:
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: The User Query is in HINDI. You MUST generate ALL 4 related queries in HINDI ONLY.
    Use Devanagari script. Every single query must be written entirely in Hindi.
    """
    input += language_instruction
```

---

### Stage 2 - Change 3: `src/ai/chart_bot/chart_bot_utils/generate_related_qn.py` - Updated `chart_bot_related_query()`

**Changes made:**

1. Added `detect_query_language()` function (same as above)

2. Removed the `**IMPORTANT**` instruction from `system_prompt`

3. Added language detection at the start:
```python
    # Detect language of user query
    detected_language = detect_query_language(user_query)
    print(f"chart_bot_related_query - Detected language: {detected_language} (from query: {user_query})")
```

4. Added CRITICAL language instruction after context, before schema:
```python
    # Add explicit language instruction at the END (more effective position)
    if detected_language == 'english':
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: You MUST generate ALL 4 questions in ENGLISH ONLY.
    Do NOT use Hindi, Devanagari script, or any other language. Every single question must be written entirely in English.
    The company name may be Indian but your output MUST be in English.
    """
    else:
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: You MUST generate ALL 4 questions in HINDI ONLY.
    Use Devanagari script. Every single question must be written entirely in Hindi.
    """
    input += language_instruction
```

---

## Summary Table

| Stage | File | Change | Reason |
|-------|------|--------|--------|
| 1 | `utils.py` | Added language instruction at beginning | Tell LLM to match user query language |
| 1 | `generate_related_qn.py` | Added `user_query` param + instruction | Enable language matching |
| 1 | `session.py` | Extract and pass `user_query` | Provide user query to function |
| 2 | `utils.py` | Added `detect_query_language()` | Programmatic language detection |
| 2 | `utils.py` | Moved instruction to END of prompt | LLMs follow end instructions better |
| 2 | `utils.py` | Used "CRITICAL" + explicit prohibition | Stronger compliance |
| 2 | `generate_related_qn.py` | Added `detect_query_language()` | Programmatic language detection |
| 2 | `generate_related_qn.py` | Moved instruction to END of prompt | LLMs follow end instructions better |
| 2 | `generate_related_qn.py` | Added Indian company clarification | Handle edge case explicitly |

---

## Why Stage 2 Should Work

1. **Programmatic detection** - No reliance on LLM to detect language
2. **End-of-prompt placement** - LLMs tend to follow instructions at the end more strictly
3. **Explicit prohibition** - "Do NOT use Hindi, Devanagari script" leaves no ambiguity
4. **CRITICAL keyword** - Signals high importance to the model
5. **Edge case handling** - "The company name may be Indian but..." addresses the specific issue

---

## Testing

To verify the fix works correctly:

1. **English Query Test:** Ask a query in English about an Indian stock (e.g., "Tell me about Jyoti Limited stock")
   - Expected: Related queries should be in English
   - Check logs for: `Detected language: english`

2. **Hindi Query Test:** Ask a query in Hindi about any stock
   - Expected: Related queries should be in Hindi
   - Check logs for: `Detected language: hindi`

3. **Mixed Content Test:** Ask in English about a stock with Hindi company name in data
   - Expected: Related queries should still be in English (matching user query)

---

## Timeline

- **Issue Identified:** 2026-02-02
- **Stage 1 Fix Applied:** 2026-02-03 (prompt-only approach - FAILED)
- **Stage 2 Fix Applied:** 2026-02-03 (programmatic detection + end-of-prompt instruction - CURRENT)
