#!/usr/bin/env python3
"""
Pokemon Card Duplicate Checker
Extracts card data from TCG Collector and Cardmarket HTML files
"""

import re
import html
import requests
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

def extract_set_info_from_tcg_collector(html_content):
    """Extract set name and code from TCG Collector HTML"""
    # Primary pattern: Adjacent span elements with specific IDs
    pattern = r'<span id="card-search-result-title-set-like-name">([^<]+)</span><span id="card-search-result-title-set-code">([^<]+)</span>'
    match = re.search(pattern, html_content, re.IGNORECASE)

    if match:
        set_name = html.unescape(match.group(1).strip())
        set_code = html.unescape(match.group(2).strip())
        return set_name, set_code

    # Fallback: Extract from page title
    title_pattern = r'<title>([^<]+) card list \(International TCG\) – TCG Collector</title>'
    title_match = re.search(title_pattern, html_content, re.IGNORECASE)
    if title_match:
        set_name = html.unescape(title_match.group(1).strip())
        return set_name, None

    return None, None

def fetch_card_image_url(card_id):
    """Fetch the image URL for a specific card ID from TCG Collector"""
    try:
        # Construct the card detail page URL (we don't need the slug, just the ID works)
        url = f"https://www.tcgcollector.com/cards/{card_id}/"

        # Add a small delay to be respectful to the server
        time.sleep(0.1)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Look for the main card image URL in the HTML content - handle multiple formats
            image_pattern = r'https://static\.tcgcollector\.com/content/images/[a-f0-9/]+\.(jpg|webp|png)'
            image_match = re.search(image_pattern, response.text)
            if image_match:
                return image_match.group(0)
    except Exception as e:
        print(f"Error fetching image for card {card_id}: {e}")

    return None

def extract_tcg_collector_cards(html_content):
    """Extract card data from TCG Collector HTML"""
    cards = []

    # Extract set information dynamically from the HTML
    dynamic_set_name, dynamic_set_code = extract_set_info_from_tcg_collector(html_content)

    # Look for card name patterns to find individual cards
    # Each card has a unique structure we can target
    name_pattern = r'<a[^>]*href="[^"]*cards/[^"]*"[^>]*title="([^"]*\([^)]*\))"[^>]*class="[^"]*card-list-item-entry-text[^"]*"[^>]*>\s*([^<]+)\s*</a>'
    name_matches = re.findall(name_pattern, html_content, re.IGNORECASE)
    
    for title, name in name_matches:
        card = {
            'name': html.unescape(name.strip()),
            'source': 'tcg_collector'
        }
        
        # Use dynamically extracted set information as the primary source
        if dynamic_set_name:
            card['set_name'] = dynamic_set_name
        if dynamic_set_code:
            card['set_code'] = dynamic_set_code

        # Extract card number and set info from title
        # Title format: "Bulbasaur (Scarlet & Violet 151 001/165)" or "Basic Grass Energy (Scarlet & Violet Energies 001)"
        title_match = re.search(r'\(([^)]+)\s+(\d+(?:/\d+)?)\)', title)
        if title_match:
            # Only use title set name if we don't have dynamic set name
            if not dynamic_set_name:
                card['set_name'] = html.unescape(title_match.group(1).strip())
            full_number = title_match.group(2)
            # Store both the normalized number (for matching) and total count (for display)
            if '/' in full_number:
                card['number'] = full_number.split('/')[0]
                card['total_count'] = full_number.split('/')[1]
            else:
                # For cards with just individual numbers, store the number and try to find total later
                card['number'] = full_number
                card['total_count'] = None  # Will be set later if found
        
        # Look for set code near this card (fallback if dynamic extraction didn't work)
        if not dynamic_set_code:
            card_context_pattern = rf'<a[^>]*>{re.escape(name)}</a>.*?<span[^>]*card-list-item-expansion-code[^>]*>\s*([^<]+)\s*</span>'
            code_match = re.search(card_context_pattern, html_content, re.DOTALL | re.IGNORECASE)
            if code_match:
                card['set_code'] = html.unescape(code_match.group(1).strip())
            else:
                # Try a broader search for set code without requiring specific proximity to card name
                general_code_pattern = r'<span[^>]*card-list-item-expansion-code[^>]*>\s*([^<]+)\s*</span>'
                all_codes = re.findall(general_code_pattern, html_content, re.IGNORECASE)
                if all_codes:
                    # Use the most common set code found in the file
                    from collections import Counter
                    most_common_code = Counter(all_codes).most_common(1)[0][0].strip()
                    card['set_code'] = html.unescape(most_common_code)
        
        # Look for collection indicators near this card
        # Try to find data-card-id for this specific card using both name and number for uniqueness
        if card.get('number'):
            # First try: match using title attribute which should contain the full card info
            title_pattern = rf'data-card-id="(\d+)"[^>]*title="[^"]*{re.escape(name)}[^"]*{re.escape(card["number"])}[^"]*"'
            card_id_match = re.search(title_pattern, html_content, re.IGNORECASE)
            
            # Second try: look in broader context around the specific card number
            if not card_id_match:
                total_fallback = card.get("total_count")
                if total_fallback:
                    number_context_pattern = rf'{re.escape(card["number"])}/{re.escape(total_fallback)}.*?data-card-id="(\d+)"'
                else:
                    # For cards without total count, just match the card number alone
                    number_context_pattern = rf'{re.escape(card["number"])}.*?data-card-id="(\d+)"'
                context_match = re.search(number_context_pattern, html_content, re.IGNORECASE | re.DOTALL)
                if context_match:
                    card_id_match = context_match
        else:
            # Fallback to original method if no number available
            card_id_pattern = rf'data-card-id="(\d+)"[^>]*data-full-card-name-without-tcg-region="[^"]*{re.escape(name)}[^"]*"'
            card_id_match = re.search(card_id_pattern, html_content, re.IGNORECASE)
        
        has_regular = False
        has_reverse = False
        variants = []  # Initialize variants list before any conditional logic

        if card_id_match:
            card_id = card_id_match.group(1)
            card['card_id'] = card_id  # Store card ID for image fetching
            # Look for indicators for this specific card
            indicator_pattern = rf'data-card-id="{card_id}".*?card-collection-card-controls-indicators.*?</button>'
            indicator_match = re.search(indicator_pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            if indicator_match:
                indicator_html = indicator_match.group(0)
                
                # Find all indicator spans and determine what variants exist and their status
                all_spans = re.findall(r'<span[^>]*class="([^"]*card-collection-card-indicator[^"]*)"[^>]*>', indicator_html, re.IGNORECASE)
                
                # Check for standard/normal variant
                for class_attr in all_spans:
                    if 'card-collection-card-indicator-standard-set' in class_attr:
                        has_dot = 'card-collection-card-indicator-with-dot' in class_attr
                        is_active = 'active' in class_attr
                        # Include if has dot OR is active (meaning variant exists)
                        if has_dot or is_active:
                            variants.append({
                                'type': 'Normal',
                                'has_card': is_active
                            })
                        break
                
                # Check for parallel/reverse holo variant  
                for class_attr in all_spans:
                    if 'card-collection-card-indicator-parallel-set' in class_attr:
                        has_dot = 'card-collection-card-indicator-with-dot' in class_attr
                        is_active = 'active' in class_attr
                        # Always include parallel variant if the span exists (variant exists in set)
                        variants.append({
                            'type': 'Reverse Holo',
                            'has_card': is_active
                        })
                        break
                
                # Check for other variants (we'll ignore these for now but detect them)
                for class_attr in all_spans:
                    if 'card-collection-card-indicator-other-variants' in class_attr:
                        has_dot = 'card-collection-card-indicator-with-dot' in class_attr
                        is_active = 'active' in class_attr
                        if has_dot:  # Other variants exist but we'll skip them
                            pass  # Could add special variants here if needed
                        break
                
                # If no variants detected, assume normal exists
                if not variants:
                    variants.append({
                        'type': 'Normal', 
                        'has_card': False
                    })
        
        # Create a card entry for each variant
        for variant in variants:
            variant_card = card.copy()
            variant_card['variant_type'] = variant['type']
            variant_card['has_card'] = variant['has_card']
            # Remove old boolean fields
            variant_card.pop('has_regular', None)
            variant_card.pop('has_reverse', None)
            
            
            cards.append(variant_card)
        
        
    
    return cards

def extract_cardmarket_cards(html_content):
    """Extract card data from Cardmarket HTML"""
    cards = []
    
    # Look for the specific pattern in Cardmarket table cells:
    # <td class="name text-start d-none d-md-table-cell"><a href="/en/Pokemon/Products/Singles/151/Alakazam-ex-V1-MEW065">Alakazam ex  (MEW 065)</a></td>
    card_pattern = r'<td[^>]*class="[^"]*name[^"]*"[^>]*><a[^>]*href="[^"]*">([^<]+)</a></td>'
    card_matches = re.findall(card_pattern, html_content, re.IGNORECASE)
    
    for match in card_matches:
        clean_name = html.unescape(match.strip())
        
        # Skip if too short
        if len(clean_name) < 3:
            continue
        
        card = {
            'name': clean_name,
            'source': 'cardmarket',
            'variant_type': 'Normal',  # Default to Normal variant for CM cards
            'has_card': False  # Pending purchase, not yet owned
        }
        
        # Try to extract set code and number from the name
        # Pattern 1: "Alakazam ex  (MEW 065)" - standard format
        # Pattern 2: "Dragonite (M24 012)" - alternative format
        card_info_match = re.search(r'([^(]+?)\s*\(([A-Z0-9]{2,4})\s+(\d+(?:/\d+)?)\)', clean_name)
        if card_info_match:
            card['name'] = card_info_match.group(1).strip()
            card['set_code'] = card_info_match.group(2)
            card['number'] = card_info_match.group(3)

            # Set name will be resolved dynamically from TCG Collector data
            # For now, use a placeholder that will be updated when matching with TCG Collector cards
            card['set_name'] = f"Unknown Set ({card['set_code']})"
        
        cards.append(card)
        
    
    return cards

def generate_set_overview_page(all_cards):
    """Generate main overview page with set statistics and links"""

    # Calculate stats by set
    set_stats = {}
    for card in all_cards.values():
        set_name = card.get('set_name', 'Unknown')
        if set_name not in set_stats:
            set_stats[set_name] = {
                'total_cards': 0,
                'owned_cards': 0,
                'pending_cards': 0,
                'set_code': card.get('set_code', 'UNK')
            }

        set_stats[set_name]['total_cards'] += 1
        if card.get('has_card'):
            set_stats[set_name]['owned_cards'] += 1
        elif card.get('cardmarket_pending'):
            set_stats[set_name]['pending_cards'] += 1

    # Calculate overall stats
    total_cards = len(all_cards)
    total_owned = sum(1 for card in all_cards.values() if card.get('has_card'))
    total_pending = sum(1 for card in all_cards.values() if card.get('cardmarket_pending'))

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pokemon Card Collection Overview</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .overview-stats {{ margin-bottom: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 10px; }}
        .set-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }}
        .set-card {{
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .set-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
        .set-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
        .set-code {{ color: #666; font-size: 14px; margin-bottom: 15px; }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            display: flex;
            transition: width 0.3s ease;
        }}
        .progress-owned {{
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
        }}
        .progress-pending {{
            background: linear-gradient(90deg, #6c757d 0%, #495057 100%);
        }}
        .set-stats {{ font-size: 14px; color: #666; }}
        .set-link {{
            display: inline-block;
            margin-top: 15px;
            padding: 8px 16px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 14px;
        }}
        .set-link:hover {{ background-color: #0056b3; }}
        .overall-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .stat-box {{ text-align: center; padding: 15px; background: white; border-radius: 8px; }}
        .stat-number {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .stat-label {{ font-size: 14px; color: #666; }}
    </style>
</head>
<body>
    <h1>Pokemon Card Collection Overview</h1>

    <div class="overview-stats">
        <h2>Overall Collection Statistics</h2>
        <div class="overall-stats">
            <div class="stat-box">
                <div class="stat-number">{total_cards}</div>
                <div class="stat-label">Total Cards Tracked</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{total_owned}</div>
                <div class="stat-label">Cards Owned</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{total_pending}</div>
                <div class="stat-label">Pending Purchase</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{((total_owned / total_cards) * 100):.1f}%</div>
                <div class="stat-label">Collection Complete</div>
            </div>
        </div>
    </div>

    <h2>Sets</h2>
    <div class="set-grid">"""

    # Sort sets by completion percentage (owned + pending) / total (descending)
    sorted_sets = sorted(set_stats.items(),
                        key=lambda x: (x[1]['owned_cards'] + x[1]['pending_cards']) / x[1]['total_cards'] if x[1]['total_cards'] > 0 else 0,
                        reverse=True)

    for set_name, stats in sorted_sets:
        completion_percent = (stats['owned_cards'] / stats['total_cards'] * 100) if stats['total_cards'] > 0 else 0
        pending_percent = (stats['pending_cards'] / stats['total_cards'] * 100) if stats['total_cards'] > 0 else 0

        # Create safe filename for set
        safe_filename = set_name.replace(' ', '_').replace('&', 'and').replace("'", "").replace('.', '')

        html_content += f"""
        <div class="set-card">
            <div class="set-title">{html.escape(set_name)}</div>
            <div class="set-code">Set Code: {html.escape(stats['set_code'])}</div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {completion_percent + pending_percent}%">
                    <div class="progress-owned" style="width: {(completion_percent / (completion_percent + pending_percent) * 100) if (completion_percent + pending_percent) > 0 else 0}%"></div>
                    <div class="progress-pending" style="width: {(pending_percent / (completion_percent + pending_percent) * 100) if (completion_percent + pending_percent) > 0 else 0}%"></div>
                </div>
            </div>

            <div class="set-stats">
                <strong>{stats['owned_cards']}</strong> of <strong>{stats['total_cards']}</strong> cards owned
                (<strong>{completion_percent:.1f}%</strong> complete)
                {f'<br><strong>{stats["pending_cards"]}</strong> cards pending purchase ({pending_percent:.1f}%)' if stats['pending_cards'] > 0 else ''}
            </div>

            <a href="{safe_filename}.html" class="set-link">View Set Details →</a>
        </div>"""

    html_content += """
    </div>
</body>
</html>"""

    return html_content

def generate_cardmarket_want_list_for_set(set_name, set_cards, chunk_size=200):
    """Generate Cardmarket want list for a specific set, chunked for size limits"""

    # Filter for cards you don't have and aren't pending
    want_cards = [card for card in set_cards if not card.get('has_card') and not card.get('cardmarket_pending')]

    if not want_cards:
        return []

    # Sort by number
    sorted_cards = sorted(want_cards, key=lambda x: (int(x.get('number', '999')) if x.get('number', '999').isdigit() else 999, x.get('name', '')))

    # Create decklist format
    decklist_lines = []
    for card in sorted_cards:
        number = card.get('number', '???')
        name = card.get('name', 'Unknown')
        set_code = card.get('set_code', 'UNK')
        variant = card.get('variant_type', 'Normal')

        if variant != 'Normal':
            decklist_lines.append(f"1 {name} ({variant}) {set_code} {number}")
        else:
            decklist_lines.append(f"1 {name} {set_code} {number}")

    # Split into chunks
    chunks = []
    for i in range(0, len(decklist_lines), chunk_size):
        chunk = decklist_lines[i:i + chunk_size]
        chunks.append('\n'.join(chunk))

    # Convert each chunk via API
    converted_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"Converting chunk {i+1}/{len(chunks)} for {set_name}...")
        converted = convert_decklist_to_cardmarket(chunk)
        if converted:
            converted_chunks.append(converted.strip())
        else:
            # Fallback to manual format if conversion fails
            lines = chunk.split('\n')
            manual_lines = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        card_name = ' '.join(parts[1:-2])
                        set_code = parts[-2]
                        manual_lines.append(f"{card_name} [ABILITY] [{set_code}]")
            converted_chunks.append('\n'.join(manual_lines))

    return converted_chunks

def generate_individual_set_page(set_name, set_cards):
    """Generate individual set page with detailed card list using templates"""
    import html

    # Calculate set statistics
    total_cards = len(set_cards)
    owned_cards = sum(1 for card in set_cards if card.get('has_card'))
    pending_cards = sum(1 for card in set_cards if card.get('cardmarket_pending'))
    completion_percent = (owned_cards / total_cards * 100) if total_cards > 0 else 0

    # Get set code (assuming all cards in set have same code)
    set_code = set_cards[0].get('set_code', 'UNK') if set_cards else 'UNK'

    # Load HTML template
    with open('templates/set_page.html', 'r', encoding='utf-8') as f:
        html_template = f.read()

    # Load JavaScript template
    with open('templates/cardmarket.js', 'r', encoding='utf-8') as f:
        js_template = f.read()

    # Generate card rows HTML
    card_rows_html = ""

    # Sort cards by number and variant
    def sort_key(card):
        variant_order = {'Normal': 0, 'Reverse Holo': 1, 'Holo': 2}
        variant_type = card.get('variant_type', 'Normal')
        return (
            card.get('number', ''),
            variant_order.get(variant_type, 99)
        )

    sorted_cards = sorted(set_cards, key=sort_key)

    for card in sorted_cards:
        number = card.get('number', 'XXX')
        total_count = card.get('total_count') or ''
        name = card.get('name', 'Unknown')
        variant = card.get('variant_type', 'Normal')
        card_id = card.get('card_id')

        # Create camera icon HTML if card has an ID
        camera_icon_html = ''
        if card_id:
            camera_icon_html = f'<span class="camera-icon" onmouseover="showCardPreview(event, \'{card_id}\')" onmouseout="hideCardPreview()">📷</span>'

        have = '✓' if card.get('has_card') else '✗'

        # Determine status
        if card.get('cardmarket_pending'):
            if card.get('has_card'):
                status = 'Have + Pending Purchase (Duplicate!)'
                row_class = 'pending'
            else:
                status = 'Pending Purchase'
                row_class = 'pending'
        elif card.get('source') == 'tcg_collector':
            if card.get('has_card'):
                status = 'Have'
                row_class = 'has-card'
            else:
                status = 'Need'
                row_class = 'missing-card'
        else:
            status = 'Pending Purchase'
            row_class = 'pending'

        card_rows_html += f"""
            <tr class="{row_class}">
                <td style="text-align: center;">{camera_icon_html}</td>
                <td>{html.escape(number)}</td>
                <td>{html.escape(total_count)}</td>
                <td>{html.escape(name)}</td>
                <td>{html.escape(variant)}</td>
                <td>{have}</td>
                <td>{status}</td>
            </tr>"""

    # Replace placeholders in JavaScript template
    js_code = js_template.replace('{{SET_CODE}}', set_code)

    # Replace placeholders in HTML template
    html_content = html_template.replace('{{SET_NAME}}', html.escape(set_name))
    html_content = html_content.replace('{{SET_CODE}}', html.escape(set_code))
    html_content = html_content.replace('{{TOTAL_CARDS}}', str(total_cards))
    html_content = html_content.replace('{{OWNED_CARDS}}', str(owned_cards))
    html_content = html_content.replace('{{PENDING_CARDS}}', str(pending_cards))
    html_content = html_content.replace('{{COMPLETION_PERCENT}}', f"{completion_percent:.1f}")
    html_content = html_content.replace('{{CARD_ROWS}}', card_rows_html)
    html_content = html_content.replace('{{CARDMARKET_JS}}', js_code)

    return html_content

def build_set_mapping_from_tcg_cards(tcg_cards):
    """Build a mapping of set codes to set names from TCG Collector cards"""
    set_mapping = {}
    for card in tcg_cards:
        set_code = card.get('set_code')
        set_name = card.get('set_name')
        if set_code and set_name:
            set_mapping[set_code] = set_name
    return set_mapping


def generate_html_report(tcg_cards, cm_cards):
    """Generate HTML report showing card status"""

    # Build set mapping from TCG Collector data
    set_mapping = build_set_mapping_from_tcg_cards(tcg_cards)

    # Update Cardmarket cards with proper set names
    for card in cm_cards:
        set_code = card.get('set_code')
        if set_code and set_code in set_mapping:
            card['set_name'] = set_mapping[set_code]

    # Combine all cards by set code and number
    all_cards = {}
    
    # Add TCG Collector cards first - now with variants
    for card in tcg_cards:
        key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_{card.get('variant_type', 'Normal')}"
        all_cards[key] = card.copy()
    
    # Add Cardmarket cards, checking for duplicates
    for card in cm_cards:
        # For Cardmarket cards, we'll check against both Normal and Reverse Holo variants
        normal_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_Normal"
        reverse_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_Reverse Holo"
        
        found_duplicate = False
        
        # Check if we already have this card in any variant
        for existing_key in [normal_key, reverse_key]:
            if existing_key in all_cards:
                # Mark existing card as having pending purchase
                all_cards[existing_key]['status'] = 'pending_purchase'
                all_cards[existing_key]['cardmarket_pending'] = True
                found_duplicate = True
                break
        
        if not found_duplicate:
            # New card from Cardmarket - it already has the right structure
            card['status'] = 'pending_purchase'
            card['cardmarket_pending'] = True
            # card already has variant_type and has_card set correctly
            all_cards[normal_key] = card
    
    # Get unique sets for filter dropdown
    unique_sets = sorted(set(card.get('set_name', 'Unknown') for card in all_cards.values()))
    unique_statuses = ['All', 'Have', 'Need', 'Pending Purchase', 'Have + Pending Purchase (Duplicate!)']
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pokemon Card Collection Status</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .filters {{ margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
        .filter-group {{ display: inline-block; margin-right: 20px; }}
        .filter-group label {{ font-weight: bold; margin-right: 5px; }}
        .filter-group select, .filter-group input {{ padding: 5px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; cursor: pointer; }}
        th:hover {{ background-color: #e9ecef; }}
        .has-card {{ background-color: #d4edda; }}
        .missing-card {{ background-color: #f8d7da; }}
        .pending {{ background-color: #fff3cd; }}
        .stats {{ margin-bottom: 20px; font-size: 18px; }}
        .camera-icon {{
            cursor: pointer;
            color: #007bff;
            margin-left: 5px;
            font-size: 14px;
            position: relative;
        }}
        .camera-icon:hover {{ color: #0056b3; }}
        .card-preview {{
            position: absolute;
            z-index: 1000;
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 5px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            max-width: 200px;
            display: none;
            pointer-events: auto;
        }}
        .card-preview img {{
            width: 100%;
            height: auto;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <h1>Pokemon Card Collection Status</h1>
    <div class="stats">
        <strong>Total cards tracked: {len(all_cards)}</strong>
    </div>
    
    <div class="filters">
        <div class="filter-group">
            <label for="setFilter">Filter by Set:</label>
            <select id="setFilter" onchange="filterTable()">
                <option value="All">All Sets</option>"""
    
    for set_name in unique_sets:
        html_content += f'<option value="{html.escape(set_name)}">{html.escape(set_name)}</option>'
    
    html_content += f"""
            </select>
        </div>
        <div class="filter-group">
            <label for="statusFilter">Filter by Status:</label>
            <select id="statusFilter" onchange="filterTable()">"""
    
    for status in unique_statuses:
        html_content += f'<option value="{html.escape(status)}">{html.escape(status)}</option>'
    
    html_content += f"""
            </select>
        </div>
        <div class="filter-group">
            <label for="searchBox">Search:</label>
            <input type="text" id="searchBox" placeholder="Card name..." onkeyup="filterTable()">
        </div>
    </div>
    
    <table id="cardTable">
        <thead>
            <tr>
                <th>Preview</th>
                <th onclick="sortTable(1)">Set Name</th>
                <th onclick="sortTable(2)">Set Code</th>
                <th onclick="sortTable(3)">Card Number</th>
                <th onclick="sortTable(4)">Total</th>
                <th onclick="sortTable(5)">Card Name</th>
                <th onclick="sortTable(6)">Variant</th>
                <th onclick="sortTable(7)">Have</th>
                <th onclick="sortTable(8)">Status</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Sort cards by set code, number, and variant (Normal first, then Reverse Holo)
    def sort_key(item):
        card = item[1]
        variant_order = {'Normal': 0, 'Reverse Holo': 1, 'Holo': 2}
        variant_type = card.get('variant_type', 'Normal')
        return (
            card.get('set_code', ''), 
            card.get('number', ''),
            variant_order.get(variant_type, 99)
        )
    
    sorted_cards = sorted(all_cards.items(), key=sort_key)
    
    for key, card in sorted_cards:
        set_name = card.get('set_name', 'Unknown')
        set_code = card.get('set_code', 'UNK')
        number = card.get('number', 'XXX')
        total_count = card.get('total_count') or ''  # Use total count if available, handle None
        name = card.get('name', 'Unknown')
        variant = card.get('variant_type', 'Normal')
        card_id = card.get('card_id')

        # Create camera icon HTML if card has an ID
        camera_icon_html = ''
        if card_id:
            camera_icon_html = f'<span class="camera-icon" onmouseover="showCardPreview(event, \'{card_id}\')" onmouseout="hideCardPreview()">📷</span>'


        have = '✓' if card.get('has_card') else '✗'
        
        # Determine status
        if card.get('cardmarket_pending'):
            if card.get('has_card'):
                status = 'Have + Pending Purchase (Duplicate!)'
                row_class = 'pending'
            else:
                status = 'Pending Purchase'
                row_class = 'pending'
        elif card.get('source') == 'tcg_collector':
            if card.get('has_card'):
                status = 'Have'
                row_class = 'has-card'
            else:
                status = 'Need'
                row_class = 'missing-card'
        else:
            status = 'Pending Purchase'
            row_class = 'pending'
        
        html_content += f"""
            <tr class="{row_class}">
                <td style="text-align: center;">{camera_icon_html}</td>
                <td>{html.escape(set_name)}</td>
                <td>{html.escape(set_code)}</td>
                <td>{html.escape(number)}</td>
                <td>{html.escape(total_count or 'Unknown')}</td>
                <td>{html.escape(name)}</td>
                <td>{html.escape(variant)}</td>
                <td>{have}</td>
                <td>{status}</td>
            </tr>"""
    
    html_content += """
        </tbody>
    </table>
    
    <script>
    // Apply filters on page load
    window.onload = function() {
        filterTable();
    };

    function filterTable() {
        var setFilter = document.getElementById("setFilter").value;
        var statusFilter = document.getElementById("statusFilter").value;
        var searchBox = document.getElementById("searchBox").value.toLowerCase();
        var table = document.getElementById("cardTable");
        var rows = table.getElementsByTagName("tr");
        
        for (var i = 1; i < rows.length; i++) {
            var row = rows[i];
            var cells = row.getElementsByTagName("td");
            var setName = cells[1].textContent;
            var cardName = cells[5].textContent.toLowerCase();
            var status = cells[8].textContent;
            
            var showRow = true;
            
            // Filter by set
            if (setFilter !== "All" && setName !== setFilter) {
                showRow = false;
            }
            
            // Filter by status
            if (statusFilter !== "All" && status !== statusFilter) {
                showRow = false;
            }
            
            // Filter by search
            if (searchBox !== "" && !cardName.includes(searchBox)) {
                showRow = false;
            }
            
            row.style.display = showRow ? "" : "none";
        }
    }
    
    function sortTable(columnIndex) {
        var table = document.getElementById("cardTable");
        var tbody = table.getElementsByTagName("tbody")[0];
        var rows = Array.from(tbody.getElementsByTagName("tr"));
        
        rows.sort(function(a, b) {
            var aValue = a.getElementsByTagName("td")[columnIndex].textContent;
            var bValue = b.getElementsByTagName("td")[columnIndex].textContent;
            
            // Try to parse as numbers for numeric columns
            if (columnIndex === 3) { // Card Number column
                var aNum = parseInt(aValue);
                var bNum = parseInt(bValue);
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return aNum - bNum;
                }
            }
            
            return aValue.localeCompare(bValue);
        });
        
        rows.forEach(function(row) {
            tbody.appendChild(row);
        });
    }

    let cardPreviewElement = null;
    let cardImageCache = {};
    let hideTimeout = null;

    async function showCardPreview(event, cardId) {
        // Clear any pending hide timeout
        if (hideTimeout) {
            clearTimeout(hideTimeout);
            hideTimeout = null;
        }
        if (!cardId) return;

        // Create preview element if it doesn't exist
        if (!cardPreviewElement) {
            cardPreviewElement = document.createElement('div');
            cardPreviewElement.className = 'card-preview';

            // Add hover events to keep popup visible when hovering over it
            cardPreviewElement.addEventListener('mouseenter', function() {
                if (hideTimeout) {
                    clearTimeout(hideTimeout);
                    hideTimeout = null;
                }
            });

            cardPreviewElement.addEventListener('mouseleave', function() {
                hideCardPreview();
            });

            document.body.appendChild(cardPreviewElement);
        }

        // Position the preview near the mouse cursor
        const rect = event.target.getBoundingClientRect();
        cardPreviewElement.style.left = (rect.right + 10) + 'px';
        cardPreviewElement.style.top = rect.top + 'px';

        // Check if we have the image URL cached
        if (cardImageCache[cardId]) {
            if (cardImageCache[cardId] !== 'failed') {
                cardPreviewElement.innerHTML = `<img src="${cardImageCache[cardId]}" alt="Card preview" />`;
                cardPreviewElement.style.display = 'block';
            }
            return;
        }

        // Show loading message
        cardPreviewElement.innerHTML = '<div style="padding: 10px;">Loading...</div>';
        cardPreviewElement.style.display = 'block';

        try {
            // Try to fetch the card detail page to get the actual image URL
            // Note: This will likely fail due to CORS, but we'll provide a fallback
            fetch(`https://www.tcgcollector.com/cards/${cardId}/`)
                .then(response => response.text())
                .then(html => {
                    // Extract the image URL from the HTML - handle multiple formats
                    const imageMatch = html.match(/https:\/\/static\.tcgcollector\.com\/content\/images\/[a-f0-9\/]+\.(jpg|webp|png)/);
                    if (imageMatch) {
                        const imageUrl = imageMatch[0];
                        cardImageCache[cardId] = imageUrl;
                        if (cardPreviewElement.style.display === 'block') {
                            cardPreviewElement.innerHTML = `<img src="${imageUrl}" alt="Card preview" />`;
                        }
                    } else {
                        throw new Error('Image URL not found');
                    }
                })
                .catch(error => {
                    // CORS fallback: Show card link instead of image
                    console.log('CORS prevented image fetch, showing link instead:', error);
                    cardImageCache[cardId] = 'link';
                    if (cardPreviewElement.style.display === 'block') {
                        cardPreviewElement.innerHTML = `
                            <div style="padding: 10px; text-align: center;">
                                <p>🔗 <a href="https://www.tcgcollector.com/cards/${cardId}/" target="_blank" style="color: #007bff;">View card on TCG Collector</a></p>
                                <small>Image preview blocked by CORS</small>
                            </div>
                        `;
                    }
                });

        } catch (error) {
            console.log('Error loading card preview:', error);
            cardPreviewElement.style.display = 'none';
            cardImageCache[cardId] = 'failed';
        }
    }

    function hideCardPreview() {
        // Use a small delay to allow moving mouse to the preview popup
        hideTimeout = setTimeout(function() {
            if (cardPreviewElement) {
                cardPreviewElement.style.display = 'none';
            }
        }, 100);
    }
    </script>
</body>
</html>"""
    
    return html_content

def main():
    # Set up data directory
    data_dir = Path("data")
    if not data_dir.exists():
        print("Error: data/ folder not found. Please create it and add your HTML files.")
        return

    # Option to fetch card images (disabled by default due to time constraints)
    fetch_images = False  # Set to True to fetch actual image URLs
    
    # Find all TCG Collector HTML files
    tcg_files = list(data_dir.glob("*TCG Collector*.html"))
    if not tcg_files:
        print("No TCG Collector HTML files found in data/ folder")
        return
    
    # Find all Cardmarket HTML files  
    cm_files = list(data_dir.glob("*Cardmarket*.html"))
    if not cm_files:
        print("No Cardmarket HTML files found in data/ folder")
        return
    
    print(f"Found {len(tcg_files)} TCG Collector files and {len(cm_files)} Cardmarket files")
    
    # Process all TCG Collector files
    all_tcg_cards = []
    for tcg_file in tcg_files:
        print(f"Reading TCG Collector file: {tcg_file.name}")
        with open(tcg_file, 'r', encoding='utf-8') as f:
            tcg_content = f.read()
        
        tcg_cards = extract_tcg_collector_cards(tcg_content)
        all_tcg_cards.extend(tcg_cards)
        print(f"  Found {len(tcg_cards)} cards")
    
    print(f"Total TCG Collector cards: {len(all_tcg_cards)}")
    
    # Process all Cardmarket files
    all_cm_cards = []
    for cm_file in cm_files:
        print(f"Reading Cardmarket file: {cm_file.name}")
        with open(cm_file, 'r', encoding='utf-8') as f:
            cm_content = f.read()
        
        cm_cards = extract_cardmarket_cards(cm_content)
        all_cm_cards.extend(cm_cards)
        print(f"  Found {len(cm_cards)} cards")
    
    print(f"Total Cardmarket cards: {len(all_cm_cards)}")
    
    # Use the combined data
    tcg_cards = all_tcg_cards
    cm_cards = all_cm_cards
    
    # Print some sample data for debugging
    if tcg_cards:
        print("\nSample TCG Collector card:")
        print(tcg_cards[0])
    
    if cm_cards:
        print("\nSample Cardmarket card:")
        print(cm_cards[0])
    
    print("Generating HTML reports...")

    # Generate the old single-page report (keep for compatibility)
    html_report = generate_html_report(tcg_cards, cm_cards)
    output_file = Path("card_collection_report.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_report)
    print(f"Legacy report generated: {output_file}")

    # Generate new multi-page reports

    # Build set mapping from TCG Collector data
    set_mapping = build_set_mapping_from_tcg_cards(tcg_cards)

    # Update Cardmarket cards with proper set names
    for card in cm_cards:
        set_code = card.get('set_code')
        if set_code and set_code in set_mapping:
            card['set_name'] = set_mapping[set_code]

    # Combine all cards by set code and number (same logic as before)
    all_cards = {}

    # Add TCG Collector cards first - now with variants
    for card in tcg_cards:
        key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_{card.get('variant_type', 'Normal')}"
        all_cards[key] = card.copy()

    # Add Cardmarket cards, checking for duplicates
    for card in cm_cards:
        # For Cardmarket cards, we'll check against both Normal and Reverse Holo variants
        normal_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_Normal"
        reverse_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_Reverse Holo"

        found_duplicate = False

        # Check if we already have this card in any variant
        for existing_key in [normal_key, reverse_key]:
            if existing_key in all_cards:
                # Mark existing card as having pending purchase
                all_cards[existing_key]['status'] = 'pending_purchase'
                all_cards[existing_key]['cardmarket_pending'] = True
                found_duplicate = True
                break

        if not found_duplicate:
            # New card from Cardmarket - it already has the right structure
            card['status'] = 'pending_purchase'
            card['cardmarket_pending'] = True
            # card already has variant_type and has_card set correctly
            all_cards[normal_key] = card

    # Generate overview page
    overview_html = generate_set_overview_page(all_cards)
    overview_file = Path("index.html")
    with open(overview_file, 'w', encoding='utf-8') as f:
        f.write(overview_html)
    print(f"Overview page generated: {overview_file}")

    # Generate individual set pages
    sets_by_name = {}
    for card in all_cards.values():
        set_name = card.get('set_name', 'Unknown')
        if set_name not in sets_by_name:
            sets_by_name[set_name] = []
        sets_by_name[set_name].append(card)

    for set_name, set_cards in sets_by_name.items():
        # Create safe filename for set
        safe_filename = set_name.replace(' ', '_').replace('&', 'and').replace("'", "").replace('.', '')

        set_html = generate_individual_set_page(set_name, set_cards)
        set_file = Path(f"{safe_filename}.html")
        with open(set_file, 'w', encoding='utf-8') as f:
            f.write(set_html)
        print(f"Set page generated: {set_file} ({len(set_cards)} cards)")

    print(f"\nGenerated {len(sets_by_name) + 1} HTML files:")
    print(f"- index.html (overview)")
    print(f"- {len(sets_by_name)} individual set pages")
    print(f"- card_collection_report.html (legacy single page)")

    # Generate want lists
    print(f"\nGenerating want lists...")
    generate_want_lists(all_cards)

def convert_decklist_to_cardmarket(decklist_text):
    """Convert decklist format to Cardmarket format using pokedata.ovh API"""
    try:
        # Prepare the POST data
        post_data = f"decklist={quote(decklist_text)}"

        # Headers matching the working browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Referer': 'https://www.pokedata.ovh/misc/cardmarket',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.pokedata.ovh',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        # Make the request
        response = requests.post(
            'https://www.pokedata.ovh/misc/cardmarket',
            data=post_data,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            # Extract the converted text from the textarea
            import re
            textarea_pattern = r'<textarea[^>]*id="cardmarket"[^>]*>(.*?)</textarea>'
            match = re.search(textarea_pattern, response.text, re.DOTALL)
            if match:
                converted_text = match.group(1).strip()
                return converted_text
            else:
                print("Warning: Could not find converted text in response")
                return None
        else:
            print(f"Warning: Converter API returned status {response.status_code}")
            return None

    except Exception as e:
        print(f"Warning: Failed to convert decklist: {e}")
        return None

def generate_want_lists(all_cards):
    """Generate want lists in various formats for cards that are needed"""

    # Group cards by set and filter for cards you don't have and aren't pending
    want_lists = {}
    for card in all_cards.values():
        if not card.get('has_card') and not card.get('cardmarket_pending'):
            set_name = card.get('set_name', 'Unknown Set')
            if set_name not in want_lists:
                want_lists[set_name] = []
            want_lists[set_name].append(card)

    # Generate different format files
    formats = {
        'simple': generate_simple_want_list,
        'cardmarket': generate_cardmarket_want_list,
        'decklist': generate_decklist_want_list,
        'cardmarket_converted': generate_cardmarket_converted_want_list
    }

    for format_name, generator_func in formats.items():
        filename = f"want_list_{format_name}.txt"
        content = generator_func(want_lists)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

        total_cards = sum(len(cards) for cards in want_lists.values())
        print(f"Want list generated: {filename} ({total_cards} cards)")

def generate_simple_want_list(want_lists):
    """Generate a simple list of card names by set"""
    content = "# Pokemon Card Want List (Simple Format)\n"
    content += f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    for set_name, cards in sorted(want_lists.items()):
        if not cards:
            continue

        content += f"## {set_name}\n"
        for card in sorted(cards, key=lambda x: (x.get('number', '999'), x.get('name', ''))):
            number = card.get('number', '???')
            name = card.get('name', 'Unknown')
            variant = card.get('variant_type', 'Normal')
            if variant != 'Normal':
                content += f"{number} {name} ({variant})\n"
            else:
                content += f"{number} {name}\n"
        content += "\n"

    return content

def generate_cardmarket_want_list(want_lists):
    """Generate a list formatted for Cardmarket import (best guess format)"""
    content = "# Pokemon Card Want List (Cardmarket Format)\n"
    content += f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "# Format: Card Name [Set Code] (modify abilities manually if needed)\n\n"

    all_cards = []
    for set_name, cards in want_lists.items():
        for card in cards:
            set_code = card.get('set_code', 'UNK')
            name = card.get('name', 'Unknown')
            variant = card.get('variant_type', 'Normal')

            # Format for Cardmarket - this is a best guess
            if variant != 'Normal':
                formatted_name = f"{name} ({variant}) [{set_code}]"
            else:
                formatted_name = f"{name} [{set_code}]"

            all_cards.append((name, formatted_name, card))

    # Sort alphabetically by card name
    for name, formatted_name, card in sorted(all_cards, key=lambda x: x[0]):
        content += f"{formatted_name}\n"

    content += "\n# Note: You may need to manually add abilities in brackets like:\n"
    content += "# Exeggcute [Precocious Evolution] [SSP]\n"
    content += "# Durant ex [Sudden Shearing | Vengeful Crush] [SSP]\n"

    return content

def generate_decklist_want_list(want_lists):
    """Generate a list in decklist format for pokedata.ovh converter"""
    content = "# Pokemon Card Want List (Decklist Format for pokedata.ovh)\n"
    content += f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "# Format: 1 CardName SetCode Number\n"
    content += "# Use this with https://www.pokedata.ovh/misc/cardmarket\n\n"

    # Collect all cards and sort them by set and number
    all_want_cards = []
    for set_name, cards in want_lists.items():
        for card in cards:
            all_want_cards.append(card)

    # Sort by set code, then by number
    sorted_cards = sorted(all_want_cards, key=lambda x: (x.get('set_code', 'ZZZ'), int(x.get('number', '999')) if x.get('number', '999').isdigit() else 999, x.get('name', '')))

    for card in sorted_cards:
        number = card.get('number', '???')
        name = card.get('name', 'Unknown')
        set_code = card.get('set_code', 'UNK')
        variant = card.get('variant_type', 'Normal')

        # Format exactly as the converter expects: "1 CardName SetCode Number"
        if variant != 'Normal':
            content += f"1 {name} ({variant}) {set_code} {number}\n"
        else:
            content += f"1 {name} {set_code} {number}\n"

    content += "\n# Instructions:\n"
    content += "# 1. Copy the list above\n"
    content += "# 2. Paste into https://www.pokedata.ovh/misc/cardmarket\n"
    content += "# 3. Click Convert to get Cardmarket format with abilities\n"

    return content

def generate_cardmarket_converted_want_list(want_lists):
    """Generate a list automatically converted via pokedata.ovh API"""
    content = "# Pokemon Card Want List (Auto-Converted via pokedata.ovh)\n"
    content += f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "# Automatically converted with abilities included!\n\n"

    # First generate the decklist format
    decklist_content = ""
    all_want_cards = []
    for set_name, cards in want_lists.items():
        for card in cards:
            all_want_cards.append(card)

    # Sort by set code, then by number (same as decklist format)
    sorted_cards = sorted(all_want_cards, key=lambda x: (x.get('set_code', 'ZZZ'), int(x.get('number', '999')) if x.get('number', '999').isdigit() else 999, x.get('name', '')))

    for card in sorted_cards:
        number = card.get('number', '???')
        name = card.get('name', 'Unknown')
        set_code = card.get('set_code', 'UNK')
        variant = card.get('variant_type', 'Normal')

        # Format exactly as the converter expects: "1 CardName SetCode Number"
        if variant != 'Normal':
            decklist_content += f"1 {name} ({variant}) {set_code} {number}\n"
        else:
            decklist_content += f"1 {name} {set_code} {number}\n"

    # Try to convert via the API
    print("Converting decklist to Cardmarket format via pokedata.ovh...")
    converted_text = convert_decklist_to_cardmarket(decklist_content)

    if converted_text:
        content += "# SUCCESS: Automatically converted with abilities!\n"
        content += "# Copy the text below and paste directly into Cardmarket:\n\n"
        content += converted_text
        content += "\n\n# Note: This was automatically converted - abilities are included!"
    else:
        content += "# CONVERSION FAILED: Using manual format instead\n"
        content += "# You may need to manually add abilities or try the pokedata.ovh converter\n\n"
        content += "# Original decklist format (copy to https://www.pokedata.ovh/misc/cardmarket):\n"
        content += decklist_content
        content += "\n# Manual format (add abilities manually):\n"
        for line in decklist_content.strip().split('\n'):
            if line.strip():
                # Extract card name and set code for manual format
                parts = line.split()
                if len(parts) >= 4:  # 1 CardName SetCode Number
                    card_name = ' '.join(parts[1:-2])  # Everything between count and set code
                    set_code = parts[-2]
                    content += f"{card_name} [ABILITY] [{set_code}]\n"

    return content

if __name__ == "__main__":
    main()