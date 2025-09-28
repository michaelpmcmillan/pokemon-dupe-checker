#!/usr/bin/env python3
"""
Pokemon Card Data Extractor
Extracts card data from TCG Collector and Cardmarket HTML files and saves to JSON
"""

import re
import html
import json
import os
import glob
from datetime import datetime
from pathlib import Path

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
            cards.append(variant_card)

    return cards

def extract_cardmarket_cards(html_content):
    """Extract card data from Cardmarket purchase pages"""
    cards = []

    # Updated pattern for new Cardmarket HTML structure
    # Look for full table rows containing td elements with card links in format "CardName (SET NUM)"
    # This captures both the card info AND the full row content for variant detection
    row_pattern = r'<tr[^>]*>(.*?<td[^>]*class="(?:info|name[^"]*)"[^>]*>.*?<a[^>]*>([^<]*\([A-Z]+\s+\d+\))</a>.*?)</tr>'
    row_matches = re.findall(row_pattern, html_content, re.IGNORECASE | re.DOTALL)

    for row_content, card_text in row_matches:
        # Parse the card text in format "CardName (SET NUM)"
        # Extract card name and the (SET NUM) pattern
        card_match = re.match(r'^(.*?)\s*\(([A-Z]+)\s+(\d+)\)$', card_text.strip())
        if not card_match:
            continue

        card_name = html.unescape(card_match.group(1).strip())
        set_code = card_match.group(2).strip()
        card_number = card_match.group(3).strip()

        # Skip empty card names
        if not card_name:
            continue

        # Determine variant type by looking for "Reverse Holo" in the row content
        variant_type = 'Normal'
        if 'Reverse Holo' in row_content:
            variant_type = 'Reverse Holo'
        elif 'Holo' in row_content and 'Reverse Holo' not in row_content:
            variant_type = 'Holo'

        # Use set code as-is, no need for mapping
        set_name = f'Set {set_code}'

        card = {
            'name': card_name,
            'source': 'cardmarket',
            'variant_type': variant_type,
            'has_card': False,  # Cardmarket cards are pending delivery, not owned yet
            'set_code': set_code,
            'number': card_number.zfill(3) if card_number else None,  # Pad with zeros to match TCG format
            'set_name': set_name
        }

        cards.append(card)

    return cards

def build_set_mapping_from_tcg_cards(tcg_cards):
    """Build a mapping of set codes to set names from TCG Collector cards"""
    set_mapping = {}
    for card in tcg_cards:
        set_code = card.get('set_code')
        set_name = card.get('set_name')
        if set_code and set_name:
            set_mapping[set_code] = set_name
    return set_mapping

def extract_all_data():
    """Extract all card data from HTML files and return structured data"""
    # Set up data directory
    data_dir = Path("data")
    if not data_dir.exists():
        print("Error: data/ folder not found. Please create it and add your HTML files.")
        return None

    # Find all TCG Collector HTML files
    tcg_files = list(data_dir.glob("*TCG Collector*.html"))
    if not tcg_files:
        print("No TCG Collector HTML files found in data/ folder")
        return None

    # Find all Cardmarket HTML files
    cm_files = list(data_dir.glob("*Cardmarket*.html"))
    if not cm_files:
        print("No Cardmarket HTML files found in data/ folder (orders delivered/removed)")
        cm_files = []  # Continue with empty list instead of returning None

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
    if cm_files:
        for cm_file in cm_files:
            print(f"Reading Cardmarket file: {cm_file.name}")
            with open(cm_file, 'r', encoding='utf-8') as f:
                cm_content = f.read()

            cm_cards = extract_cardmarket_cards(cm_content)
            all_cm_cards.extend(cm_cards)
            print(f"  Found {len(cm_cards)} cards")
    else:
        print("No Cardmarket files to process")

    print(f"Total Cardmarket cards: {len(all_cm_cards)}")

    # Build set mapping
    set_mapping = build_set_mapping_from_tcg_cards(all_tcg_cards)

    # Update Cardmarket cards with proper set names
    for card in all_cm_cards:
        set_code = card.get('set_code')
        set_name = card.get('set_name')

        # Special handling for McDonald's sets - map different variations to the correct TCG set
        if set_name and "McDonald's Dragon Discovery" in set_name:
            # Map all McDonald's Dragon Discovery variations to the TCG version
            card['set_code'] = 'M24'
            card['set_name'] = "McDonald's Dragon Discovery 2024"
        elif set_code and set_code in set_mapping:
            card['set_name'] = set_mapping[set_code]

    # Get source file information for change detection
    source_files = {}
    for file_path in list(tcg_files) + list(cm_files):
        source_files[str(file_path)] = {
            'size': file_path.stat().st_size,
            'mtime': file_path.stat().st_mtime
        }

    # Print some sample data for debugging
    if all_tcg_cards:
        print("\nSample TCG Collector card:")
        print(all_tcg_cards[0])

    if all_cm_cards:
        print("\nSample Cardmarket card:")
        print(all_cm_cards[0])

    return {
        "extraction_timestamp": datetime.now().isoformat(),
        "tcg_cards": all_tcg_cards,
        "cardmarket_cards": all_cm_cards,
        "set_mapping": set_mapping,
        "source_files": source_files,
        "stats": {
            "tcg_files_count": len(tcg_files),
            "cardmarket_files_count": len(cm_files),
            "total_tcg_cards": len(all_tcg_cards),
            "total_cardmarket_cards": len(all_cm_cards)
        }
    }

def save_data(data, filename="card_data.json"):
    """Save extracted data to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Data saved to {filename}")

def main():
    """Main extraction function"""
    print("Extracting card data from HTML files...")

    data = extract_all_data()
    if data is None:
        return 1

    save_data(data)

    print(f"\nExtraction complete!")
    print(f"- {data['stats']['total_tcg_cards']} TCG Collector cards")
    print(f"- {data['stats']['total_cardmarket_cards']} Cardmarket cards")
    print(f"- {len(data['set_mapping'])} sets identified")

    return 0

if __name__ == "__main__":
    exit(main())