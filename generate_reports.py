#!/usr/bin/env python3
"""
Pokemon Card Report Generator
Generates HTML reports from extracted card data
"""

import json
import html
import requests
import os
import glob
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

def load_data(filename="card_data.json"):
    """Load extracted card data from JSON file"""
    if not Path(filename).exists():
        print(f"Error: {filename} not found. Run extract_data.py first.")
        return None

    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_sets_needing_regeneration(data, force_all=False):
    """Determine which sets need HTML regeneration based on source file changes"""
    if force_all:
        return set()  # Empty set means regenerate all

    source_files = data.get('source_files', {})
    sets_to_regenerate = set()

    # Check if any source files have been modified since extraction
    for file_path, file_info in source_files.items():
        if os.path.exists(file_path):
            current_mtime = os.path.getmtime(file_path)
            stored_mtime = file_info.get('mtime', 0)

            # If file was modified after extraction, find which sets it affects
            if current_mtime > stored_mtime:
                file_name = os.path.basename(file_path)
                print(f"File changed since extraction: {file_name}")

                # Extract set name from TCG Collector filename patterns
                if 'TCG Collector' in file_name:
                    # Try to match common patterns like "Set Name card list (International TCG) – TCG Collector.html"
                    if 'card list' in file_name:
                        set_name = file_name.split(' card list')[0].strip()
                        sets_to_regenerate.add(set_name)
                        print(f"  -> Will regenerate set: {set_name}")

    # Also check if any HTML files exist that weren't in the original source files
    # (this handles newly added files)
    current_html_files = set(glob.glob('data/*.html'))
    tracked_files = set(source_files.keys())
    new_files = current_html_files - tracked_files

    if new_files:
        print(f"Found {len(new_files)} new HTML files - will regenerate all sets")
        return set()  # Regenerate all if new files found

    return sets_to_regenerate

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
        if card.get('has_card'):
            if card.get('cardmarket_pending'):
                status = 'Have + Pending Purchase (Duplicate!)'
                row_class = 'has-card'  # Still color as owned since they have it
            else:
                status = 'Have'
                row_class = 'has-card'
        elif card.get('cardmarket_pending'):
            status = 'Pending Purchase'
            row_class = 'pending'
        else:
            status = 'Need'
            row_class = 'missing-card'

        card_rows_html += f'''
            <tr class="{row_class}">
                <td>{camera_icon_html}</td>
                <td>{html.escape(number)}</td>
                <td>{html.escape(total_count)}</td>
                <td>{html.escape(name)}</td>
                <td>{html.escape(variant)}</td>
                <td>{have}</td>
                <td>{status}</td>
            </tr>'''

    # Replace placeholders in JavaScript template
    js_code = js_template.replace('{{SET_CODE}}', set_code)

    # Calculate progress bar percentages
    pending_percent = (pending_cards / total_cards * 100) if total_cards > 0 else 0
    total_progress_percent = completion_percent + pending_percent

    # Calculate percentages within the progress bar (owned vs pending)
    owned_percent_of_total = (completion_percent / total_progress_percent * 100) if total_progress_percent > 0 else 0
    pending_percent_of_total = (pending_percent / total_progress_percent * 100) if total_progress_percent > 0 else 0

    # Replace placeholders in HTML template
    html_content = html_template.replace('{{SET_NAME}}', html.escape(set_name))
    html_content = html_content.replace('{{SET_CODE}}', html.escape(set_code))
    html_content = html_content.replace('{{TOTAL_CARDS}}', str(total_cards))
    html_content = html_content.replace('{{OWNED_CARDS}}', str(owned_cards))
    html_content = html_content.replace('{{PENDING_CARDS}}', str(pending_cards))
    html_content = html_content.replace('{{COMPLETION_PERCENT}}', f"{completion_percent:.1f}")
    html_content = html_content.replace('{{TOTAL_PROGRESS_PERCENT}}', f"{total_progress_percent:.1f}")
    html_content = html_content.replace('{{OWNED_PERCENT_OF_TOTAL}}', f"{owned_percent_of_total:.1f}")
    html_content = html_content.replace('{{PENDING_PERCENT_OF_TOTAL}}', f"{pending_percent_of_total:.1f}")
    html_content = html_content.replace('{{CARD_ROWS}}', card_rows_html)
    html_content = html_content.replace('{{CARDMARKET_JS}}', js_code)

    return html_content

def generate_set_overview_page(all_cards):
    """Generate the main overview page with all sets"""
    # Group cards by set
    sets_by_name = {}
    for card in all_cards.values():
        set_name = card.get('set_name', 'Unknown')
        if set_name not in sets_by_name:
            sets_by_name[set_name] = []
        sets_by_name[set_name].append(card)

    # Calculate overall statistics
    total_cards = len(all_cards)
    total_owned = sum(1 for card in all_cards.values() if card.get('has_card'))
    total_pending = sum(1 for card in all_cards.values() if card.get('cardmarket_pending'))

    # Calculate set-specific statistics
    set_stats = {}
    for set_name, cards in sets_by_name.items():
        set_code = cards[0].get('set_code', 'UNK') if cards else 'UNK'
        owned_cards = sum(1 for card in cards if card.get('has_card'))
        pending_cards = sum(1 for card in cards if card.get('cardmarket_pending'))

        set_stats[set_name] = {
            'set_code': set_code,
            'total_cards': len(cards),
            'owned_cards': owned_cards,
            'pending_cards': pending_cards
        }

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pokemon Card Collection Overview</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #666; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .overview-stats {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .set-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        .set-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }}
        .set-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.2); }}
        .set-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; }}
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

def generate_legacy_report(all_cards):
    """Generate the legacy single-page report for compatibility"""
    # Simple single-page version for backwards compatibility
    content = "<!DOCTYPE html><html><head><title>Pokemon Card Collection Report</title></head><body>"
    content += "<h1>Pokemon Card Collection Report</h1>"
    content += "<p>This is the legacy single-page report. Please use index.html for the modern interface.</p>"
    content += "</body></html>"
    return content

def process_all_cards(data):
    """Process the loaded data into the format expected by report generation"""
    tcg_cards = data['tcg_cards']
    cm_cards = data['cardmarket_cards']
    set_mapping = data['set_mapping']

    # Combine all cards by set code and number (same logic as original)
    all_cards = {}

    # Add TCG Collector cards first - now with variants
    for card in tcg_cards:
        key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_{card.get('variant_type', 'Normal')}"
        all_cards[key] = card.copy()

    # Add Cardmarket cards, checking for duplicates
    for card in cm_cards:
        # Create the exact key for this specific variant
        card_variant = card.get('variant_type', 'Normal')
        card_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_{card_variant}"

        # Check if we already have this exact variant
        if card_key in all_cards:
            # Mark existing card as having pending purchase
            all_cards[card_key]['status'] = 'pending_purchase'
            all_cards[card_key]['cardmarket_pending'] = True
        else:
            # New card from Cardmarket - add it with pending status
            card['status'] = 'pending_purchase'
            card['cardmarket_pending'] = True
            # card already has variant_type and has_card set correctly
            all_cards[card_key] = card

    return all_cards

def main(force_all=False):
    """Main report generation function"""
    print("Loading extracted card data...")

    data = load_data()
    if data is None:
        return 1

    print(f"Loaded data extracted on: {data['extraction_timestamp']}")
    print(f"- {data['stats']['total_tcg_cards']} TCG Collector cards")
    print(f"- {data['stats']['total_cardmarket_cards']} Cardmarket cards")

    # Determine which sets need regeneration
    sets_to_regenerate = get_sets_needing_regeneration(data, force_all)
    regenerate_all = len(sets_to_regenerate) == 0 or force_all

    if regenerate_all:
        print("Regenerating all HTML files...")
    else:
        print(f"Selective regeneration for {len(sets_to_regenerate)} changed sets: {sets_to_regenerate}")

    # Process the data into the format needed for reports
    all_cards = process_all_cards(data)

    print("Generating HTML reports...")

    # Always regenerate overview pages (they're fast and may depend on multiple sets)
    html_report = generate_legacy_report(all_cards)
    output_file = Path("card_collection_report.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_report)
    print(f"Legacy report generated: {output_file}")

    overview_html = generate_set_overview_page(all_cards)
    overview_file = Path("index.html")
    with open(overview_file, 'w', encoding='utf-8') as f:
        f.write(overview_html)
    print(f"Overview page generated: {overview_file}")

    # Generate individual set pages (selective or all)
    sets_by_name = {}
    for card in all_cards.values():
        set_name = card.get('set_name', 'Unknown')
        if set_name not in sets_by_name:
            sets_by_name[set_name] = []
        sets_by_name[set_name].append(card)

    sets_generated = 0
    sets_skipped = 0

    for set_name, set_cards in sets_by_name.items():
        # Check if this set needs regeneration
        if not regenerate_all and set_name not in sets_to_regenerate:
            # Check if HTML file exists, if not, we must generate it
            safe_filename = set_name.replace(' ', '_').replace('&', 'and').replace("'", "").replace('.', '')
            set_file = Path(f"{safe_filename}.html")
            if set_file.exists():
                sets_skipped += 1
                continue
            else:
                print(f"Set HTML missing, generating: {set_name}")

        # Create safe filename for set
        safe_filename = set_name.replace(' ', '_').replace('&', 'and').replace("'", "").replace('.', '')

        set_html = generate_individual_set_page(set_name, set_cards)
        set_file = Path(f"{safe_filename}.html")
        with open(set_file, 'w', encoding='utf-8') as f:
            f.write(set_html)
        print(f"Set page generated: {set_file} ({len(set_cards)} cards)")
        sets_generated += 1

    print(f"\nGenerated {2 + sets_generated} HTML files:")
    print(f"- index.html (overview)")
    print(f"- card_collection_report.html (legacy single page)")
    print(f"- {sets_generated} individual set pages")
    if sets_skipped > 0:
        print(f"- {sets_skipped} set pages skipped (unchanged)")

    # Generate want lists
    print(f"\nGenerating want lists...")
    generate_want_lists(all_cards)

    print("\nReport generation complete!")
    return 0

if __name__ == "__main__":
    exit(main())