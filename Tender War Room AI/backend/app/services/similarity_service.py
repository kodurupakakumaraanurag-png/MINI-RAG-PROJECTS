import logging
from typing import Any, Dict, List, Optional
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tender import Tender
from app.models.historical import HistoricalTender

logger = logging.getLogger("app.similarity")


class SimilarityService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        logger.info("Initializing SentenceTransformer model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        self.dimension = 384  # Dimension of all-MiniLM-L6-v2 embeddings
        self.index: Optional[faiss.IndexFlatIP] = None
        self.tenders_map: List[Dict[str, Any]] = []

    async def rebuild_index(self, db: AsyncSession) -> None:
        """
        Fetches all historical and current tenders from the database,
        computes their embeddings, and builds a FAISS IndexFlatIP.
        """
        logger.info("Rebuilding similarity index from database records...")
        
        # 1. Fetch Historical Tenders
        hist_result = await db.execute(select(HistoricalTender))
        hist_tenders = hist_result.scalars().all()
        
        # 2. Fetch Current Tenders
        current_result = await db.execute(select(Tender))
        current_tenders = current_result.scalars().all()
        
        # Assemble texts and mappings
        texts = []
        self.tenders_map = []
        
        for t in hist_tenders:
            texts.append(t.work_name)
            self.tenders_map.append({
                "id": str(t.id),
                "tender_number": t.tender_number,
                "work_name": t.work_name,
                "estimated_cost": float(t.estimated_cost),
                "winning_bid_amount": float(t.winning_bid_amount) if t.winning_bid_amount else None,
                "winning_bid_percent_diff": float(t.winning_bid_percent_diff) if t.winning_bid_percent_diff else None,
                "completion_period_months": t.completion_period_months,
                "type": "Historical"
            })
            
        for t in current_tenders:
            texts.append(t.work_name)
            self.tenders_map.append({
                "id": str(t.id),
                "tender_number": t.tender_number,
                "work_name": t.work_name,
                "estimated_cost": float(t.estimated_cost) if t.estimated_cost else None,
                "winning_bid_amount": None,
                "winning_bid_percent_diff": None,
                "completion_period_months": t.completion_period_months,
                "type": "Current"
            })
            
        if not texts:
            logger.warning("No tenders found in the database. Vector index will remain uninitialized.")
            self.index = None
            return

        # 3. Generate Embeddings
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        # L2-normalize vectors for Cosine Similarity (Inner Product FlatIP index)
        faiss.normalize_L2(embeddings)
        
        # 4. Build index
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings)
        
        logger.info(
            "FAISS index rebuilt successfully with %d documents.",
            len(self.tenders_map)
        )

    async def search_similar_tenders(
        self, db: AsyncSession, query_text: str, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Embeds the query, runs cosine similarity search on the FAISS index,
        and aggregates comparison statistics for matching records.
        """
        # Build index if not initialized
        if self.index is None or not self.tenders_map:
            await self.rebuild_index(db)
            
        if self.index is None or not self.tenders_map:
            return {
                "query": query_text,
                "results": [],
                "analytics": {
                    "avg_estimated_cost": 0.0,
                    "avg_completion_period": 0.0,
                    "avg_winning_deviation_percent": 0.0
                }
            }

        # Embed and normalize query vector
        query_vector = self.model.encode([query_text], convert_to_numpy=True)
        faiss.normalize_L2(query_vector)
        
        # Search the index
        scores, indices = self.index.search(query_vector, min(limit, len(self.tenders_map)))
        
        results = []
        valid_costs = []
        valid_periods = []
        valid_deviations = []
        
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.tenders_map):
                continue
                
            match = self.tenders_map[idx]
            similarity_score = float(score)
            
            # Map result row
            results.append({
                "id": match["id"],
                "tender_number": match["tender_number"],
                "work_name": match["work_name"],
                "estimated_cost": match["estimated_cost"],
                "winning_bid_amount": match["winning_bid_amount"],
                "winning_bid_percent_diff": match["winning_bid_percent_diff"],
                "completion_period_months": match["completion_period_months"],
                "type": match["type"],
                "similarity_score": similarity_score
            })
            
            # Collect data for statistics
            if match["estimated_cost"] is not None:
                valid_costs.append(match["estimated_cost"])
            if match["completion_period_months"] is not None:
                valid_periods.append(match["completion_period_months"])
            if match["winning_bid_percent_diff"] is not None:
                valid_deviations.append(match["winning_bid_percent_diff"])

        # Compute comparison statistics
        analytics = {
            "avg_estimated_cost": float(np.mean(valid_costs)) if valid_costs else 0.0,
            "avg_completion_period": float(np.mean(valid_periods)) if valid_periods else 0.0,
            "avg_winning_deviation_percent": float(np.mean(valid_deviations)) if valid_deviations else 0.0
        }
        
        return {
            "query": query_text,
            "results": results,
            "analytics": analytics
        }


similarity_service = SimilarityService()
