#!/usr/bin/env python3
"""
Script to add new satellites to satellites.json from CelesTrak.

Usage:
    python add_satellite.py --catalog 25544
    python add_satellite.py --name "International Space Station"
    python add_satellite.py --catalog 25544 --key ISS
    python add_satellite.py --name "Hubble" --key HUBBLE --description "Space telescope"
"""

import json
import requests
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional


def extract_catalog_number(tle_line1: str) -> Optional[str]:
    """Extract catalog number from TLE line 1."""
    match = re.match(r'1\s+(\d+)', tle_line1.strip())
    if match:
        return match.group(1)
    return None


def fetch_tle_by_catalog(catalog_number: str) -> Optional[Dict[str, Any]]:
    """Fetch satellite data by catalog number from CelesTrak."""
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalog_number}&FORMAT=TLE"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        lines = response.text.strip().split('\n')
        
        if len(lines) >= 3:
            return {
                'name': lines[0].strip(),
                'tle_line1': lines[1].strip(),
                'tle_line2': lines[2].strip()
            }
        elif len(lines) == 2:
            # Sometimes only 2 lines are returned, try to get name from another source
            return {
                'name': f"Satellite {catalog_number}",
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


def search_satellite_by_name(satellite_name: str) -> Optional[Dict[str, Any]]:
    """Search for satellite by name using CelesTrak NAME query."""
    url = f"https://celestrak.org/NORAD/elements/gp.php?NAME={satellite_name}&FORMAT=TLE"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        lines = response.text.strip().split('\n')
        
        if len(lines) >= 3:
            # If multiple satellites returned, take the first one
            return {
                'name': lines[0].strip(),
                'tle_line1': lines[1].strip(),
                'tle_line2': lines[2].strip()
            }
            
    except requests.RequestException as e:
        print(f"Error searching for satellite '{satellite_name}': {e}")
        return None
    except Exception as e:
        print(f"Unexpected error searching for '{satellite_name}': {e}")
        return None
    
    return None


def generate_key_from_name(name: str) -> str:
    """Generate a database key from satellite name."""
    # Remove common prefixes and suffixes
    clean_name = name.upper()
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', clean_name)  # Remove parentheses content
    clean_name = re.sub(r'\s+', '', clean_name)  # Remove spaces
    clean_name = re.sub(r'[^A-Z0-9]', '', clean_name)  # Keep only alphanumeric
    
    # Limit length
    if len(clean_name) > 15:
        clean_name = clean_name[:15]
    
    return clean_name


def add_satellite_to_json(json_file_path: str, satellite_data: Dict[str, Any], 
                         key: str = None, description: str = None, force: bool = False) -> bool:
    """Add satellite data to satellites.json."""
    try:
        # Read current satellites data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            satellites_data = json.load(f)
        
        # Generate key if not provided
        if not key:
            key = generate_key_from_name(satellite_data['name'])
        
        # Check if key already exists
        if key in satellites_data:
            print(f"Warning: Satellite key '{key}' already exists")
            existing_name = satellites_data[key].get('name', 'Unknown')
            print(f"Existing satellite: {existing_name}")
            return False
        
        # Prepare satellite entry
        catalog_number = extract_catalog_number(satellite_data['tle_line1'])
        if not description:
            description = f"Satellite {catalog_number}" if catalog_number else "Satellite"
        
        satellite_entry = {
            'name': satellite_data['name'],
            'tle_line1': satellite_data['tle_line1'],
            'tle_line2': satellite_data['tle_line2'],
            'description': description
        }
        
        # Add to database
        satellites_data[key] = satellite_entry
        
        # Write updated data back to file
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(satellites_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Successfully added satellite '{key}'")
        print(f"  Name: {satellite_data['name']}")
        print(f"  Catalog: {catalog_number}")
        print(f"  Description: {description}")
        
        return True
        
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
        description='Add new satellites to satellites.json from CelesTrak',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python add_satellite.py --catalog 25544
  python add_satellite.py --name "International Space Station"
  python add_satellite.py --catalog 25544 --key ISS
  python add_satellite.py --name "Hubble" --key HUBBLE --description "Space telescope"
  python add_satellite.py --list
        """)
    
    parser.add_argument('--catalog', type=str, metavar='NUMBER',
                       help='Satellite catalog number (NORAD ID)')
    parser.add_argument('--name', type=str, metavar='NAME',
                       help='Satellite name to search for')
    parser.add_argument('--key', type=str, metavar='KEY',
                       help='Database key for the satellite (auto-generated if not provided)')
    parser.add_argument('--description', type=str, metavar='DESC',
                       help='Description for the satellite')
    parser.add_argument('--list', action='store_true',
                       help='List all current satellites in database')
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
    
    # Validate arguments
    if not args.catalog and not args.name:
        print("Error: Must specify either --catalog or --name")
        print("Use --help for usage information or --list to see current satellites")
        sys.exit(1)
    
    if args.catalog and args.name:
        print("Error: Cannot specify both --catalog and --name")
        sys.exit(1)
    
    print("Satellite Addition Tool")
    print("=" * 40)
    print(f"Target file: {satellites_json_path}")
    print()
    
    # Fetch satellite data
    satellite_data = None
    
    if args.catalog:
        print(f"Fetching satellite data for catalog number: {args.catalog}")
        satellite_data = fetch_tle_by_catalog(args.catalog)
        if not satellite_data:
            print(f"✗ Failed to find satellite with catalog number {args.catalog}")
            sys.exit(1)
    
    elif args.name:
        print(f"Searching for satellite: {args.name}")
        satellite_data = search_satellite_by_name(args.name)
        if not satellite_data:
            print(f"✗ Failed to find satellite with name '{args.name}'")
            print("Try using a more specific name or the catalog number instead")
            sys.exit(1)
    
    # Display found satellite info
    catalog_num = extract_catalog_number(satellite_data['tle_line1'])
    print(f"Found satellite:")
    print(f"  Name: {satellite_data['name']}")
    print(f"  Catalog: {catalog_num}")
    print()
    
    # Confirm addition
    if not args.key:
        suggested_key = generate_key_from_name(satellite_data['name'])
        print(f"Suggested database key: {suggested_key}")
        
        if not args.force:
            try:
                confirm = input("Add this satellite to the database? (Y/n): ").strip().lower()
                if confirm in ['n', 'no']:
                    print("Operation cancelled")
                    sys.exit(0)
                
                # Allow user to modify the key
                user_key = input(f"Enter database key (press Enter for '{suggested_key}'): ").strip()
                if user_key:
                    args.key = user_key.upper()
                else:
                    args.key = suggested_key
            except EOFError:
                print("No interactive input available, using suggested key")
                args.key = suggested_key
        else:
            args.key = suggested_key
    
    # Add satellite to database
    success = add_satellite_to_json(
        str(satellites_json_path),
        satellite_data,
        key=args.key,
        description=args.description,
        force=args.force
    )
    
    if success:
        print(f"\n✓ Satellite successfully added to database!")
        print(f"You can now use key '{args.key}' to reference this satellite.")
        sys.exit(0)
    else:
        print(f"\n✗ Failed to add satellite to database.")
        sys.exit(1)


if __name__ == "__main__":
    main()