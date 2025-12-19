from fastapi import HTTPException
from litellm import acompletion
import src.backend.db.mongodb as mongodb
import json
import src.backend.utils as utils
from typing import AsyncGenerator
from datetime import datetime
import json
from dotenv import load_dotenv
import time
#from src.ai.llm.config import SummarizerConfig
from src.ai.llm.config_openai import  SummarizerConfig
from src.backend.utils.utils import get_unique_response_id

load_dotenv()
smc = SummarizerConfig()

async def stream_summary(user_id: str, session_id: str, message_id: str, prev_message_id: str, user_query: str, local_time: datetime, timezone: str, is_elaborate: bool = False, give_examples: bool = True) -> AsyncGenerator[str, None]:
    start_time = time.monotonic()
    last_message = await mongodb.get_response_by_message_id(prev_message_id)

    if 'error' in last_message:
        yield f"data: {json.dumps({'type': 'error', 'content': 'No message found for this session', 'message_id': message_id})}\n\n"
        return

    text_to_summarize = last_message.get('response')

    operation_title = "Elaborating response" if is_elaborate else "Summarizing response"
    agent_name = "Elaborating Agent" if is_elaborate else "Summarizing Agent"

    base_prompt = f"""Below is a response from an AI assistant:

{text_to_summarize}

Your task:
"""

    if is_elaborate:
        base_prompt += """- The response is short — **elaborate** on it and make it more informative.
- **CRITICAL**: If you see any HTML elements like <iframe>, <div>, etc., preserve them EXACTLY as they are. Do not modify, wrap, or change them in any way.
- Expand on the content around these elements, providing more context, analysis, and insights.
- Add more detailed explanations, market analysis, trends, and business insights. Generate additional definitions for complex technical or any other complex terms.
"""
    else:
        base_prompt += "- The response is long — condense it into a concise list of 5–10 lines of information.\n"

    base_prompt += """- **Do not mention or refer to any backend systems, agents, APIs, or implementation details used to generate the original response.**
- Return the final response in **Markdown** format
- Strictly don't return ```markdown ``` content blocks.
"""

    if give_examples:
        base_prompt += """- After the improved response, add a new section titled **Examples**.
- Under **Examples**, provide **relevant bullet-point examples** that illustrate key points clearly.
- Format both the main content and examples in **Markdown**, but do **not** include triple backticks or code fences.
"""
    try:
        yield f"data: {json.dumps({'type': 'research', 'agent_name': agent_name, 'title': operation_title, 'id': get_unique_response_id(), 'created_at': local_time.isoformat(), 'message_id': message_id})}\n\n"
        
        stream = await acompletion(
            model=smc.MODEL,
            messages=[{
                "role": "user",
                "content": base_prompt
            }],
            temperature=smc.TEMPERATURE,
            stream=smc.STREAM
        )

        summary_chunks = []
        response_id = get_unique_response_id()
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    content_piece = delta.content
                    summary_chunks.append(content_piece)
                    yield f"data: {json.dumps({'type': 'response-chunk', 'agent_name': agent_name, 'message_id': message_id, 'id': response_id, 'content': content_piece})}\n\n"

        full_summary = ''.join(summary_chunks)
        
        end_time = time.monotonic()
        duration_seconds = end_time - start_time
        time_event = {"type": "response_time", "content": f"{int(duration_seconds)} sec", "message_id": message_id, "in_seconds": int(duration_seconds)}

        if duration_seconds >= 60:
            minutes = int(duration_seconds // 60)
            remaining_seconds = int(duration_seconds % 60)
            time_event["content"] = f"{minutes} min {remaining_seconds} sec"

        yield f"data: {json.dumps(time_event)}\n\n"

        complete_payload = {
            'type': 'complete',
            'message_id': message_id,
            'notification': True,
            'suggestions': False,
            'retry': False,
        }

        yield f"data: {json.dumps(complete_payload)}\n\n"
        retry_flag = complete_payload['retry']
        # yield f"data: {json.dumps({'type': 'complete', 'message_id': message_id, 'notification': True, 'suggestions': False, 'retry': True})}\n\n"

        messages_for_db = [
            {
                'user_query': user_query,
                'operation_type': 'elaborate' if is_elaborate else 'summarize',
                'created_at': local_time,
                'retry': retry_flag
            },
            {
                'type': 'research',
                'agent_name': agent_name,
                'title': operation_title,
                'id': get_unique_response_id(),
                'created_at': local_time
            },
            {
                'type': 'response',
                'agent_name': agent_name,
                'content': full_summary,
                'id': get_unique_response_id(),
                'created_at': local_time
            }
        ]
        local_time = local_time
        
        await mongodb.append_data(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            messages=messages_for_db,
            local_time=local_time,
            time_zone=local_time,
            retry=retry_flag,
            metadata=None,
            time_taken=2
        )
        await mongodb.update_session_history_in_db(session_id, user_id, message_id, user_query, full_summary, [], local_time, 'UTC')

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'message_id': message_id})}\n\n"
        try:
            error_msg = f"Error in Summarizing/Elaborating agent processing: {str(e)}"
            error_messages = [
                {
                    'user_query': user_query,
                    'operation_type': 'elaborate' if is_elaborate else 'summarize',
                    'created_at': local_time,
                    'retry': False
                },
                {
                    'error': error_msg,
                    'agent_name': agent_name,
                    'message_id': message_id
                }
            ]
            await mongodb.append_data(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                messages=error_messages,
                local_time=utils.get_date_time().isoformat(),
                time_zone='UTC',
                retry=False,
            )
            await mongodb.update_session_history_in_db(session_id, user_id, message_id, user_query, error_msg, [], local_time, 'UTC')
        except Exception as db_error:
            print(f"Failed to save error to database: {db_error}")
