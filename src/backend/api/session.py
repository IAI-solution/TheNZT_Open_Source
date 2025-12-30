import asyncio
import json
import os
import re
import uuid
import traceback
import time
import base64
import tempfile

from src.ai.chart_bot.chart_bot_utils.generate_related_qn import chart_bot_related_query
from src.ai.stock_prediction.stock_prediction_functions import get_sentiment_rating, get_stock_history, sarimax_predict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, HTTPException, Query,status, BackgroundTasks, File, UploadFile
from fastapi.responses import StreamingResponse,JSONResponse, StreamingResponse
from typing import Optional, Dict, Any, AsyncGenerator
from src.ai.ai_schemas.tool_structured_input import TickerSchema
from src.ai.tools.financial_tools import get_stock_data
import src.backend.db.mongodb as mongodb
from src.backend.utils.agent_comm import process_agent_input_functional
from src.ai.agents.fast_agent import process_fast_agent_input
from src.ai.agents.summarizer import stream_summary
from src.backend.models.app_io_schemas import StockPredictionRequest, StockDataRequest, ResponseFeedback, ExportResponse, UpdateSessionAccess,UpdateMessageAccess
# from src.backend.utils.api_utils import notify_slack_error, redis_manager
from src.backend.utils.export_utils import markdown_to_pdf, markdown_to_docx, slugify
import src.backend.utils as utils
import src.backend.db.filestorage as filestorage
from src.backend.db.mongodb import RelatedQueriesResponse,UploadResponse, MessageLog,StockDataRequest, QueryRequestModel
from src.backend.core.api_limit import apiSecurityFree
from src.ai.stock_prediction.stock_prediction import StockAnalysisAgent
from src.backend.utils.api_utils import redis_manager
from src.backend.db.mongodb import handle_partial_data_storage
from src.backend.utils.utils import render_charts_as_images

stock_agent = StockAnalysisAgent()
router = APIRouter()

@router.get("/__ping")
async def ping():
    return {"ok": True}

@router.get("/sessions")
async def list_sessions2(user : apiSecurityFree, page: int = 1, limit: int = 25) -> Dict[str, Any]:
    """
    Fetch all sessions of a user, ordered by timestamp.
    """
    
    sessions = await mongodb.get_sessions_by_user2(user.id.__str__(), page, limit)
    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found for this user.")
    return sessions

@router.get("/filter-with-title-pagination/search")
async def search_sessions_by_title_pagination(
    user: apiSecurityFree,
    keyword: str = None,
    page: int = 1,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Return paginated sessions whose title contains the keyword, grouped by timeline.
    """
    
    if(keyword == "" or keyword == None or keyword == " "):
        return await mongodb.get_sessions_by_user2(user.id.__str__(), page, limit)
    result = await mongodb.get_sessions_by_user_and_keyword_pagination(user.id.__str__(), keyword, page, limit)
    return result

@router.put("/sessions/rename")
async def rename_session(user: apiSecurityFree, session_id: str, new_title: str):
    """
    Rename the title of a session for the current user.
    """
    if not session_id or not new_title:
        raise HTTPException(status_code=400, detail="Session ID and title are required.")
    return await mongodb.rename_session_title(user.id.__str__(), session_id, new_title)

@router.get("/messages")
async def list_messages(user: apiSecurityFree, session_id: str = Query(..., alias="sessionId")):
    """
    Fetch all message logs for a session, ordered by timestamp.
    """
    try:
        session_log = await mongodb.get_session_log_by_user_and_session_id(user.id.__str__(), session_id)
        print("session logs",session_log)

        if not session_log:
            raise HTTPException(status_code=404, detail="Session not found or access denied.")

        messages = await mongodb.get_messages_by_session(session_id)

        if not messages:
            raise HTTPException(status_code=404, detail="No messages found for this session.")

        return messages

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encountered error in loading session messages: {str(e)}")


@router.delete("/delete/{session_id}")
async def delete_session(user: apiSecurityFree, session_id: str):
    
    result = await mongodb.delete_session(user.id, session_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID '{session_id}' not found"
        )

    return {"status": "success", "message": f"Session '{session_id}' deleted"}



@router.post("/query-stream")
async def query_and_stream(user: apiSecurityFree, query: QueryRequestModel, request: Request, bgt: BackgroundTasks):
    
    user_id = user.id.__str__()
    user_query = query.user_query
    session_id = query.session_id
    realtime_info = query.realtime_info
    search_mode = query.search_mode
    retry_response = query.retry_response
    message_id = query.message_id
    prev_message_id = query.prev_message_id
    timezone = query.timezone
    doc_ids = query.doc_ids
    ip_address = request.client.host
    website = str(request.base_url)
    is_elaborate = query.is_elaborate
    is_example = query.is_example

    user_tz = ZoneInfo(timezone)
    local_time = datetime.now(user_tz)
    stopTime = time.time()
    # if (not user_id or not user_query):
    #     async def error_gen_missing_field():
    #         error_event = {"type": "error", "content": "user_id and user_query are required."}
    #         yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        
    #     return StreamingResponse(error_gen_missing_field(), media_type="text/event-stream", status_code=422)
    
    # ✅ validation logic
    if not user_id:
        async def error_gen_missing_field():
            error_event = {"type": "error", "content": "user_id is required."}
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        return StreamingResponse(error_gen_missing_field(), media_type="text/event-stream", status_code=422)

    
    
    if not session_id:
        session_id = str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal session_id, message_id

        session_info_event_data = {
            "session_id": session_id,
            "message_id": message_id,
            "status": "starting query processing"
        }
        yield f"event: session_info\ndata: {json.dumps(session_info_event_data)}\n\n"

        token_buffer = []
        stock_graph = set()
        user_data = await mongodb.fetch_user_by_id(user_id)
        user_name = user_data.full_name if user_data and user_data.full_name else "user"
        error_flag = False
        message_log = ""
        current_messages_log = []
        processor_iterator = None
        time_taken = 0


         # Variables to track partial data for storage
        partial_content_buffer = []  # Store all streamed content chunks
        partial_sources = []
        partial_related_queries = []
        partial_metadata = None

        try:
            if search_mode == 'summarizer':
                async for event in stream_summary(user_id, session_id, message_id, prev_message_id, user_query, local_time, timezone, is_elaborate, is_example):
                    yield event.encode('utf-8')
                return
                
            else:
                if search_mode == 'fast':
                    processor_iterator = process_fast_agent_input(
                        user_id=user_id,
                        session_id=session_id,
                        user_query=user_query,
                        message_id=message_id,
                        prev_message_id=prev_message_id,
                        timezone = timezone,
                        ip_address = ip_address,
                        doc_ids = doc_ids
                    )

                else:
                    pro_reasoning = (search_mode == 'agentic-reasoning')

                    processor_iterator = process_agent_input_functional(
                        user_id=user_id,
                        session_id=session_id,
                        user_query=user_query,
                        message_id=message_id,
                        prev_message_id=prev_message_id,
                        realtime_info=realtime_info,
                        pro_reasoning=pro_reasoning,
                        retry_response=retry_response,
                        timezone = timezone,
                        ip_address = ip_address,
                        doc_ids = doc_ids,
                    )
                    
            TIMEOUT_PERIOD = 300
            KEEP_ALIVE_INTERVAL = 5
            KEEP_ALIVE_COUNT = 0
            MAX_KEEP_ALIVE_COUNT = 60
            batched_event_count = 0
            await mongodb.append_data(user_id, session_id, message_id, current_messages_log, local_time, timezone)
            while True:
                stop_key = f"stop:{session_id}"
                stop_signal = await redis_manager.safe_execute("get", stop_key)
                if stop_signal:
                    # Handle both string and bytes responses from Redis
                    stop_signal_str = stop_signal.decode('utf-8') if isinstance(stop_signal, bytes) else str(stop_signal)
                    if stop_signal_str == message_id:
                        # Clear the stop signal
                        await redis_manager.safe_execute("delete", stop_key)
                        raise asyncio.CancelledError("User requested stop")
                try:
                    processor_task = asyncio.create_task(anext(processor_iterator))
                    try:
                        while True:
                            done, _ = await asyncio.wait({processor_task}, timeout=KEEP_ALIVE_INTERVAL)
                            if processor_task in done:
                                try:
                                    data_from_processor = processor_task.result()
                                    KEEP_ALIVE_COUNT = 0  # Reset keep-alive count
                                except asyncio.CancelledError:
                                    print("Processor task was cancelled.")
                                    stream_completed = True
                                    break
                                except StopAsyncIteration:
                                    stream_completed = True
                                    break
                                except Exception as e:
                                    print("Exception in processor task:", e)
                                    continue

                                if not data_from_processor:
                                    continue    
                                break

                            else:
                                KEEP_ALIVE_COUNT += 1
                                if KEEP_ALIVE_COUNT >= MAX_KEEP_ALIVE_COUNT:
                                    processor_task.cancel()
                                    try:
                                        await processor_task
                                    except Exception:
                                        pass
                                    raise RuntimeError(f"No update from processor for {TIMEOUT_PERIOD} seconds. Stream aborted.")
                                yield f"data: {json.dumps({'type': 'Keep-alive', 'alive-counter': KEEP_ALIVE_COUNT})}\n\n".encode('utf-8')
                                
                                # Check for stop signal during keep-alive
                                stop_signal = await redis_manager.safe_execute("get", stop_key)
                                if stop_signal:
                                    # Handle both string and bytes responses from Redis
                                    stop_signal_str = stop_signal.decode('utf-8') if isinstance(stop_signal, bytes) else str(stop_signal)
                                    if stop_signal_str == message_id:
                                        processor_task.cancel()
                                        await redis_manager.safe_execute("delete", stop_key)
                                        raise asyncio.CancelledError("User requested stop")

                    # except StopAsyncIteration:
                    #     stream_completed = True
                    #     break
                    except Exception as e:
                        traceback.print_exc()
                        raise RuntimeError(f"Error in waiting for data: {str(e)}")

                    data_to_send = data_from_processor.copy()

                    if 'start_stream' in data_to_send:
                        payload = {"type": "connected", "message_id": message_id}
                        yield f"data: {json.dumps(payload)}\n\n".encode('utf-8')

                        if search_mode == "agentic-planner" or "agentic-reasoning":
                            progress_payload = {"type": "progress", "progress_bar": 0.0}
                            yield f"data: {json.dumps(progress_payload)}\n\n".encode('utf-8')
                            

                    elif 'type' in data_to_send and data_to_send['type'].endswith('chunk'):
                        # Store chunk content for partial data recovery
                        if 'content' in data_to_send:
                            partial_content_buffer.append({
                                'content': data_to_send['content'],
                                'agent_name': data_to_send.get('agent_name', ''),
                                'type': data_to_send['type'],
                                'timestamp': time.time()
                            })
                        # agent_changed = (token_buffer and (data_to_send.get('agent_name', '') != token_buffer[0].get('agent_name', '') or data_to_send.get('id', '') != token_buffer[0].get('id', '')))

                        if token_buffer and (len(token_buffer) >= 15 or data_to_send.get('agent_name') != token_buffer[0].get('agent_name')):
                            batched_event_type = token_buffer[0].get('type', 'unknown_chunk_type')
                            
                            batched_event = {
                                "type": batched_event_type, 
                                "agent_name": token_buffer[0].get('agent_name', ''), 
                                "message_id": message_id, 
                                "id": token_buffer[0].get('id','')
                            }

                            if any('content' in t for t in token_buffer):
                                batched_event["content"] = "".join([t.get('content','') for t in token_buffer if 'content' in t])

                            if any('title' in t for t in token_buffer):
                                batched_event["title"] = "".join([t.get('title','') for t in token_buffer if 'title' in t])

                            yield f"data: {json.dumps(batched_event)}\n\n".encode('utf-8')
                            batched_event_count += 1
                            token_buffer = []

                        token_buffer.append(data_to_send)

                    else:
                        if token_buffer:
                            batched_event_type = token_buffer[0].get('type', 'unknown_chunk_type')
                            
                            batched_event = {
                                "type": batched_event_type, 
                                "agent_name": token_buffer[0].get('agent_name', ''), 
                                "message_id": message_id, 
                                "id": token_buffer[0].get('id','')
                            }

                            if any('content' in t for t in token_buffer):
                                batched_event["content"] = "".join([t.get('content','') for t in token_buffer if 'content' in t])

                            if any('title' in t for t in token_buffer):
                                batched_event["title"] = "".join([t.get('title','') for t in token_buffer if 'title' in t])

                            yield f"data: {json.dumps(batched_event)}\n\n".encode('utf-8')
                            token_buffer = []

                        if 'type' in data_to_send:
                            if data_to_send['type'] == 'stock_data':
                                symbol = data_to_send['data']['realtime']['symbol']
                                if symbol not in stock_graph:
                                    stock_graph.add(symbol)
                                    stock_payload = {"stock_data": data_to_send.get('data'), "message_id": message_id, "id": data_to_send.get('chat_session_id', '')}
                                    yield f"event: stock_chart\ndata: {json.dumps(stock_payload)}\n\n".encode('utf-8')

                           
                            elif data_to_send['type'] == 'map_layers':
                                data_to_send['message_id'] = message_id
                                yield f"event: map_data\ndata: {json.dumps(data_to_send)}\n\n".encode('utf-8')
                            
                            else:
                                data_to_send['message_id'] = message_id
                                yield f"data: {json.dumps(data_to_send)}\n\n".encode('utf-8')
                        elif 'message_logs' in data_to_send:
                            message_log += data_to_send['message_logs']
                        elif 'enriched_content' in data_to_send:
                            current_messages_log.append(data_to_send['enriched_content'])

                        elif 'time' in data_to_send:
                            time_taken = data_to_send.get('in_seconds', 0)
                            time_payload = {
                                "type": "response_time", 
                                "content": data_to_send['time'],
                                "message_id": message_id
                            }
                            yield f"data: {json.dumps(time_payload)}\n\n".encode('utf-8')
                        
                        elif 'state' in data_to_send:
                            if 'sources' in data_to_send and data_to_send.get('sources'):
                                sources_payload = {"type": "sources", "content": data_to_send['sources'], "message_id": message_id}
                                partial_sources.extend(data_to_send['sources'])
                                yield f"data: {json.dumps(sources_payload)}\n\n".encode('utf-8')

                            if 'related_queries' in data_to_send and data_to_send.get('related_queries'):
                                related_payload = {"type": "related_queries", "content": data_to_send['related_queries'], "message_id": message_id}
                                partial_related_queries.extend(data_to_send['related_queries'])
                                yield f"data: {json.dumps(related_payload)}\n\n".encode('utf-8')

                        elif 'error' in data_to_send:
                            error_flag = True
                            error_payload = {"type": "error", "content": data_to_send['error'], "message_id": message_id}

                            # if not ("localhost" in website or "127.0.0.1" in website):
                            #     await notify_slack_error(user_name or user_id, str(error_payload))

                            yield f"data: {json.dumps(error_payload)}\n\n".encode('utf-8')
                        
                        elif 'store_data' in data_to_send:
                            store_data = data_to_send['store_data']
                            store_data['retry'] = data_to_send.get('retry', False)
                            partial_metadata = store_data.get('metadata', None)
                            bgt.add_task(mongodb.append_data, user_id, session_id, message_id, current_messages_log, local_time, timezone, store_data['retry'], store_data.get('metadata', None), time_taken)

                            yield f"data: {json.dumps({'type': 'metadata', 'data': store_data.get('metadata',None)})}\n\n".encode('utf-8')

                            # if not error_flag:
                            #     yield f"data: {json.dumps({'type': 'complete', 'message_id': message_id, 'notification': data_to_send.get('notification', True), 'suggestions': data_to_send.get('suggestions', True)})}\n\n".encode('utf-8')

                            if not error_flag:
                                complete_payload = {
                                    'type': 'complete', 
                                    'message_id': message_id, 
                                    'notification': data_to_send.get('notification', True), 
                                    'suggestions': data_to_send.get('suggestions', True),
                                    # 'retry': data_to_send.get('retry', False),
                                    'retry': store_data['retry']
                                }

                                if search_mode == "agentic-planner" or "agentic-reasoning":
                                    progress_payload = {"type": "progress", "progress_bar": 100.0}
                                    yield f"data: {json.dumps(progress_payload)}\n\n".encode('utf-8')
                                
                                if batched_event_count > 300:
                                    complete_payload['is_elaborate'] = False
                                else:
                                    complete_payload['is_elaborate'] = True                             
                                    
                                yield f"data: {json.dumps(complete_payload)}\n\n".encode('utf-8')

                            if message_log:
                                bgt.add_task(mongodb.append_graph_log_to_mongo, session_id, message_id, message_log)

                            break

                        elif 'logs' in data_to_send:
                            if 'metadata' in data_to_send:
                                yield f"data: {json.dumps({'type': 'metadata', 'data': data_to_send.get('metadata',None)})}\n\n".encode('utf-8')

                            if not error_flag:
                                complete_payload = {
                                    'type': 'complete',
                                    'message_id': message_id,
                                    'notification': False,
                                    'suggestions': False,
                                    'retry': True
                                }

                                if search_mode == "agentic-planner" or "agentic-reasoning":
                                    progress_payload = {"type": "progress", "progress_bar": 100.0}
                                    yield f"data: {json.dumps(progress_payload)}\n\n".encode('utf-8')

                                if batched_event_count > 300:
                                    complete_payload['is_elaborate'] = False
                                else:
                                    complete_payload['is_elaborate'] = True        

                                # yield f"data: {json.dumps({'type': 'complete', 'message_id': message_id, 'notification': False, 'suggestions': False})}\n\n".encode('utf-8')
                                yield f"data: {json.dumps(complete_payload)}\n\n".encode('utf-8')

                            bgt.add_task(mongodb.append_graph_log_to_mongo, session_id, message_id, message_log)
                            break
                except Exception as e:
                    traceback.print_exc()
                    raise RuntimeError(f"Data retrieval error: {str(e)}")
        except asyncio.CancelledError:
        
           
           print("User stopped query processing or timeout occurred.")
           # Handle partial data storage for cancelled/stopped streams
           await handle_partial_data_storage(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                partial_content_buffer=partial_content_buffer,
                current_messages_log=current_messages_log,
                partial_sources=partial_sources,
                partial_related_queries=partial_related_queries,
                partial_metadata=partial_metadata,
                message_log=message_log,
                local_time=local_time,
                timezone=timezone,
                time_taken=time_taken,
                bgt=bgt,
                is_cancelled=True
            )
           return
        except Exception as e:
            traceback.print_exc()
            error_payload = {"type": "error", "content": f"Critical stream processing error: {str(e)}", "message_id": message_id}

            # if not ("localhost" in website or "127.0.0.1" in website):
            #     await notify_slack_error(user_name or user_id, str(error_payload))

            yield f"data: {json.dumps(error_payload)}\n\n".encode('utf-8')

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        background=bgt,
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@router.post("/stop-generation")
async def stop_response_generation(user: apiSecurityFree, session_id: str = Query(..., alias="session_id"), message_id: str = Query(..., alias="message_id")):
    session_log = await mongodb.get_session_log_by_user_and_session_id(user.id.__str__(), session_id)
    if not session_log:
        raise HTTPException(status_code=404, detail="Session not found or access denied.")
    key = f"stop:{session_id}"
    await redis_manager.safe_execute("set", key, message_id, 3)

@router.post("/stock_data")
async def stock_data_endpoint(user: apiSecurityFree, payload: StockDataRequest):
    """
    Get real-time stock quote data and historical stock prices based on the period.
    Allowed periods: '1mo', '3mo', '6mo', 'ytd', '1y', '5y', 'max'.
    """
    try:
        # request = await request.json()
        # print("Received stock data request:", request)
        # request = StockDataRequest(**request)
        # period = request.period
        # if period.endswith('m'):
        #     period = period+"o"
        ticker_data = TickerSchema(ticker=payload.ticker, exchange_symbol=payload.exchange_symbol)
        result_json = await asyncio.to_thread(
            get_stock_data._run,
            ticker_data=[ticker_data],
            period=payload.period,
            strictly = True
        )
        
        response_data = result_json[0]
        chat_session_id = await mongodb.get_chat_session_id_from_message(message_id=payload.message_id, ticker=payload.ticker)

        if 'error' in response_data['realtime'] or 'error' in response_data['historical']:
            print(response_data['realtime'].get('error', "NA"), response_data['historical'].get('error', "NA"))
            raise HTTPException(status_code=500, detail=f"Encountered error in fetching stock data.")
        
        return {"stock_data": response_data, "message_id": payload.message_id, 'id': payload.id, 'chart_session_id': chat_session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stock data: {str(e)}")


@router.put("/response-feedback")
async def response_feedback(user: apiSecurityFree, payload: ResponseFeedback):
    try:
        # request = await request.json()
        # rf = ResponseFeedback(**request)
        result = await mongodb.add_response_feedback(message_id=payload.message_id, response_id=payload.response_id, liked=payload.liked, feedback_tag=payload.feedback_tag, human_feedback=payload.human_feedback)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in storing response feedback: {str(e)}")


@router.post("/export-response")
async def export_response_endpoint(user: apiSecurityFree, payload: ExportResponse):
    
    # request = await request.json()
    # request = ExportResponse(**request)
    
    # Fetch the chat log by message ID
    data = await mongodb.get_response_by_message_id(payload.message_id)
    if not data or "error" in data:
        raise HTTPException(status_code=404, detail="Response not found.")
    print("Data for export-response:", data)
    query_text = data["query"]
    response_text = data["response"]

    # Find all graph blocks
    graph_blocks = re.findall(
        r"```graph\n(.*?)\n<END_OF_GRAPH>", response_text, re.DOTALL
    )

    image_replacements = []

    for graph_json in graph_blocks:
        try:
            image_paths = render_charts_as_images(graph_json)
            # image_tags = (
            #     "\n\n"
            #     + "\n\n".join(
            #         f"### Chart\n\n![Chart]({path})\n\n---" for path in image_paths
            #     )
            #     + "\n\n"
            # )
            image_tags = "\n\n" + "\n\n".join(
                f"### Chart\n\n![Chart](data:image/png;base64,{base64.b64encode(open(path, 'rb').read()).decode('utf-8')})\n\n---"
                for path in image_paths
            ) + "\n\n"

            image_replacements.append(image_tags)
        except Exception as e:
            print("Chart rendering failed:", e)
            image_replacements.append("*[Chart rendering failed]*")

    # Replace all graph blocks
    def replace_graph_blocks(text, replacements):
        return re.sub(
            r"```graph\n(.*?)\n<END_OF_GRAPH>\s*",
            lambda _: replacements.pop(0),
            text,
            flags=re.DOTALL,
        )

    cleaned_response = replace_graph_blocks(response_text, image_replacements)
    cleaned_response = cleaned_response.replace("```", "")
    markdown_content = f"# {query_text}\n\n{cleaned_response}"

    file_content_64 = ""
    filename = ""

    if payload.format == "md":
        file_content_64 = base64.b64encode(markdown_content.encode("utf-8")).decode(
            "utf-8"
        )
        filename = f"{slugify(query_text)}.md"

    elif payload.format == "pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        try:
            await markdown_to_pdf(markdown_content, pdf_path)
            with open(pdf_path, "rb") as f:
                file_content_64 = base64.b64encode(f.read()).decode("utf-8")
        finally:
            os.remove(pdf_path)
        filename = f"{slugify(query_text)}.pdf"

    elif payload.format == "docx":
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            docx_path = tmp.name
        try:
            await markdown_to_docx(markdown_content, docx_path)
            with open(docx_path, "rb") as f:
                file_content_64 = base64.b64encode(f.read()).decode("utf-8")
        finally:
            os.remove(docx_path)
        filename = f"{slugify(query_text)}.docx"

    else:
        raise HTTPException(status_code=400, detail="Unsupported format.")

    # Validate export result
    if not file_content_64:
        raise HTTPException(
            status_code=500, detail="File export failed. Empty file content."
        )

    return {"file_content_64": file_content_64, "filename": filename}


@router.put("/update-session-access")
async def update_session_access_endpoint(user: apiSecurityFree, payload: UpdateSessionAccess):
    
    try:
        # request = await request.json()
        # data = UpdateSessionAccess(**request)
        result = await mongodb.change_session_access_level(payload.session_id, user.id, payload.access_level)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session access: {str(e)}")
    

@router.put("/update-message-access")
async def update_message_access_endpoint(user: apiSecurityFree, payload: UpdateMessageAccess):

    try:
        # request = await request.json()
        # data = UpdateMessageAccess(**request)
        result = await mongodb.change_message_access_level(payload.message_id, payload.session_id, payload.access_level)
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating message access: {str(e)}")
    


@router.get("/public/{session_id}")
async def list_messages(session_id: str):
    try:
        is_public = await mongodb.check_public_session(session_id)

        if is_public:
            messages = await mongodb.get_messages_by_session(session_id)

            if not messages:
                raise HTTPException(status_code=404, detail="No messages found.")

            return messages

        else:
            raise HTTPException(status_code=404, detail="Session not found.")

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public session messages: {str(e)}")


@router.get("/public/message/{message_id}")
async def list_public_message(message_id: str):
    try:
        is_public = await mongodb.check_public_message(message_id)

        if is_public:
            message  = await mongodb.get_msglog_by_msgid(message_id)
            
            if not message:
                raise HTTPException(status_code=404, detail="No message found.")
        
            return {"message_list": [message]}
        
        else:
            raise HTTPException(status_code=404, detail="Message not found.")
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public session message: {str(e)}")
        

@router.get("/map-data/{message_id}")
async def get_map_data(user: apiSecurityFree, message_id: str):
    """
    Fetch Map Agent Data from MongoDB
    """
    
    try:
        result = await mongodb.fetch_map_data(message_id=message_id)

        if not result:
            raise HTTPException(status_code=404, detail="Map data not found")
        
        return result
    
    except HTTPException as he:
        raise he
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public session messages: {str(e)}")


@router.post("/stock-predict")
async def predict_stock(user: apiSecurityFree, request: StockPredictionRequest):
    """Predict stock prices for a given company using LangGraph agent."""
    
    if not request.ticker or not request.company_name:
        raise HTTPException(status_code=400, detail="Company name cannot be empty")
    
    company_name = request.company_name
    ticker = request.ticker
    exchange_symbol = request.exchange_symbol
    if stock_agent is None:
        raise HTTPException(status_code=503, detail="Stock Analysis Agent not initialized")
    
    try:

        rating, reason = await asyncio.to_thread(get_sentiment_rating, company_name, exchange_symbol)

        history_data = await asyncio.to_thread(get_stock_history, ticker, rating, reason)

        adjusted_mean_series, adjusted_ci_df = await asyncio.to_thread(
            sarimax_predict, history_data, exchange_symbol, 5
        )

        historical_data = []
        current_date = datetime.now()
        fourteen_days_ago = current_date - timedelta(days=14)
        ticker_data = TickerSchema(ticker=ticker, exchange_symbol=request.exchange_symbol)
        period = request.period.lower()
        if period.endswith('m'):
            period = period+"o"
        result_json = await asyncio.to_thread(
            get_stock_data._run,
            ticker_data=[ticker_data],
            period=period
        )
        response_data = result_json[0]
        for data_point in response_data['historical']['data']:
            date_str = data_point.get("date")
            if date_str:
                try:
                    data_date = datetime.strptime(date_str, "%b %d, %Y")
                    if data_date >= fourteen_days_ago:
                        historical_data.append({
                            "date": data_point.get("date"),
                            "high": float(data_point.get("high", 0).replace(",", "")),
                            "low": float(data_point.get("low", 0).replace(",", "")),
                            "open": float(data_point.get("open", 0).replace(",", "")),
                            "close": float(data_point.get("close", 0).replace(",", "")),
                            "type": "historical",
                            "ticker": company_name
                        })
                except ValueError:
                    continue

        predicted_data = []
        for date, predicted_price in adjusted_mean_series.items():
            ci = adjusted_ci_df.loc[date]
            formatted_date = date.strftime('%b %d, %Y')
            predicted_data.append({
                "date": formatted_date,
                "high": round(ci['upper'], 2),
                "low": round(ci['lower'], 2),
                "close": round(predicted_price, 2),
                "type": "predicted",
                "ticker": company_name
            })

        combined_data = historical_data + predicted_data
        print("Combined Data Length:", combined_data)
        return {"combined_chart": combined_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/time-taken2")
async def check_time_taken_endpoint(user: apiSecurityFree, session_id: Optional[str] = None, message_id: Optional[str]= None):
    # check_user = await MessageOutput.find_one(
    #     MessageOutput.session_id == session_id,
    #     MessageOutput.message_id == message_id,
    #     MessageOutput.user_id == user.id.__str__()
    # )
    messages = await mongodb.check_time_taken(session_id, message_id)
    count = 0
    tot_time = 0
    for msg in messages:
        if msg.time_taken != 0:
            tot_time = tot_time + int(msg.time_taken)
            count += 1
    return {"count": count, "total_time": tot_time, "average": tot_time / count if count > 0 else "NA"}

@router.post("/time-taken")
async def check_time_taken_endpoint(user: apiSecurityFree, session_id: Optional[str] = None, message_id: Optional[str] = None):
    # check_user = await MessageOutput.find_one(
    #     MessageOutput.session_id == session_id,
    #     MessageOutput.message_id == message_id,
    #     MessageOutput.user_id == user.id.__str__()
    # )
    messages = await mongodb.check_time_taken(session_id, message_id)
    count = 0
    tot_time = 0
    max_time = 0
    min_time = float('inf')
    max_query = ""
    min_query = ""
    query_times = []
    
    for msg in messages:
        if msg.time_taken != 0 and msg.get('human_input'):
            time_taken = int(msg.time_taken)
            tot_time = tot_time + time_taken
            count += 1
            user_query = ""
            if hasattr(msg, 'user_query') and msg.user_query:
                user_query = msg.user_query
            elif hasattr(msg, 'human_input') and msg.human_input:
                user_query = msg.human_input.get('user_query', "NA")
            else:
                user_query = "NA"

            query_times.append({
                "query": user_query,
                "time_taken": time_taken,
                "created_at": msg.created_at,
                "message_id": str(msg._id) if hasattr(msg, '_id') else None
            })
            
            # Track max time
            if time_taken > max_time:
                max_time = time_taken
                max_query = user_query
                
            # Track min time
            if time_taken < min_time:
                min_time = time_taken
                min_query = user_query
    
    # Handle edge cases for min_time
    if count == 0 or min_time == float('inf'):
        min_time = "NA"
        min_query = "NA"
    
    return {
        "count": count,
        "total_time": tot_time,
        "average": tot_time / count if count > 0 else "NA",
        "max_time": max_time if count > 0 else "NA",
        "max_query": max_query if count > 0 else "NA",
        "min_time": min_time,
        "min_query": min_query,
        "query_times": query_times
    }


@router.post("/related-queries", response_model=RelatedQueriesResponse)
async def get_related_queries(
    user: apiSecurityFree,
    message_id: str = Query(...),
    chart_session_id: str = Query(...)
):
    try:
        user_id = user.id.__str__()

        message_log = await MessageLog.find_one({
            "message_id": message_id,
            "stock_chart.chart_session_id": chart_session_id     
        })

        if not message_log:
            raise HTTPException(status_code=404, detail="MessageLog with matching chart not found")

        chart = next(
            (chart for chart in message_log.stock_chart if chart.get("chart_session_id") == chart_session_id),
            None
        )
        if not chart:
            raise HTTPException(status_code=404, detail="Chart with matching chat_session_id not found")

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
        return {"related_queries": queries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


