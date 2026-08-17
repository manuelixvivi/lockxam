from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_authenticated
from app.schemas.master.master import (
    LicenseTypeResponse,
    SchoolLevelResponse,
)
from app.services.master.master_data_service import MasterDataService

router = APIRouter(prefix="/api/v1/master", tags=["Master Data"])


@router.get(
    "/school-levels",
    response_model=list[SchoolLevelResponse],
    dependencies=[Depends(require_authenticated())],
)
def get_school_levels(db: Session = Depends(get_db)):
    return MasterDataService.get_all_school_levels(db)


@router.get(
    "/license-types",
    response_model=list[LicenseTypeResponse],
    dependencies=[Depends(require_authenticated())],
)
def get_license_types(db: Session = Depends(get_db)):
    return MasterDataService.get_all_license_types(db)
