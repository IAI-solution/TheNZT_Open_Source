import asyncio
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING, MongoClient, ReturnDocument
from typing import Any, List, Optional, Dict, Union
from beanie.odm.fields import PydanticObjectId
from beanie.operators import  And
from src.backend.utils import JWT
from fastapi import HTTPException, UploadFile, BackgroundTasks
from zoneinfo import ZoneInfo
from typing import Optional
from src.backend.models.model import *
from src.backend.models.app_io_schemas import Onboarding
from src.ai.agents.utils import generate_session_title
import requests

MONGO_URI = os.getenv("MONGO_URI")
FMP_API_KEY= os.getenv("FM_API_KEY")

jwt_handler = None


async def init_db():
    global jwt_handler, MONGO_URI
    client = AsyncIOMotorClient(MONGO_URI)
    database = client["insight_agent"]
    jwt_handler = JWT.JWTHandler("f524fdd634e89fd7a3d886564d026666b3ea46db9c77a57d68309f02190020cb", "HS256", "30")
    await init_beanie(database=database, document_models=[MessageLog, JSONBackup, SessionLog, Users, MessageFeedback, ExternalData, SessionHistory, MessageOutput, MapData, GraphLog, Personalization, Onboarding,UploadResponse, ChartBotLogs])

def _fetch_fmp_data(query: str) -> Union[List[Dict[str, Any]], str]:
    try:
        # url = f"https://financialmodelingprep.com/api/v3/search?query={query}&apikey={FMP_API_KEY}"
        url = f"https://financialmodelingprep.com/stable/search-symbol?query={query}&apikey={FMP_API_KEY}"
        fmp_response = requests.get(url)
        fmp_response.raise_for_status()
        return fmp_response.json()
    except Exception as e:
        return f"Error in getting company information from FMP for {query}: {str(e)}"
    
def search_company(query: str):
    query_upper = query.upper()
    client = MongoClient(MONGO_URI)
    db = client["insight_agent_fmp"]
    collection = db["fmp_query_results"]

    one_month_ago = datetime.now() - timedelta(days=30)
    cached = collection.find_one({"query": query_upper})

    if cached:
        if cached.get("timestamp") and cached["timestamp"] > one_month_ago:
            return cached

        result = _fetch_fmp_data(query)
        if isinstance(result, str):
            raise HTTPException(status_code=500, detail=result)

        collection.update_one(
            {"_id": cached["_id"]},
            {"$set": {
                "results": result,
                "timestamp": datetime.now()
            }}
        )
        cached = collection.find_one({"_id": cached["_id"]})
        return cached

    result = _fetch_fmp_data(query)
    if isinstance(result, str):
        raise HTTPException(status_code=500, detail=result)

    new_entry = {
        "query": query_upper,
        "results": result,
        "timestamp": datetime.now()
    }
    collection.insert_one(new_entry)
    return new_entry


def get_or_fetch_company_profile(symbol: str):
    symbol = symbol.upper()
    client = MongoClient(MONGO_URI)
    db = client["insight_agent_fmp"]
    collection = db["company_profiles"]

    today = datetime.now().date()

    # Check for cached data
    existing = collection.find_one({"symbol": symbol})
    if existing:
        last_updated = existing.get("last_updated")
        if last_updated and last_updated.date() == today:
            return {
                "data": existing["data"],
                "source": "https://financialmodelingprep.com/"
            }
        else:
            try:
                # url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FMP_API_KEY}"
                url = f"https://financialmodelingprep.com/stable/profile?symbol={symbol}&apikey={FMP_API_KEY}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()

                if not data or not isinstance(data, list):
                    raise HTTPException(status_code=404, detail="Company not found")
                data = data[0]

                collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "data": data,
                        "last_updated": datetime.now()
                    }}
                )
                return {
                    "data": data,
                    "source": "https://financialmodelingprep.com/"
                }

            except Exception as e:
                return {
                    "data": existing["data"],
                    "source": f"mongodb (fallback, update failed: {str(e)})"
                }

    # No existing record, fetch and store
    try:
        # url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FMP_API_KEY}"
        url = f"https://financialmodelingprep.com/stable/profile?symbol={symbol}&apikey={FMP_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list):
            raise HTTPException(status_code=404, detail="Company not found")

        data = data[0]

        collection.insert_one({
            "symbol": symbol,
            "data": data,
            "last_updated": datetime.now()
        })

        return {
            "data": data,
            "source": "https://financialmodelingprep.com/"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


def fetch_financial_data(symbol: str, statement_type: str, period: str = "annual", limit: int = 5) -> dict:
    symbol = symbol.upper()
    client = MongoClient(MONGO_URI)
    db = client["insight_agent_fmp"]
    financial_statements = db["financial_statements"]
    record = financial_statements.find_one({
        "symbol": symbol,
        "statement_type": statement_type,
        "period": period
    })

    is_outdated = True
    if record and "last_updated" in record:
        age = datetime.now() - record["last_updated"]
        is_outdated = age > timedelta(days=30)

    if not record or is_outdated:
        fmp_endpoints = {
            "balance_sheet": "balance-sheet-statement",
            "cash_flow": "cash-flow-statement",
            "income_statement": "income-statement"
        }

        if statement_type not in fmp_endpoints:
            raise ValueError("Invalid statement_type")

        # url = f"https://financialmodelingprep.com/api/v3/{fmp_endpoints[statement_type]}/{symbol}?limit={limit}&apikey={FMP_API_KEY}"
        url = f"https://financialmodelingprep.com/stable/{fmp_endpoints[statement_type]}?symbol={symbol}&limit={limit}&apikey={FMP_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and data:
            now = datetime.now()
            update_data = {
                "symbol": symbol,
                "statement_type": statement_type,
                "period": period,
                "data": data,
                "last_updated": now
            }
            if record:
                financial_statements.update_one(
                    {"_id": record["_id"]},
                    {"$set": update_data}
                )
            else:
                financial_statements.insert_one(update_data)
        else:
            raise Exception("No data found in FMP")
        
        record = financial_statements.find_one({
            "symbol": symbol,
            "statement_type": statement_type,
            "period": period
        })

    return record["data"]

# def get_historical_data_fmp(ticker: str, period: str):
#     today = datetime.now()
#     from_date = datetime(today.year, 1, 1)
#     ytd_days=today-from_date
#     days_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "5Y": 1825,"MAX": 7300,"YTD":ytd_days.days}
#     days = days_map.get(period, 30)
#     to_date = datetime.now()
#     from_date = to_date - timedelta(days=days)

#     # url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from={from_date.date()}&to={to_date.date()}&apikey={FMP_API_KEY}"
#     url = f"https://financialmodelingprep.com/stable/historical-price-eod/full?symbol={ticker}&from={from_date.date()}&to={to_date.date()}&apikey={FMP_API_KEY}"
#     response = requests.get(url)
#     response.raise_for_status()
#     return response.json()

def get_historical_data_fmp(ticker: str, period: str):
    today = datetime.now(timezone.utc)
    
    # FIX: Make sure from_date for YTD is also timezone-aware
    from_date_ytd = datetime(today.year, 1, 1, tzinfo=timezone.utc)
    ytd_days = today - from_date_ytd
    
    days_map = {
        "1M": 30, 
        "3M": 90, 
        "6M": 180, 
        "1Y": 365, 
        "5Y": 1825,
        "MAX": 7300,
        "YTD": ytd_days.days
    }
    
    days = days_map.get(period, 30)
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=days)

    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from={from_date.date()}&to={to_date.date()}&apikey={FMP_API_KEY}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# def get_or_update_historical(ticker: str, period: str) -> dict:
#     now = datetime.now()
#     ticker = ticker.upper()
#     client = MongoClient(MONGO_URI)
#     db = client["insight_agent_fmp"]
#     historical_collection = db["historical_data"]

#     record = historical_collection.find_one({"ticker": ticker, "period": period})
#     if record:
#         # if (now - record["last_updated"]) < timedelta(hours=24):
#         #     return record["data"]
#         if now.date() == record["last_updated"].date():
#             return record["data"]
#         else:
#             data = get_historical_data_fmp(ticker, period)
#             updated_record = historical_collection.find_one_and_update(
#                 {"_id": record["_id"]},
#                 {"$set": {"data": data, "last_updated": now}},
#                 return_document=ReturnDocument.AFTER
#             )
#             return updated_record["data"]
#     else:
#         data = get_historical_data_fmp(ticker, period)
#         try:
#             new_doc = {
#                 "ticker": ticker,
#                 "period": period,
#                 "data": data,
#                 "last_updated": now
#             }
#             historical_collection.insert_one(new_doc)
#         except Exception as insert_error:
#             record = historical_collection.find_one({"ticker": ticker, "period": period})
#             if record:
#                 return record["data"]
#             else:
#                 raise insert_error
#         return data

def get_or_update_historical(ticker: str, period: str) -> dict:
    now = datetime.now(timezone.utc)
    ticker = ticker.upper()
    client = MongoClient(MONGO_URI)
    db = client["insight_agent_fmp"]
    historical_collection = db["historical_data"]

    record = historical_collection.find_one({"ticker": ticker, "period": period})
    if record:
        # FIX: Ensure last_updated is timezone-aware before comparison
        last_updated = record["last_updated"]
        
        # Make last_updated timezone-aware if it's naive
        if last_updated.tzinfo is None or last_updated.tzinfo.utcoffset(last_updated) is None:
            # Assume UTC for naive datetimes from database
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        
        # Now both are timezone-aware, comparison will work
        if now.date() == last_updated.date():
            return record["data"]
        else:
            data = get_historical_data_fmp(ticker, period)
            updated_record = historical_collection.find_one_and_update(
                {"_id": record["_id"]},
                {"$set": {"data": data, "last_updated": now}},
                return_document=ReturnDocument.AFTER
            )
            return updated_record["data"]
    else:
        data = get_historical_data_fmp(ticker, period)
        try:
            new_doc = {
                "ticker": ticker,
                "period": period,
                "data": data,
                "last_updated": now
            }
            historical_collection.insert_one(new_doc)
        except Exception as insert_error:
            record = historical_collection.find_one({"ticker": ticker, "period": period})
            if record:
                return record["data"]
            else:
                raise insert_error
        return data



def fetch_stock_price_change(symbol: str) -> dict:
    """
    Get stock price change for the given symbol.
    Uses cached data if updated today; else updates from FMP.
    """
    symbol = symbol.upper()

    client = MongoClient(MONGO_URI)
    db = client["insight_agent_fmp"]
    collection = db["stock_price_changes"]
    # 1. Check for cached data
    record = collection.find_one({"symbol": symbol})
    today = datetime.now().date()

    if record and "last_updated" in record and record["last_updated"].date() == today:
        return {
            "symbol": symbol,
            "changes": [record["data"]],
            "source": "https://financialmodelingprep.com/"
        }

    # 2. Fetch fresh data from FMP
    # url = f"https://financialmodelingprep.com/api/v3/stock-price-change/{symbol}?apikey={FMP_API_KEY}"
    url = f"https://financialmodelingprep.com/stable/stock-price-change?symbol={symbol}&apikey={FMP_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        fmp_data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FMP request error: {str(e)}")

    if not fmp_data:
        raise HTTPException(status_code=404, detail="No stock price change data found.")

    new_data = fmp_data[0]
    # 3. Update or insert record in DB
    if record:
        collection.update_one(
            {"_id": record["_id"]},
            {"$set": {
                "data": new_data,
                "last_updated": datetime.now()
            }}
        )
    else:
        collection.insert_one({
            "symbol": symbol,
            "data": new_data,
            "last_updated": datetime.now()
        })

    return {
        "symbol": symbol,
        "changes": [new_data],
        "source": "https://financialmodelingprep.com/"
    }

async def init_web_search_db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client["insight_agent"]
    await init_beanie(database=database, document_models=[ExternalData])

async def create_user(user_data: dict) -> Users:
    user = Users(**user_data)
    user.account_status = AccountStatus.ACTIVE
    us = await user.insert()
    return user


async def get_user(email: str) -> Optional[Users]:
    email_match = And(Users.email == email, Users.account_status == AccountStatus.ACTIVE)
    user = await Users.find_one(email_match)
    return user

async def is_new_user_token(token: str):
    payload = jwt_handler.decode_jwt(token)
    is_new_user = payload.get("is_new_user")
    return is_new_user

async def fetch_user_by_id(user_id: str) -> Optional[Users]:
    id_match = And(Users.id == PydanticObjectId(user_id), Users.account_status == AccountStatus.ACTIVE)
    # user = await Users.find_one(id_match)
    # return user.to_dict() if user else None
    return await Users.find_one(id_match)


async def get_user_by_token(token: str)->returnStatus:
    try:
        payload = jwt_handler.decode_jwt(token)
        user_id = payload.get("user_id")
        user = await fetch_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


async def append_data(user_id, session_id, message_id, messages, local_time, time_zone, retry = False, metadata = None, time_taken = 0):
    from src.backend.utils.utils import get_unique_response_id, get_date_time
    try:
        log_entry = await MessageLog.find_one({"session_id": str(session_id), "message_id": str(message_id)})
        if not log_entry:
            log_entry = MessageLog(session_id=str(session_id), message_id=str(message_id))
            log_entry.created_at = local_time
        else:
            log_entry.research = []
            log_entry.stock_chart = []

        if metadata:
            log_entry.metadata = metadata

        if time_taken:
            log_entry.time_taken = time_taken

        # canvas_response_data = {}

        for content in messages:
            if not content:
                continue
            if 'user_query' in content:
                content['retry'] = retry
                log_entry.human_input = content

            elif 'type' in content and content['type'] == 'research':
                if content['agent_name'] != "DB Search Agent":
                    log_entry.research.append({'agent_name': content['agent_name'], 'title': content['title'], 'id': content.get('id', get_unique_response_id()), 'created_at': content['created_at']})
            
            elif 'research-manager' in content:
                log_entry.research.append({'agent_name': content['agent_name'], 'title': content['research-manager'], 'id': content.get('id', get_unique_response_id()), 'created_at': content['created_at']})
            
            elif 'response' in content:
                log_entry.response = {'agent_name': content['agent_name'], 'content': content['response'], 'id': content.get('id', get_unique_response_id()), 'created_at': content['created_at']}

            elif 'type' in content and content['type'] == 'response':
                log_entry.response = {'agent_name': content['agent_name'], 'content': content['content'], 'id': content.get('id', get_unique_response_id()), 'created_at': content['created_at']}

            # elif 'type' in content and content['type'] == 'canvas_info':
            #     canvas_response_data["document_id"] = content.get("canvas_document_id")
            #     canvas_response_data["version_number"] = content.get("canvas_version_number", 1)

            # elif 'type' in content and content['type'] == 'canvas-preview':
            #     canvas_response_data["preview"] = content.get("content", "")

            # elif 'type' in content and content['type'] == 'stock_data':
            #     data = content['data']
            #     symbol = data['realtime']['symbol']
            #     timestamp = data['realtime']['timestamp']

            #     already_exists = any(
            #         d['realtime']['symbol'] == symbol and d['realtime']['timestamp'] == timestamp
            #         for d in log_entry.stock_chart
            #     )
            #     if not already_exists:
            #         log_entry.stock_chart.append(data)
            elif content.get('type') == 'stock_data':
                data = content.get('data') or {}
                realtime = data.get('realtime') or {}

                # symbol fallback: try multiple places, default to None
                symbol = realtime.get('symbol') or data.get('symbol') or None

                # If timestamp missing, generate one (UTC ISO8601)
                try:
                    timestamp = realtime.get('timestamp')
                    if not timestamp:
                        timestamp = datetime.now(timezone).isoformat()
                        realtime['timestamp'] = timestamp
                        data['realtime'] = realtime
                        # optional debug:
                        # print(f"[DEBUG] Auto-added timestamp for {symbol}: {timestamp}")
                except Exception:
                    timestamp = datetime.now(timezone).isoformat()
                    realtime['timestamp'] = timestamp
                    data['realtime'] = realtime

                # Ensure log_entry.stock_chart exists and iterate defensively
                existing_charts = log_entry.stock_chart if getattr(log_entry, "stock_chart", None) else []

                already_exists = any(
                    (d.get('realtime', {}).get('symbol') == symbol) and (d.get('realtime', {}).get('timestamp') == timestamp)
                    for d in existing_charts
                )

                if not already_exists:
                    # append the (possibly updated) data dict
                    if not getattr(log_entry, "stock_chart", None):
                        log_entry.stock_chart = []
                    log_entry.stock_chart.append(data)

            elif 'type' in content and content['type'] == 'map_layers':
                log_entry.map_layers.append(content['data'])

            elif 'sources' in content:
                log_entry.sources = content['sources']
            
            elif "error" in content:
                log_entry.error = content
        
        # if canvas_response_data:
        #     log_entry.canvas_response = {
        #         "document_id": canvas_response_data.get("document_id", ""),
        #         "version_number": canvas_response_data.get("version_number", 1),
        #         "final_content": log_entry.response["content"] if log_entry.response else "",
        #         "preview": canvas_response_data.get("preview", "")
        #     }

        if not log_entry.response:
            log_entry.response = {'agent_name': 'Response Generator Agent', 'content': '**There was an error generating the response**', 'id': get_unique_response_id(), 'created_at': get_date_time(timezone=time_zone).isoformat()}

        # if "document_id" in canvas_response_data:
        #     log_entry.response = {
        #         "agent_name":    "",
        #         "content":       "",
        #         "id":            get_unique_response_id(),
        #         "created_at":    get_date_time(timezone=time_zone).isoformat()
        #     }

        lg = await log_entry.save()

        await add_session(session_id, 'New Chat', local_time, time_zone, user_id)

        print(f"Added session {session_id}, message {message_id} to db.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in storing message log: {str(e)}")


async def append_graph_log_to_mongo(session_id: str, message_id: str, log: str):
    existing_log = await GraphLog.find_one({"session_id": session_id, "message_id": message_id})
    if existing_log:
        existing_log.logs += f"\n{'='*15}\n\n{log}"
        await existing_log.save()
    else:
        new_log = GraphLog(session_id=session_id, message_id=message_id, logs=log)
        await new_log.insert()
        
async def handle_partial_data_storage(
    user_id: str,
    session_id: str,
    message_id: str,
    partial_content_buffer: list,
    current_messages_log: list,
    partial_sources: list,
    partial_related_queries: list,
    partial_metadata: dict,
    message_log: str,
    local_time: datetime,
    timezone: str,
    time_taken: float,
    bgt: BackgroundTasks,
    is_cancelled: bool = False,
    error_content: str = None
):
    """
    Handle storage of partial data when stream is cancelled or encounters error
    Store as normal data without special treatment
    """
    try:
        # Reconstruct partial content from buffer and create standard response format
        if partial_content_buffer:
            # Group content by agent_name and combine
            agent_contents = {}
            for chunk in partial_content_buffer:
                agent_name = chunk.get('agent_name', 'Response Generator Agent')
                if agent_name not in agent_contents:
                    agent_contents[agent_name] = []
                agent_contents[agent_name].append(chunk['content'])
            
            # Create standard response entry (same format as complete responses)
            for agent_name, content_chunks in agent_contents.items():
                combined_content = "".join(content_chunks)
                if combined_content.strip():  # Only add non-empty content
                    # Use standard format that append_data expects
                    response_entry = {
                        'type': 'response',
                        'agent_name': agent_name,
                        'content': combined_content,
                        'created_at': time.time()
                    }
                    current_messages_log.append(response_entry)
        
        # Add sources to current_messages_log if available (standard format)
        if partial_sources:
            sources_entry = {
                'sources': partial_sources
            }
            current_messages_log.append(sources_entry)
        
        # Store using existing append_data function with standard parameters
        # Use existing metadata or empty dict (no special partial metadata)
        store_metadata = partial_metadata if partial_metadata else {}
        
        bgt.add_task(
            append_data, 
            user_id, 
            session_id, 
            message_id, 
            current_messages_log, 
            local_time, 
            timezone, 
            True,  # retry = True (standard parameter)
            store_metadata,  # standard metadata format
            time_taken
        )
        
        # Store graph logs if available
        if message_log:
            bgt.add_task(append_graph_log_to_mongo, session_id, message_id, message_log)
            
        print(f"Partial data stored as normal response for message_id: {message_id}, chunks: {len(partial_content_buffer)}")
        
    except Exception as e:
        print(f"Error storing partial data for message_id {message_id}: {str(e)}")
        
async def add_session(session_id, title, local_time, time_zone, user_id=None):
    session = await SessionLog.find_one({"session_id": session_id})

    if not session:
        session = SessionLog(
            user_id=PydanticObjectId(user_id),
            session_id=session_id,
            title=title,
            access_level=AccessLevel.PRIVATE,
            created_at= local_time,
            timezone= time_zone if timezone else "UTC",
            visible=True
        )
        await session.insert()
        print(f"Created new session with title")
    elif session and session.title == 'New Chat' and title != 'New Chat':
        session.title = title
        session.updated_at = local_time
        await session.save()
        print(f"Updated session {session_id} title to {title}")


async def get_sessions_by_user2(user_id: str, page: int = 1, limit: int = 25) -> Dict[str, Any]:

    skip_count = (page - 1) * limit
    sessions = await SessionLog.find({"user_id": PydanticObjectId(user_id),"visible": True}).sort("-created_at").skip(skip_count).limit(limit).to_list()
    serialized_sessions = []
    
    for session in sessions:
        serialized_sessions.append({
            "id": str(session.session_id),
            "user_id": str(session.user_id),
            "title": session.title.title(),
            "created_at": session.created_at.isoformat()
        })
    if not serialized_sessions:
        return {"data": [], "has_more": False}
    
    sorted_sessions = sorted(
        serialized_sessions, key=lambda x: x["created_at"], reverse=True)

    if bool(sorted_sessions) == False :
        return None
    
    if sorted_sessions[0].get("timezone"):
        tz = ZoneInfo(sorted_sessions[0].get("timezone"))
    else:
        tz = ZoneInfo("UTC")
    
    current_date = datetime.now(tz).date()
    
    categorized_data = {
        "Today": [],
        "Previous 7 days": [],
        "Previous 30 days": [],
    }
    
    # Process each session
    for session in sorted_sessions:
        # Convert ISO string to datetime object
        created_date = datetime.fromisoformat(session["created_at"]).date()
        
        days_diff = (current_date - created_date).days
        
        if days_diff == 0:
            categorized_data["Today"].append(session)
        elif 1 <= days_diff <= 7:
            categorized_data["Previous 7 days"].append(session)
        elif 8 <= days_diff <= 30:
            categorized_data["Previous 30 days"].append(session)
        else:
            if created_date.year == current_date.year:
                month_name = created_date.strftime("%B")
                if month_name not in categorized_data:
                    categorized_data[month_name] = []
                categorized_data[month_name].append(session)
            else:
                year_month = f"{created_date.strftime('%B')} {created_date.year}"
                if year_month not in categorized_data:
                    categorized_data[year_month] = []
                categorized_data[year_month].append(session)
    
    result = []
    for timeline, sessions in categorized_data.items():
        if sessions:
            result.append({
                "timeline": timeline,
                "data": sessions
            })
    total_fetched = skip_count + len(serialized_sessions)
    total_count = await SessionLog.find(
        {"user_id": PydanticObjectId(user_id), "visible": True}
    ).count()
    has_more = bool(total_count - total_fetched > 0)

    return {
        "data":result,
        "has_more": has_more,
    }


async def get_session_log_by_user_and_session_id(user_id: str, session_id: str) -> Optional[SessionLog]:
    session_log = await SessionLog.find_one({"user_id": PydanticObjectId(user_id), "session_id": session_id, "visible": True})
    return session_log

async def get_msglog_by_msgid(message_id: str):
    return await MessageLog.find_one({"message_id": message_id})

def convert_seconds(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} sec"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes} min {remaining_seconds} sec" if remaining_seconds else f"{minutes} min"

async def get_messages_by_session(session_id: str) -> List[dict]:
    logs = await MessageLog.find({"session_id": session_id}, sort=[("created_at", 1)]).to_list()
    try:
        session_messages = {"session_id": session_id, 'message_list': [
        ]}
        for log in logs:
            research_data = log.research if log.research else None
            if (research_data and isinstance(research_data, list) and len(research_data) > 0 and 'created_at' in research_data[0]):
                research_data = sorted(research_data, key=lambda x: x['created_at'])

            
            feedback = await MessageFeedback.find_one({"message_id": log.message_id})
            feedback_data = {
                "liked": "yes" if feedback and feedback.liked is True else "no" if feedback and feedback.liked is False else None,
                "feedback_tag": feedback.feedback_tag if feedback else [],
                "human_feedback": feedback.human_feedback if feedback else []
            }
            
            doc_info_list = []
            if log.human_input and isinstance(log.human_input, dict):
                doc_ids = log.human_input.get("doc_ids", [])
                if doc_ids:
                    for file_id in doc_ids:
                        doc = await UploadResponse.find_one({"file_id": file_id})
                        if doc:
                            file_name = doc.original_filename
                            if file_name and "." in file_name:
                                file_type = file_name.split(".")[-1]
                            else:
                                file_type = "unknown"

                            doc_info_list.append({
                                "file_id": file_id,
                                "file_name": file_name or "unknown",
                                "file_type": file_type
                            })
            # canvas_data = log.canvas_response if hasattr(log, "canvas_response") and log.canvas_response else {}

            session_messages["message_list"].append({
                "message_id": log.message_id,
                "human_input": log.human_input,
                "doc_info": doc_info_list,
                "research": research_data,
                "response": log.response,
                # "canvas_response": canvas_data,
                "stock_chart": log.stock_chart if log.stock_chart else [],
                "map_layers": log.map_layers,
                "sources": log.sources if log.sources else [],
                "created_at": log.created_at.isoformat(),
                "feedback": feedback_data,
                "time_taken": convert_seconds(log.time_taken) if log.time_taken else "0 sec"
            })

        return session_messages
    except Exception as e:
        error = f"Error occurred in getting previous session: {str(e)}"
        print(error)
        raise e



async def get_response_by_message_id(message_id: str) -> dict:
    log = await MessageLog.find_one({"message_id": str(message_id)})
    if log:
        response = {'query': log.human_input.get('user_query'), 'response': log.response.get('content')}
        return response
    else:
        return {'error': 'Not found.'}


async def add_response_feedback(message_id: str, response_id: str, liked: bool = None, feedback_tag: str = None, human_feedback: str = None):
    try:
        response_feedback = await MessageFeedback.find_one({
            "message_id": message_id,
            "response_id": response_id
        })

        if not response_feedback:
            response_feedback = MessageFeedback(
                message_id=message_id, 
                response_id=response_id,
                liked = liked if liked is not None else None, 
                feedback_tag = [feedback_tag] if feedback_tag else [],
                human_feedback = [human_feedback] if human_feedback else []
            )
        else:
            if liked is not None:
                response_feedback.liked = liked
            if feedback_tag:
                if not response_feedback.feedback_tag:
                    response_feedback.feedback_tag = []
                response_feedback.feedback_tag.append(feedback_tag)
            if human_feedback:
                if not response_feedback.human_feedback:
                    response_feedback.human_feedback = []
                response_feedback.human_feedback.append(human_feedback)


        rf = await response_feedback.save()

        return f"Saved response feedback: {rf}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Encountered error in adding response feedback: {str(e)}")
        raise e

#############################
async def change_session_access_level(session_id: str, user_id: PydanticObjectId, access_level: str):
    session = await SessionLog.find_one({"session_id": session_id, "user_id": user_id, "visible": True})

    if not session:
        raise HTTPException(status_code=404, detail="Session not found or you don't have permission to modify it")

    session.access_level = access_level
    session.updated_at = datetime.now(timezone.utc)

    await session.save()

    return {"status": "success", "session_id": session_id}


async def check_public_session(session_id: str):
    session = await SessionLog.find_one({"session_id": session_id, "access_level": 'public', "visible": True})
    if not session:
        return False
    return True

async def check_public_message(message_id: str):
    message = await MessageLog.find_one({"message_id": message_id, "access_level": 'public'})
    if not message:
        return False
    return True

async def update_user_password(email: str, new_hashed_password: str) -> bool:
    user = await Users.find_one(Users.email == email)
    if not user:
        return False

    await user.set({Users.password: new_hashed_password})
    return True


def insert_in_db(file_data: list):
    try:
        client = MongoClient(MONGO_URI)
        collection = client['insight_agent']['ExternalData']

        records = [{'filename': indi_file['filename'], 'data': indi_file['data']} for indi_file in file_data]
        collection.insert_many(records)
        print("data inserted")
    except Exception as e:
        print(f"MongoDB bulk insert error: {str(e)}")


async def fetch_by_filename(filename: str):
    try:
        result = await ExternalData.find_one({"filename": filename})
        print(filename)
        return result
    except Exception as e:
        print(f"MongoDB fetch error: {str(e)}")
        return None

async def multi_fetch_by_filename(filenames: list):
    fetched_files = {}
    if filenames:
        try:
            cursor = ExternalData.find({"filename": {"$in": filenames}})
            file_docs = await cursor.to_list()
            fetched_files = {doc.filename: doc for doc in file_docs}
            return fetched_files
        except Exception as e:
            print(f"MongoDB batch fetch error: {str(e)}")
            return None

async def update_session_history_in_db(session_id: str, user_id: str, message_id: str, user_query: str, assistant_response: str, doc_ids: List[str], local_time: Optional[datetime], time_zone: Optional[str]):
    from src.backend.utils.utils import get_date_time

    user_object_id = PydanticObjectId(user_id)
    session = await SessionHistory.find_one(SessionHistory.session_id == session_id, SessionHistory.user_id == user_object_id)

    message_entry = {message_id: (user_query, assistant_response, doc_ids)}

    if not session:
        session = SessionHistory(
            user_id=user_object_id,
            session_id=session_id,
            title="New Chat",
            history=[message_entry],
            created_at=local_time,
            updated_at=local_time,
        )

        title = await generate_title(session.history)
        session.title = title
        await session.insert()
        await add_session(session_id, title, local_time, time_zone, user_id)

    else:
        message_found = False
        for entry in reversed(session.history):
            if message_id in entry:
                entry[message_id] = (user_query, assistant_response, doc_ids)
                message_found = True
                break

        if not message_found:
            session.history.append(message_entry)

        if not session.title or session.title == "New Chat":
            title = await generate_title(session.history)
            if title and title != "New Chat":
                session.title = title

                session_log = await SessionLog.find_one(SessionLog.session_id == session_id, SessionLog.user_id == user_object_id)
                if session_log:
                    session_log.title = title
                    await session_log.save()
        session.updated_at = local_time
        await session.save()


async def get_session_history_from_db(session_id: str, prev_message_id: str, limit: int = None) -> dict:
    session = await SessionHistory.find_one(SessionHistory.session_id == session_id)
    all_messages = []
    all_doc_ids = []
    
    if session:
        collecting = False
        for entry in reversed(session.history):
            if prev_message_id in entry:
                collecting = True
            
            if collecting:
                message_data = list(entry.values())[0]
                # message_data is a tuple: (user_query, assistant_response, doc_ids)
                user_query, assistant_response, doc_ids = message_data
                
                # Add user query and assistant response to messages
                all_messages.append([user_query, assistant_response])
                
                # Add doc_ids to the list (extend to flatten the list if doc_ids is a list)
                if doc_ids:
                    if isinstance(doc_ids, list):
                        all_doc_ids.extend(doc_ids)
                    else:
                        all_doc_ids.extend([doc_ids])

                if limit and len(all_messages) >= limit:
                    break

        # Reverse to get chronological order
        all_messages.reverse()

        all_doc_ids.reverse()
        
        return {
            'messages': all_messages,
            'doc_ids': all_doc_ids
        }
    
    return {'messages': [], 'doc_ids': []}


async def insert_map_data(session_id: str, message_id: str, data: Dict[str, Any]):
    try:
        record = MapData(
            session_id=session_id,
            message_id=message_id,
            data=data,
        )
        await record.insert()
    except Exception as e:
        print(f"MongoDB insert error (MapData): {str(e)}")


async def fetch_map_data(message_id: str):
    try:
        result = await MapData.find_one({"message_id": message_id})
        return result.data
    except Exception as e:
        print(f"MongoDB fetch error (MapData): {str(e)}")
        return None


async def get_user_details(user_id: str) -> Optional[Users]:
    try:
        user = await Users.get(PydanticObjectId(user_id))

        if user and user.account_status == "active":
            return user
        return None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None


async def update_user_profile(user_id: str, full_name: Optional[str], email: Optional[str], profile_picture: Optional[str]) -> Optional[Users]:
    user = await Users.get(PydanticObjectId(user_id))
    if not user:
        return None

    if full_name is not None:
        user.full_name = full_name
    if email is not None:
        user.email = email
    if profile_picture is not None:
        user.profile_picture = profile_picture

    user.last_updated = datetime.now()
    await user.save()
    return user


async def get_personalization(user_id: str) -> Optional[Personalization]:
    try:
        perInfo = await Personalization.find_one(Personalization.user_id == PydanticObjectId(user_id))
        if perInfo :
            perInfo = perInfo.model_dump(exclude={"user_id","id"})
        return perInfo
    except Exception as e:
        print(f"Error in get_personalization: {e}")
        return None

async def create_or_update_personalization(user_id: str, data: dict) -> Personalization:
    try:
        personalization = await Personalization.find_one(Personalization.user_id == PydanticObjectId(user_id))
        if personalization:
            for key, value in data.items():
                setattr(personalization, key, value)
            personalization.last_updated = datetime.now(timezone.utc)
            await personalization.save()
        else:
            personalization = Personalization(
                user_id=PydanticObjectId(user_id),
                **data
            )
            await personalization.insert()
        return personalization.model_dump(exclude={"user_id","id"})
    except Exception as e:
        print(f"Error in create_or_update_personalization: {e}")
        raise

async def get_sessions_by_user_and_keyword_pagination(
    user_id: str,
    keyword: str,
    page: int,
    limit: int
) -> Dict[str, Any]:

    regex = re.compile(re.escape(keyword), re.IGNORECASE)

    # Step 1: Find all matching sessions from history
    sessions = await SessionHistory.find(
        {
            "user_id": PydanticObjectId(user_id),
            "title": {"$regex": regex},
        }
    ).to_list()
    
    if not sessions:
        return {"data": [], "has_more": False}

    # Step 2: Get all session_ids from history
    session_ids = [s.session_id for s in sessions]

    # Step 3: Find all visible session logs for these IDs (only return session_id field)
    logs = await SessionLog.find(
        {
            "user_id": PydanticObjectId(user_id),
            "session_id": {"$in": session_ids},
            "visible": True
        }
    ).to_list()

    # Step 4: Extract valid session_ids from logs
    valid_session_ids = {log.session_id for log in logs}

    # Step 5: Filter sessions in one pass
    valid_sessions = [s for s in sessions if s.session_id in valid_session_ids]

    if not valid_sessions:
        return {"data": [], "has_more": False}

    # Step 6: Serialize
    serialized = [
        {
            "id": str(s.session_id),
            "user_id": str(s.user_id),
            "title": s.title.title(),
            "created_at": s.created_at.isoformat(),
            "timezone": getattr(s, "timezone", None)
        }
        for s in valid_sessions
    ]

    serialized.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(serialized)
    start = (page - 1) * limit
    end = start + limit
    paginated_data = serialized[start:end]

    tz = ZoneInfo(paginated_data[0].get("timezone") or "UTC") if paginated_data else ZoneInfo("UTC")
    current_date = datetime.now(tz).date()

    buckets: Dict[str, List[Dict]] = {
        "Today": [],
        "Previous 7 days": [],
        "Previous 30 days": [],
    }

    for s in paginated_data:
        created_date = datetime.fromisoformat(s["created_at"]).date()
        days_diff = (current_date - created_date).days

        if days_diff == 0:
            buckets["Today"].append(s)
        elif 1 <= days_diff <= 7:
            buckets["Previous 7 days"].append(s)
        elif 8 <= days_diff <= 30:
            buckets["Previous 30 days"].append(s)
        else:
            key = (
                created_date.strftime("%B")
                if created_date.year == current_date.year
                else f"{created_date.strftime('%B')} {created_date.year}"
            )
            buckets.setdefault(key, []).append(s)

    grouped_data = [
        {"timeline": tl, "data": data}
        for tl, data in buckets.items() if data
    ]

    return {
        "data": grouped_data,
        "has_more": end < total
    }

async def rename_session_title(user_id:str, session_id: str, new_title:str):
    """
    Rename the title of a session for the current user.
    """
    # Update SessionLog
    session_log = await SessionLog.find_one({"session_id": session_id, "user_id": PydanticObjectId(user_id)})
    if not session_log:
        raise HTTPException(status_code=404, detail="SessionLog not found.")
    
    session_log.title = new_title
    session_log.updated_at = datetime.now(timezone.utc)
    await session_log.save()

    # Update SessionHistory
    session_history = await SessionHistory.find_one({"session_id": session_id, "user_id": PydanticObjectId(user_id)})
    if session_history:
        session_history.title = new_title
        session_history.updated_at = datetime.now(timezone.utc)
        await session_history.save()

    return {"new_title": new_title}
    
async def delete_session(user_id: PydanticObjectId, session_id: str):
   
    try:        
        deletion_and_fetch_tasks = [
            MessageOutput.find(MessageOutput.session_id == session_id).delete(),
            MessageLog.find(MessageLog.session_id == session_id).delete(),
            # GraphLog.find(GraphLog.session_id == session_id).delete(),
            MapData.find(MapData.session_id == session_id).delete(),
            SessionLog.find(SessionLog.session_id == session_id).delete(),
            SessionHistory.find(SessionHistory.session_id == session_id).delete(),
            ##Get message_ids at the same time (parallel)
            MessageOutput.find(MessageOutput.session_id == session_id).to_list(),
        ]
        print("Operation start")
        results = await asyncio.gather(*deletion_and_fetch_tasks, return_exceptions=True)
        print("Operation stop")
        # Check if session existed (if all deletions returned 0, session didn't exist)
        deletion_results = results[:6]  # First 7 are deletions
        message_outputs = results[6]    # Last one is message_outputs
        
        total_deleted = sum(
            getattr(result, 'deleted_count', 0) 
            for result in deletion_results 
            if not isinstance(result, Exception)
        )
        
        if total_deleted == 0:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # SPEED OPTIMIZATION 3: Bulk MessageFeedback deletion
        feedback_deleted_count = 0
        if not isinstance(message_outputs, Exception) and message_outputs:
            # Collect unique message_ids
            message_ids = set()
            for record in message_outputs:
                if hasattr(record, 'message_id') and record.message_id:
                    message_ids.add(str(record.message_id))
            
            if message_ids:
                
                feedback_tasks = []
                batch_size = 50  # Process 50 message_ids at once
                message_id_list = list(message_ids)
                
                for i in range(0, len(message_id_list), batch_size):
                    batch = message_id_list[i:i + batch_size]
                    # Delete multiple feedback records in one query per batch
                    for msg_id in batch:
                        feedback_tasks.append(
                            MessageFeedback.find(MessageFeedback.message_id == msg_id).delete()
                        )
                
                # Execute all feedback deletions in parallel
                if feedback_tasks:
                    feedback_results = await asyncio.gather(*feedback_tasks, return_exceptions=True)
                    feedback_deleted_count = sum(
                        getattr(result, 'deleted_count', 0)
                        for result in feedback_results
                        if not isinstance(result, Exception)
                    )
        
        ##Build response (streamlined)
        deleted_items = []
        deletion_names = ['message_outputs', 'message_logs', 'map_data', 'session_log', 'session_history']
        
        for i, result in enumerate(deletion_results):
            if not isinstance(result, Exception) and hasattr(result, 'deleted_count') and result.deleted_count > 0:
                deleted_items.append(f"{deletion_names[i]} ({result.deleted_count})")
        
        if feedback_deleted_count > 0:
            deleted_items.append(f"message_feedback ({feedback_deleted_count})")
        
        # Get session title from the deleted records if available
        session_title = None
        if not isinstance(message_outputs, Exception) and message_outputs:
            # Try to get title from any message output that might have it
            for output in message_outputs:
                if hasattr(output, 'session_title'):
                    session_title = output.session_title
                    break
        
        return {
            "status": "success",
            "message": f"Session '{session_id}' and all associated data deleted",
            "session_title": session_title,
            "deleted": deleted_items,
            "message_ids_checked_in_messageFeedback": len(message_ids) if 'message_ids' in locals() else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting session '{session_id}': {str(e)}"
        )

async def create_or_update_onboarding(user_id: str, data: dict) -> Onboarding:
    try:
        onboarding = await Onboarding.find_one(Onboarding.user_id == PydanticObjectId(user_id))
        if onboarding:
            for key, value in data.items():
                setattr(onboarding, key, value)
            await onboarding.save()
        else:
            onboarding = Onboarding(user_id=PydanticObjectId(user_id), **data)
            await onboarding.insert()
        return onboarding
    except Exception as e:
        print(f"Error in create_or_update_onboarding: {e}")
        raise

async def check_time_taken(session_id: Optional[str] = None, message_id: Optional[str]= None):
    query = {}
    if session_id:
        query["session_id"] = session_id
    if message_id:
        query["message_id"] = message_id
    return await MessageLog.find(query).to_list()

async def delete_user(user_id: str) -> Dict[str, Any]:
    """
    Delete ALL user data simultaneously - no batches for maximum speed
    """
    try:
        user_object_id = PydanticObjectId(user_id)
        
        print(f"Starting user deletion for: {user_id}")
        
        # Step 1: Get user and all session info in parallel
        user, session_logs, session_histories = await asyncio.gather(
            Users.get(user_object_id),
            SessionLog.find(SessionLog.user_id == user_object_id).to_list(),
            SessionHistory.find(SessionHistory.user_id == user_object_id).to_list(),
            return_exceptions=True
        )
        
        if isinstance(user, Exception) or not user:
            print(f"User {user_id} not found")
            raise HTTPException(status_code=404, detail="User not found.")
        
        # Collect unique session_ids
        session_ids = set()
        if not isinstance(session_logs, Exception):
            session_ids.update(log.session_id for log in session_logs)
        if not isinstance(session_histories, Exception):
            session_ids.update(history.session_id for history in session_histories)
        
        session_ids = list(session_ids)
        if len(session_ids) == 0:
            print("User has no sessions to delete.")
        else:
            print(f"Found {len(session_ids)} sessions - deleting ALL at once...")
        
        # Step 2: Delete ALL sessions simultaneously (no batches)
        all_tasks = []
        
        if session_ids:
            # Create tasks for ALL sessions at once
            session_tasks = [delete_session(user_id, session_id) for session_id in session_ids]
            all_tasks.extend(session_tasks)
        
        # Step 3: Add user-specific data deletion tasks to the same batch
        all_tasks.extend([
            Personalization.find(Personalization.user_id == user_object_id).delete(),
            UploadResponse.find(UploadResponse.user_id == user_object_id).delete(),
            Onboarding.find(Onboarding.user_id == user_object_id).delete(),
        ])
        
        print(f"Executing {len(all_tasks)} operations simultaneously...")
        
        # Execute EVERYTHING at once
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        print("All operations completed!")
        
        # Process results
        deleted_summary = []
        
        # Process session results
        session_results = all_results[:len(session_ids)]
        for i, result in enumerate(session_results):
            session_id = session_ids[i]
            if isinstance(result, Exception):
                deleted_summary.append(f"Session {session_id}: Error")
                print(f"Session {session_id} error: {str(result)}")
            else:
                session_title = result.get('session_title', 'No title')
                deleted_summary.append(f"Session {session_id} ({session_title}): {', '.join(result['deleted'])}")
        
        # Process user-specific data results
        user_data_results = all_results[len(session_ids):]
        data_types = ['personalization', 'upload_responses', 'onboarding']
        
        for i, result in enumerate(user_data_results):
            if isinstance(result, Exception):
                print(f"Error deleting {data_types[i]}: {str(result)}")
                deleted_summary.append(f"{data_types[i]}: Error - {str(result)}")
            elif hasattr(result, 'deleted_count') and result.deleted_count > 0:
                deleted_summary.append(f"{data_types[i]}: {result.deleted_count}")
        
        # Step 4: Delete user record (final step)
        await user.delete()
        deleted_summary.append("User record")
        
        print(f"User {user_id} deletion completed successfully!")
        
        return {
            "status": "success", 
            "message": f"User {user_id} and all associated data deleted successfully",
            "sessions_deleted": len(session_ids),
            "deleted_summary": deleted_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting user '{user_id}': {str(e)}"
        )

async def generate_title(history:List[dict]) -> str:    
    content = ""
    for idx, entry in enumerate(history, start=1):
        for message_id, message_pair in entry.items():
            user_query, assistant_response, _ = message_pair
            content = f"{idx}. User Query: {user_query}\n- Response: {assistant_response}\n"
            
    if not content.strip():
        return "New Chat"

    try:
        title = await generate_session_title(content)
        return title.strip()
    except Exception as e:
        print(f"Title generation error: {e}")
        return "New Chat"

async def get_last_msg_in_session(session_id: str):
    return await MessageLog.find(
        {"session_id": session_id},
        sort=[("created_at", -1)]
        ).first_or_none()

async def store_user_query(user_id: str, session_id: str, message_id: str, user_query: str, timezone: str, doc_ids: List[str]=None):
    from src.backend.utils.utils import get_unique_response_id
    local_time = datetime.now(ZoneInfo(timezone))

    log_entry = await MessageLog.find_one({
        "session_id": str(session_id),
        "message_id": str(message_id)
    })
    if not log_entry:
        human_input_data = {
            "user_query": user_query,
            "file_id" : doc_ids or [],
        }

        dummy_response = {'agent_name': "Unknown Agent", 'content': "*There was an error generating the response!*", 'id': get_unique_response_id()}

        log_entry = MessageLog(
            session_id=str(session_id),
            message_id=str(message_id),
            created_at=local_time,
            human_input=human_input_data,
            response=dummy_response,
        )
        await log_entry.insert()

        print("log_entry_created", log_entry)
    # else:
    #     log_entry.human_input = human_input_data
    #     log_entry.created_at = local_time  # optional update
    #     await log_entry.save()


# ===== UTILITY FUNCTIONS =====

def read_markdown_file(file_path: str) -> str:
    """Read and convert markdown file to HTML if needed, or return as text"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content

def process_markdown_content(content: str) -> str:
    """Process markdown content - can convert to HTML or keep as markdown"""
    # For now, we'll keep it as markdown
    # If you want HTML conversion: return markdown.markdown(content)
    return content

    

async def update_or_create_message_log(session_id: str, message_id: str, human_input: dict, response: dict, canvas_document_id: str = None) -> str:
    """Helper function to update existing message log or create new one"""
    try:
        # Check if message log already exists
        existing_message_log = await MessageLog.find_one(
            MessageLog.message_id == message_id,
            MessageLog.session_id == session_id
        )
        
        if existing_message_log:
            # Update existing message log
            existing_message_log.human_input = human_input
            existing_message_log.response = response
            existing_message_log.canvas_document_id = canvas_document_id
            existing_message_log.error = None  # Clear any previous errors
            existing_message_log.created_at = datetime.now(timezone.utc)
            await existing_message_log.save()
            return "updated"
        else:
            # Create new message log
            message_log = MessageLog(
                session_id=session_id,
                message_id=message_id,
                human_input=human_input,
                response=response,
                canvas_document_id=canvas_document_id,
                created_at=datetime.now(timezone.utc)
            )
            await message_log.insert()
            return "created"
    except Exception as log_error:
        print(f"Failed to update or create message log: {str(log_error)}")
        return "failed"
 

async def change_message_access_level(message_id: str, session_id: str, access_level: str):
    message = await MessageLog.find_one({
        "message_id": message_id,
        "session_id": session_id
    })
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission to modify it")

    message.access_level = access_level

    await message.save()

    return {"status": "success", "message_id": message_id}


async def upsert_chart_log(
    user_id: str,
    session_id: str,
    message_id: str,
    user_input: str,
    context: ChatContext,
    response: str,
    chat_session_id: str
) -> ChartBotLogs:
    try:
        new_log = ChartBotLogs(
            user_id=PydanticObjectId(user_id),
            session_id=session_id,
            message_id=message_id,
            user_input=user_input,
            context=context,
            response=response,
            chat_session_id=chat_session_id
           )
        await new_log.insert()
        return new_log

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inserting log: {str(e)}")

async def get_chat_session_id_from_message(message_id: str, ticker: str) -> Optional[str]:
    log = await MessageLog.find_one({
        "message_id": message_id,
        "stock_chart": {
            "$elemMatch": {
                "realtime.symbol": ticker
            }
        }
    })

    if not log:
        return None

    for chart in log.stock_chart:
        if chart.get("realtime", {}).get("symbol") == ticker:
            return chart.get("chart_session_id")

    return None


async def get_chartbot_session_logs(chat_session_id: str, limit: int = None) -> List[List[str]]:
    try:
        query = ChartBotLogs.find(ChartBotLogs.chat_session_id == chat_session_id).sort("+created_at")
        
        if limit:
            query = query.limit(limit)
        
        logs = await query.to_list()
        
        messages = []
        for log in logs:
            messages.append([log.user_input, log.response])
        
        return messages
    
    except Exception as e:
        print(f"Error retrieving ChartBotLogs for session_id {chat_session_id}: {e}")
        return []
