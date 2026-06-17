import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def get_api_key() -> str:
    # .env 로딩 후 GPT API 키 반환 (없으면 즉시 중단)
    load_dotenv()
    key = os.getenv("GPT_API_KEY")
    if key is None:
        logger.error("GPT_API_KEY가 .env에 설정되지 않았습니다")
        raise ValueError("GPT_API_KEY가 설정되지 않았습니다")
    return key
