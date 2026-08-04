import logging
import math
import json
import re
from uuid import UUID
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tender import Tender
from app.models.recommendation import BidRecommendation
from app.services.similarity_service import similarity_service
from app.services.estimation_service import estimation_service


logger = logging.getLogger("app.recommendation")


class RecommendationService:
    def calculate_win_probability(self, bid_percent: float, mean_dev: float, std_dev: float) -> float:
        """
        Calculates the probability of winning a tender at a specific bid percent deviation
        using the cumulative distribution function (CDF) of a normal distribution.
        Formula: P(Win) = 1.0 - CDF(bid_percent, mean, std)
        """
        if std_dev <= 0:
            std_dev = 1.0
        
        # Standardize value (Z-score)
        z = (bid_percent - mean_dev) / std_dev
        
        # Approximation of normal CDF using math.erf
        cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        
        # Win probability is the complement (1 - cdf)
        prob = 1.0 - cdf
        return float(prob)

    async def get_gemini_risk_assessment(
        self, work_name: str, eligibility: str, penalty_clauses: str, similar_count: int
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Calls Gemini API to evaluate risk scores, highlight critical assumptions,
        and summarize penalty clause exposure.
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. Using fallback mock risk assessment.")
            # Fallback mock values
            risk_score = 4.5
            confidence_level = "High" if similar_count >= 3 else "Medium" if similar_count > 0 else "Low"
            assumptions = {
                "assumed_material_inflation_annual_percent": 8.0,
                "assumed_labour_escalation_clause": "None detected",
                "similar_tenders_confidence": f"Fitted using {similar_count} matching historical contracts."
            }
            return risk_score, confidence_level, assumptions

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        
        prompt = (
            "You are a contract risk analyst evaluating a civil engineering government tender.\n"
            "Analyze the following tender details and return a risk score (float between 1.0 and 10.0), "
            "a confidence level for bidding (string: High, Medium, Low), and a list of key bidding assumptions.\n"
            "Your output must be strictly in JSON format. Do not wrap it in markdown block tags.\n\n"
            "JSON structure:\n"
            "{\n"
            '  "risk_score": number (e.g. 5.5),\n'
            '  "confidence_level": string (e.g. "Medium"),\n'
            '  "assumptions": {\n'
            '    "material_risk_notes": string,\n'
            '    "penalty_exposure_notes": string,\n'
            '    "eligibility_confidence": string\n'
            "  }\n"
            "}\n\n"
            f"Tender Details:\n"
            f"- Work Name: {work_name}\n"
            f"- Eligibility Criteria: {eligibility[:1000]}\n"
            f"- Penalty Clauses: {penalty_clauses[:1000]}\n"
            f"- Number of Similar Historical Tenders Mapped: {similar_count}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                if response.status_code == 200:
                    res_json = response.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                        cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text)
                        data = json.loads(cleaned_json)
                        
                        risk = float(data.get("risk_score", 5.0))
                        conf = str(data.get("confidence_level", "Medium"))
                        assump = data.get("assumptions", {})
                        return risk, conf, assump
        except Exception as e:
            logger.error("Gemini risk assessment API call failed: %s", str(e), exc_info=True)

        # Fallback values if API fails
        return 5.0, "Medium", {"error": "API extraction failed. Default parameters applied."}

    async def generate_recommendation(
        self, db: AsyncSession, tender_id: str
    ) -> Dict[str, Any]:
        """
        Compiles the historical tender similarity data and the contractor's cost estimates
        to build and persist an optimal AI Bidding Strategy recommendation.
        """
        logger.info("Generating AI bid recommendation for tender: %s", tender_id)
        tender_uuid = UUID(tender_id)
        
        # 1. Load Tender
        tender = await db.get(Tender, tender_uuid)
        if not tender:
            raise ValueError("Tender not found")

        # 2. Get Contractor cost estimate summary
        cost_sheet = await estimation_service.get_cost_sheet_summary(db, tender_id)
        break_even_cost = cost_sheet["break_even_cost"]
        official_cost = cost_sheet["official_estimated_cost"]
        
        # Calculate break-even deviation percentage from official estimated cost (ECV)
        # e.g., if break-even cost is 90,000 and official is 100,000, break_even_dev = -10.0%
        if official_cost > 0:
            break_even_dev = ((break_even_cost - official_cost) / official_cost) * 100
        else:
            break_even_dev = 0.0

        # 3. Query similar historical tenders
        similarity_res = await similarity_service.search_similar_tenders(
            db, query_text=tender.work_name, limit=5
        )
        
        similar_results = similarity_res["results"]
        similar_ids = [r["id"] for r in similar_results]
        
        # Extract winning bid deviations
        winning_deviations = [
            r["winning_bid_percent_diff"]
            for r in similar_results
            if r["winning_bid_percent_diff"] is not None
        ]
        
        # If we have no historical bids, supply standard fallback bounds around Telangana eProcurement averages
        if not winning_deviations:
            logger.warning("No similar tenders with winning bid deviations found. Using baseline fallback deviations.")
            winning_deviations = [-4.0, -6.0, -8.0] # default -6% mean, 2% std dev
            
        mean_dev = float(np.mean(winning_deviations))
        std_dev = float(np.std(winning_deviations)) if len(winning_deviations) > 1 else 2.0
        if std_dev == 0.0:
            std_dev = 2.0

        # 4. Formulate Recommended Bid Range
        # Bidding below break-even margin yields expected loss, so minimum recommended bid is capped at break-even deviation
        recommended_min = max(break_even_dev, mean_dev - 1.0 * std_dev)
        # Cap recommended max at historical mean to preserve high winning probabilities
        recommended_max = min(mean_dev, mean_dev + 0.5 * std_dev)
        
        if recommended_max < recommended_min:
            recommended_max = recommended_min + 2.0 # Force small profit window above break-even
            
        # Calculate expected profit ranges
        bid_amount_min = official_cost * (1.0 + (recommended_min / 100.0))
        bid_amount_max = official_cost * (1.0 + (recommended_max / 100.0))
        
        profit_min = bid_amount_min - break_even_cost
        profit_max = bid_amount_max - break_even_cost

        # 5. Gemini Contextual Risk Assessment
        risk_score, confidence_level, assumptions = await self.get_gemini_risk_assessment(
            work_name=tender.work_name,
            eligibility=tender.eligibility_criteria or "None specified",
            penalty_clauses=tender.penalty_clauses or "None specified",
            similar_count=len(similar_results)
        )

        # 6. Persist BidRecommendation
        # Check if recommendation already exists for this tender
        stmt = select(BidRecommendation).filter(BidRecommendation.tender_id == tender_id)
        res = await db.execute(stmt)
        rec = res.scalars().first()
        
        if not rec:
            rec = BidRecommendation(tender_id=tender_id)
            
        rec.recommended_bid_range_min = recommended_min
        rec.recommended_bid_range_max = recommended_max
        rec.estimated_profit_min = profit_min
        rec.estimated_profit_max = profit_max
        rec.risk_score = risk_score
        rec.confidence_level = confidence_level
        rec.similar_tenders_used = similar_ids
        rec.assumptions = assumptions
        rec.generated_at = datetime.utcnow()
        
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        
        # Calculate winning probabilities for visual sliders
        win_prob_min = self.calculate_win_probability(recommended_min, mean_dev, std_dev)
        win_prob_max = self.calculate_win_probability(recommended_max, mean_dev, std_dev)
        
        return {
            "id": str(rec.id),
            "tender_id": tender_id,
            "tender_number": tender.tender_number,
            "work_name": tender.work_name,
            "official_estimated_cost": official_cost,
            "break_even_cost": break_even_cost,
            "break_even_deviation_percent": round(break_even_dev, 3),
            "recommended_bid_range": {
                "min_percent": round(recommended_min, 3),
                "max_percent": round(recommended_max, 3),
                "min_profit": round(profit_min, 2),
                "max_profit": round(profit_max, 2),
                "win_probability_at_min": round(win_prob_min * 100, 2),
                "win_probability_at_max": round(win_prob_max * 100, 2)
            },
            "risk_score": float(rec.risk_score),
            "confidence_level": rec.confidence_level,
            "similar_tenders_count": len(similar_results),
            "assumptions": rec.assumptions,
            "generated_at": rec.generated_at.isoformat(),
            # Normal distribution parameters for UI plot rendering
            "win_probability_distribution": {
                "mean_deviation": round(mean_dev, 3),
                "std_deviation": round(std_dev, 3)
            }
        }


recommendation_service = RecommendationService()
