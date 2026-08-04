from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tender import Tender, TenderDocument, Department, Area, TenderStatus


class TenderRepository:
    async def get_by_tender_number(self, db: AsyncSession, tender_number: str) -> Optional[Tender]:
        result = await db.execute(
            select(Tender).filter(Tender.tender_number == tender_number)
        )
        return result.scalars().first()

    async def get(self, db: AsyncSession, id: UUID) -> Optional[Tender]:
        result = await db.execute(select(Tender).filter(Tender.id == id))
        return result.scalars().first()

    async def list_tenders(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Tender]:
        result = await db.execute(select(Tender).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_or_create_department(self, db: AsyncSession, name: str) -> Department:
        result = await db.execute(select(Department).filter(Department.name == name))
        dept = result.scalars().first()
        if not dept:
            dept = Department(name=name)
            db.add(dept)
            await db.commit()
            await db.refresh(dept)
        return dept

    async def get_or_create_area(self, db: AsyncSession, name: str, state: str = "Telangana") -> Area:
        result = await db.execute(
            select(Area).filter(Area.name == name, Area.state == state)
        )
        area = result.scalars().first()
        if not area:
            area = Area(name=name, state=state)
            db.add(area)
            await db.commit()
            await db.refresh(area)
        return area

    async def create_tender(
        self,
        db: AsyncSession,
        *,
        tender_number: str,
        work_name: str,
        department_name: str,
        area_name: str,
        estimated_cost: Optional[float] = None,
        emd: Optional[float] = None,
        completion_period_months: Optional[int] = None,
        bidding_class: Optional[str] = None,
        closing_date: Optional[datetime] = None,
        opening_date: Optional[datetime] = None,
        eligibility_criteria: Optional[str] = None,
        defect_liability_months: Optional[int] = None,
        penalty_clauses: Optional[str] = None,
        raw_pdf_path: Optional[str] = None,
    ) -> Tender:
        dept = await self.get_or_create_department(db, department_name)
        area = await self.get_or_create_area(db, area_name)
        
        tender = Tender(
            tender_number=tender_number,
            work_name=work_name,
            department_id=dept.id,
            area_id=area.id,
            estimated_cost=estimated_cost,
            emd=emd,
            completion_period_months=completion_period_months,
            bidding_class=bidding_class,
            closing_date=closing_date,
            opening_date=opening_date,
            eligibility_criteria=eligibility_criteria,
            defect_liability_months=defect_liability_months,
            penalty_clauses=penalty_clauses,
            raw_pdf_path=raw_pdf_path,
            status=TenderStatus.SCRAPED
        )
        db.add(tender)
        await db.commit()
        await db.refresh(tender)
        return tender

    async def update_tender_status(
        self, db: AsyncSession, *, tender_id: UUID, status: TenderStatus
    ) -> Optional[Tender]:
        tender = await self.get(db, tender_id)
        if tender:
            tender.status = status
            db.add(tender)
            await db.commit()
            await db.refresh(tender)
        return tender

    async def add_document(
        self,
        db: AsyncSession,
        *,
        tender_id: UUID,
        document_type: str,
        file_name: str,
        file_path: str,
        file_hash: str,
        version: int = 1
    ) -> TenderDocument:
        # Mark other documents of same type and filename as inactive
        await db.execute(
            update(TenderDocument)
            .where(
                TenderDocument.tender_id == tender_id,
                TenderDocument.document_type == document_type,
                TenderDocument.file_name == file_name
            )
            .values(is_active=False)
        )
        
        doc = TenderDocument(
            tender_id=tender_id,
            document_type=document_type,
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            version=version,
            is_active=True
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def get_active_document_by_name(
        self, db: AsyncSession, *, tender_id: UUID, file_name: str
    ) -> Optional[TenderDocument]:
        result = await db.execute(
            select(TenderDocument).filter(
                TenderDocument.tender_id == tender_id,
                TenderDocument.file_name == file_name,
                TenderDocument.is_active == True
            )
        )
        return result.scalars().first()


tender_repository = TenderRepository()
