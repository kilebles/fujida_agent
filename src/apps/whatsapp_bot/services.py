import httpx
from settings import config
from logger import get_logger

logger = get_logger(__name__)


async def send_whatsapp_message(to: str, text: str):
    url = (
        f"{config.GREEN_API_URL}/waInstance{config.GREEN_API_INSTANCE_ID}"
        f"/sendMessage/{config.GREEN_API_TOKEN}"
    )
    payload = {
        "chatId": f"{to}@c.us",
        "message": text,
    }
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.RequestError as e:
            logger.error("Ошибка соединения с Green API: %s", e)
            raise
        except httpx.HTTPStatusError as e:
            logger.error("Ошибка ответа Green API: %s", e.response.text)
            raise

    logger.info("Сообщение отправлено в WhatsApp: %s", resp.json())
    return resp.json()