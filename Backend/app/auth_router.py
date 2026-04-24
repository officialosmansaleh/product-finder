from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from app.auth import (
    AnalyticsEventRequest,
    AdminSettingUpdateRequest,
    AdminUserUpdateRequest,
    AuthService,
    CookieConsentRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SavedQuoteUpsertRequest,
    SignupRequest,
    UserApprovalRequest,
    UserPublic,
    build_auth_dependencies,
)


def create_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter()
    get_current_user, require_admin, require_leadership, require_staff, _get_token_from_request = build_auth_dependencies(auth_service)

    def require_settings_admin(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if str(user.role or "").strip().lower() not in {"admin", "it"}:
            raise HTTPException(status_code=403, detail="Admin or IT privileges required")
        return user

    def get_optional_user(request: Request) -> UserPublic | None:
        token = _get_token_from_request(request, None)
        if not token:
            return None
        try:
            return auth_service.decode_token(token)
        except HTTPException:
            return None

    @router.post("/auth/signup")
    def signup(payload: SignupRequest):
        user = auth_service.create_signup(payload)
        return {
            "success": True,
            "message": "Signup received and pending admin approval",
            "user": user.model_dump(),
        }

    @router.post("/auth/login")
    def login(payload: LoginRequest, response: Response, request: Request):
        session = auth_service.authenticate(payload)
        auth_service.set_auth_cookies(
            response,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
        )
        consent = auth_service.consent_from_request(request)
        if consent.get("analytics"):
            auth_service.record_activity_event(
                event_type="login",
                user_id=int(session.user.id),
                session_id=auth_service.analytics_session_from_request(request),
                page="auth",
                path="/auth/login",
                metadata={"source": "password"},
                ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
                user_agent=str(request.headers.get("user-agent") or ""),
            )
        return session.model_dump()

    @router.post("/auth/refresh")
    def refresh_session(request: Request, response: Response):
        refresh_token = str(request.cookies.get(auth_service.refresh_cookie_name) or "").strip()
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh session required")
        session = auth_service.refresh_session(refresh_token)
        auth_service.set_auth_cookies(
            response,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
        )
        return {"success": True, "user": session.user.model_dump()}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        refresh_token = str(request.cookies.get(auth_service.refresh_cookie_name) or "").strip()
        if refresh_token:
            auth_service.revoke_refresh_token(refresh_token)
        auth_service.clear_auth_cookies(response)
        return {"success": True}

    @router.get("/auth/consent")
    def consent_status(request: Request):
        data = auth_service.consent_from_request(request)
        return {
            "analytics": bool(data.get("analytics")),
            "consent_version": str(data.get("version") or ""),
            "updated_at": str(data.get("updated_at") or ""),
            "has_choice": bool(str(data.get("version") or "").strip()),
        }

    @router.post("/auth/consent")
    def update_consent(payload: CookieConsentRequest, request: Request, response: Response):
        current_user = get_optional_user(request)
        analytics_enabled = bool(payload.analytics)
        session_id = auth_service.analytics_session_from_request(request)
        if analytics_enabled and not session_id:
            session_id = auth_service.create_analytics_session_id()
        auth_service.set_consent_cookies(
            response,
            analytics_enabled=analytics_enabled,
            consent_version=payload.consent_version,
            analytics_session_id=session_id,
        )
        auth_service.upsert_consent_preference(
            analytics_enabled=analytics_enabled,
            consent_version=payload.consent_version,
            source=payload.source,
            user_id=(int(current_user.id) if current_user else None),
            session_id=session_id,
            ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
            user_agent=str(request.headers.get("user-agent") or ""),
        )
        return {
            "success": True,
            "consent": {
                "analytics": analytics_enabled,
                "consent_version": payload.consent_version,
                "session_id": session_id if analytics_enabled else "",
            },
        }

    @router.post("/auth/analytics/event")
    def analytics_event(payload: AnalyticsEventRequest, request: Request):
        consent = auth_service.consent_from_request(request)
        if not consent.get("analytics"):
            return {"success": True, "ignored": True, "reason": "no-consent"}
        current_user = get_optional_user(request)
        auth_service.record_activity_event(
            event_type=payload.event_type,
            user_id=(int(current_user.id) if current_user else None),
            session_id=auth_service.analytics_session_from_request(request),
            page=payload.page,
            path=payload.path,
            product_code=payload.product_code,
            query_text=payload.query_text,
            filters=payload.filters,
            metadata=payload.metadata,
            ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
            user_agent=str(request.headers.get("user-agent") or ""),
        )
        return {"success": True}

    @router.post("/auth/password-reset/request")
    def password_reset_request(payload: PasswordResetRequest):
        return auth_service.request_password_reset(payload.email)

    @router.post("/auth/password-reset/confirm")
    def password_reset_confirm(payload: PasswordResetConfirmRequest, response: Response):
        result = auth_service.confirm_password_reset(payload.token, payload.password)
        auth_service.clear_auth_cookies(response)
        return result

    @router.post("/auth/password/change")
    def password_change(payload: PasswordChangeRequest, current_user: UserPublic = Depends(get_current_user)):
        return auth_service.change_password(
            current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )

    @router.get("/auth/me")
    def me(current_user: UserPublic = Depends(get_current_user)):
        return current_user.model_dump()

    @router.get("/auth/quotes")
    def list_saved_quotes(current_user: UserPublic = Depends(get_current_user)):
        quotes = auth_service.list_saved_quotes(current_user.id)
        return {"count": len(quotes), "items": [quote.model_dump() for quote in quotes]}

    @router.get("/auth/quotes/{quote_id}")
    def get_saved_quote(quote_id: int, current_user: UserPublic = Depends(get_current_user)):
        quote = auth_service.get_saved_quote(current_user.id, quote_id)
        return quote.model_dump()

    @router.post("/auth/quotes")
    def create_saved_quote(payload: SavedQuoteUpsertRequest, request: Request, current_user: UserPublic = Depends(get_current_user)):
        quote = auth_service.save_quote(current_user.id, payload)
        consent = auth_service.consent_from_request(request)
        if consent.get("analytics"):
            auth_service.record_activity_event(
                event_type="quote_save",
                user_id=int(current_user.id),
                session_id=auth_service.analytics_session_from_request(request),
                page="quote",
                path="/auth/quotes",
                query_text=str(payload.project or ""),
                metadata={"item_count": len(payload.items or []), "quote_id": int(quote.id)},
                ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
                user_agent=str(request.headers.get("user-agent") or ""),
            )
        return {"success": True, "quote": quote.model_dump()}

    @router.put("/auth/quotes/{quote_id}")
    def update_saved_quote(quote_id: int, payload: SavedQuoteUpsertRequest, request: Request, current_user: UserPublic = Depends(get_current_user)):
        quote = auth_service.save_quote(current_user.id, payload, quote_id=quote_id)
        consent = auth_service.consent_from_request(request)
        if consent.get("analytics"):
            auth_service.record_activity_event(
                event_type="quote_update",
                user_id=int(current_user.id),
                session_id=auth_service.analytics_session_from_request(request),
                page="quote",
                path=f"/auth/quotes/{int(quote_id)}",
                query_text=str(payload.project or ""),
                metadata={"item_count": len(payload.items or []), "quote_id": int(quote.id)},
                ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
                user_agent=str(request.headers.get("user-agent") or ""),
            )
        return {"success": True, "quote": quote.model_dump()}

    @router.delete("/auth/quotes/{quote_id}")
    def delete_saved_quote(quote_id: int, request: Request, current_user: UserPublic = Depends(get_current_user)):
        auth_service.delete_saved_quote(current_user.id, quote_id)
        consent = auth_service.consent_from_request(request)
        if consent.get("analytics"):
            auth_service.record_activity_event(
                event_type="quote_delete",
                user_id=int(current_user.id),
                session_id=auth_service.analytics_session_from_request(request),
                page="quote",
                path=f"/auth/quotes/{int(quote_id)}",
                metadata={"quote_id": int(quote_id)},
                ip_address=str(getattr(getattr(request, "client", None), "host", "") or ""),
                user_agent=str(request.headers.get("user-agent") or ""),
            )
        return {"success": True, "deleted": int(quote_id)}

    @router.get("/admin/users")
    def admin_list_users(
        status: Optional[str] = Query(default=None, pattern="^(pending|approved|rejected)$"),
        staff_user: UserPublic = Depends(require_staff),
    ):
        users = auth_service.list_visible_users(staff_user, status=status)
        return {"count": len(users), "items": [u.model_dump() for u in users]}

    @router.get("/admin/users/pending")
    def admin_pending_users(_lead_user: UserPublic = Depends(require_leadership)):
        users = auth_service.list_visible_users(_lead_user, status="pending")
        return {"count": len(users), "items": [u.model_dump() for u in users]}

    @router.get("/admin/users/{user_id}/quotes")
    def admin_list_user_quotes(user_id: int, staff_user: UserPublic = Depends(require_staff)):
        if str(staff_user.role or "").lower() in {"admin", "director"}:
            quotes = auth_service.admin_list_saved_quotes(user_id)
        else:
            quotes = auth_service.manager_list_saved_quotes(staff_user, user_id)
        return {"count": len(quotes), "items": [quote.model_dump() for quote in quotes]}

    @router.get("/admin/users/{user_id}/quotes/{quote_id}")
    def admin_get_user_quote(user_id: int, quote_id: int, staff_user: UserPublic = Depends(require_staff)):
        if str(staff_user.role or "").lower() in {"admin", "director"}:
            quote = auth_service.admin_get_saved_quote(user_id, quote_id)
        else:
            quote = auth_service.manager_get_saved_quote(staff_user, user_id, quote_id)
        return quote.model_dump()

    @router.get("/admin/quotes")
    def admin_list_visible_quotes(staff_user: UserPublic = Depends(require_staff)):
        quotes = auth_service.list_visible_quotes(staff_user)
        return {"count": len(quotes), "items": [quote.model_dump() for quote in quotes]}

    @router.post("/admin/users/{user_id}/approve")
    def admin_approve_user(
        user_id: int,
        payload: UserApprovalRequest = Body(default_factory=UserApprovalRequest),
        lead_user: UserPublic = Depends(require_leadership),
    ):
        user = auth_service.approve_user(
            user_id,
            acting_admin_id=lead_user.id,
            role=payload.role,
            assigned_countries=payload.assigned_countries,
        )
        return {"success": True, "user": user.model_dump()}

    @router.put("/admin/users/{user_id}")
    def admin_update_user(
        user_id: int,
        payload: AdminUserUpdateRequest,
        lead_user: UserPublic = Depends(require_leadership),
    ):
        user = auth_service.update_user(user_id, acting_admin_id=lead_user.id, payload=payload)
        return {"success": True, "user": user.model_dump()}

    @router.post("/admin/users/{user_id}/reject")
    def admin_reject_user(user_id: int, lead_user: UserPublic = Depends(require_leadership)):
        user = auth_service.reject_user(user_id, acting_admin_id=lead_user.id)
        return {"success": True, "user": user.model_dump()}

    @router.delete("/admin/users/{user_id}")
    def admin_delete_user(user_id: int, lead_user: UserPublic = Depends(require_leadership)):
        return auth_service.delete_user(user_id, acting_admin_id=lead_user.id)

    @router.get("/admin/settings")
    def admin_list_settings(settings_user: UserPublic = Depends(require_settings_admin)):
        items = auth_service.list_admin_settings()
        if str(settings_user.role or "").strip().lower() == "it":
            items = [item for item in items if str(item.category or "") != "Scoring"]
        return {"count": len(items), "items": [item.model_dump() for item in items]}

    @router.get("/admin/analytics/summary")
    def admin_analytics_summary(
        days: int = Query(default=30, ge=1, le=365),
        top_n: int = Query(default=10, ge=1, le=50),
        lead_user: UserPublic = Depends(require_leadership),
    ):
        return auth_service.get_analytics_summary(lead_user, days=days, top_n=top_n)

    @router.put("/admin/settings/{setting_key}")
    def admin_update_setting(
        setting_key: str,
        payload: AdminSettingUpdateRequest,
        admin_user: UserPublic = Depends(require_settings_admin),
    ):
        if str(admin_user.role or "").strip().lower() == "it":
            current = next((item for item in auth_service.list_admin_settings() if item.key == setting_key), None)
            if current and str(current.category or "") == "Scoring":
                raise HTTPException(status_code=403, detail="Scoring controls require admin privileges")
        setting = auth_service.update_admin_setting(setting_key, payload.value, acting_admin_id=admin_user.id)
        return {"success": True, "setting": setting.model_dump()}

    return router
