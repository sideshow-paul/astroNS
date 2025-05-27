# Satellite Data Management

This folder contains satellite data and utilities for maintaining up-to-date orbital information.

## Files

- `satellites.json` - Main satellite database with TLE (Two-Line Element) data
- `update_tle.py` - Python script to update all TLE data from CelesTrak
- `update_specific.py` - Python script to update specific satellites
- `add_satellite.py` - Python script to add new satellites to the database
- `remove_satellite.py` - Python script to remove satellites from the database
- `requirements.txt` - Python dependencies for the scripts

## Installation

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

## Updating TLE Data

The TLE (Two-Line Element) data in `satellites.json` contains orbital parameters that become outdated over time. To maintain accuracy, this data should be updated regularly using the latest information from CelesTrak.

### Update All Satellites

To update all satellites with fresh TLE data:

```bash
python update_tle.py
```

### Update Specific Satellites

To update only selected satellites:

```bash
# Update specific satellites by key
python update_specific.py ISS HUBBLE

# Update satellites by catalog number
python update_specific.py --catalog 25544 20580

# Update all satellites
python update_specific.py --all

# List available satellites
python update_specific.py --list
```

## Adding New Satellites

To add new satellites to the database:

```bash
# Add satellite by catalog number
python add_satellite.py --catalog 25544 --key ISS --description "International Space Station"

# Add satellite by name (searches CelesTrak)
python add_satellite.py --name "Hubble Space Telescope" --description "Space telescope"

# Add satellite with auto-generated key
python add_satellite.py --catalog 20580

# Add satellite without interactive prompts
python add_satellite.py --name "NOAA" --force --description "Weather satellite"

# List current satellites
python add_satellite.py --list
```

### Key Generation

If no key is specified, the script automatically generates one from the satellite name:
- Removes parentheses and special characters
- Converts to uppercase
- Limits to 15 characters

## Removing Satellites

To remove satellites from the database:

```bash
# Remove satellites by key
python remove_satellite.py ISS HUBBLE

# Remove satellites by catalog number
python remove_satellite.py --catalog 25544 20580

# Remove single satellite by key
python remove_satellite.py --key UNWANTED_SAT

# List current satellites
python remove_satellite.py --list
```

## CelesTrak API

All scripts use CelesTrak's General Perturbations (GP) API which supports various query types:

- `CATNR`: Catalog Number (NORAD ID)
- `INTDES`: International Designator
- `GROUP`: Satellite groups
- `NAME`: Satellite name search
- `SPECIAL`: Special datasets

The API endpoint format:
```
https://celestrak.org/NORAD/elements/gp.php?{QUERY}=VALUE[&FORMAT=VALUE]
```

Available formats include TLE, XML, JSON, CSV, and KVN. These scripts use TLE format.

## Database Structure

Each satellite in `satellites.json` has the following structure:

```json
"SATELLITE-KEY": {
  "name": "Satellite Name",
  "tle_line1": "1 NNNNN...",
  "tle_line2": "2 NNNNN...",
  "description": "Description of the satellite"
}
```

- **Key**: Unique identifier for the satellite (uppercase, alphanumeric)
- **name**: Official satellite name from CelesTrak
- **tle_line1**: First line of TLE data containing orbital elements
- **tle_line2**: Second line of TLE data containing orbital elements
- **description**: Human-readable description of the satellite

## Error Handling

The scripts handle various error conditions:
- Network timeouts and connection errors
- Invalid catalog numbers
- Malformed TLE data
- Missing satellites in CelesTrak database
- Duplicate satellite keys

Failed operations are reported but don't stop the process for other satellites.

## Update Frequency Recommendations

TLE data accuracy degrades over time. Recommended update frequency:
- **Low Earth Orbit (LEO)**: Daily to weekly
- **Medium Earth Orbit (MEO)**: Weekly to monthly  
- **Geostationary Orbit (GEO)**: Monthly

## Automation

The scripts can be automated using cron jobs or task schedulers for regular updates:

```bash
# Example cron job to update all satellites daily at 6 AM
0 6 * * * cd /path/to/astroNS/source/data && python update_tle.py

# Example cron job to update ISS hourly
0 * * * * cd /path/to/astroNS/source/data && python update_specific.py ISS
```

## Common Use Cases

### Adding a New Mission
```bash
# Find and add a new satellite
python add_satellite.py --name "ARTEMIS" --description "Lunar mission satellite"
```

### Bulk Operations
```bash
# Update all Earth observation satellites
python update_specific.py TERRA AQUA LANDSAT8 SENTINEL1A

# Remove test satellites
python remove_satellite.py EXAMPLE-SAT-1 TEST-SAT
```

### Maintenance
```bash
# Check current database status
python add_satellite.py --list

# Update everything
python update_tle.py
```

The satellite management system is designed to be robust, user-friendly, and suitable for both manual operations and automated workflows.