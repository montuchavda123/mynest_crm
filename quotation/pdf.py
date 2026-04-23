import os
from decimal import Decimal

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import CompanyDetails, Quotation

PDF_NAVY = colors.HexColor("#1B1E3F")
PDF_GOLD = colors.HexColor("#D4AF37")
PDF_BG_LIGHT = colors.HexColor("#F8F9FA")
PDF_BORDER = colors.HexColor("#E5E7EB")
PDF_TEXT_MAIN = colors.HexColor("#2D2D2D")
PDF_TEXT_SECONDARY = colors.HexColor("#64748B")


DEFAULT_NOT_INCLUDED = [
    "Electricals, automation, Server, network and wifi Wiring",
    "VRV (Duct AC etc), Acs",
    "Appliances",
    "Civil and construction work",
    "Washroom Closet",
    "Any item or work which is not specifically mentioned in the Quotation",
]

MYNEST_INCLUSIONS = [
    "Space management",
    "3D (360) Designing",
    "2 Layers Execution",
    "Labour Handling",
    "Debris Cleaning",
    "Basic Deep Cleaning",
    "Floor Cover",
    "2 years of Service Warranty",
]

hardware_note = "German and Indian Brands only"
MATERIAL_SPECIFICATIONS = [
    ("Paint Work", "Asian Paint Royal", ""),
    ("Plywood", "BWR and BWP (Kitchen & washroom base)", ""),
    ("Laminate", "2K", ""),
    ("Veneer", "3K", ""),
    ("Acrylic", "5K", ""),
    ("Hardware - Hinges", "HIKO/Hettich/Godrej/E-Square", hardware_note),
    ("Hardware - Locks", "Godrej", hardware_note),
    ("Hardware - Drawer Channels", "HIKO/Hettich/Godrej/E-Square", hardware_note),
    ("Hardware - Tendum", "HIKO/Hettich/Godrej/E-Square", hardware_note),
    ("Knobs/Handles", "150–500 rs", ""),
    ("Fabric", "300–500 rs", ""),
    ("False Ceiling", "Gypsum", ""),
    ("Lights", "Syska/Astro", ""),
    ("Wires", "RR/Finolex", ""),
]

PACKAGE_DETAILS = [
    (
        "Economic",
        [
            "All finishes will feature laminate, while all other raw materials will adhere to the specified brands and warranties.",
            "It is essential that the raw materials used directly impact the strength and durability of the furniture.",
            "Under no circumstances should these standards be compromised unless requested by the clients.",
        ],
    ),
    (
        "Semi-Luxury Interior",
        [
            "The living area and master bedroom will feature duco/veneer finishes, while the kitchen will have an acrylic finish.",
            "All other areas will be finished in laminate and highlighted (imported) laminates.",
            "We use high-quality raw materials from specified brands, backed by warranties, to ensure the strength and durability of our furniture.",
            "It is essential to maintain these standards for optimal performance, and any deviations will only be made upon client request.",
        ],
    ),
    (
        "Full-Luxury Interior",
        [
            "All finishes will feature PU-Duco, veneer, acrylic, and imported highlighted polymer luxurious laminates that support our targeted luxury design and aesthetic.",
            "Complementing these finishes, all other raw materials will adhere to specified high-end brands and maximum warranties.",
            "It is crucial that the raw materials used directly impact the strength, durability, and look of the furniture.",
            "Under no circumstances should these standards be compromised unless explicitly requested by the clients.",
        ],
    ),
]

BRAND_LOGO_PATHS = [
    fr"static\img\brand_logos\logo_{i}.jpeg" for i in range(1, 10)
]
MAIN_COMPANY_LOGO_PATH = r"static\img\brand_logos\main_logo.png"


def _money(value: Decimal) -> str:
    if value is None:
        value = Decimal("0.00")
    s = f"{abs(value):.2f}"
    integer_part, decimal_part = s.split('.')
    last_three = integer_part[-3:]
    other = integer_part[:-3]
    if other:
        other_chunks = []
        while other:
            other_chunks.append(other[-2:])
            other = other[:-2]
        other_chunks.reverse()
        integer_part = ",".join(other_chunks) + "," + last_three
    
    if decimal_part == "00":
        currency_str = f"₹ {integer_part}"
    else:
        currency_str = f"₹ {integer_part}.{decimal_part}"
    if value < 0:
        currency_str = "-" + currency_str
    return currency_str


def _gold_line(elements, width=7.1 * inch):
    from reportlab.platypus import HRFlowable
    elements.append(HRFlowable(width=width, thickness=1, color=PDF_GOLD, spaceBefore=4, spaceAfter=8))


def _section_table(section):
    data = [["No", "Description", "Remarks"]]
    section_total = Decimal("0.00")
    for idx, item in enumerate(section.items.all(), start=1):
        data.append(
            [
                str(idx),
                Paragraph(item.description, ParagraphStyle("ItemDesc", parent=getSampleStyleSheet()["Normal"], fontSize=10, fontName="Helvetica", leading=14)),
                item.remarks or "",
            ]
        )
        section_total += item.total_price
    
    table = Table(data, colWidths=[0.5 * inch, 4.5 * inch, 2.1 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table, section_total


def _company_or_default(company):
    if company:
        return company
    fallback = CompanyDetails()
    fallback.company_name = "Mynest.me Design Studio"
    fallback.legal_name = "JAYANTILAL CHAMPALAL SOLANKI"
    fallback.gst_number = "24DPUPS9833D1Z8"
    fallback.bank_name = "Kotak Bank"
    fallback.account_number = "3549713882"
    fallback.ifsc_code = "KKBK0002560"
    fallback.business_address = (
        "B-707, Infinity Tower, Corporate Road, "
        "Prahladnagar, Ahmedabad<br/>- 380015"
    )
    fallback.contact_number = "+91 76655 88577"
    fallback.email = "me.mynest@gmail.com"
    return fallback


def _brand_logos_table():
    logos = []
    for path in BRAND_LOGO_PATHS:
        if os.path.exists(path):
            try:
                logos.append(Image(path, width=1.5 * inch, height=0.7 * inch))
            except Exception:
                continue
    if not logos:
        return None

    while len(logos) < 9:
        logos.append("")
    rows = [logos[0:3], logos[3:6], logos[6:9]]
    table = Table(rows, colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch], rowHeights=[0.85 * inch] * 3)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.2, PDF_BORDER),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


class NumberedCanvas:
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas
        self._canvas = canvas.Canvas(*args, **kwargs)
        self._saved_page_states = []

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def showPage(self):
        self._saved_page_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self._canvas.__dict__.update(state)
            self.draw_page_number(page_count)
            self._canvas.showPage()
        self._canvas.save()

    def draw_page_number(self, page_count):
        self._canvas.setFont("Helvetica", 9)
        self._canvas.setFillColor(PDF_TEXT_SECONDARY)
        self._canvas.drawRightString(A4[0] - 30, 18, f"Page {self._canvas._pageNumber} of {page_count}")


def generate_quotation_pdf(quotation: Quotation) -> str:
    company = _company_or_default(CompanyDetails.objects.first())
    filename = f"dynamic_quotation_{quotation.id}.pdf"
    folder = os.path.join(settings.MEDIA_ROOT, "quotations")
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, filename)

    doc = SimpleDocTemplate(file_path, pagesize=A4, leftMargin=35, rightMargin=35, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Premium Styles
    title_style = ParagraphStyle("QTitle", parent=styles["Heading1"], alignment=1, fontSize=22, fontName="Helvetica-Bold", textColor=PDF_NAVY, spaceAfter=20)
    section_title_style = ParagraphStyle("QSection", parent=styles["Normal"], fontSize=14, fontName="Times-BoldItalic", textColor=PDF_NAVY, spaceBefore=15, spaceAfter=8)
    normal = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=10, fontName="Helvetica", leading=14)
    elements = []

    # 1. HEADER (3 Column Grid)
    logo_img = None
    if company.logo and os.path.exists(company.logo.path):
        try:
            logo_img = Image(company.logo.path, width=1.4 * inch, height=0.7 * inch)
            logo_img.hAlign = 'LEFT'
        except: pass
    elif os.path.exists(MAIN_COMPANY_LOGO_PATH):
        try:
            logo_img = Image(MAIN_COMPANY_LOGO_PATH, width=1.5 * inch, height=0.8 * inch)
            logo_img.hAlign = 'LEFT'
        except: pass
    
    address_str = company.business_address
    if "B-707" in address_str and "Infinity Tower" in address_str:
        address_str = "B-707, Infinity Tower, Corporate Road<br/>Prahladnagar, Ahmedabad - 380015"
        
    header_center = Paragraph(
        f"<font size=18 color='#1B1E3F'><b>{company.company_name}</b></font><br/>"
        f"<font size=9.5 color='#64748B'>{address_str}</font>",
        ParagraphStyle("HCenter", parent=normal, alignment=1, leading=14)
    )
    
    header_right = Paragraph(
        f"<b>Quotation No:</b> {quotation.quotation_number}<br/>"
        f"<b>Date:</b> {quotation.quotation_date.strftime('%d-%m-%Y')}",
        ParagraphStyle("HRight", parent=normal, alignment=2, leading=16)
    )
    
    header_table = Table([[logo_img or "", header_center, header_right]], colWidths=[1.4 * inch, 4.3 * inch, 1.4 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    elements.append(header_table)
    _gold_line(elements)
    elements.append(Spacer(1, 15))

    # 2. TITLE
    elements.append(Paragraph("<letterSpacing amount='1.5'>INTERIOR DESIGN QUOTATION</letterSpacing>", title_style))
    elements.append(Spacer(1, 10))

    # 3. CLIENT DETAILS
    elements.append(Paragraph("<i><b>CLIENT DETAILS</b></i>", section_title_style))
    detail_rows = [
        [Paragraph("<b>Quotation No</b>", normal), quotation.quotation_number],
        [Paragraph("<b>Date</b>", normal), quotation.quotation_date.strftime("%d-%m-%Y")],
        [Paragraph("<b>Client Name</b>", normal), quotation.client_name],
        [Paragraph("<b>Phone</b>", normal), quotation.client_phone or "-"],
        [Paragraph("<b>Email</b>", normal), quotation.client_email or "-"],
        [Paragraph("<b>Project Type</b>", normal), quotation.project_type or "-"],
        [Paragraph("<b>Location</b>", normal), quotation.project_location or "-"],
    ]
    detail_table = Table(detail_rows, colWidths=[2.0 * inch, 5.1 * inch])
    detail_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, PDF_BG_LIGHT]),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 25))

    # 4. ROOM SECTIONS
    for section in quotation.sections.all():
        if section.section_name.strip().lower() == "mynest includings":
            continue # Handled later
        if not section.items.exists():
            continue
        
        elements.append(Paragraph(section.section_name.upper(), section_title_style))
        table, section_total = _section_table(section)
        elements.append(table)
        elements.append(Spacer(1, 15))

    # 5. MYNEST INCLUSIONS
    elements.append(Paragraph("MYNEST INCLUSIONS", section_title_style))
    inclusion_data = [["No", "Inclusion Details"]]
    for idx, item in enumerate(MYNEST_INCLUSIONS, start=1):
        inclusion_data.append([str(idx), Paragraph(item, normal)])
    
    inclusion_table = Table(inclusion_data, colWidths=[0.5 * inch, 6.6 * inch])
    inclusion_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
    ]))
    elements.append(inclusion_table)
    elements.append(Spacer(1, 15))

    # 6. PAINT WORK
    elements.append(Paragraph("PAINT WORK", section_title_style))
    paint_data = [["Task", "Specifications"], ["Paint Work", "Asian Paint"]]
    paint_table = Table(paint_data, colWidths=[2.3 * inch, 4.8 * inch])
    paint_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
    ]))
    elements.append(paint_table)
    elements.append(Spacer(1, 15))

    # 7. MATERIAL SPECIFICATIONS
    elements.append(Paragraph("MATERIAL SPECIFICATIONS", section_title_style))
    spec_data = [["Material", "Specification", "Brand Type"]]
    for mat, spec, brand in MATERIAL_SPECIFICATIONS:
        spec_data.append([
            Paragraph(f"<b>{mat}</b>", normal), 
            Paragraph(spec, normal),
            Paragraph(brand, normal) if brand else ""
        ])
    spec_table = Table(spec_data, colWidths=[2.1 * inch, 3.2 * inch, 1.8 * inch], repeatRows=1)
    spec_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
        ("TEXTCOLOR", (2, 1), (2, -1), colors.darkblue),
        ("FONTNAME", (2, 1), (2, -1), "Times-Bold"),
    ]))
    elements.append(spec_table)
    elements.append(Spacer(1, 20))

    # 8. INTERIOR PACKAGE PRICING
    elements.append(Paragraph("INTERIOR PACKAGE PRICING", section_title_style))
    effective_base = quotation.base_amount if quotation.base_amount else Decimal("0.0")
    semi_amount = effective_base + (effective_base * Decimal("0.27"))
    full_amount = effective_base + (effective_base * Decimal("0.54"))
    selected_code = quotation.selected_package or "BASIC"
    
    package_rows = [
        ["LAMINATED (BASIC-ECO)", _money(effective_base), "Selected" if selected_code == "BASIC" else ""],
        ["DUCO/VENEER/LAMINATE (Semi-Luxury Interior)", _money(semi_amount), "Selected" if selected_code == "SEMI" else ""],
        ["PU-DUCO/VENEER/ACRYLIC/H.LAM (Full-Luxury Interior)", _money(full_amount), "Selected" if selected_code == "FULL" else ""],
    ]
    
    package_table = Table(package_rows, colWidths=[4.0 * inch, 1.8 * inch, 1.3 * inch])
    package_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, -1), PDF_BG_LIGHT),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
    ]))
    # Highlight selected package
    highlight_idx = 0 if selected_code == "BASIC" else (1 if selected_code == "SEMI" else 2)
    package_table.setStyle(TableStyle([
        ("BACKGROUND", (0, highlight_idx), (-1, highlight_idx), PDF_NAVY),
        ("TEXTCOLOR", (0, highlight_idx), (-1, highlight_idx), colors.white),
    ]))
    elements.append(package_table)
    elements.append(Spacer(1, 15))

    # 9. IN DETAIL
    elements.append(Paragraph("IN DETAIL", section_title_style))
    detail_data = [["Package", "Inclusions Description"]]
    for title, bullets in PACKAGE_DETAILS:
        bullet_text = "<br/>".join([f"&bull; {line}" for line in bullets])
        detail_data.append([Paragraph(f"<b>{title}</b>", normal), Paragraph(bullet_text, normal)])
    
    detail_package_table = Table(detail_data, colWidths=[2.3 * inch, 4.8 * inch], repeatRows=1)
    detail_package_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
    ]))
    elements.append(detail_package_table)
    elements.append(Spacer(1, 20))

    # 10. PAYMENT TERMS
    elements.append(Paragraph("PAYMENT TERMS", section_title_style))
    payment_rows = [["Stage", "%", "Amount", "Description"]]
    if quotation.payment_plans.exists():
        for p in quotation.payment_plans.all():
            payment_rows.append([p.payment_stage, f"{p.percentage}%", _money(p.amount), p.description or ""])
    else:
        # Fallback if no payment plan is saved
        total_project = quotation.package_amount if quotation.package_amount else Decimal("0.00")
        booking_amt = total_project * Decimal("0.09")
        phase1_amt = total_project * Decimal("0.56")
        phase2_raw = total_project * Decimal("0.35")
        
        # Deduct 50k from phase 2, ensuring no negative balance
        deductible = Decimal("50000.00")
        if phase2_raw < deductible:
            handover_amt = phase2_raw
            phase2_amt = Decimal("0.00")
        else:
            handover_amt = deductible
            phase2_amt = phase2_raw - deductible
            
        # Format labels
        phase2_label = "35%" if handover_amt == deductible else "35% (Bal)"
        
        payment_rows.extend([
            ["Booking Amount", "9%", _money(booking_amt), "Initial booking and design initiation"],
            ["Phase 1", "56%", _money(phase1_amt), "Civil, ceiling, electrical and base structures"],
            ["Phase 2", phase2_label, _money(phase2_amt), "Carpentry, shutters and final assembly"],
            ["Before 1 Week Of Handover", " ", _money(handover_amt), "Final finishing and handover closure"],
        ])
    
    payment_table = Table(payment_rows, colWidths=[1.8 * inch, 0.8 * inch, 1.5 * inch, 3.0 * inch], repeatRows=1)
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PDF_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-BoldItalic"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PDF_BG_LIGHT]),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 20))

    # 11. CONTACT DETAILS
    elements.append(Paragraph("CONTACT DETAILS", section_title_style))
    contact_data = [[Paragraph(f"<b>Phone:</b> {company.contact_number}  |  <b>Email:</b> {company.email}", normal)]]
    contact_table = Table(contact_data, colWidths=[7.1 * inch])
    contact_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, PDF_NAVY),
        ("BACKGROUND", (0, 0), (-1, -1), PDF_BG_LIGHT),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(contact_table)
    elements.append(Spacer(1, 15))

    # 12. ACCOUNT DETAILS
    elements.append(Paragraph("ACCOUNT DETAILS", section_title_style))
    bank_rows = [
        ["Account Name", company.company_name],
        ["Account Number", company.account_number],
        ["IFSC Code", company.ifsc_code],
        ["Bank Name", company.bank_name],
    ]
    bank_table = Table(bank_rows, colWidths=[1.8 * inch, 5.3 * inch])
    bank_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (0, -1), PDF_BG_LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(bank_table)
    elements.append(Spacer(1, 15))

    # 13. GST DETAILS
    elements.append(Paragraph("GST DETAILS", section_title_style))
    gst_rows = [
        ["GSTIN", company.gst_number],
        ["Trade Name", company.company_name],
        ["Legal Name", company.legal_name or "-"],
        ["Business Address", Paragraph(company.business_address, normal)],
    ]
    gst_table = Table(gst_rows, colWidths=[1.8 * inch, 5.3 * inch])
    gst_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER),
        ("BACKGROUND", (0, 0), (0, -1), PDF_BG_LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(gst_table)
    elements.append(Spacer(1, 20))

    # 14. NOT INCLUDED
    elements.append(Paragraph("NOT INCLUDED", section_title_style))
    for idx, line in enumerate(DEFAULT_NOT_INCLUDED, start=1):
        elements.append(Paragraph(f"{idx}. {line}", normal))
    elements.append(Spacer(1, 30))

    # 15. SIGNATURE SECTION
    sig_data = [
        [Paragraph("<b>Authorized Signatory</b>", normal), Paragraph("<b>Company Stamp</b>", normal)],
        ["", ""],
        ["________________________", "________________________"]
    ]
    sig_table = Table(sig_data, colWidths=[3.5 * inch, 3.5 * inch])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
    ]))
    elements.append(sig_table)

    # 16. FOOTER BRAND LOGOS
    elements.append(Spacer(1, 20))
    logos_table = _brand_logos_table()
    if logos_table:
        elements.append(logos_table)
    
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Thank you for trusting us with your dream space.", ParagraphStyle("Thanks", parent=normal, alignment=1, textColor=PDF_TEXT_SECONDARY)))

    doc.build(elements, canvasmaker=NumberedCanvas)
    return f"quotations/{filename}"
