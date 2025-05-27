#!/usr/bin/env python3
"""
Script to update TLE (Two-Line Element) data in satellites.json from CelesTrak.

This script fetches the latest orbital data for satellites from CelesTrak's
REST API and updates the local satellites.json file.
"""

import json
import requests
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def extract_catalog_number(tle_line1: str) -> Optional[str]:
    """
    Extract catalog number from TLE line 1.
    
    Args:
        tle_line1: First line of TLE data
        
    Returns:
        Catalog number as string, or None if not found
    """
    # TLE line 1 format: 1 NNNNN... where NNNNN is the catalog number
    match = re.match(r'1\s+(\d+)', tle_line1.strip())
    if match:
        return match.group(1)
    return None


def fetch_tle_from_celestrak(catalog_number: str) -> Optional[Dict[str, str]]:
    """
    Fetch TLE data for a satellite from CelesTrak.
    
    Args:
        catalog_number: Satellite catalog number
        
    Returns:
        Dictionary with tle_line1 and tle_line2, or None if failed
    """
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_number}&FORMAT=TLE"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        lines = response.text.strip().split('\n')
        
        # TLE format has 3 lines: name, line1, line2
        if len(lines) >= 3:
            return {
                'tle_line1': lines[1].strip(),
                'tle_line2': lines[2].strip()
            }
        elif len(lines) == 2:
            # Sometimes only 2 lines are returned
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


def update_satellites_json(json_file_path: str) -> bool:
    """
    Update satellites.json with latest TLE data from CelesTrak.
    
    Args:
        json_file_path: Path to satellites.json file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read current satellites data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            satellites_data = json.load(f)
        
        print(f"Loaded {len(satellites_data)} satellites from {json_file_path}")
        
        updated_count = 0
        failed_count = 0
        
        # Update each satellite
        for sat_key, sat_data in satellites_data.items():
            print(f"Processing {sat_key} ({sat_data.get('name', 'Unknown')})...")
            
            # Extract catalog number from current TLE data
            catalog_number = extract_catalog_number(sat_data.get('tle_line1', ''))
            
            if not catalog_number:
                print(f"  Warning: Could not extract catalog number for {sat_key}")
                failed_count += 1
                continue
            
            print(f"  Catalog number: {catalog_number}")
            
            # Fetch updated TLE data
            new_tle_data = fetch_tle_from_celestrak(catalog_number)
            
            if new_tle_data:
                # Update TLE data while preserving other fields
                old_tle1 = sat_data.get('tle_line1', '')
                old_tle2 = sat_data.get('tle_line2', '')
                
                sat_data['tle_line1'] = new_tle_data['tle_line1']
                sat_data['tle_line2'] = new_tle_data['tle_line2']
                
                # Check if data actually changed
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
        print(f"  Total: {len(satellites_data)} satellites")
        
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


def main():
    """Main function to run the TLE update process."""
    # Get the script directory and construct path to satellites.json
    script_dir = Path(__file__).parent
    satellites_json_path = script_dir / "satellites.json"
    
    print("TLE Data Updater for satellites.json")
    print("=" * 40)
    print(f"Target file: {satellites_json_path}")
    print()
    
    if not satellites_json_path.exists():
        print(f"Error: {satellites_json_path} does not exist")
        sys.exit(1)
    
    # Perform the update
    success = update_satellites_json(str(satellites_json_path))
    
    if success:
        print("\n✓ All satellites updated successfully!")
        sys.exit(0)
    else:
        print("\n⚠ Some satellites failed to update. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()