"""Erros da API com campos além de ``detail``.

``HTTPException`` só carrega ``detail``; o cálculo precisa devolver também
``faltando`` e a importação, ``erros``. ``ErroApi`` leva esses campos e
``tratar_erro_api`` os põe no corpo, ao lado de ``detail``.
"""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MES = r"^\d{4}-(0[1-9]|1[0-2])$"
MENSAGEM_MES = "Mês inválido. Use o formato AAAA-MM, com o mês de 01 a 12, por exemplo 2023-02."


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


async def tratar_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    """O 422 do Pydantic, no mesmo formato (lista em ``detail``), mas com o texto
    do padrão de mês em português: a mensagem original é a própria regex."""
    erros = [
        {**e, "msg": MENSAGEM_MES}
        if e.get("type") == "string_pattern_mismatch" and e.get("ctx", {}).get("pattern") == MES
        else e
        for e in exc.errors()
    ]
    return await request_validation_exception_handler(request, RequestValidationError(erros))
