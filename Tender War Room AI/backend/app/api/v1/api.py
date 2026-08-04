from fastapi import APIRouter
from app.api.v1.endpoints import auth, tenders, market_prices, estimates, recommendations, simulations, reports

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(tenders.router, prefix="/tenders", tags=["Tenders"])
api_router.include_router(market_prices.router, prefix="/market-prices", tags=["Market Prices"])
api_router.include_router(estimates.router, prefix="/estimates", tags=["Estimates"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(simulations.router, prefix="/simulations", tags=["Simulations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])






