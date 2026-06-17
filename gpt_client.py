import logging

import httpx
from openai import APIConnectionError, AuthenticationError, OpenAI

from config import get_api_key

logger = logging.getLogger(__name__)

# 동시 요청을 3개로 제한하는 커넥션 풀 설정 (연결 1개당 요청 1개 → 사실상 동시 3개 캡)
_LIMITS = httpx.Limits(max_connections=3, max_keepalive_connections=3)


def launch_gpt() -> OpenAI:
    # GPT 클라이언트 기동: 키 로딩 → 풀 제한 클라이언트 생성 → 연결 핑퐁 → 반환
    api_key = get_api_key()
    client = OpenAI(api_key=api_key, http_client=httpx.Client(limits=_LIMITS))
    health_check(client)
    logger.info("연결 수립 완료")
    return client


def health_check(client: OpenAI) -> None:
    # 핑퐁: 모델 목록 조회로 키 유효성과 연결 확인 (토큰 비용 없음)
    try:
        client.models.list()
    except AuthenticationError:
        logger.error("GPT 인증 실패: API 키가 올바른지 확인하세요")
        raise
    except APIConnectionError:
        logger.error("GPT 서버 연결 실패: 네트워크 상태를 확인하세요")
        raise
