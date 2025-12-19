from src.ai.tools.web_search_tools import advanced_internet_search
from src.ai.tools.finance_data_tools import get_stock_data, search_company_info
# from src.ai.tools.internal_db_tools import search_qdrant_tool
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from src.ai.llm.model import get_llm, get_llm_alt
#from src.ai.llm.config import FastAgentConfig, CountUsageMetricsPricingConfig
from src.ai.llm.config import FastAgentConfig, CountUsageMetricsPricingConfig
from langgraph.types import Command
from src.backend.utils.utils import get_date_time, format_fast_agent_update, PRICING, get_user_metadata
import asyncio
import src.backend.db.mongodb as mongodb
import time
from src.backend.utils.api_utils import check_stop_conversation
from src.ai.agents.utils import get_related_queries_util
import traceback
from src.ai.agent_prompts.fast_agent import SYSTEM_PROMPT

fc = FastAgentConfig()
cmp = CountUsageMetricsPricingConfig()

llm = get_llm(fc.MODEL, fc.TEMPERATURE, fc.MAX_TOKENS)
llm_alt = get_llm_alt(fc.ALT_MODEL, fc.ALT_TEMPERATURE, fc.ALT_MAX_TOKENS)


async def format_fast_agent_input_prompt(user_query: str, session_id: str, prev_message_id: str, timezone: str, ip_address: str = "", doc_ids: Optional[list[str]] = None) -> str:
    input_prompt = ""
    history = []
    prev_session_data = await mongodb.get_session_history_from_db(session_id, prev_message_id, limit=7)

    input_prompt += f"### Latest User Query: {user_query}\n"
    
    if doc_ids:
        input_prompt += f"### Document IDs of user uploaded files: {doc_ids}\n\n"

    if prev_session_data.get('doc_ids'):
        input_prompt += f"### The Latest User Query maybe based on these Previous Document IDs of user uploaded files: {prev_session_data.get('doc_ids')}\n\n"

    input_prompt += f"\n{await asyncio.to_thread(get_user_metadata, timezone, ip_address)}\n\n"

    if prev_message_id:
        previous_message_pairs = prev_session_data.get('messages', [])
        if previous_message_pairs != []:
            for msg in previous_message_pairs:
                history.append(HumanMessage(content="### User Query: " + msg[0]))
                history.append(AIMessage(content=msg[1]))

    history.append(HumanMessage(content=input_prompt))
    return history


async def process_fast_agent_input(user_id: str, session_id: str, user_query: str, message_id: str, prev_message_id: str, timezone: str = "UTC", ip_address: str = "", doc_ids: Optional[list[str]] = []):
    """
    Process the user's input and generate a response using the Insight Agent.
    """
    start_time = time.monotonic()
    sources_for_message = []
    query_metadata = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'token_cost': 0.0}
    final_response_content = ""
    stopTime = time.time()

    local_time = get_date_time(timezone)

    def store_current_message(content: dict):
        enriched_content = content.copy()

        if 'created_at' not in enriched_content:
            enriched_content['created_at'] = local_time.isoformat()

        if 'response' in enriched_content:
            return enriched_content

        if 'type' in enriched_content and enriched_content['type'].endswith('chunk'):
            return

        return enriched_content


    def count_usage_metrics(token_usage):


        model = token_usage.get(get_llm(cmp.MODEL))
        pricing = PRICING.get(model, PRICING.get[cmp.MODEL])

        input_cost = pricing["input"] * token_usage.get("input_tokens", 0)
        output_cost = pricing["output"] * token_usage.get("output_tokens", 0)
        total_cost = input_cost + output_cost

        query_metadata["input_tokens"] += token_usage.get("input_tokens", 0)
        query_metadata["output_tokens"] += token_usage.get("output_tokens", 0)
        query_metadata["total_tokens"] += token_usage.get("total_tokens", 0)
        query_metadata["token_cost"] += total_cost


    yield {"start_stream": str(message_id)}
    
    try:
        system_msg = SystemMessage(content=SYSTEM_PROMPT)
        input_messages = await format_fast_agent_input_prompt(user_query, session_id, prev_message_id, timezone, ip_address, doc_ids)
        
        # agent = create_react_agent(model=llm, tools=[advanced_internet_search, get_stock_data, search_qdrant_tool, search_company_info], prompt=system_msg)
        agent = create_react_agent(model=llm, tools=[advanced_internet_search, get_stock_data, search_company_info], prompt=system_msg)
        
        input_data = {
            'user_query': user_query,
            'doc_ids': doc_ids if doc_ids else [],
        }
        yield {"enriched_content": store_current_message(input_data)}
        message_logs = f"HUMAN INPUT\n{str(input_data)}\n\n"
        yield {"message_logs": message_logs}
        await mongodb.store_user_query(user_id, session_id, message_id, user_query, timezone, doc_ids)

        async for stream_mode, update in agent.astream(input={"messages": input_messages}, stream_mode=['updates', 'messages', 'custom'], config={'recursion_limit': 50}):
            # Add delay at the start of each iteration
            # await asyncio.sleep(0.1)  # Small delay between steps
            if stream_mode == 'updates':
                print("---\n", update, "\n---")
                message_logs = f"AGENT UPDATE\n{str((stream_mode, update))}\n\n"
                yield {"message_logs": message_logs}
            
            if stream_mode == 'custom':
                print("---\n", update, "\n---")
                if 'source_update' in update:
                    sources_for_message.extend(update['source_update'])
            # if stopTime + 3 < time.time():
            #     stop_processing = await check_stop_conversation(session_id, message_id)
            #     if stop_processing:
            #         raise RuntimeError("User stopped query processing.")
            #     stopTime = time.time()
            
            msg_to_yield = await format_fast_agent_update(stream_mode, update)

            if msg_to_yield:
                message_logs = f"FORMATTED MESSAGE\n{str(msg_to_yield)}\n\n"
                yield {"message_logs": message_logs}

            if isinstance(msg_to_yield, list):
                for m_item in msg_to_yield:
                    if 'token_usage' in m_item:
                        count_usage_metrics(m_item['token_usage'])
                    else:
                        yield m_item

                        yield {"enriched_content": store_current_message(m_item)}
                        if 'sources' in m_item:
                            sources_for_message.extend(m_item['sources'])
                            
                        if 'response' in m_item:
                            final_response_content = m_item['response']

        end_time = time.monotonic()
        duration_seconds = end_time - start_time
        time_event = {"time": f"{int(duration_seconds)} sec", "message_id": message_id, "in_seconds": int(duration_seconds)}

        if duration_seconds >= 60:
            minutes = int(duration_seconds // 60)
            remaining_seconds = int(duration_seconds % 60)
            time_event["time"] = f"{minutes} min {remaining_seconds} sec"
        yield time_event

        await mongodb.update_session_history_in_db(session_id, user_id, message_id, user_query, final_response_content, doc_ids, local_time, timezone)

        final_data_event = {'state': "completed_from_graph"}

        related_queries = await asyncio.to_thread(get_related_queries_util, await mongodb.get_session_history_from_db(session_id, message_id, limit = 3))

        if related_queries:
            final_data_event['related_queries'] = related_queries

        if sources_for_message:
            final_data_event['sources'] = sources_for_message
            yield {"enriched_content": store_current_message({'sources': sources_for_message})}

        yield final_data_event

        yield {"store_data": {}, 'notification': True, 'suggestions': True, 'retry': True}

    except Exception as e:
        error_msg = f"Error in agent processing: {traceback.format_exc()}"
        print(error_msg)
        message_logs = f"ERROR MESSAGE\n{str(error_msg)}\n\n"
        yield {"message_logs": message_logs}
        error_event = {'error': error_msg}
        yield error_event

        if final_response_content == "No response generated":
            await mongodb.update_session_history_in_db(session_id, user_id, message_id, user_query, final_response_content or error_msg, doc_ids, local_time, timezone)

        yield {"enriched_content": store_current_message(error_event)}
        yield {"store_data": {}, 'notification': False, 'suggestions': False, 'retry': True}

    finally:
        pass
