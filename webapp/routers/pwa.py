"""PWA a statika (WASM, manifest, service worker), webhook a hlavní stránka."""
import secrets
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, FileResponse
import tzi_trener
from ..config import WEBHOOK_SECRET
from ..git_sync import git_pull
from ..sessions import get_current_user

router = APIRouter()


# --- PWA & WASM Endpoints ---
@router.get("/quiz.wasm")
def get_quiz_wasm():
    return FileResponse(tzi_trener.UI_DIR / "quiz.wasm", media_type="application/wasm", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@router.get("/manifest.webmanifest")
def get_manifest():
    return FileResponse(tzi_trener.UI_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@router.get("/sw.js")
def get_sw():
    return FileResponse(tzi_trener.UI_DIR / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache, no-store, must-revalidate"})


@router.get("/icon.svg")
def get_icon():
    return FileResponse(tzi_trener.UI_DIR / "icon.svg", media_type="image/svg+xml")


@router.get("/favicon.ico")
def get_favicon():
    return FileResponse(tzi_trener.UI_DIR / "icon.svg", media_type="image/svg+xml")


@router.post("/webhook")
def post_webhook(request: Request, secret: str = ""):
    header_secret = request.headers.get("X-Webhook-Secret") or secret
    if not WEBHOOK_SECRET or not secrets.compare_digest(header_secret, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    out = git_pull()
    return PlainTextResponse(f"OK: {out}")


# --- Main Frontend View ---
@router.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    try:
        content = tzi_trener.load_ui("novy")
    except OSError:
        return PlainTextResponse("Chybí soubor šablony UI.", status_code=500)

    return HTMLResponse(content)
