import io
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from app.database.models import CarListing

class PdfExportService:
    @staticmethod
    def generate_car_report(car: CarListing, price_metrics: dict, days_online: int) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm
        )

        styles = getSampleStyleSheet()
        
        style_title = ParagraphStyle(
            'HeaderTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=18,
            textColor=colors.HexColor('#0f172a')
        )
        style_subtitle = ParagraphStyle(
            'HeaderSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#64748b')
        )
        style_score = ParagraphStyle(
            'ScoreText',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#047857') if car.deal_score >= 88 else colors.HexColor('#1d4ed8')
        )
        style_score_label = ParagraphStyle(
            'ScoreLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#475569')
        )
        style_sec_header = ParagraphStyle(
            'SectionHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#1e293b')
        )
        style_body = ParagraphStyle(
            'BodySmall',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#334155')
        )
        style_bold = ParagraphStyle(
            'BodySmallBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#0f172a')
        )
        style_pro = ParagraphStyle(
            'ProItem',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#065f46')
        )
        style_con = ParagraphStyle(
            'ConItem',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#991b1b')
        )

        elements = []

        # -------------------------------------------------------------
        # 1. HEADER-BLOCK (Titel links + Deal-Score rechts)
        # -------------------------------------------------------------
        title_text = f"<b>{car.make} {car.model}</b> &bull; {car.title}"
        sub_text = (
            f"Standort: {car.postal_code} {car.city} (~{round(car.distance_km, 1)} km von 97271 Kleinrinderfeld) | "
            f"Händler: {car.dealer_name or 'Händler'} | Quelle: {car.provider}"
        )
        left_header = [
            Paragraph("AUTO-AGENT &bull; KAUFBERATER-REPORT", ParagraphStyle('Pre', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#2563eb'))),
            Spacer(1, 2 * mm),
            Paragraph(title_text, style_title),
            Spacer(1, 1.5 * mm),
            Paragraph(sub_text, style_subtitle)
        ]

        score_box_data = [
            [Paragraph(f"{car.deal_score} <font size=9>/ 100</font>", style_score)],
            [Paragraph("DEAL-SCORE", style_score_label)],
            [Paragraph(f"<b>{int(car.price):,} €</b>".replace(",", "."), ParagraphStyle('Price', alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0f172a')))]
        ]
        score_table = Table(score_box_data, colWidths=[38 * mm])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        header_table = Table([[left_header, score_table]], colWidths=[142 * mm, 40 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 2.5 * mm))

        # -------------------------------------------------------------
        # 2. FAHRZEUGDATEN & TEIL-SCORES TABELLE (inkl. Verbrauch & Farbe)
        # -------------------------------------------------------------
        elements.append(Paragraph("Fahrzeug-Eckdaten &amp; Teil-Scores (8 Kriterien)", style_sec_header))
        elements.append(Spacer(1, 1.5 * mm))

        subs = car.sub_scores or {}
        specs_data = [
            [
                Paragraph("<b>Preis:</b>", style_bold), Paragraph(f"{int(car.price):,} €".replace(",", "."), style_body),
                Paragraph("<b>Marktpreis-Score (22%):</b>", style_bold), Paragraph(f"{subs.get('market_price', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Laufleistung:</b>", style_bold), Paragraph(f"{car.mileage:,} km".replace(",", "."), style_body),
                Paragraph("<b>Ausstattungs-Score (23%):</b>", style_bold), Paragraph(f"{subs.get('features', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Erstzulassung:</b>", style_bold), Paragraph(f"{car.first_registration_year}", style_body),
                Paragraph("<b>Laufleistungs-Score (15%):</b>", style_bold), Paragraph(f"{subs.get('mileage', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Leistung:</b>", style_bold), Paragraph(f"{car.power_hp} PS ({car.transmission})", style_body),
                Paragraph("<b>Verbrauchs-Score (10%):</b>", style_bold), Paragraph(f"{subs.get('consumption', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Kraftstoff:</b>", style_bold), Paragraph(f"{car.fuel_type} (rein Benzin)", style_body),
                Paragraph("<b>Alters-Score (8%):</b>", style_bold), Paragraph(f"{subs.get('age', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Entfernung:</b>", style_bold), Paragraph(f"{round(car.distance_km, 1)} km ({car.city})", style_body),
                Paragraph("<b>Leistungs-Score (7%):</b>", style_bold), Paragraph(f"{subs.get('power', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Lackierung:</b>", style_bold), Paragraph("Blau / Rot bevorzugt", style_body),
                Paragraph("<b>Farb-Präferenz (5%):</b>", style_bold), Paragraph(f"{subs.get('color_preference', 0)} / 100", style_body)
            ],
            [
                Paragraph("<b>Verkäufer:</b>", style_bold), Paragraph(f"{car.dealer_name or 'Autohaus'}", style_body),
                Paragraph("<b>Distanz-Score (5%):</b>", style_bold), Paragraph(f"{subs.get('distance', 0)} / 100", style_body)
            ]
        ]
        specs_table = Table(specs_data, colWidths=[30 * mm, 55 * mm, 50 * mm, 47 * mm])
        specs_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.0),
        ]))
        elements.append(specs_table)
        elements.append(Spacer(1, 3 * mm))

        # -------------------------------------------------------------
        # 3. MARKTVERGLEICH & PREISENTWICKLUNG
        # -------------------------------------------------------------
        elements.append(Paragraph("Marktvergleich &amp; Beobachtung", style_sec_header))
        elements.append(Spacer(1, 1.5 * mm))

        m = car.market_stats or {}
        med_diff = m.get('diff_to_median', 0)
        med_str = f"-{abs(int(med_diff)):,} €" if med_diff < 0 else f"+{int(med_diff):,} €"
        
        market_data = [
            [
                Paragraph("<b>Vergleichsfahrzeuge:</b>", style_bold), Paragraph(str(m.get('peer_count', 0)), style_body),
                Paragraph("<b>Erstmals gesehen:</b>", style_bold), Paragraph(str(car.first_seen)[:10], style_body)
            ],
            [
                Paragraph("<b>Marktmedian:</b>", style_bold), Paragraph(f"{int(m.get('median_price', car.price)):,} €".replace(",", "."), style_body),
                Paragraph("<b>Standzeit:</b>", style_bold), Paragraph(f"Seit {days_online} Tagen online", style_body)
            ],
            [
                Paragraph("<b>Differenz zum Median:</b>", style_bold), Paragraph(f"{med_str.replace(',', '.')} ({m.get('diff_percent', 0)}%)", style_body),
                Paragraph("<b>Preishistorie:</b>", style_bold), Paragraph(price_metrics.get("summary", "Keine Historie"), style_body)
            ]
        ]
        market_table = Table(market_data, colWidths=[42 * mm, 45 * mm, 38 * mm, 57 * mm])
        market_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.0),
        ]))
        elements.append(market_table)
        elements.append(Spacer(1, 3 * mm))

        # -------------------------------------------------------------
        # 4. VORTEILE & NACHTEILE (2-SPALTIG)
        # -------------------------------------------------------------
        pros_content = [Paragraph("<b>VORTEILE (+)</b>", ParagraphStyle('ProHead', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor('#047857')))]
        for p in (car.pros or ["Gute Grundausstattung"]):
            pros_content.append(Paragraph(f"+ {p}", style_pro))

        cons_content = [Paragraph("<b>NACHTEILE (-)</b>", ParagraphStyle('ConHead', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor('#b91c1c')))]
        for c in (car.cons or ["Keine gravierenden Nachteile"]):
            cons_content.append(Paragraph(f"- {c}", style_con))

        pros_cons_table = Table([[pros_content, cons_content]], colWidths=[90 * mm, 92 * mm])
        pros_cons_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#ecfdf5')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#fef2f2')),
            ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor('#a7f3d0')),
            ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#fecaca')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(pros_cons_table)
        elements.append(Spacer(1, 3 * mm))

        # -------------------------------------------------------------
        # 5. AUSSTATTUNGEN & LINK
        # -------------------------------------------------------------
        feat_str = " &bull; ".join(car.features) if car.features else "Keine Ausstattungsmerkmale hinterlegt"
        elements.append(Paragraph("Dokumentierte Ausstattung", style_sec_header))
        elements.append(Spacer(1, 1 * mm))
        elements.append(Paragraph(feat_str, style_body))
        elements.append(Spacer(1, 2.5 * mm))

        elements.append(Paragraph(
            f"Report generiert am {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')} &bull; "
            f"Original-Link: <font color='#2563eb'><u>{car.url}</u></font>",
            style_subtitle
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_comparison_report(car1: CarListing, car2: CarListing, comparison: dict) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),  # 297 x 210 mm
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm
        )

        styles = getSampleStyleSheet()

        style_title = ParagraphStyle(
            'CompTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=17,
            textColor=colors.HexColor('#0f172a')
        )
        style_col_head1 = ParagraphStyle(
            'ColHead1',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor('#1d4ed8')
        )
        style_col_head2 = ParagraphStyle(
            'ColHead2',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor('#4338ca')
        )
        style_crit = ParagraphStyle(
            'CritText',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#334155')
        )
        style_val = ParagraphStyle(
            'ValText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#0f172a')
        )
        style_val_win = ParagraphStyle(
            'ValTextWin',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#047857')
        )
        style_win_item = ParagraphStyle(
            'WinItem',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#065f46')
        )

        elements = []

        # -------------------------------------------------------------
        # 1. HEADER-BEREICH
        # -------------------------------------------------------------
        header_data = [
            [
                Paragraph("AUTO-AGENT &bull; DIREKTVERGLEICH", ParagraphStyle('PreH', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#2563eb'))),
                Paragraph(f"Standort: 97271 Kleinrinderfeld (100 km Radius) &bull; Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ParagraphStyle('RightSub', fontName='Helvetica', fontSize=7.5, alignment=TA_RIGHT, textColor=colors.HexColor('#64748b')))
            ],
            [
                Paragraph(f"<b>{car1.make} {car1.model}</b> <font color='#64748b'>vs.</font> <b>{car2.make} {car2.model}</b>", style_title),
                ""
            ]
        ]
        head_table = Table(header_data, colWidths=[170 * mm, 99 * mm])
        head_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(head_table)
        elements.append(Spacer(1, 3 * mm))

        # -------------------------------------------------------------
        # 2. DETAIL-VERGLEICHSTABELLE (inkl. Verbrauch & Farbe)
        # -------------------------------------------------------------
        c1_m = car1.market_stats or {}
        c2_m = car2.market_stats or {}
        c1_diff = c1_m.get('diff_to_median', 0)
        c2_diff = c2_m.get('diff_to_median', 0)

        c1_diff_str = f"{abs(int(c1_diff)):,} € günstiger".replace(",", ".") if c1_diff < 0 else f"+{int(c1_diff):,} € vs. Median".replace(",", ".")
        c2_diff_str = f"{abs(int(c2_diff)):,} € günstiger".replace(",", ".") if c2_diff < 0 else f"+{int(c2_diff):,} € vs. Median".replace(",", ".")

        c1_sub = car1.sub_scores or {}
        c2_sub = car2.sub_scores or {}

        rows = [
            [
                Paragraph("<b>Kriterium</b>", style_crit),
                Paragraph(f"<b>{car1.make} {car1.model}</b><br/><font size=6.5 color='#64748b'>{car1.title[:45]}...</font>", style_col_head1),
                Paragraph(f"<b>{car2.make} {car2.model}</b><br/><font size=6.5 color='#64748b'>{car2.title[:45]}...</font>", style_col_head2)
            ],
            [
                Paragraph("Deal-Score (0 - 100)", style_crit),
                Paragraph(f"<b>{car1.deal_score} / 100</b>", style_val_win if car1.deal_score >= car2.deal_score else style_val),
                Paragraph(f"<b>{car2.deal_score} / 100</b>", style_val_win if car2.deal_score >= car1.deal_score else style_val)
            ],
            [
                Paragraph("Kaufpreis", style_crit),
                Paragraph(f"<b>{int(car1.price):,} €</b>".replace(",", "."), style_val_win if car1.price <= car2.price else style_val),
                Paragraph(f"<b>{int(car2.price):,} €</b>".replace(",", "."), style_val_win if car2.price <= car1.price else style_val)
            ],
            [
                Paragraph("Marktpreis-Abweichung (22%)", style_crit),
                Paragraph(f"{c1_diff_str} (Score: {c1_sub.get('market_price', 0)})", style_val_win if c1_diff <= c2_diff else style_val),
                Paragraph(f"{c2_diff_str} (Score: {c2_sub.get('market_price', 0)})", style_val_win if c2_diff <= c1_diff else style_val)
            ],
            [
                Paragraph("Ausstattungs-Score (23%)", style_crit),
                Paragraph(f"{c1_sub.get('features', 0)} / 100 ({len(car1.features)} Merkmale)", style_val_win if c1_sub.get('features', 0) >= c2_sub.get('features', 0) else style_val),
                Paragraph(f"{c2_sub.get('features', 0)} / 100 ({len(car2.features)} Merkmale)", style_val_win if c2_sub.get('features', 0) >= c1_sub.get('features', 0) else style_val)
            ],
            [
                Paragraph("Laufleistung (15%)", style_crit),
                Paragraph(f"{car1.mileage:,} km (Score: {c1_sub.get('mileage', 0)})".replace(",", "."), style_val_win if car1.mileage <= car2.mileage else style_val),
                Paragraph(f"{car2.mileage:,} km (Score: {c2_sub.get('mileage', 0)})".replace(",", "."), style_val_win if car2.mileage <= car1.mileage else style_val)
            ],
            [
                Paragraph("Spritverbrauchs-Score (10%)", style_crit),
                Paragraph(f"Score: {c1_sub.get('consumption', 0)} / 100", style_val_win if c1_sub.get('consumption', 0) >= c2_sub.get('consumption', 0) else style_val),
                Paragraph(f"Score: {c2_sub.get('consumption', 0)} / 100", style_val_win if c2_sub.get('consumption', 0) >= c1_sub.get('consumption', 0) else style_val)
            ],
            [
                Paragraph("Leistung &amp; Getriebe (7%)", style_crit),
                Paragraph(f"{car1.power_hp} PS ({car1.transmission})", style_val_win if car1.power_hp >= car2.power_hp else style_val),
                Paragraph(f"{car2.power_hp} PS ({car2.transmission})", style_val_win if car2.power_hp >= car1.power_hp else style_val)
            ],
            [
                Paragraph("Farbbewertungs-Score (5%)", style_crit),
                Paragraph(f"Score: {c1_sub.get('color_preference', 0)} / 100 (Blau/Rot Präferenz)", style_val_win if c1_sub.get('color_preference', 0) >= c2_sub.get('color_preference', 0) else style_val),
                Paragraph(f"Score: {c2_sub.get('color_preference', 0)} / 100 (Blau/Rot Präferenz)", style_val_win if c2_sub.get('color_preference', 0) >= c1_sub.get('color_preference', 0) else style_val)
            ],
            [
                Paragraph("Erstzulassung &amp; Alter (8%)", style_crit),
                Paragraph(f"EZ {car1.first_registration_year} (Score: {c1_sub.get('age', 0)})", style_val_win if car1.first_registration_year >= car2.first_registration_year else style_val),
                Paragraph(f"EZ {car2.first_registration_year} (Score: {c2_sub.get('age', 0)})", style_val_win if car2.first_registration_year >= car1.first_registration_year else style_val)
            ],
            [
                Paragraph("Entfernung (5%)", style_crit),
                Paragraph(f"{round(car1.distance_km, 1)} km ({car1.city})", style_val_win if car1.distance_km <= car2.distance_km else style_val),
                Paragraph(f"{round(car2.distance_km, 1)} km ({car2.city})", style_val_win if car2.distance_km <= car1.distance_km else style_val)
            ],
            [
                Paragraph("Plattform &amp; Inserat-ID", style_crit),
                Paragraph(f"{car1.provider} (ID: {car1.external_id})", style_val),
                Paragraph(f"{car2.provider} (ID: {car2.external_id})", style_val)
            ]
        ]

        matrix_table = Table(rows, colWidths=[65 * mm, 102 * mm, 102 * mm])
        matrix_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(matrix_table)
        elements.append(Spacer(1, 3 * mm))

        # -------------------------------------------------------------
        # 3. KATEGORIESIEGE (2-SPALTIG)
        # -------------------------------------------------------------
        c1_wins_content = [Paragraph(f"<b>{car1.make} {car1.model} punktet bei:</b>", ParagraphStyle('W1Head', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#1d4ed8')))]
        for w in (comparison.get("wins_car1") or ["Keine klaren Kategoriesiege"]):
            c1_wins_content.append(Paragraph(f"&bull; {w}", style_win_item))

        c2_wins_content = [Paragraph(f"<b>{car2.make} {car2.model} punktet bei:</b>", ParagraphStyle('W2Head', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#4338ca')))]
        for w in (comparison.get("wins_car2") or ["Keine klaren Kategoriesiege"]):
            c2_wins_content.append(Paragraph(f"&bull; {w}", style_win_item))

        wins_table = Table([[c1_wins_content, c2_wins_content]], colWidths=[133 * mm, 136 * mm])
        wins_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#eff6ff')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#eef2ff')),
            ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor('#bfdbfe')),
            ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#c7d2fe')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(wins_table)
        elements.append(Spacer(1, 2.5 * mm))

        # -------------------------------------------------------------
        # 4. KAUFBERATER-GESAMTFAZIT
        # -------------------------------------------------------------
        winner = comparison.get("overall_winner", car1)
        fazit_text = (
            f"<b>Kaufberater-Fazit:</b> Unter Einbeziehung aller 8 gewichteten Kriterien (Marktwert, Ausstattung, Verbrauch, "
            f"Laufleistung, Alter, Leistung, Lackierungspräferenz und Distanz) erzielt der <b>{winner.make} {winner.model}</b> mit einem Gesamt-Deal-Score von "
            f"<b>{winner.deal_score} / 100</b> das wirtschaftlich und qualitativ überlegene Gesamtpaket gegenüber dem Mitbewerber."
        )
        fazit_table = Table([[Paragraph(fazit_text, ParagraphStyle('Fazit', fontName='Helvetica', fontSize=7.5, leading=10.5, textColor=colors.HexColor('#0f172a')))]], colWidths=[269 * mm])
        fazit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(fazit_table)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()