from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from apps.knowledge_base.services.answer_service import AnswerService
from utils.google_sheets import GoogleSheetsLogger
from logger import get_logger
from .services import send_whatsapp_message
import re

router = APIRouter()
logger = get_logger(__name__)

answer_service = AnswerService(model="gpt-4o")
sheets_logger = GoogleSheetsLogger()


def clean_text(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        data = await request.json()
        logger.info("WhatsApp update received: %s", data)

        if data.get("typeWebhook") != "incomingMessageReceived":
            return {"ok": True}

        msg_data = data.get("messageData", {})
        msg_type = msg_data.get("typeMessage")

        text = None
        if msg_type == "textMessage":
            text = msg_data.get("textMessageData", {}).get("textMessage")
        elif msg_type == "extendedTextMessage":
            text = msg_data.get("extendedTextMessageData", {}).get("text")

        if not text:
            return {"ok": True}

        from_number = data["senderData"]["chatId"].replace("@c.us", "")

        answer = await answer_service.fallback(text)
        answer = clean_text(answer)

        try:
            sheets_logger.log_message(text, answer, source="whatsapp")
        except Exception as e:
            logger.error("Ошибка логирования в Google Sheets", exc_info=e)

        await send_whatsapp_message(from_number, answer)

        return {"ok": True}
    except Exception as e:
        logger.error("Unhandled error in WhatsApp webhook: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "details": str(e)},
        )