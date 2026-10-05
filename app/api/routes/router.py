from fastapi import APIRouter

from app.schemas.router import RouterPreviewRequest, RoutedRequest
from app.services.router import RequestRouter

router = APIRouter(prefix="/router", tags=["router"])
service = RequestRouter()


@router.post("/preview", response_model=RoutedRequest)
async def preview(payload: RouterPreviewRequest) -> RoutedRequest:
    return service.route(payload.text)
