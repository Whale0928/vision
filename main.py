import logging

from gpt_client import launch_gpt
from logging_config import setup_logging

logger = logging.getLogger(__name__)


def main():
    # 프로그램 기동: 로깅 설정 → GPT 클라이언트 런치
    setup_logging()
    logger.info("애플리케이션 기동")
    launch_gpt()


if __name__ == "__main__":
    main()

