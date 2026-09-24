"""API REST em ``/api/v1``: o que o frontend novo, o curl e scripts consomem.

A documentação interativa (OpenAPI) fica em ``/docs``.
"""

from fastapi import APIRouter

from . import catalogo, contratos
from .erros import ErroApi, tratar_erro_api

router = APIRouter(prefix="/api/v1")
router.include_router(contratos.router)
router.include_router(catalogo.router)

__all__ = ["ErroApi", "router", "tratar_erro_api"]
