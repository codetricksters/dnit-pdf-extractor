"""Erros da API com campos além de ``detail``.

``HTTPException`` só carrega ``detail``; o cálculo precisa devolver também
``faltando`` e a importação, ``erros``. ``ErroApi`` leva esses campos e
``tratar_erro_api`` os põe no corpo, ao lado de ``detail``.
"""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


class ErroApi(Exception):
    def __init__(self, status: int, detail: str, **extra) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = extra


async def tratar_erro_api(request: Request, exc: ErroApi) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"detail": exc.detail, **jsonable_encoder(exc.extra)},
    )
