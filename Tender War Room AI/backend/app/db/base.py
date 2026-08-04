# Import all the models, so that Base has them before being
# imported by Alembic or other modules
from app.db.base_class import Base, BaseUUID # noqa
from app.models.user import User # noqa
from app.models.tender import Department, Area, Tender, TenderDocument # noqa
from app.models.boq import BOQ # noqa
from app.models.historical import Contractor, HistoricalTender, HistoricalBid, Award # noqa
from app.models.market import MaterialPrices, LabourRates, MachineRates # noqa
from app.models.recommendation import Competitors, BidRecommendation # noqa

