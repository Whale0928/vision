from __future__ import annotations

from logging_config import setup_logging
from app.main import app


def main() -> None:
    import uvicorn

    setup_logging()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)



if __name__ == "__main__":
    main()
