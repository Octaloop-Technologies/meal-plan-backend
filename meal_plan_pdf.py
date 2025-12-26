"""
Meal Plan PDF Service - generates PDFs for daily and weekly meal plans
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from typing import List, Dict, Optional
from datetime import date
import os
from config import settings
from database import Meal


def generate_meal_plan_pdf(
    daily_plans: List[Dict],
    plan_type: str = 'today',  # 'today' or 'week'
    user_name: str = "Customer",
    output_path: Optional[str] = None
) -> str:
    """
    Generate a PDF for meal plan (today or weekly)
    
    Args:
        daily_plans: List of daily meal plan dictionaries
        plan_type: 'today' or 'week'
        user_name: Customer name
        output_path: Optional custom output path
    """
    # Ensure output directory exists
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    
    # Generate filename
    if not output_path:
        date_str = daily_plans[0]['plan_date'] if daily_plans else date.today().isoformat()
        filename = f"meal_plan_{plan_type}_{date_str}.pdf"
        output_path = os.path.join(settings.PDF_STORAGE_PATH, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(output_path, pagesize=letter, 
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    meal_title_style = ParagraphStyle(
        'MealTitle',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#4CAF50'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    
    # Header
    title_text = "Today's Meal Plan" if plan_type == 'today' else "Weekly Meal Plan"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.1*inch))
    
    # User name
    story.append(Paragraph(f"Prepared for: {user_name}", heading_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Process each day
    for day_plan in daily_plans:
        plan_date = day_plan.get('plan_date', '')
        if isinstance(plan_date, str):
            try:
                date_obj = date.fromisoformat(plan_date)
                date_str = date_obj.strftime('%A, %B %d, %Y')
            except:
                date_str = plan_date
        else:
            date_str = plan_date.strftime('%A, %B %d, %Y') if hasattr(plan_date, 'strftime') else str(plan_date)
        
        # Day header
        story.append(Paragraph(date_str, heading_style))
        
        # Daily totals
        if day_plan.get('total_calories'):
            totals_data = [
                ['Calories', 'Protein', 'Carbs', 'Fat'],
                [
                    f"{day_plan.get('total_calories', 0)}",
                    f"{day_plan.get('total_protein_g', 0):.0f}g",
                    f"{day_plan.get('total_carbs_g', 0):.0f}g",
                    f"{day_plan.get('total_fat_g', 0):.0f}g"
                ]
            ]
            totals_table = Table(totals_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            totals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8F5E9')),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#2E7D32')),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 12),
                ('TOPPADDING', (0, 1), (-1, 1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#C8E6C9')),
            ]))
            story.append(totals_table)
            story.append(Spacer(1, 0.15*inch))
        
        # Meals
        meals = [
            ('breakfast_meal', '🍳 Breakfast'),
            ('lunch_meal', '🍽️ Lunch'),
            ('dinner_meal', '🍲 Dinner'),
            ('snack_meal', '🍎 Snack'),
        ]
        
        for meal_key, meal_label in meals:
            meal = day_plan.get(meal_key)
            if meal:
                story.append(Paragraph(meal_label, meal_title_style))
                story.append(Paragraph(meal.get('title', 'N/A'), normal_style))
                
                # Meal macros
                if meal.get('calories'):
                    macro_text = f"Calories: {meal.get('calories')} | Protein: {meal.get('protein_g', 0):.0f}g | Carbs: {meal.get('carbs_g', 0):.0f}g | Fat: {meal.get('fat_g', 0):.0f}g"
                    story.append(Paragraph(macro_text, normal_style))
                
                # Description
                if meal.get('description'):
                    desc_style = ParagraphStyle(
                        'Description',
                        parent=normal_style,
                        fontSize=9,
                        textColor=colors.HexColor('#666'),
                        leftIndent=0.2*inch,
                    )
                    story.append(Paragraph(meal.get('description'), desc_style))
                
                story.append(Spacer(1, 0.1*inch))
        
        # Add page break for weekly plans (except last day)
        if plan_type == 'week' and daily_plans.index(day_plan) < len(daily_plans) - 1:
            story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    return output_path

