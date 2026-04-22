from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.requests import Request


def create_debug_router(
    *,
    security,
    clear_facets_cache_impl: Callable[[], dict],
    recreate_database_impl: Callable[[], dict],
    debug_families_impl: Callable[[], dict],
    debug_pim_source_impl: Callable[[], dict],
    refresh_database_impl: Callable[[], dict],
    debug_parse_impl: Callable[[str], dict],
    debug_parse_pdf_impl: Callable[[UploadFile], Awaitable[dict]],
    debug_parse_image_impl: Callable[[UploadFile], Awaitable[dict]],
    debug_nonnull_sample_impl: Callable[[str, int], dict],
) -> APIRouter:
    router = APIRouter()

    @router.post("/debug/clear_facets_cache")
    def clear_facets_cache(request: Request):
        security.require_admin_access(request)
        return clear_facets_cache_impl()

    @router.post("/database/recreate")
    def recreate_database(request: Request):
        security.require_admin_access(request)
        return recreate_database_impl()

    @router.get("/debug/families")
    def debug_families(request: Request):
        security.require_admin_access(request)
        return debug_families_impl()

    @router.get("/debug/pim-source")
    def debug_pim_source(request: Request):
        security.require_admin_access(request)
        return debug_pim_source_impl()

    @router.post("/database/refresh")
    def refresh_database(request: Request):
        security.require_admin_access(request)
        return refresh_database_impl()

    @router.get("/debug/parse")
    def debug_parse(request: Request, q: str = ""):
        security.require_admin_access(request)
        return debug_parse_impl(q)

    @router.post("/debug/parse-pdf")
    async def debug_parse_pdf(request: Request, file: UploadFile = File(...)):
        security.require_admin_access(request)
        limit, window = security.debug_pdf_limit()
        security.enforce_rate_limit(request, bucket="debug-parse-pdf", limit=limit, window_sec=window)
        return await debug_parse_pdf_impl(file)

    @router.post("/debug/parse-image")
    async def debug_parse_image(request: Request, file: UploadFile = File(...)):
        security.require_admin_access(request)
        limit, window = security.debug_image_limit()
        security.enforce_rate_limit(request, bucket="debug-parse-image", limit=limit, window_sec=window)
        return await debug_parse_image_impl(file)

    @router.get("/debug/nonnull_sample")
    def debug_nonnull_sample(
        request: Request,
        col: str = Query(..., description="Column name to check, e.g. efficacy_value"),
        limit: int = 10,
    ):
        security.require_admin_access(request)
        return debug_nonnull_sample_impl(col, limit)

    return router
