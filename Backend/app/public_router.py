from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Query


def create_public_router(
    *,
    home_impl: Callable[[], Any],
    frontend_home_impl: Callable[[], Any],
    health_impl: Callable[[], Any],
    codes_suggest_impl: Callable[[str, int], Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def home():
        return home_impl()

    @router.get("/frontend")
    @router.get("/frontend/")
    def frontend_home():
        return frontend_home_impl()

    @router.get("/health")
    def health():
        return health_impl()

    @router.get("/codes/suggest")
    def codes_suggest(
        q: str = Query("", description="Code or product name prefix"),
        limit: int = Query(25, ge=1, le=100),
    ):
        return codes_suggest_impl(q, limit)

    return router
