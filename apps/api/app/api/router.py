from fastapi import APIRouter

from app.api.routes import (
    calculations,
    configuration,
    grading,
    imports,
    marks,
    members,
    onboarding,
    students,
)

api_router = APIRouter(prefix="/v1")
api_router.include_router(calculations.router)
api_router.include_router(configuration.router)
api_router.include_router(members.router)
api_router.include_router(grading.router)
api_router.include_router(imports.router)
api_router.include_router(onboarding.router)
api_router.include_router(students.router)
api_router.include_router(marks.router)
