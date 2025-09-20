# Claude Development Guide

This document provides context for Claude AI assistants working on this Pokemon card collection tracker project.

## Project Overview

A Python-based tool that analyzes saved HTML pages from TCG Collector and Cardmarket to generate interactive reports showing Pokemon card collection progress, with integrated Cardmarket want list generation.

## Architecture

### Core Components

1. **extract_cards.py** - Main Python script that:
   - Parses TCG Collector HTML pages for card data and collection status
   - Parses Cardmarket purchase pages for pending/purchased cards
   - Generates HTML reports using template system
   - Creates various want list formats

2. **Templates System** (`templates/` folder):
   - **set_page.html** - Jinja2-style template for individual set pages
   - **cardmarket.js** - JavaScript for want list generation with CORS bypass
   - Uses `{{PLACEHOLDER}}` syntax for variable replacement

3. **Generated Files**:
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

## Important Code Patterns

### Template Variable Replacement
```python
# In extract_cards.py
html_content = html_template.replace('{{SET_NAME}}', html.escape(set_name))
html_content = html_content.replace('{{SET_CODE}}', html.escape(set_code))
html_content = html_content.replace('{{COMPLETION_PERCENT}}', f"{completion_percent:.1f}")
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

## File Structure

```
pokemon-dupe-checker/
├── extract_cards.py              # Main script
├── test_templates.py             # Template testing
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
- Process files efficiently (don't re-read unnecessarily)
- Use chunking for large datasets
- Cache API responses when possible

## Troubleshooting

### "No cards found" Issues
- Check HTML parsing logic in `extract_tcg_collector_cards()`
- Verify saved pages are in "List" view, not "Grid" view
- Ensure complete page saves (not just HTML source)

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
# Regenerate everything
python3 extract_cards.py

# Test templates only
python3 test_templates.py

# Check generated files
ls -la *.html want_list_*.txt

# Clean generated files
rm *.html want_list_*.txt test_template_output.html
```

---

*Last updated: Session that implemented filter-aware want list generation, visible card count display, and improved UX flow*