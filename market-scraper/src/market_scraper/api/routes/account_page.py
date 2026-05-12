"""Static account positions page."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
_ACCOUNT_PAGE = Path(__file__).parents[2] / "static" / "account.html"


@router.get("/account", response_class=HTMLResponse, include_in_schema=False)
async def account_page() -> HTMLResponse:
    """Serve the saved Binance account positions page."""
    return HTMLResponse(_ACCOUNT_PAGE.read_text(encoding="utf-8"))
