from openai import AsyncOpenAI
from settings import config

openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
