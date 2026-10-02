from fastapi import APIRouter

from eyohe.api.v1 import auth, cases, entities, evidence, findings, health, investigations, system

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(investigations.router)
api_router.include_router(evidence.router)
api_router.include_router(entities.router)
api_router.include_router(findings.router)
api_router.include_router(system.router)
