"""Wyjątki domenowe i handlery zapewniające spójny format błędów ``{detail, code}``."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int | str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} o id={resource_id} nie istnieje")


class UnknownStopError(NotFoundError):
    def __init__(self, stop_id: str) -> None:
        super().__init__("Przystanek", stop_id)


class GtfsNotImportedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Rozkład GTFS nie został zaimportowany. Uruchom: python -m app.cli.gtfs import"
        )


def _serialize_validation_errors(errors: Any) -> list[dict[str, Any]]:
    # Tylko pola serializowalne — ``ctx`` może zawierać obiekty wyjątków.
    return [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in errors
    ]


async def not_found_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc), "code": "not_found"},
    )


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": _serialize_validation_errors(exc.errors()), "code": "validation_error"},
    )


async def gtfs_not_imported_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc), "code": "gtfs_not_imported"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(GtfsNotImportedError, gtfs_not_imported_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
