import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tender import Tender
from app.models.boq import BOQ
from app.services.estimation_service import estimation_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger("app.report")


class ReportService:
    async def generate_print_report(self, db: AsyncSession, tender_id: str) -> str:
        """
        Gathers estimation cost sheets, semantic strategy matches, and Gemini risk outputs
        to compile a premium print-optimized HTML bid dossier.
        """
        logger.info("Compiling printable bid report for tender: %s", tender_id)
        tender_uuid = UUID(tender_id)
        
        # 1. Fetch Tender
        tender = await db.get(Tender, tender_uuid)
        if not tender:
            raise ValueError(f"Tender with ID {tender_id} not found.")
            
        # 2. Fetch Cost Sheet
        cost_sheet = await estimation_service.get_cost_sheet_summary(db, tender_id)
        
        # 3. Fetch Recommendation
        rec = await recommendation_service.generate_recommendation(db, tender_id)
        
        # 4. Fetch BOQ Items
        stmt = select(BOQ).filter(BOQ.tender_id == tender_uuid).order_by(BOQ.item_number)
        res = await db.execute(stmt)
        boq_items = res.scalars().all()
        
        # Build BOQ rows HTML
        boq_rows_html = ""
        for item in boq_items:
            c_rate = f"Rs. {item.contractor_rate:,.2f}" if item.contractor_rate is not None else "-"
            c_amt = f"Rs. {item.contractor_amount:,.2f}" if item.contractor_amount is not None else "-"
            boq_rows_html += f"""
            <tr>
                <td>{item.item_number}</td>
                <td>{item.description}</td>
                <td>{float(item.quantity):,.2f}</td>
                <td>{item.unit}</td>
                <td>Rs. {float(item.estimated_rate):,.2f}</td>
                <td>Rs. {float(item.estimated_amount):,.2f}</td>
                <td style="font-weight: bold; color: #1e3a8a;">{c_rate}</td>
                <td style="font-weight: bold; color: #1e3a8a;">{c_amt}</td>
            </tr>
            """

        # Build Projection rows HTML
        projection_rows_html = ""
        for proj in cost_sheet["margin_projections"]:

            # Check row viability styling
            viability_color = "#15803d" if proj["expected_profit"] > 0 else "#b91c1c"
            projection_rows_html += f"""
            <tr>
                <td>{proj["bid_percent_deviation"]:+.3f}%</td>
                <td>Rs. {proj["bid_amount"]:,.2f}</td>
                <td style="color: {viability_color}; font-weight: bold;">Rs. {proj["expected_profit"]:,.2f}</td>
                <td style="color: {viability_color}; font-weight: bold;">{proj["profit_margin_percent"]:.2f}%</td>
                <td>
                    <span style="background-color: {viability_color}1a; color: {viability_color}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                        {proj["recommendation_status"]}
                    </span>
                </td>
            </tr>
            """

        # Build Assumptions HTML
        assumptions_html = ""
        assumptions_dict = rec.get("assumptions") or {}
        for key, val in assumptions_dict.items():
            clean_key = key.replace("_", " ").title()
            assumptions_html += f"""
            <div style="margin-bottom: 8px;">
                <span style="font-weight: bold; color: #374151;">{clean_key}:</span>
                <span style="color: #4b5563;">{val}</span>
            </div>
            """

        # HTML and CSS Printable template
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bid Dossier: {tender.tender_number}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: #f3f4f6;
            margin: 0;
            padding: 40px;
            color: #111827;
        }}
        
        .container {{
            max-width: 1000px;
            background: #ffffff;
            margin: 0 auto;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            border-top: 8px solid #1e3a8a;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 28px;
            color: #1e3a8a;
            font-weight: 700;
        }}
        
        .header-meta {{
            text-align: right;
            font-size: 14px;
            color: #6b7280;
        }}
        
        .grid-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: #f9fafb;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            text-align: center;
        }}
        
        .card-title {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        
        .card-value {{
            font-size: 18px;
            font-weight: 700;
            color: #111827;
        }}
        
        .card-accent {{
            color: #1e3a8a;
        }}
        
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1e3a8a;
            margin-top: 40px;
            margin-bottom: 16px;
            border-left: 4px solid #1e3a8a;
            padding-left: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            font-size: 13px;
        }}
        
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        th {{
            background-color: #f3f4f6;
            color: #374151;
            font-weight: 600;
        }}
        
        .risk-box {{
            background-color: #fef2f2;
            border: 1px solid #fee2e2;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        
        .risk-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }}
        
        .risk-title {{
            font-weight: 600;
            color: #991b1b;
            font-size: 16px;
            margin: 0;
        }}
        
        .risk-badge {{
            background-color: #991b1b;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        @media print {{
            body {{
                background-color: white;
                padding: 0;
                color: black;
            }}
            .container {{
                box-shadow: none;
                padding: 0;
                border-top: none;
            }}
            .no-print {{
                display: none;
            }}
            .page-break {{
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Print Header -->
        <div class="header">
            <div>
                <h1>BID STRATEGY DOSSIER</h1>
                <div style="font-size: 14px; margin-top: 4px; color: #4b5563;">Tender War Room AI • Decision Support Report</div>
            </div>
            <div class="header-meta">
                <div><strong>Tender No:</strong> {tender.tender_number}</div>
                <div><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
            </div>
        </div>

        <!-- Meta Grid Cards -->
        <div class="grid-cards">
            <div class="card">
                <div class="card-title">Official Estimate</div>
                <div class="card-value">Rs. {float(cost_sheet["official_estimated_cost"]):,.2f}</div>
            </div>
            <div class="card">
                <div class="card-title">Break-Even Cost</div>
                <div class="card-value card-accent">Rs. {float(cost_sheet["break_even_cost"]):,.2f}</div>
            </div>
            <div class="card">
                <div class="card-title">Optimal Bid Range</div>
                <div class="card-value" style="font-size: 15px; color: #16a34a;">
                    {rec["recommended_bid_range"]["min_percent"]:+.2f}% to {rec["recommended_bid_range"]["max_percent"]:+.2f}%
                </div>
            </div>
            <div class="card">
                <div class="card-title">Win Probability Range</div>
                <div class="card-value" style="font-size: 15px; color: #16a34a;">
                    {rec["recommended_bid_range"]["win_probability_at_min"]:.1f}% to {rec["recommended_bid_range"]["win_probability_at_max"]:.1f}%
                </div>
            </div>
        </div>

        <!-- Project Details -->
        <div class="section-title">Project Specifications</div>
        <div style="margin-bottom: 20px; line-height: 1.6; font-size: 14px;">
            <div style="margin-bottom: 8px;"><strong>Work Scope:</strong> {tender.work_name}</div>
            <div style="margin-bottom: 8px;"><strong>Eligibility Criteria:</strong> {tender.eligibility_criteria or "Standard portal class registrations apply."}</div>
            <div><strong>Penalty Clauses:</strong> {tender.penalty_clauses or "Standard liquidated damages terms apply."}</div>
        </div>

        <!-- Risk Assessment -->
        <div class="risk-box">
            <div class="risk-header">
                <h3 class="risk-title">AI Volatility & Risk Analysis</h3>
                <span class="risk-badge">Risk Score: {rec["risk_score"]}/10</span>
            </div>
            <div style="font-size: 13.5px; line-height: 1.6; color: #7f1d1d; margin-bottom: 16px;">
                <strong>Confidence Rating:</strong> {rec["confidence_level"]}<br>
                <strong>Bidding Guidelines:</strong> Bids priced above the maximum boundary exhibit low winning probabilities due to historical competitor benchmarks. Bids priced below the minimum boundary trigger high expected financial losses.
            </div>
            <div style="font-size: 13px; line-height: 1.5; color: #4b5563;">
                <strong>Key Strategy Assumptions:</strong>
                <div style="margin-top: 8px;">
                    {assumptions_html}
                </div>
            </div>
        </div>

        <div class="page-break"></div>

        <!-- Cost Sheet Table -->
        <div class="section-title">Customized Cost Estimation Sheet (BOQ)</div>
        <table>
            <thead>
                <tr>
                    <th style="width: 80px;">Item No</th>
                    <th>Description of Works</th>
                    <th>Quantity</th>
                    <th>Unit</th>
                    <th>Est. Rate</th>
                    <th>Est. Amount</th>
                    <th>Custom Rate</th>
                    <th>Custom Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {boq_rows_html}
            </tbody>
        </table>

        <!-- Bidding Projections Table -->
        <div class="section-title">Expected Profit Projections (Sensitivity Analysis)</div>
        <table>
            <thead>
                <tr>
                    <th>Bidding Margin</th>
                    <th>Bidding Proposal Amount</th>
                    <th>Expected Profit Margin</th>
                    <th>Expected Profit Margin %</th>
                    <th>Bidding Viability Status</th>
                </tr>
            </thead>
            <tbody>
                {projection_rows_html}
            </tbody>
        </table>

        <!-- Print Instructions / Footer -->
        <div class="no-print" style="margin-top: 50px; text-align: center; padding: 20px; background-color: #eff6ff; border: 1px dashed #bfdbfe; border-radius: 8px;">
            <span style="font-size: 14px; color: #1e40af;">
                💡 <strong>Print Tip:</strong> Press <strong>Ctrl + P</strong> (or Command + P on Mac) to print this dossier or save it as a clean PDF document.
            </span>
        </div>
    </div>
</body>
</html>
"""
        return html_template


report_service = ReportService()
