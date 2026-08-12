from __future__ import annotations

from fastapi import APIRouter, Request

from src.schemas.segmentation import SegmentationResponse
from src.services import segmentation_service

router = APIRouter(prefix="/api/segmentation", tags=["segmentation"])


@router.get("", response_model=SegmentationResponse)
def get_segmentation(request: Request) -> SegmentationResponse:
    state: segmentation_service.SegmentationState = request.app.state.segmentation
    return segmentation_service.segments(state)
