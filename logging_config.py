import logging


def setup_logging(level: int = logging.INFO) -> None:
    # 애플리케이션 로깅 1회 설정 (기동 시 호출)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
