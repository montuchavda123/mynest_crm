from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from django.conf import settings
from decimal import Decimal
import os

def generate_quotation_pdf(quotation):
    """
    Generates a professional PDF for the given quotation and returns the file path.
    """
    # Define file path
    filename = f"quotation_{quotation.id}.pdf"
    folder_path = os.path.join(settings.MEDIA_ROOT, 'quotations')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    filepath = os.path.join(folder_path, filename)
    
    # Create the document
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Custom Styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor("#6366f1"),
        spaceAfter=20,
        alignment=1 # Center
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=15
    )

    # 1. Header (Company Info)
    elements.append(Paragraph("MyNest CRM", title_style))
    elements.append(Paragraph("Your Trusted Real Estate Partner", company_style))
    if quotation.prepared_by:
        prepared_by = quotation.prepared_by.get_full_name() or quotation.prepared_by.username
        elements.append(Paragraph(f"<b>Prepared By:</b> {prepared_by}", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    # 2. Quotation Info & Client Details (Two-column layout)
    client_data = [
        [Paragraph(f"<b>QUOTE TO:</b><br/>{quotation.lead.name}<br/>{quotation.lead.phone}<br/>{quotation.lead.email or ''}", styles['Normal']),
         Paragraph(f"<b>QUOTATION NO:</b> QTN-{quotation.created_at.year}-{quotation.id:03d}<br/><b>DATE:</b> {quotation.created_at.strftime('%d %b, %Y')}<br/><b>STATUS:</b> {quotation.get_status_display()}", styles['Normal'])]
    ]
    client_table = Table(client_data, colWidths=[3*inch, 3*inch])
    client_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 0.3 * inch))

    # 3. Itemized Table
    # Table Header
    table_data = [['Service Description', 'Qty', 'Rate (INR)', 'Total (INR)']]
    
    # Items
    for item in quotation.items.all():
        table_data.append([
            item.service_name,
            str(item.quantity),
            f"{item.rate:,.2f}",
            f"{item.total:,.2f}"
        ])
    
    # Subtotal, GST, Grand Total
    subtotal = sum((item.total for item in quotation.items.all()), Decimal("0.00"))
    gst = subtotal * Decimal("0.18")
    grand_total = subtotal + gst

    table_data.append(['', '', 'Subtotal', f"{subtotal:,.2f}"])
    table_data.append(['', '', 'GST (18%)', f"{gst:,.2f}"])
    table_data.append(['', '', 'Grand Total', f"{grand_total:,.2f}"])

    # Table Styling
    item_table = Table(table_data, colWidths=[3*inch, 0.5*inch, 1.2*inch, 1.3*inch])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#475569")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-4), 0.5, colors.grey),
        ('LINEBELOW', (2,-3), (-1,-1), 1, colors.black),
        ('FONTNAME', (2,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (2,-1), (-1,-1), 12),
        ('TOPPADDING', (0,-3), (-1,-1), 10),
    ]))
    
    elements.append(item_table)
    elements.append(Spacer(1, 0.5 * inch))

    # 4. Dynamic section-wise quotation content.
    for section in quotation.sections.all():
        elements.append(Paragraph(f"<b>{section.title}</b>", styles['Heading4']))
        for line in section.content.splitlines():
            if line.strip():
                elements.append(Paragraph(line.strip(), styles['Normal']))
        elements.append(Spacer(1, 0.12 * inch))

    # 5. Default Terms & Conditions
    elements.append(Paragraph("<b>Terms & Conditions:</b>", styles['Normal']))
    elements.append(Paragraph("1. This quotation is valid for 30 days from the date of issue.", styles['Normal']))
    elements.append(Paragraph("2. 50% advance payment is required to commence the project.", styles['Normal']))
    elements.append(Paragraph("3. All taxes are inclusive as per GST norms.", styles['Normal']))
    
    elements.append(Spacer(1, 1 * inch))
    elements.append(Paragraph("Authorized Signatory", styles['Normal']))

    # Build PDF
    doc.build(elements)
    
    return f"quotations/{filename}"
