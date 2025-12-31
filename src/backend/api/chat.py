
import os
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query, Response , Path
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi import status
from src.backend.core.api_limit import apiSecurityFree
from src.backend.models.model import SessionLog,MessageLog ,ChartBotLogs
from src.backend.db.mongodb import upsert_chart_log ,ChatContext,get_chartbot_session_logs
from src.ai.chart_bot.chart_bot import start_chat_session

router = APIRouter()

@router.post("/chat_bot")
async def chat_endpoint(
    user: apiSecurityFree,
    user_input: str = Query(...),
    session_id: str = Query(...),
    message_id: str = Query(...),
    chat_session_id: str = Query(...)
):
    try:
        session_log = await SessionLog.find_one({
            "user_id": user.id,
            "session_id": session_id
        })

        if not session_log:
            raise HTTPException(status_code = 404, detail="Session not found")

        message_log = await MessageLog.find_one({
            "session_id": session_id,
            "message_id": message_id,
        })

        if not message_log:
            raise HTTPException(status_code=404, detail="MessageLog with matching chart not found")

        chart = next(
            (chart for chart in message_log.stock_chart if chart.get("chart_session_id") == chat_session_id),
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

        response = await start_chat_session(
            name=name,
            user_input=user_input,
            ticker=ticker,
            exchange=exchange,
            context_data=context_data,
            messages = await get_chartbot_session_logs(chat_session_id, limit = 5),
        )

        log_doc = await upsert_chart_log(
            user_id=user.id,
            session_id=session_id,
            message_id=message_id,
            user_input=user_input,
            context=ChatContext(
                name=name,
                ticker=ticker,
                exchange=exchange,
                context_data=context_data
            ),
            response=response,
            chat_session_id=chat_session_id
        )
        return {
            "response": response,
            "response_id": str(log_doc.id),
            "chat_session_id": chat_session_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        

@router.get("/chat/{response_id}")
async def get_chat_response_by_id(
    user: apiSecurityFree,
    response_id: str = Path(...)
):
    try:
        user_id = user.id.__str__()

        log = await ChartBotLogs.get(PydanticObjectId(response_id))
        print(f"response_id type: {type(response_id)}, value: {response_id}")

        if not log or log.user_id != PydanticObjectId(user_id):
            raise HTTPException(status_code=404, detail="Chat response not found")

        return {
            "message_id": log.message_id,
            "user_input": log.user_input,
            "response": log.response,
            "context": log.context.dict() if isinstance(log.context, BaseModel) else log.context,
            "created_at": log.created_at.isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/chat/session/{chat_session_id}")
async def get_chat_by_session(
    user: apiSecurityFree,
    chat_session_id: str
):
    try:
        logs = await ChartBotLogs.find({
            "user_id": user.id,
            "chat_session_id": chat_session_id
        }).sort("created_at").to_list()

        return [
            {
                "response_id": str(log.id),
                "user_input": log.user_input,
                "response": log.response,
                "timestamp": log.created_at.isoformat()
            }
            for log in logs
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
