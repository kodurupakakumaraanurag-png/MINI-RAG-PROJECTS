import io
import re
import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import fitz  # PyMuPDF
import pdfplumber
import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tender import Tender, TenderStatus
from app.repositories.tender_repo import tender_repository


logger = logging.getLogger("app.extraction")

# Try importing pytesseract for OCR, handle gracefully if missing
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False
    logger.warning("pytesseract is not installed. OCR extraction will be disabled.")


class PDFExtractionService:
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extracts raw text from a PDF document using PyMuPDF.
        If the extracted text is empty or too short, triggers OCR fallback.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
            
        logger.info("Extracting text from PDF: %s", pdf_path.name)
        text = ""
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception as e:
            logger.error("PyMuPDF failed to extract text from %s: %s", pdf_path.name, str(e))
            
        # Trigger OCR fallback if the text is minimal (e.g. scanned images)
        if len(text.strip()) < 150:
            logger.info("Minimal text detected (%d chars). Triggering OCR fallback...", len(text.strip()))
            text = self.ocr_pdf(pdf_path)
            
        return text

    def ocr_pdf(self, pdf_path: Path) -> str:
        """
        Renders PDF pages as images and performs OCR using Tesseract.
        """
        if not HAS_PYTESSERACT:
            logger.warning("OCR requested but pytesseract is unavailable. Returning blank text.")
            return ""
            
        text = ""
        try:
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc):
                logger.info("Running OCR on %s page %d", pdf_path.name, page_num + 1)
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Perform OCR
                page_text = pytesseract.image_to_string(img)
                text += page_text + "\n"
            doc.close()
        except Exception as e:
            logger.error("OCR failed for %s: %s", pdf_path.name, str(e))
            
        return text

    def clean_numeric(self, val_str: str) -> Optional[float]:
        if not val_str:
            return None
        # Remove common currency text prefixes like "Rs.", "Rs", "INR"
        cleaned_text = re.sub(r"(?i)Rs\.?|INR", "", val_str)
        # Remove commas, currency symbols, spaces
        cleaned = re.sub(r"[^\d.]", "", cleaned_text)
        try:
            return float(cleaned)
        except ValueError:
            # Fallback if there are multiple dots:
            parts = cleaned.split('.')
            if len(parts) > 1:
                cleaned = "".join(parts[:-1]) + "." + parts[-1]
                try:
                    return float(cleaned)
                except ValueError:
                    return None
            return None

    def clean_integer(self, val_str: str) -> Optional[int]:
        if not val_str:
            return None
        cleaned = re.sub(r"\D", "", val_str)
        try:
            return int(cleaned)
        except ValueError:
            return None

    def parse_metadata_with_regex(self, text: str) -> Dict[str, Any]:
        """
        Heuristic parsing using regular expressions for standard fields.
        """
        metadata = {
            "tender_number": None,
            "estimated_cost": None,
            "emd": None,
            "completion_period_months": None,
            "closing_date": None,
            "opening_date": None,
            "bidding_class": None,
            "eligibility_criteria": None,
            "defect_liability_months": None,
            "penalty_clauses": None
        }

        # Tender number matches
        no_match = re.search(
            r"(?i)(?:Tender\s+Notice\s+No|NIT\s+No|Ref\s+No|Tender\s+Ref\s+No)[^0-9a-zA-Z]*([A-Z0-9/\-_()]+)",
            text
        )
        if no_match:
            metadata["tender_number"] = no_match.group(1).strip()

        # Estimated cost matches
        cost_match = re.search(
            r"(?i)(?:Estimated\s+Contract\s+Value|ECV|Estimated\s+Cost|Value\s+of\s+Work)[^0-9\.]*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d{2})?)",
            text
        )
        if cost_match:
            metadata["estimated_cost"] = self.clean_numeric(cost_match.group(1))

        # EMD matches
        emd_match = re.search(
            r"(?i)(?:Earnest\s+Money\s+Deposit|EMD|Bid\s+Security)[^0-9\.]*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d{2})?)",
            text
        )
        if emd_match:
            metadata["emd"] = self.clean_numeric(emd_match.group(1))

        # Completion period matches
        period_match = re.search(
            r"(?i)(?:Period\s+of\s+Completion|Completion\s+Period|Time\s+for\s+Completion)[^0-9]*(\d+)\s*(months|days|weeks|year)",
            text
        )
        if period_match:
            num = self.clean_integer(period_match.group(1))
            unit = period_match.group(2).lower()
            if num:
                if "day" in unit:
                    metadata["completion_period_months"] = max(1, num // 30)
                elif "week" in unit:
                    metadata["completion_period_months"] = max(1, num // 4)
                elif "year" in unit:
                    metadata["completion_period_months"] = num * 12
                else:
                    metadata["completion_period_months"] = num


        # Bidding class matches
        class_match = re.search(
            r"(?i)Class[\s:-]+(?:of\s+Registration)?\s*([IVX\d\w\s]+?)(?:\s+Class|\s+or\s+above|\s+Registration|\s+Contractors|\n|$)",
            text
        )
        if class_match:
            metadata["bidding_class"] = class_match.group(1).strip()

        return metadata

    async def parse_metadata_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Uses Gemini API (via HTTP client) to extract structured fields from unstructured text.
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set. Skipping LLM-based metadata extraction.")
            return {}

        logger.info("Invoking Gemini API for metadata extraction fallback.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        
        prompt = (
            "You are a procurement expert parsing government tender notice documents.\n"
            "Extract the following fields from the text snippet. Return the result strictly as a JSON object.\n"
            "Do not include any markdown format tags like ```json or ```, just return the raw JSON string.\n"
            "If a field is not found or cannot be determined, set it to null.\n\n"
            "JSON structure:\n"
            "{\n"
            '  "tender_number": string,\n'
            '  "estimated_cost": number (no commas, e.g. 5400000.00),\n'
            '  "emd": number (no commas, e.g. 54000.00),\n'
            '  "completion_period_months": integer,\n'
            '  "bidding_class": string,\n'
            '  "closing_date": string (format YYYY-MM-DD),\n'
            '  "opening_date": string (format YYYY-MM-DD),\n'
            '  "eligibility_criteria": string,\n'
            '  "defect_liability_months": integer,\n'
            '  "penalty_clauses": string\n'
            "}\n\n"
            f"Tender Document Text:\n{text[:6000]}"
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
                        # Sanitize JSON outputs
                        cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text)
                        return json.loads(cleaned_json)
                logger.error("Gemini API call failed with status: %d", response.status_code)
        except Exception as e:
            logger.error("Failed to parse metadata via Gemini API: %s", str(e), exc_info=True)
            
        return {}

    def extract_boq_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extracts tabular BOQ schedule lines from the PDF using pdfplumber.
        """
        boq_items = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables):
                        logger.info("Found table %d on page %d in %s", t_idx+1, page_num+1, pdf_path.name)
                        # Expect headers in first 2 rows
                        if len(table) < 2:
                            continue
                        
                        # Process rows
                        for row in table[1:]:
                            # Skip headers or empty rows
                            if not row or not any(row):
                                continue
                            # Example mapping of columns: [item_no, description, quantity, unit, estimated_rate, amount]
                            # Clean and identify row segments
                            non_empty = [c for c in row if c]
                            if len(non_empty) >= 4:
                                boq_items.append({
                                    "item_number": row[0].strip() if row[0] else "",
                                    "description": row[1].strip() if row[1] else "",
                                    "quantity": self.clean_numeric(row[2]) if len(row) > 2 else 0.0,
                                    "unit": row[3].strip() if len(row) > 3 and row[3] else "",
                                    "estimated_rate": self.clean_numeric(row[4]) if len(row) > 4 else 0.0,
                                    "estimated_amount": self.clean_numeric(row[5]) if len(row) > 5 else 0.0
                                })
        except Exception as e:
            logger.error("pdfplumber BOQ extraction failed for %s: %s", pdf_path.name, str(e))
            
        return boq_items

    async def extract_and_update_tender(self, db: AsyncSession, tender_id: str) -> Tender:
        """
        Main runner that loads the active TenderNotice document, extracts text/metadata/BOQ,
        and saves it to the database.
        """
        from uuid import UUID
        tender_uuid = UUID(tender_id)
        
        tender = await tender_repository.get(db, tender_uuid)
        if not tender:
            raise ValueError("Tender not found")

        # Load active TenderNotice document
        from sqlalchemy import select
        from app.models.tender import TenderDocument
        result = await db.execute(
            select(TenderDocument).filter(
                TenderDocument.tender_id == tender.id,
                TenderDocument.document_type == "TenderNotice",
                TenderDocument.is_active == True
            )
        )
        doc_record = result.scalars().first()
        if not doc_record:
            raise FileNotFoundError("Active TenderNotice document record not found for tender")

        doc_path = Path(doc_record.file_path)
        if not doc_path.exists():
            raise FileNotFoundError(f"Physical file missing at: {doc_path}")

        # Extract Text
        text = self.extract_text_from_pdf(doc_path)
        
        # Regex Metadata
        extracted_data = self.parse_metadata_with_regex(text)
        
        # LLM Metadata fallback
        llm_data = await self.parse_metadata_with_llm(text)
        
        # Merge dictionaries, prioritizing LLM values for dates and clauses
        for key in extracted_data:
            if key in llm_data and llm_data[key] is not None:
                extracted_data[key] = llm_data[key]

        # Update Tender record
        if extracted_data.get("tender_number"):
            tender.tender_number = extracted_data["tender_number"]
        if extracted_data.get("estimated_cost"):
            tender.estimated_cost = extracted_data["estimated_cost"]
        if extracted_data.get("emd"):
            tender.emd = extracted_data["emd"]
        if extracted_data.get("completion_period_months"):
            tender.completion_period_months = extracted_data["completion_period_months"]
        if extracted_data.get("bidding_class"):
            tender.bidding_class = extracted_data["bidding_class"]
        if extracted_data.get("eligibility_criteria"):
            tender.eligibility_criteria = extracted_data["eligibility_criteria"]
        if extracted_data.get("defect_liability_months"):
            tender.defect_liability_months = extracted_data["defect_liability_months"]
        if extracted_data.get("penalty_clauses"):
            tender.penalty_clauses = extracted_data["penalty_clauses"]

        # Parse dates
        for date_key in ["closing_date", "opening_date"]:
            val = extracted_data.get(date_key)
            if val:
                try:
                    # Expect YYYY-MM-DD
                    parsed_date = datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    setattr(tender, date_key, parsed_date)
                except ValueError:
                    logger.warning("Could not parse date string: %s", val)

        tender.status = TenderStatus.EXTRACTED
        db.add(tender)
        await db.commit()
        await db.refresh(tender)
        
        return tender


pdf_extraction_service = PDFExtractionService()
