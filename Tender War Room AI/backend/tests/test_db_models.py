from datetime import datetime, date, timezone
from uuid import uuid4
import pytest
from app.models.tender import Tender, Department, Area, TenderStatus, TenderDocument
from app.models.boq import BOQ
from app.models.historical import Contractor, HistoricalTender, HistoricalBid, Award, BidStatus
from app.models.market import MaterialPrices, LabourRates, MachineRates
from app.models.recommendation import Competitors, BidRecommendation


def test_model_instantiations() -> None:
    """
    Assert that all new model schemas can be instantiated with appropriate type values
    and relationships.
    """
    # 1. BOQ model
    tender_id = uuid4()
    boq = BOQ(
        tender_id=tender_id,
        item_number="BOQ-1.1",
        description="Excavation of soil in all soils",
        quantity=1500.50,
        unit="Cum",
        estimated_rate=120.00,
        estimated_amount=180060.00
    )
    assert boq.item_number == "BOQ-1.1"
    assert boq.estimated_amount == 180060.00

    # 2. Historical models
    contractor = Contractor(
        company_name="Anurag Infra Projects",
        registration_class="Class I",
        blacklisted=False,
        rating=4.8
    )
    assert contractor.company_name == "Anurag Infra Projects"

    hist_tender = HistoricalTender(
        tender_number="HIST-SCCL-2025-01",
        work_name="Laying of pipeline",
        estimated_cost=25000000.00,
        winning_bid_amount=24500000.00,
        winning_bid_percent_diff=-2.00
    )
    assert hist_tender.tender_number == "HIST-SCCL-2025-01"

    hist_bid = HistoricalBid(
        historical_tender_id=uuid4(),
        contractor_id=uuid4(),
        bid_amount=24000000.00,
        bid_percent_diff=-4.00,
        bid_rank=2,
        bid_status=BidStatus.LOST
    )
    assert hist_bid.bid_status == BidStatus.LOST

    award = Award(
        historical_tender_id=uuid4(),
        contractor_id=uuid4(),
        award_amount=24500000.00,
        loi_number="LOI-12345-SCCL"
    )
    assert award.loi_number == "LOI-12345-SCCL"

    # 3. Market models
    mat_price = MaterialPrices(
        material_type="Steel",
        price_per_unit=55000.00,
        unit="MT",
        region="Hyderabad",
        recorded_date=date.today()
    )
    assert mat_price.material_type == "Steel"

    lab_rate = LabourRates(
        labour_type="Skilled",
        rate_per_day=800.00,
        recorded_date=date.today()
    )
    assert lab_rate.rate_per_day == 800.00

    mach_rate = MachineRates(
        machine_type="Excavator",
        rate_per_hour=1500.00,
        recorded_date=date.today()
    )
    assert mach_rate.machine_type == "Excavator"

    # 4. Recommendation models
    competitor = Competitors(
        company_name="Mega Engineering",
        tender_type_preference="Roads and Bridges",
        historical_win_rate=22.50,
        bidding_behavior_profile={"aggressiveness": "High"}
    )
    assert competitor.company_name == "Mega Engineering"
    assert competitor.bidding_behavior_profile["aggressiveness"] == "High"

    bid_rec = BidRecommendation(
        tender_id=uuid4(),
        recommended_bid_range_min=-8.500,
        recommended_bid_range_max=-5.000,
        estimated_profit_min=150000.00,
        estimated_profit_max=250000.00,
        risk_score=3.5,
        confidence_level="High"
    )
    assert bid_rec.recommended_bid_range_min == -8.500
    assert bid_rec.confidence_level == "High"
