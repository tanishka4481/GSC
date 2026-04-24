"""
PROVCHAIN — PDF Builder
=======================
Generates PDF documents for the evidence bundle using ReportLab.
"""

import io
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from registration.models import AssetRecord
from monitoring.models import PropagationReport, ScanRecord


def build_registration_certificate(asset: AssetRecord) -> bytes:
    """
    Creates a PDF showing original asset registration details, timestamps, 
    IPFS CIDs, and Hashes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    elements = []
    
    elements.append(Paragraph("PROVCHAIN", title_style))
    elements.append(Paragraph("Digital Asset Registration Certificate", heading_style))
    elements.append(Spacer(1, 20))
    
    data = [
        ["Asset ID", str(asset.asset_id)],
        ["Owner ID", str(asset.owner_id)],
        ["Filename", str(asset.filename)],
        ["Content Type", str(asset.content_type)],
        ["File Size", f"{asset.file_size} bytes"],
        ["SHA-256 Hash", str(asset.sha256)],
        ["Registration Date", str(asset.created_at or datetime.utcnow().isoformat())],
    ]
    
    if asset.phash:
        data.append(["pHash", str(asset.phash)])
    
    if asset.ipfs_cid:
        data.append(["IPFS CID", str(asset.ipfs_cid)])
        
    if asset.timestamp_proof:
        data.append(["Timestamp Status", str(asset.timestamp_proof.get("status", "unknown"))])
        if asset.timestamp_proof.get("confirmed_at"):
            data.append(["Bitcoin Confirmed", str(asset.timestamp_proof["confirmed_at"])])
        if asset.timestamp_proof.get("bitcoin_block"):
            data.append(["Bitcoin Block", str(asset.timestamp_proof.get("bitcoin_block", ""))])
    
    # Use Paragraph for the values to allow text wrapping for long hashes
    for i in range(len(data)):
        data[i][1] = Paragraph(data[i][1], normal_style)
        
    table = Table(data, colWidths=[130, 320])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph(
        "This document certifies that the digital asset identified by the SHA-256 hash above "
        "was registered on the PROVCHAIN platform. If a timestamp proof is present, it means "
        "the asset's existence at that time is cryptographically anchored to the Bitcoin blockchain.", 
        normal_style
    ))
    
    doc.build(elements)
    return buffer.getvalue()


def build_match_report(report: PropagationReport, scan_record: ScanRecord) -> bytes:
    """
    Creates a PDF outlining the detected matches, domains, and Fingerprint similarity scores.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    elements = []
    
    elements.append(Paragraph("PROVCHAIN", title_style))
    elements.append(Paragraph("Fingerprint Match Report", heading_style))
    elements.append(Spacer(1, 20))
    
    # Summary
    anomaly_val = report.anomaly.anomaly_type.value if report.anomaly else "None"
    summary_data = [
        ["Asset ID", str(report.asset_id)],
        ["Scan ID", str(report.scan_id)],
        ["Scan Date", str(report.scanned_at)],
        ["Total Hits", str(report.metrics.total_hits)],
        ["Unique Domains", str(report.metrics.unique_domains)],
        ["Anomaly Type", str(anomaly_val)],
        ["Risk Score", f"{report.risk_score:.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[130, 320])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Detected Matches", heading_style))
    elements.append(Spacer(1, 10))
    
    if not scan_record.hits:
        elements.append(Paragraph("No matches found in this scan.", normal_style))
    else:
        # Match Decisions
        # Build a table of hits
        hits_data = [["Domain", "URL", "Confidence", "Reasoning"]]
        
        for i, hit in enumerate(scan_record.hits):
            domain = hit.get("domain", "unknown")
            url = hit.get("url", "unknown")
            
            confidence = "UNKNOWN"
            reasoning = "N/A"
            if i < len(report.match_decisions):
                decision = report.match_decisions[i]
                confidence = decision.confidence.value
                reasoning = decision.reasoning
                
            hits_data.append([
                Paragraph(domain, normal_style),
                Paragraph(url, normal_style),
                Paragraph(confidence, normal_style),
                Paragraph(reasoning, normal_style)
            ])
            
        hits_table = Table(hits_data, colWidths=[80, 150, 90, 130])
        hits_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4285F4")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        elements.append(hits_table)
        
    doc.build(elements)
    return buffer.getvalue()
