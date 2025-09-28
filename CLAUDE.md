# Claude Development Guide

This document provides context for Claude AI assistants working on this Pokemon card collection tracker project.

## Project Overview

A Python-based tool that analyzes saved HTML pages from TCG Collector and Cardmarket to generate interactive reports showing Pokemon card collection progress, with integrated Cardmarket want list generation.

## Architecture

### Core Components (Split Architecture)

1. **extract_cards.py** - Main orchestrator script that:
   - Manages the two-phase workflow (extraction + report generation)
   - Implements smart change detection using file timestamps
   - Provides command-line options for different workflows
   - Coordinates between data extraction and HTML generation phases

2. **extract_data.py** - Data extraction module that:
   - Parses TCG Collector HTML pages for card data and collection status
   - Parses Cardmarket purchase pages for pending/purchased cards
   - Saves structured data to `card_data.json` for caching
   - Handles all HTML parsing and data normalization

3. **generate_reports.py** - Report generation module that:
   - Loads cached data from `card_data.json`
   - Generates HTML reports using template system
   - Creates various want list formats
   - Handles all presentation logic and file output

4. **Templates System** (`templates/` folder):
   - **set_page.html** - Jinja2-style template for individual set pages
   - **cardmarket.js** - JavaScript for want list generation with CORS bypass
   - Uses `{{PLACEHOLDER}}` syntax for variable replacement

5. **Data Cache**:
   - **card_data.json** - Structured data cache with extraction metadata
   - Enables fast report regeneration without re-parsing HTML
   - Includes timestamps and file metadata for change detection

6. **Generated Files**:
   - **index.html** - Main overview with all sets
   - **[Set_Name].html** - Individual set pages with detailed card lists
   - **want_list_*.txt** - Various want list formats

## Key Technical Decisions

### Template System
- **Problem**: Originally had mixed HTML/CSS/JS embedded in Python strings
- **Solution**: Extracted to separate template files with placeholder replacement
- **Benefit**: Clean separation of concerns, maintainable code

### CORS Bypass for Want List Generation
- **Problem**: Browser CORS policy blocked direct API calls to pokedata.ovh
- **Solution**: Use `corsproxy.io` as proxy service
- **Implementation**: `templates/cardmarket.js` handles the proxied requests

### JavaScript Escape Sequences
- **Problem**: Python f-strings were double-escaping JavaScript regex patterns
- **Solution**: Use simple string replacement instead of f-string interpolation
- **Example**: `/https:\/\/static\.tcgcollector\.com/` (correct) vs `/https:\\/\\/static\\.tcgcollector\\.com/` (broken)

### Card Number Formatting
- **Problem**: pokedata.ovh API requires card numbers without leading zeros
- **Solution**: Strip leading zeros in JavaScript: `card.number.replace(/^0+/, '') || card.number`

### Cardmarket Limits
- **Problem**: Cardmarket want lists limited to 150 cards
- **Solution**: Split large lists into chunks of 150 cards each

### Variant Filtering System
- **Problem**: Users wanted to filter card variants and see cleaner views
- **Solution**: Implemented multi-mode filtering with intelligent "Best" logic
- **Implementation**: Client-side JavaScript filtering with stable table layout

### Filter-Aware Want List Generation
- **Problem**: Users wanted separate want lists for normal vs reverse holo variants
- **Solution**: Modified want list generation to respect current table filters
- **Implementation**: Want list only processes visible table rows, moved UI below filters

### Filtered Item Count Display
- **Problem**: Users needed to see how many cards are visible after filtering
- **Solution**: Added dynamic count display showing "X of Y cards" or "Showing all X cards"
- **Implementation**: JavaScript updates count in real-time as filters change

### Split Architecture for Performance
- **Problem**: HTML parsing was slow (minutes), making development cycles painful
- **Solution**: Separated data extraction from report generation with JSON caching
- **Benefits**:
  - Data extraction: Only runs when HTML files change (smart timestamp detection)
  - Report generation: Fast regeneration (seconds) for template/UI changes
  - Development workflow: Use `--reports-only` for rapid iteration
- **Implementation**: Three-file architecture with orchestrator pattern

### Cardmarket HTML Structure Changes (2025 A/B Testing)
- **Problem**: Cardmarket changed HTML structure, breaking extraction (0 cards extracted)
- **Old Pattern**: Used `data-name`, `data-expansion-name`, `data-number` attributes
- **New Pattern**: Card data in `<td class="info">` and `<td class="name">` elements with format "CardName (SET NUM)"
- **Solution**: Updated regex to match actual table structure, extract set codes directly from content
- **Implementation**: `extract_data.py:189` - captures full table rows for variant detection

### Variant-Specific Deduplication
- **Problem**: Deduplication matched across different variants (Normal vs Reverse Holo)
- **Example**: Chansey (TWM 133) Reverse Holo marked as "Need" when Normal variant was pending
- **Solution**: Match exact variants using `{set_code}_{number}_{variant}` keys
- **Implementation**: `generate_reports.py:564-578` - precise variant matching instead of cross-matching

### Progress Bar Consistency
- **Problem**: Set pages had simple green progress bars, index.html had green+gray segments
- **Solution**: Added pending (gray) segments to all set page progress bars
- **Implementation**: Updated `templates/set_page.html` with two-segment progress bars matching index.html style
- **Visual**: Shows both owned (green) and pending delivery (gray) progress in all views

## Important Code Patterns

### Template Variable Replacement
```python
# In generate_reports.py
html_content = html_template.replace('{{SET_NAME}}', html.escape(set_name))
html_content = html_content.replace('{{SET_CODE}}', html.escape(set_code))
html_content = html_content.replace('{{COMPLETION_PERCENT}}', f"{completion_percent:.1f}")
```

### Data Cache Management
```python
# In extract_data.py - Save structured data
def save_data(data, filename="card_data.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# In generate_reports.py - Load cached data
def load_card_data(filename="card_data.json"):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
```

### Smart Change Detection
```python
# In extract_cards.py - Check if re-extraction is needed
def needs_reextraction():
    data_file = Path('card_data.json')
    if not data_file.exists():
        return True

    data_mtime = data_file.stat().st_mtime
    html_files = glob.glob('data/*.html')

    for html_file in html_files:
        if os.path.getmtime(html_file) > data_mtime:
            return True
    return False
```

### Updated Cardmarket Extraction Pattern
```python
# In extract_data.py - Updated HTML parsing for 2025 structure
row_pattern = r'<tr[^>]*>(.*?<td[^>]*class="(?:info|name[^"]*)"[^>]*>.*?<a[^>]*>([^<]*\([A-Z]+\s+\d+\))</a>.*?)</tr>'
row_matches = re.findall(row_pattern, html_content, re.IGNORECASE | re.DOTALL)

for row_content, card_text in row_matches:
    # Parse "CardName (SET NUM)" format
    card_match = re.match(r'^(.*?)\s*\(([A-Z]+)\s+(\d+)\)$', card_text.strip())
    set_code = card_match.group(2)  # Extract directly, no hardcoded mappings

    # Detect variants from full row content
    if 'Reverse Holo' in row_content:
        variant_type = 'Reverse Holo'
```

### Variant-Specific Deduplication Logic
```python
# In generate_reports.py - Exact variant matching
for card in cm_cards:
    card_variant = card.get('variant_type', 'Normal')
    card_key = f"{card.get('set_code', 'UNK')}_{card.get('number', 'XXX')}_{card_variant}"

    if card_key in all_cards:
        # Mark EXACT variant as pending delivery
        all_cards[card_key]['status'] = 'pending_delivery'
```

### CORS Proxy Usage
```javascript
// In templates/cardmarket.js
const proxyUrl = 'https://corsproxy.io/?' + encodeURIComponent('https://www.pokedata.ovh/misc/cardmarket');
const response = await fetch(proxyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'decklist=' + encodeURIComponent(chunk)
});
```

### Card Deduplication
```javascript
// Remove variants, keep one entry per card name
const uniqueCards = {};
wantCards.forEach(card => {
    const key = card.name + '_' + setCode;
    if (!uniqueCards[key]) {
        uniqueCards[key] = card;
    }
});
```

### Variant Filtering Logic
```javascript
// "Best" filter prioritization
var ownedReverseHolo = group.find(item => item.hasCard && item.variant === "Reverse Holo");
var ownedNormal = group.find(item => item.hasCard && item.variant === "Normal");
var anyNormal = group.find(item => item.variant === "Normal");
var anyReverseHolo = group.find(item => item.variant === "Reverse Holo");

// Priority: owned reverse holo > owned normal > unowned normal > unowned reverse holo
if (ownedReverseHolo) {
    bestRow = ownedReverseHolo.row;
} else if (ownedNormal) {
    bestRow = ownedNormal.row;
} else if (anyNormal) {
    bestRow = anyNormal.row;
} else if (anyReverseHolo) {
    bestRow = anyReverseHolo.row;
}
```

### Filter-Aware Want List Generation
```javascript
// Only process visible rows that need cards
for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const cells = row.getElementsByTagName('td');

    // Only process visible rows that need cards
    if (row.style.display !== 'none' && cells.length >= 7) {
        const status = cells[6].textContent;
        if (status === 'Need') {
            // Add to want list
        }
    }
}
```

### Dynamic Item Count Display
```javascript
// Update visible count display
var totalRows = document.getElementById("cardTable").getElementsByTagName("tr").length - 1; // -1 for header
var countElement = document.getElementById("visibleCount");
if (finalVisibleCount === totalRows) {
    countElement.textContent = "Showing all " + totalRows + " cards";
} else {
    countElement.textContent = "Showing " + finalVisibleCount + " of " + totalRows + " cards";
}
```

### Stable Table Layout
```css
/* Fixed table layout prevents column jumping */
table { table-layout: fixed; }
th:nth-child(1), td:nth-child(1) { width: 8%; }  /* Preview */
th:nth-child(4), td:nth-child(4) { width: 40%; } /* Card Name */
/* Text overflow handling */
th, td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
td:hover { overflow: visible; white-space: normal; }
```

## Common Tasks

### Adding New Template Variables
1. Add `{{NEW_VARIABLE}}` to relevant template file
2. Add replacement in `generate_individual_set_page()` function:
   ```python
   html_content = html_content.replace('{{NEW_VARIABLE}}', str(value))
   ```

### Debugging JavaScript Issues
- Check browser console for errors
- Common issues: escape sequences, CORS errors, API response parsing
- Test template system with `python3 test_templates.py`

### Updating Want List Logic
- Main logic in `templates/cardmarket.js`
- Test with sets that have >150 cards to verify chunking
- Verify card number formatting (no leading zeros)

### Modifying Variant Filter Logic
- Filtering logic in `templates/set_page.html` within `filterTable()` function
- "Best" filter logic prioritizes owned reverse holo, then owned normal, then unowned normal
- Test with sets containing both normal and reverse holo variants
- Column widths defined in CSS prevent layout jumping

### Working with Filter-Aware Want Lists
- Want list generation logic in `templates/cardmarket.js`
- Only processes rows where `row.style.display !== 'none'`
- UI positioned below filters for intuitive workflow: filter first, then generate
- Button text clarifies it works on "filtered cards"
- Status messages reflect "currently filtered view" instead of entire set

## Testing

### Template Testing
```bash
python3 test_templates.py
```
Generates `test_template_output.html` for verification.

### Full System Test
```bash
python3 extract_cards.py
```
Processes all data files and regenerates everything.

### Performance Testing
```bash
# Test data extraction only
python3 extract_cards.py --extract

# Test report generation only (fast)
python3 extract_cards.py --reports-only

# Check current data status
python3 extract_cards.py --info
```

## File Structure

```
pokemon-dupe-checker/
├── extract_cards.py              # Main orchestrator script
├── extract_data.py               # Data extraction from HTML files
├── generate_reports.py           # HTML report generation
├── test_templates.py             # Template testing
├── card_data.json                # Extracted data cache (auto-generated)
├── templates/
│   ├── set_page.html             # Set page template
│   └── cardmarket.js             # Want list JavaScript
├── data/                         # User's saved HTML files
├── *.html                        # Generated reports
└── want_list_*.txt              # Generated want lists
```

## Development Guidelines

### Code Style
- Use descriptive variable names
- Keep functions focused on single responsibilities
- Comment complex logic, especially regex patterns
- Follow existing patterns for consistency

### Error Handling
- Always handle API failures gracefully
- Provide user-friendly error messages
- Log detailed errors to console for debugging

### Performance
- Use split architecture: extract data only when HTML files change
- Cache structured data in JSON for fast report regeneration
- Use `--reports-only` for rapid development iteration
- Use chunking for large datasets
- Cache API responses when possible

## Troubleshooting

### "No cards found" Issues
- Check HTML parsing logic in `extract_tcg_collector_cards()` (in extract_data.py)
- Verify saved pages are in "List" view, not "Grid" view
- Ensure complete page saves (not just HTML source)

### Cardmarket Extraction Issues (2025+)
- **Symptom**: 0 Cardmarket cards extracted despite files being present
- **Cause**: Cardmarket changed HTML structure (A/B testing)
- **Check**: Look for `<td class="info">` or `<td class="name">` elements with "CardName (SET NUM)" format
- **Fix**: Update regex pattern in `extract_data.py:189` to match current structure
- **Verification**: Test with `grep -o -E 'class="(?:info|name[^"]*)".*\([A-Z]+ [0-9]+\)' data/Purchase*.html`

### Variant Deduplication Issues
- **Symptom**: Cards showing "Need" when different variant is pending (e.g., RH vs Normal)
- **Cause**: Deduplication matching across variants instead of exact variants
- **Fix**: Ensure `{set_code}_{number}_{variant}` key format in `generate_reports.py:565`
- **Test**: Check specific card like "Chansey (TWM 133) Reverse Holo" shows "Pending Delivery"

### Want List Generation Failures
- Check browser network tab for CORS/proxy issues
- Verify API response format in `templates/cardmarket.js`
- Test with smaller card lists first

### Template Rendering Issues
- Check placeholder syntax matches exactly
- Verify all variables are being replaced
- Test with `test_templates.py`

## API Dependencies

### pokedata.ovh
- **Purpose**: Converts decklist format to Cardmarket format with abilities
- **Endpoint**: `https://www.pokedata.ovh/misc/cardmarket`
- **Method**: POST with `decklist=...` form data
- **Rate Limits**: Unknown, use reasonable delays between requests

### corsproxy.io
- **Purpose**: CORS bypass for browser-based API calls
- **Usage**: Prefix target URL with `https://corsproxy.io/?`
- **Reliability**: Third-party service, have fallback plan

## Future Improvements

### Potential Enhancements
- Local caching of API responses
- Offline mode for want list generation
- Additional output formats
- Set completion notifications
- Integration with other card databases

### Code Cleanup Opportunities
- Consolidate duplicate set mapping functions
- Add type hints to Python functions
- Extract constants to configuration file
- Add comprehensive test suite

## Quick Reference Commands

```bash
# Full workflow (smart: only extracts if HTML files changed)
python3 extract_cards.py

# Fast report regeneration (seconds instead of minutes)
python3 extract_cards.py --reports-only

# Force data re-extraction (when troubleshooting)
python3 extract_cards.py --extract

# Check current data status
python3 extract_cards.py --info

# Test templates only
python3 test_templates.py

# Check generated files
ls -la *.html want_list_*.txt card_data.json

# Clean generated files (keeps data cache)
rm *.html want_list_*.txt test_template_output.html

# Clean everything including cache (forces full re-extraction)
rm *.html want_list_*.txt card_data.json test_template_output.html
```

---

*Last updated: Session that fixed secret card metrics calculation bug (2025-09-28)*

## Recent Major Fixes (2025-09-28)

### Secret Card Metrics Calculation Bug Resolution
- **Issue**: "Secret cards only" filter showed wildly incorrect counts (714 owned, 168 pending instead of 4 owned, 0 pending)
- **Root Cause**: Overall metrics calculated by treating all cards from all sets as single set, using first `total_count` found
- **Problem**: Each set has different `total_count` values (e.g., MEW=165, WHT=86) for determining secret cards (cards numbered above set limit)
- **Fix**: Calculate metrics per set individually first, then sum up to get accurate overall totals
- **Implementation**: Modified `generate_set_overview_page()` in `generate_reports.py:264-288`
- **Impact**: Secret card filter now shows correct counts: 1055 total, 4 owned, 0 pending across all sets
- **Key Learning**: When aggregating metrics across multiple datasets with different rules, always calculate per-dataset first then sum

### Previous Major Fixes (2025-09-22)

### Cardmarket Extraction Crisis Resolution
- **Issue**: Cardmarket website A/B testing broke extraction completely (0 cards → 1331 cards)
- **Root Cause**: Changed from `data-*` attributes to `<td class="info/name">` structure
- **Fix**: Complete rewrite of extraction pattern to match "CardName (SET NUM)" format
- **Impact**: Tool now reliably extracts all pending deliveries from Cardmarket orders

### Deduplication Accuracy Improvement
- **Issue**: Cross-variant matching caused incorrect "Need" status for owned variants
- **Example**: Chansey (TWM 133) RH showing "Need" when Normal variant pending delivery
- **Fix**: Exact variant matching using composite keys
- **Impact**: Perfect accuracy in duplicate detection across Normal/Reverse Holo/Holo variants

### UI Consistency Enhancement
- **Issue**: Progress bars inconsistent between overview and set pages
- **Fix**: Added pending (gray) segments to all set page progress bars
- **Impact**: Uniform visual representation of owned vs pending cards across all views

These fixes resolved critical reliability issues making the tool production-ready for accurate collection tracking and duplicate detection.
- Avoid at all costs hardcoding any data.  Set codes, card numbers, etc should always come from the source data - the tcgcollector html files.