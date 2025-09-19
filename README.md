# Pokemon Card Collection Tracker

A Python tool that helps you track your Pokemon card collection by analyzing saved web pages from TCG Collector and Cardmarket, then generating beautiful HTML reports showing your collection progress.

## Features

- 📊 **Visual Progress Tracking**: Two-color progress bars showing owned cards (green) and pending purchases (gray)
- 🔍 **Card Preview**: Hover over camera icons to see card images
- 📈 **Set Statistics**: Completion percentages and detailed breakdowns by set
- 🎯 **Smart Sorting**: Sets ordered by completion percentage (owned + pending cards)
- 📱 **Responsive Design**: Works great on desktop and mobile

## Setup

### Prerequisites
- Python 3.6 or higher
- Required Python packages: `requests`, `beautifulsoup4`

### Installation
1. Clone or download this repository
2. Install required packages:
   ```bash
   pip install requests beautifulsoup4
   ```
3. Create a `data` folder in the project directory

## How to Use

### Step 1: Download TCG Collector Set Pages

1. Navigate to a Pokemon set page on TCG Collector (e.g., https://www.tcgcollector.com/sets/11636/surging-sparks)
2. **Important**: Ensure "List" view is selected (not "Grid" view) - look for the list/grid toggle buttons
3. Save the complete webpage to the `data` folder:
   - **Chrome/Edge**: Press `Ctrl+S` (Windows) or `Cmd+S` (Mac), choose "Webpage, Complete"
   - **Firefox**: Press `Ctrl+S` (Windows) or `Cmd+S` (Mac), choose "Web Page, complete"
4. Repeat for each Pokemon set you want to track

### Step 2: Download Cardmarket Purchase Pages

1. Go to your Cardmarket purchases: https://www.cardmarket.com/en/Pokemon/Orders/Purchases/Paid
2. Click on individual purchase orders to view the details
3. Save each purchase page to the `data` folder using the same method as above
4. Repeat for all relevant purchases

### Step 3: Run the Analysis

Execute the Python script:
```bash
python3 extract_cards.py
```

The script will:
- Scan the `data` folder for TCG Collector and Cardmarket files
- Extract card information and collection status
- Generate HTML reports

### Step 4: View Your Reports

The script generates several HTML files:

- **`index.html`** - Main overview page with all sets
- **Individual set pages** (e.g., `Surging_Sparks.html`) - Detailed card lists per set
- **`card_collection_report.html`** - Legacy single-page report

Open `index.html` in your web browser to start exploring your collection!

## Understanding the Reports

### Main Overview Page (`index.html`)

- **Overall Statistics**: Total cards tracked, owned, pending, and completion percentage
- **Set Grid**: Each set shows:
  - Progress bar with green (owned) and gray (pending purchase) sections
  - Completion statistics
  - Link to detailed set page

### Individual Set Pages

- **Detailed Card Lists**: Every card in the set with status indicators
- **Card Preview**: Hover over 📷 icons to see card images (when available)
- **Status Indicators**:
  - ✓ = You own this card
  - ✗ = You need this card
  - Different row colors indicate card status

### Status Legend

- **Green rows**: Cards you own
- **Gray rows**: Cards with pending purchases
- **White rows**: Cards you still need

## File Organization

```
pokemon-dupe-checker/
├── data/                          # Save web pages here
│   ├── [TCG Collector pages].html
│   └── [Cardmarket pages].html
├── extract_cards.py              # Main script
├── index.html                    # Generated overview report
├── [Set_Name].html               # Generated individual set reports
└── README.md                     # This file
```

## Tips for Best Results

### TCG Collector Pages
- Always use "List" view (not "Grid" view) for proper parsing
- Save the complete page including all CSS/JS files
- Make sure you're logged in to see your collection status

### Cardmarket Pages
- Save individual purchase detail pages, not the main purchases list
- Include both completed and pending orders for accurate tracking
- The script automatically detects which cards are pending vs. received

### Running the Script
- Re-run the script whenever you add new data files
- The script processes all files in the `data` folder each time
- Generated HTML files are automatically updated

## Troubleshooting

### Common Issues

**"Found 0 cards" for a set:**
- Check that you saved the page in "List" view, not "Grid" view
- Ensure the complete webpage was saved (including CSS/JS files)

**Cards not showing as owned:**
- Make sure you're logged into TCG Collector when saving pages
- Verify your collection status is visible on the original page

**Missing card images:**
- Card images are fetched from TCG Collector when available
- Some cards may not have images in their database

### Getting Help

If you encounter issues:
1. Check that all required Python packages are installed
2. Verify your saved HTML files are complete and not corrupted
3. Ensure you're using the correct view modes on the source websites

## Example Workflow

1. Visit https://www.tcgcollector.com/sets/11636/surging-sparks
2. Switch to "List" view if not already selected
3. Save as "Surging Sparks card list (International TCG) – TCG Collector.html"
4. Visit your recent Cardmarket purchases
5. Save individual purchase pages to the `data` folder
6. Run `python3 extract_cards.py`
7. Open `index.html` to view your collection dashboard

---

Happy collecting! 🎮✨