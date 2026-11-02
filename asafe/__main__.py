"""Executa o Asafe:  ASAFE_ADMIN_TOKEN=... python -m asafe"""

import os

import uvicorn

from .app import criar_app

if __name__ == "__main__":
    uvicorn.run(criar_app(), host=os.environ.get("ASAFE_HOST", "127.0.0.1"),
                port=int(os.environ.get("ASAFE_PORT", "8000")))
