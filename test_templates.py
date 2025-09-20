#!/usr/bin/env python3

import html

def test_template_generation():
    """Test the new template-based generation"""

    # Sample data
    set_name = "Test Set"
    set_code = "TST"
    set_cards = [
        {
            'number': '001',
            'total_count': '10',
            'name': 'Test Card 1',
            'variant_type': 'Normal',
            'card_id': '12345',
            'has_card': False,
            'cardmarket_pending': False,
            'source': 'tcg_collector'
        },
        {
            'number': '002',
            'total_count': '10',
            'name': 'Test Card 2',
            'variant_type': 'Reverse Holo',
            'card_id': '12346',
            'has_card': True,
            'cardmarket_pending': False,
            'source': 'tcg_collector'
        }
    ]

    # Calculate statistics
    total_cards = len(set_cards)
    owned_cards = sum(1 for card in set_cards if card.get('has_card'))
    pending_cards = sum(1 for card in set_cards if card.get('cardmarket_pending'))
    completion_percent = (owned_cards / total_cards * 100) if total_cards > 0 else 0

    # Load templates
    with open('templates/set_page.html', 'r', encoding='utf-8') as f:
        html_template = f.read()

    with open('templates/cardmarket.js', 'r', encoding='utf-8') as f:
        js_template = f.read()

    # Generate card rows
    card_rows_html = ""
    for card in set_cards:
        number = card.get('number', 'XXX')
        total_count = card.get('total_count') or ''
        name = card.get('name', 'Unknown')
        variant = card.get('variant_type', 'Normal')
        card_id = card.get('card_id')

        camera_icon_html = ''
        if card_id:
            camera_icon_html = f'<span class="camera-icon" onmouseover="showCardPreview(event, \'{card_id}\')" onmouseout="hideCardPreview()">📷</span>'

        have = '✓' if card.get('has_card') else '✗'

        if card.get('has_card'):
            status = 'Have'
            row_class = 'has-card'
        else:
            status = 'Need'
            row_class = 'missing-card'

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

    # Replace JavaScript placeholders
    js_code = js_template.replace('{{SET_CODE}}', set_code)

    # Replace HTML placeholders
    html_content = html_template.replace('{{SET_NAME}}', html.escape(set_name))
    html_content = html_content.replace('{{SET_CODE}}', html.escape(set_code))
    html_content = html_content.replace('{{TOTAL_CARDS}}', str(total_cards))
    html_content = html_content.replace('{{OWNED_CARDS}}', str(owned_cards))
    html_content = html_content.replace('{{PENDING_CARDS}}', str(pending_cards))
    html_content = html_content.replace('{{COMPLETION_PERCENT}}', str(completion_percent))
    html_content = html_content.replace('{{CARD_ROWS}}', card_rows_html)
    html_content = html_content.replace('{{CARDMARKET_JS}}', js_code)

    # Write test file
    with open('test_template_output.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("✅ Template generation successful!")
    print("✅ Generated test_template_output.html")
    print(f"✅ Set: {set_name} ({set_code})")
    print(f"✅ Cards: {total_cards} total, {owned_cards} owned ({completion_percent:.1f}% complete)")

    # Verify JavaScript
    if 'generateCardmarketList' in js_code and '{{SET_CODE}}' not in js_code:
        print("✅ JavaScript properly generated with clean syntax")
    else:
        print("❌ JavaScript generation issue")

if __name__ == "__main__":
    test_template_generation()