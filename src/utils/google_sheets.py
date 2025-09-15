import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from settings import config
from logger.config import get_logger
from utils.text import strip_all_tags

logger = get_logger(__name__)


class GoogleSheetsLogger:
    def __init__(self):
        creds_path = config.GOOGLE_SHEETS_CREDS
        sheet_name = config.GOOGLE_SHEETS_NAME

        logger.info("Инициализация GoogleSheetsLogger: creds=%s, sheet=%s", creds_path, sheet_name)

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        sh = client.open(sheet_name)

        try:
            self.sheet = sh.worksheet("Логи")
            logger.info("Google Sheets подключен, используем таблицу: %s", sheet_name)
        except Exception as e:
            logger.error("Не удалось открыть таблицу Google Sheets: %s", sheet_name, exc_info=e)
            raise

    def log_message(self, question: str, answer: str, source: str = "telegram"):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [question, strip_all_tags(answer), "", "", date_str, source]
        logger.info("Пробуем записать строку в Google Sheets: %s", row)

        try:
            self.sheet.append_row(row, value_input_option="RAW")
            logger.info("Строка успешно добавлена в Google Sheets")
        except Exception as e:
            logger.error("Ошибка при записи строки в Google Sheets", exc_info=e)
            raise