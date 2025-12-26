"""
PDF Service - generates shopping list PDFs
Supports multiple PDF generation methods:
- reportlab (default, server-side)
- PDFMonkey (external API)
- Documint (external API)
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from typing import List, Dict, Optional
from datetime import date
import os
import httpx
from config import settings


class ShoppingListIngredient:
    def __init__(self, name: str, total_quantity: float, unit: str, category: str = "other"):
        self.name = name
        self.total_quantity = total_quantity
        self.unit = unit
        self.category = category
    
    def to_dict(self):
        return {
            "name": self.name,
            "total_quantity": self.total_quantity,
            "unit": self.unit,
            "category": self.category
        }


# Ingredient categorization
INGREDIENT_CATEGORIES = {
    "produce": ["apple", "banana", "orange", "lettuce", "tomato", "onion", "garlic", "carrot", "potato", 
                "broccoli", "spinach", "cucumber", "pepper", "celery", "mushroom", "avocado", "lemon", 
                "lime", "herbs", "basil", "parsley", "cilantro", "ginger"],
    "dairy": ["milk", "cheese", "butter", "yogurt", "cream", "sour cream", "cottage cheese", "mozzarella"],
    "meat": ["chicken", "beef", "pork", "turkey", "bacon", "sausage", "ground beef", "steak"],
    "seafood": ["fish", "salmon", "tuna", "shrimp", "crab", "lobster", "tilapia"],
    "pantry": ["flour", "sugar", "salt", "pepper", "oil", "vinegar", "soy sauce", "pasta", "rice", 
               "beans", "lentils", "quinoa", "oats", "bread", "cereal"],
    "spices": ["cumin", "paprika", "turmeric", "cinnamon", "nutmeg", "oregano", "thyme", "rosemary"],
    "beverages": ["water", "juice", "coffee", "tea", "wine", "beer"],
    "frozen": ["frozen vegetables", "frozen fruit", "ice cream"],
    "other": []
}


def categorize_ingredient(ingredient_name: str) -> str:
    """Categorize ingredient based on name"""
    name_lower = ingredient_name.lower()
    
    for category, keywords in INGREDIENT_CATEGORIES.items():
        if category == "other":
            continue
        for keyword in keywords:
            if keyword in name_lower:
                return category
    
    return "other"


def aggregate_ingredients(ingredients_list: List[Dict]) -> List[ShoppingListIngredient]:
    """
    Aggregate ingredients from multiple meals, combining duplicates
    Groups by category and sorts within categories
    
    Args:
        ingredients_list: List of lists of ingredient dictionaries, or flat list of ingredient dictionaries
    """
    aggregated = {}
    
    # Handle case where we get a flat list instead of list of lists
    if ingredients_list and isinstance(ingredients_list[0], dict):
        # It's a flat list of ingredient dicts, wrap it
        ingredients_list = [ingredients_list]
    
    for meal_ingredients in ingredients_list:
        # Handle string (JSON) input
        if isinstance(meal_ingredients, str):
            import json
            try:
                meal_ingredients = json.loads(meal_ingredients)
            except json.JSONDecodeError:
                continue
        
        # Ensure meal_ingredients is iterable
        if not isinstance(meal_ingredients, (list, tuple)):
            continue
        
        for ingredient in meal_ingredients:
            # Skip if ingredient is not a dictionary
            if not isinstance(ingredient, dict):
                continue
                
            try:
                name = ingredient.get("name", "").lower().strip()
                if not name:
                    continue
                    
                quantity = float(ingredient.get("quantity", 0))
                unit = ingredient.get("unit", "g")
                category = categorize_ingredient(name)
                
                # Create key for aggregation (name + unit)
                key = f"{name}_{unit}"
                
                if key in aggregated:
                    aggregated[key].total_quantity += quantity
                else:
                    aggregated[key] = ShoppingListIngredient(name, quantity, unit, category)
            except (ValueError, TypeError, AttributeError) as e:
                # Skip invalid ingredient entries
                print(f"[WARN] Skipping invalid ingredient: {ingredient}, error: {e}")
                continue
    
    # Sort by category, then alphabetically within category
    category_order = ["produce", "dairy", "meat", "seafood", "pantry", "spices", "beverages", "frozen", "other"]
    sorted_ingredients = []
    
    for category in category_order:
        category_items = [ing for ing in aggregated.values() if ing.category == category]
        category_items.sort(key=lambda x: x.name)
        sorted_ingredients.extend(category_items)
    
    return sorted_ingredients


def format_quantity(quantity: float, unit: str) -> str:
    """Format quantity for display"""
    if quantity >= 1000 and unit == "g":
        return f"{quantity/1000:.2f} kg"
    elif quantity >= 1000 and unit == "ml":
        return f"{quantity/1000:.2f} L"
    elif quantity == int(quantity):
        return f"{int(quantity)} {unit}"
    else:
        return f"{quantity:.2f} {unit}"


def generate_shopping_list_pdf(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str = "Customer",
    output_path: str = None,
    use_external_service: bool = False
) -> str:
    """
    Generate a PDF shopping list
    Returns the file path
    
    Args:
        ingredients: List of aggregated ingredients
        week_start: Start date of the week
        week_end: End date of the week
        user_name: Customer name
        output_path: Optional custom output path
        use_external_service: If True, use PDFMonkey/Documint instead of reportlab
    """
    # Check if external PDF service should be used
    pdf_method = getattr(settings, 'PDF_GENERATION_METHOD', 'reportlab').lower()
    
    if use_external_service or pdf_method in ['pdfmonkey', 'documint']:
        return generate_pdf_external(ingredients, week_start, week_end, user_name, output_path, pdf_method)
    
    # Use reportlab (default)
    return generate_pdf_reportlab(ingredients, week_start, week_end, user_name, output_path)


def generate_pdf_reportlab(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str,
    output_path: Optional[str] = None
) -> str:
    """Generate PDF using reportlab library"""
    # Ensure output directory exists
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    
    # Generate filename
    if not output_path:
        filename = f"shopping_list_{week_start}_{week_end}.pdf"
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
        fontSize=14,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    category_style = ParagraphStyle(
        'CategoryStyle',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#4CAF50'),
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        leftIndent=0.2*inch
    )
    
    normal_style = styles['Normal']
    
    # Header
    story.append(Paragraph("Weekly Shopping List", title_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Week range
    week_text = f"Week of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
    story.append(Paragraph(week_text, heading_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Group ingredients by category
    if ingredients:
        current_category = None
        category_ingredients = []
        
        for ingredient in ingredients:
            if ingredient.category != current_category:
                # Add previous category table if exists
                if category_ingredients and current_category:
                    story.append(Paragraph(
                        current_category.replace('_', ' ').title(), 
                        category_style
                    ))
                    
                    table_data = [["Ingredient", "Quantity"]]
                    for ing in category_ingredients:
                        formatted_qty = format_quantity(ing.total_quantity, ing.unit)
                        name = ing.name.capitalize()
                        table_data.append([name, formatted_qty])
                    
                    table = Table(table_data, colWidths=[4.5*inch, 1.5*inch])
                    table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F5E9')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                        ('TOPPADDING', (0, 0), (-1, 0), 10),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('TOPPADDING', (0, 1), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')]),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.15*inch))
                
                # Start new category
                current_category = ingredient.category
                category_ingredients = [ingredient]
            else:
                category_ingredients.append(ingredient)
        
        # Add last category
        if category_ingredients and current_category:
            story.append(Paragraph(
                current_category.replace('_', ' ').title(), 
                category_style
            ))
            
            table_data = [["Ingredient", "Quantity"]]
            for ing in category_ingredients:
                formatted_qty = format_quantity(ing.total_quantity, ing.unit)
                name = ing.name.capitalize()
                table_data.append([name, formatted_qty])
            
            table = Table(table_data, colWidths=[4.5*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ]))
            story.append(table)
    else:
        story.append(Paragraph("No ingredients found for this week.", normal_style))
    
    # Footer
    story.append(Spacer(1, 0.4*inch))
    footer_text = f"Generated for {user_name} on {date.today().strftime('%B %d, %Y')}"
    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=9,
        textColor=colors.HexColor('#999'),
        alignment=TA_CENTER
    )))
    
    # Build PDF
    doc.build(story)
    
    return output_path


def generate_pdf_external(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str,
    output_path: Optional[str] = None,
    service: str = 'pdfmonkey'
) -> str:
    """
    Generate PDF using external service (PDFMonkey or Documint)
    Falls back to reportlab if service fails
    """
    try:
        if service == 'pdfmonkey':
            return generate_pdf_pdfmonkey(ingredients, week_start, week_end, user_name, output_path)
        elif service == 'documint':
            return generate_pdf_documint(ingredients, week_start, week_end, user_name, output_path)
    except Exception as e:
        print(f"External PDF service failed: {e}, falling back to reportlab")
        return generate_pdf_reportlab(ingredients, week_start, week_end, user_name, output_path)


def generate_pdf_pdfmonkey(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str,
    output_path: Optional[str] = None
) -> str:
    """Generate PDF using PDFMonkey API"""
    api_key = getattr(settings, 'PDFMONKEY_API_KEY', None)
    if not api_key:
        raise ValueError("PDFMonkey API key not configured")
    
    # Prepare HTML content
    html_content = generate_shopping_list_html(ingredients, week_start, week_end, user_name)
    
    # Call PDFMonkey API
    url = "https://api.pdfmonkey.io/api/v1/documents"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "document": {
            "document_template_id": getattr(settings, 'PDFMONKEY_TEMPLATE_ID', None),
            "payload": {
                "html": html_content
            }
        }
    }
    
    async def make_request():
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                doc_data = response.json()
                # Download the PDF
                pdf_url = doc_data.get("document", {}).get("download_url")
                if pdf_url:
                    pdf_response = await client.get(pdf_url)
                    # Save to file
                    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
                    if not output_path:
                        filename = f"shopping_list_{week_start}_{week_end}.pdf"
                        output_path = os.path.join(settings.PDF_STORAGE_PATH, filename)
                    with open(output_path, 'wb') as f:
                        f.write(pdf_response.content)
                    return output_path
            raise Exception(f"PDFMonkey API error: {response.text}")
    
    # Note: This is async but we're calling it from sync context
    # In production, make the calling function async
    import asyncio
    return asyncio.run(make_request())


def generate_pdf_documint(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str,
    output_path: Optional[str] = None
) -> str:
    """Generate PDF using Documint API"""
    api_key = getattr(settings, 'DOCUMINT_API_KEY', None)
    if not api_key:
        raise ValueError("Documint API key not configured")
    
    # Similar implementation to PDFMonkey
    # Documint API implementation would go here
    raise NotImplementedError("Documint integration not yet implemented")


def generate_shopping_list_html(
    ingredients: List[ShoppingListIngredient],
    week_start: date,
    week_end: date,
    user_name: str
) -> str:
    """Generate HTML content for external PDF services"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; }}
            h1 {{ color: #2c3e50; text-align: center; }}
            h2 {{ color: #34495e; }}
            h3 {{ color: #667eea; margin-top: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th {{ background: #f8f9fa; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #e0e0e0; }}
            tr:nth-child(even) {{ background: #fafafa; }}
            .footer {{ text-align: center; color: #999; margin-top: 40px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <h1>Weekly Shopping List</h1>
        <h2>Week of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}</h2>
    """
    
    # Group by category
    current_category = None
    for ingredient in ingredients:
        if ingredient.category != current_category:
            if current_category is not None:
                html += "</table>"
            current_category = ingredient.category
            html += f'<h3>{current_category.replace("_", " ").title()}</h3>'
            html += '<table><tr><th>Ingredient</th><th>Quantity</th></tr>'
        
        formatted_qty = format_quantity(ingredient.total_quantity, ingredient.unit)
        html += f'<tr><td>{ingredient.name.capitalize()}</td><td>{formatted_qty}</td></tr>'
    
    if current_category:
        html += "</table>"
    
    html += f"""
        <div class="footer">
            Generated for {user_name} on {date.today().strftime('%B %d, %Y')}
        </div>
    </body>
    </html>
    """
    
    return html


def get_pdf_url(file_path: str) -> str:
    """Generate public URL for PDF file"""
    filename = os.path.basename(file_path)
    return f"{settings.PDF_BASE_URL}/{filename}"

