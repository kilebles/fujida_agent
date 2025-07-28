import httpx

from io import BytesIO
from aiogram.types import Message
from pydub import AudioSegment
from pydub.utils import which

from common.openai_client import openai_client

AudioSegment.converter = which("ffmpeg")


async def transcribe_voice(message: Message) -> str:
    file_info = await message.bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"

    async with httpx.AsyncClient() as client:
        response = await client.get(file_url)
        voice_data = BytesIO(response.content)

    audio = AudioSegment.from_file(voice_data, format="ogg")
    mp3_data = BytesIO()
    audio.export(mp3_data, format="mp3")
    mp3_data.seek(0)
    mp3_data.name = "voice.mp3"

    transcription = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=mp3_data,
    )

    return transcription.text
