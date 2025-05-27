#!/usr/bin/env python3
"""
Script to update specific satellites in satellites.json from CelesTrak.

Usage:
    python update_specific.py ISS HUBBLE
    python update_specific.py --all
    python update_specific.py --catalog 25544 20580
"""

import json
import requests
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List


def extract_catalog_number(tle_line1: str) -> Optional[str]:
    """Extract catalog number from TLE line 1."""
    match = re.match(r'1\s+(\d+)', tle_line1.strip())
    if match:
        return match.group(1)
    return None


def fetch_tle_from_celestrak(catalog_number: str) -> Optional[Dict[str, str]]:
    """Fetch TLE data for a satellite from CelesTrak."""
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_number}&FORMAT=TLE"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        lines = response.text.strip().split('\n')
        
        if len(lines) >= 3:
            return {
                'tle_line1': lines[1].strip(),
                'tle_line2': lines[2].strip()
            }
        elif len(lines) == 2:
            return {
                'tle_line1': lines[0].strip(),
                'tle_line2': lines[1].strip()
            }
            
    except requests.RequestException as e:
        print(f"Error fetching data for catalog {catalog_number}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error for catalog {catalog_number}: {e}")
        return None
    
    return None


def update_specific_satellites(json_file_path: str, satellite_keys: List[str] = None, 
                             catalog_numbers: List[str] = None, update_all: bool = False) -> bool:
    """Update specific satellites in satellites.json."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            satellites_data = json.load(f)
        
        total_satellites = len(satellites_data)
        updated_count = 0
        failed_count = 0
        
        # Determine which satellites to update
        satellites_to_update = []
        
        if update_all:
            satellites_to_update = list(satellites_data.keys())
            print(f"Updating all {total_satellites} satellites...")
        elif catalog_numbers:
            # Find satellites by catalog number
            for cat_num in catalog_numbers:
                found = False
                for sat_key, sat_data in satellites_data.items():
                    existing_cat_num = extract_catalog_number(sat_data.get('tle_line1', ''))
                    if existing_cat_num == cat_num:
                        satellites_to_update.append(sat_key)
                        found = True
                        break
                if not found:
                    print(f"Warning: No satellite found with catalog number {cat_num}")
        elif satellite_keys:
            # Validate satellite keys exist
            for sat_key in satellite_keys:
                if sat_key in satellites_data:
                    satellites_to_update.append(sat_key)
                else:
                    print(f"Warning: Satellite '{sat_key}' not found in database")
                    available_keys = list(satellites_data.keys())
                    print(f"Available satellites: {', '.join(available_keys)}")
        else:
            print("No satellites specified for update")
            return False
        
        if not satellites_to_update:
            print("No valid satellites to update")
            return False
        
        print(f"Updating {len(satellites_to_update)} satellites:")
        print(f"  {', '.join(satellites_to_update)}")
        print()
        
        # Update each selected satellite
        for sat_key in satellites_to_update:
            sat_data = satellites_data[sat_key]
            print(f"Processing {sat_key} ({sat_data.get('name', 'Unknown')})...")
            
            # Extract catalog number
            catalog_number = extract_catalog_number(sat_data.get('tle_line1', ''))
            
            if not catalog_number:
                print(f"  Warning: Could not extract catalog number for {sat_key}")
                failed_count += 1
                continue
            
            print(f"  Catalog number: {catalog_number}")
            
            # Fetch updated TLE data
            new_tle_data = fetch_tle_from_celestrak(catalog_number)
            
            if new_tle_data:
                old_tle1 = sat_data.get('tle_line1', '')
                old_tle2 = sat_data.get('tle_line2', '')
                
                sat_data['tle_line1'] = new_tle_data['tle_line1']
                sat_data['tle_line2'] = new_tle_data['tle_line2']
                
                if (old_tle1 != new_tle_data['tle_line1'] or 
                    old_tle2 != new_tle_data['tle_line2']):
                    print(f"  ✓ Updated TLE data")
                    updated_count += 1
                else:
                    print(f"  - No changes (data already current)")
            else:
                print(f"  ✗ Failed to fetch updated data")
                failed_count += 1
        
        # Write updated data back to file
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(satellites_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nUpdate complete!")
        print(f"  Updated: {updated_count} satellites")
        print(f"  Failed: {failed_count} satellites")
        print(f"  Processed: {len(satellites_to_update)} satellites")
        
        return failed_count == 0
        
    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_file_path}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def list_satellites(json_file_path: str):
    """List all available satellites."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            satellites_data = json.load(f)
        
        print("Available satellites:")
        print("=" * 50)
        for sat_key, sat_data in satellites_data.items():
            name = sat_data.get('name', 'Unknown')
            catalog_num = extract_catalog_number(sat_data.get('tle_line1', ''))
            print(f"  {sat_key:<15} | {name:<30} | Cat: {catalog_num}")
        
    except Exception as e:
        print(f"Error listing satellites: {e}")


def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Update specific satellites in satellites.json from CelesTrak',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_specific.py ISS HUBBLE
  python update_specific.py --all
  python update_specific.py --catalog 25544 20580
  python update_specific.py --list
        """)
    
    parser.add_argument('satellites', nargs='*', 
                       help='Satellite keys to update (e.g., ISS HUBBLE)')
    parser.add_argument('--all', action='store_true',
                       help='Update all satellites')
    parser.add_argument('--catalog', nargs='+', metavar='NUMBER',
                       help='Update satellites by catalog number')
    parser.add_argument('--list', action='store_true',
                       help='List all available satellites')
    
    args = parser.parse_args()
    
    # Get the script directory and construct path to satellites.json
    script_dir = Path(__file__).parent
    satellites_json_path = script_dir / "satellites.json"
    
    if not satellites_json_path.exists():
        print(f"Error: {satellites_json_path} does not exist")
        sys.exit(1)
    
    # Handle list command
    if args.list:
        list_satellites(str(satellites_json_path))
        return
    
    # Validate arguments
    if not args.all and not args.satellites and not args.catalog:
        print("Error: Must specify satellites to update or use --all")
        print("Use --help for usage information or --list to see available satellites")
        sys.exit(1)
    
    if sum([bool(args.all), bool(args.satellites), bool(args.catalog)]) > 1:
        print("Error: Can only use one of --all, satellite names, or --catalog")
        sys.exit(1)
    
    print("Selective TLE Data Updater")
    print("=" * 40)
    print(f"Target file: {satellites_json_path}")
    print()
    
    # Perform the update
    success = update_specific_satellites(
        str(satellites_json_path),
        satellite_keys=args.satellites,
        catalog_numbers=args.catalog,
        update_all=args.all
    )
    
    if success:
        print("\n✓ Selected satellites updated successfully!")
        sys.exit(0)
    else:
        print("\n⚠ Some satellites failed to update. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()