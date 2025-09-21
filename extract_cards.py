#!/usr/bin/env python3
"""
Pokemon Card Collection Tracker
Smart orchestrator that separates data extraction from report generation
"""

import os
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime

def needs_reextraction():
    """Check if data needs to be re-extracted from HTML files"""
    data_file = Path('card_data.json')

    # If no data file exists, we need to extract
    if not data_file.exists():
        return True

    # Get data file timestamp
    data_mtime = data_file.stat().st_mtime

    # Check if any HTML files are newer than the data file
    html_files = glob.glob('data/*.html')
    if not html_files:
        print("Warning: No HTML files found in data/ folder")
        return False

    newer_files = []
    for html_file in html_files:
        if os.path.getmtime(html_file) > data_mtime:
            newer_files.append(html_file)

    if newer_files:
        print(f"Found {len(newer_files)} HTML files newer than extracted data:")
        for file in newer_files[:5]:  # Show first 5
            print(f"  - {os.path.basename(file)}")
        if len(newer_files) > 5:
            print(f"  ... and {len(newer_files) - 5} more")
        return True

    return False

def get_data_info():
    """Get information about the current extracted data"""
    data_file = Path('card_data.json')
    if not data_file.exists():
        return None

    try:
        with open(data_file, 'r') as f:
            data = json.load(f)

        return {
            'timestamp': data.get('extraction_timestamp'),
            'tcg_cards': data.get('stats', {}).get('total_tcg_cards', 0),
            'cardmarket_cards': data.get('stats', {}).get('total_cardmarket_cards', 0),
            'sets': len(data.get('set_mapping', {}))
        }
    except Exception as e:
        print(f"Error reading data file: {e}")
        return None

def run_extraction():
    """Run the data extraction process"""
    print("=" * 60)
    print("PHASE 1: DATA EXTRACTION")
    print("=" * 60)

    # Import and run the extraction
    try:
        from extract_data import main as extract_main
        result = extract_main()
        if result != 0:
            print("Data extraction failed!")
            return False
        print("Data extraction completed successfully!")
        return True
    except ImportError:
        print("Error: extract_data.py not found!")
        return False
    except Exception as e:
        print(f"Error during extraction: {e}")
        return False

def run_report_generation(force_all=False):
    """Run the report generation process"""
    print("\n" + "=" * 60)
    print("PHASE 2: REPORT GENERATION")
    print("=" * 60)

    # Import and run the report generation
    try:
        from generate_reports import main as reports_main
        result = reports_main(force_all=force_all)
        if result != 0:
            print("Report generation failed!")
            return False
        print("Report generation completed successfully!")
        return True
    except ImportError:
        print("Error: generate_reports.py not found!")
        return False
    except Exception as e:
        print(f"Error during report generation: {e}")
        return False

def main():
    """Main orchestrator function"""
    parser = argparse.ArgumentParser(description='Pokemon Card Collection Tracker')
    parser.add_argument('--extract', action='store_true',
                       help='Force data extraction even if not needed')
    parser.add_argument('--reports-only', action='store_true',
                       help='Only generate reports (skip extraction)')
    parser.add_argument('--info', action='store_true',
                       help='Show information about current data')

    args = parser.parse_args()

    # Show data info if requested
    if args.info:
        info = get_data_info()
        if info:
            print("Current extracted data:")
            print(f"  Extracted: {info['timestamp']}")
            print(f"  TCG cards: {info['tcg_cards']}")
            print(f"  Cardmarket cards: {info['cardmarket_cards']}")
            print(f"  Sets: {info['sets']}")
        else:
            print("No extracted data found. Run with --extract to create it.")
        return 0

    # Check if we need extraction
    needs_extraction = needs_reextraction() or args.extract

    if args.reports_only:
        needs_extraction = False
        print("Skipping extraction (--reports-only specified)")

    # Show current data info
    info = get_data_info()
    if info and not needs_extraction:
        print("Using existing extracted data:")
        print(f"  Extracted: {info['timestamp']}")
        print(f"  TCG cards: {info['tcg_cards']}")
        print(f"  Cardmarket cards: {info['cardmarket_cards']}")
        print(f"  Sets: {info['sets']}")

    # Phase 1: Data Extraction (if needed)
    if needs_extraction:
        print("Data extraction needed...")
        if not run_extraction():
            return 1
    else:
        print("Data extraction not needed (HTML files unchanged)")

    # Phase 2: Report Generation
    # Force regeneration of all files if we just extracted new data
    force_all_reports = needs_extraction
    if not run_report_generation(force_all=force_all_reports):
        return 1

    print("\n" + "=" * 60)
    print("COMPLETE! 🎉")
    print("=" * 60)
    print("Open index.html to view your collection!")

    return 0

if __name__ == "__main__":
    exit(main())