#!/usr/bin/env python3
"""
Test script to verify that simple_accgen imports are working correctly
from the local astroNS/simple_accgen package.
"""

import sys
import os

# Add the astroNS source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'astroNS'))

def test_simple_accgen_imports():
    """Test that simple_accgen imports work correctly"""
    
    print("Testing simple_accgen imports...")
    print("=" * 50)
    
    try:
        # Add simple_accgen to path (same as in the nodes)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../simple_accgen/src'))
        
        # Test basic imports
        print("Testing basic imports...")
        from simple_accgen.access_generator import AccessGenerator, GrazingAngleFilter, TargetSunElevationAngleFilter
        print("✓ AccessGenerator imports successful")
        
        from simple_accgen.geometry import ObserverTargetGeometry
        print("✓ ObserverTargetGeometry import successful")
        
        from simple_accgen.propagation.statevector_provider import GeodeticPoint, TLEStateVectorProvider
        print("✓ StateVectorProvider imports successful")
        
        # Test creating objects
        print("\nTesting object creation...")
        
        # Test GeodeticPoint
        target = GeodeticPoint.createFromLatLonAlt(0.0, 0.0, 0.0)
        print("✓ GeodeticPoint creation successful")
        
        # Test TLE provider (with example ISS TLE)
        tle_line1 = "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999"
        tle_line2 = "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978"
        satellite = TLEStateVectorProvider(tle_line1, tle_line2)
        print("✓ TLEStateVectorProvider creation successful")
        
        print("\nAll imports and basic functionality working correctly!")
        return True
        
    except ImportError as e:
        print(f"✗ Import Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_node_imports():
    """Test that the aerospace nodes can import simple_accgen correctly"""
    
    print("\nTesting aerospace node imports...")
    print("=" * 50)
    
    try:
        from nodes.aerospace.accessGenerator import AccessGenerator
        print("✓ AccessGenerator node import successful")
        
        from nodes.aerospace.calculate_geometry import CalculateGeometry
        print("✓ CalculateGeometry node import successful")
        
        print("\nAerospace nodes importing simple_accgen correctly!")
        return True
        
    except ImportError as e:
        print(f"✗ Node Import Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Node Error: {e}")
        return False

if __name__ == "__main__":
    print("Simple-accgen Import Test")
    print("This script verifies that simple_accgen can be imported correctly")
    print("from the local astroNS/simple_accgen package.\n")
    
    success1 = test_simple_accgen_imports()
    success2 = test_node_imports()
    
    if success1 and success2:
        print("\n🎉 All tests passed! simple_accgen imports are working correctly.")
        exit_code = 0
    else:
        print("\n❌ Some tests failed. Check the error messages above.")
        exit_code = 1
    
    sys.exit(exit_code)