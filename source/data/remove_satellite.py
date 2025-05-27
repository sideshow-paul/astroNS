#!/usr/bin/env python3
"""
Script to remove satellites from satellites.json.

Usage:
    python remove_satellite.py ISS HUBBLE
    python remove_satellite.py --catalog 25544 20580
    python remove_satellite.py --key JWST
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List


def extract_catalog_number(tle_line1: str) -> str:
    """Extract catalog number from TLE line 1."""
    import re
    match = re.match(r'1\s+(\d+)', tle_line1.strip())
    if match:
        return match.group(1)
    return ""


def remove_satellites_from_json(json_file_path: str, satellite_keys: List[str] = None, 
                               catalog_numbers: List[str] = None, force: bool = False) -> bool:
    """Remove satellites from satellites.json."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            satellites_data = json.load(f)
        
        initial_count = len(satellites_data)
        removed_count = 0
        not_found_count = 0
        
        satellites_to_remove = []
        
        if catalog_numbers:
            # Find satellites by catalog number
            for cat_num in catalog_numbers:
                found = False
                for sat_key, sat_data in satellites_data.items():
                    existing_cat_num = extract_catalog_number(sat_data.get('tle_line1', ''))
                    if existing_cat_num == cat_num:
                        satellites_to_remove.append(sat_key)
                        found = True
                        break
                if not found:
                    print(f"Warning: No satellite found with catalog number {cat_num}")
                    not_found_count += 1
        elif satellite_keys:
            # Remove by satellite keys
            for sat_key in satellite_keys:
                if sat_key in satellites_data:
                    satellites_to_remove.append(sat_key)
                else:
                    print(f"Warning: Satellite '{sat_key}' not found in database")
                    available_keys = list(satellites_data.keys())
                    print(f"Available satellites: {', '.join(available_keys)}")
                    not_found_count += 1
        else:
            print("No satellites specified for removal")
            return False
        
        if not satellites_to_remove:
            print("No valid satellites to remove")
            return False
        
        # Show what will be removed
        print(f"Satellites to remove:")
        for sat_key in satellites_to_remove:
            sat_data = satellites_data[sat_key]
            name = sat_data.get('name', 'Unknown')
            catalog_num = extract_catalog_number(sat_data.get('tle_line1', ''))
            print(f"  {sat_key}: {name} (Cat: {catalog_num})")
        
        # Confirm removal
        if not force:
            try:
                confirm = input(f"\nRemove {len(satellites_to_remove)} satellite(s)? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    print("Operation cancelled")
                    return False
            except EOFError:
                print("No interactive input available, operation cancelled")
                return False
        
        # Remove satellites
        for sat_key in satellites_to_remove:
            del satellites_data[sat_key]
            removed_count += 1
            print(f"✓ Removed {sat_key}")
        
        # Write updated data back to file
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(satellites_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nRemoval complete!")
        print(f"  Removed: {removed_count} satellites")
        print(f"  Not found: {not_found_count} satellites")
        print(f"  Remaining: {len(satellites_data)} satellites")
        
        return not_found_count == 0
        
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
        
        print("Current satellites in database:")
        print("=" * 70)
        for sat_key, sat_data in satellites_data.items():
            name = sat_data.get('name', 'Unknown')
            catalog_num = extract_catalog_number(sat_data.get('tle_line1', ''))
            desc = sat_data.get('description', 'No description')
            print(f"  {sat_key:<15} | {name:<30} | Cat: {catalog_num:<8} | {desc}")
        
    except Exception as e:
        print(f"Error listing satellites: {e}")


def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Remove satellites from satellites.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python remove_satellite.py ISS HUBBLE
  python remove_satellite.py --catalog 25544 20580
  python remove_satellite.py --key JWST
  python remove_satellite.py --list
        """)
    
    parser.add_argument('satellites', nargs='*', 
                       help='Satellite keys to remove (e.g., ISS HUBBLE)')
    parser.add_argument('--catalog', nargs='+', metavar='NUMBER',
                       help='Remove satellites by catalog number')
    parser.add_argument('--key', nargs='+', metavar='KEY',
                       help='Remove satellites by database key')
    parser.add_argument('--list', action='store_true',
                       help='List all available satellites')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts')
    
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
    
    # Combine satellite arguments
    satellite_keys = []
    if args.satellites:
        satellite_keys.extend(args.satellites)
    if args.key:
        satellite_keys.extend(args.key)
    
    # Validate arguments
    if not satellite_keys and not args.catalog:
        print("Error: Must specify satellites to remove")
        print("Use --help for usage information or --list to see available satellites")
        sys.exit(1)
    
    if satellite_keys and args.catalog:
        print("Error: Cannot specify both satellite keys and catalog numbers")
        sys.exit(1)
    
    print("Satellite Removal Tool")
    print("=" * 40)
    print(f"Target file: {satellites_json_path}")
    print()
    
    # Perform the removal
    success = remove_satellites_from_json(
        str(satellites_json_path),
        satellite_keys=satellite_keys if satellite_keys else None,
        catalog_numbers=args.catalog,
        force=args.force
    )
    
    if success:
        print("\n✓ Satellites removed successfully!")
        sys.exit(0)
    else:
        print("\n⚠ Some satellites were not found. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()