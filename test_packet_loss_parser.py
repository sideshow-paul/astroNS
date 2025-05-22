import unittest
from packet_loss_parser import parse_packet_loss
import os

class TestPacketLossParser(unittest.TestCase):
    def setUp(self):
        # Define the path to the packet loss data file
        self.data_path = "source/models/MathisThroughputExample/US_east_packet_loss.txt"
        # Parse the data
        self.parsed_data = parse_packet_loss(self.data_path)
    
    def test_continent_count(self):
        """Test that we have the expected number of continents"""
        expected_continents = ["Africa", "Asia (ex. China)", "China", "Europe", 
                               "North America", "Oceania", "South America"]
        self.assertEqual(len(self.parsed_data), len(expected_continents))
        for continent in expected_continents:
            self.assertIn(continent, self.parsed_data)
    
    def test_provider_count(self):
        """Test that each continent has the expected cloud providers"""
        expected_providers = ["AliCloud", "AWS", "Azure", "GCP", "IBM"]
        for continent, providers in self.parsed_data.items():
            self.assertEqual(len(providers), len(expected_providers))
            for provider in expected_providers:
                self.assertIn(provider, providers)
    
    def test_percentage_conversion(self):
        """Test that percentage values are correctly converted to decimal"""
        # Original: Africa - AliCloud: 0.82%
        self.assertAlmostEqual(self.parsed_data["Africa"]["AliCloud"], 0.0082)
        # Original: Europe - Azure: 0.36%
        self.assertAlmostEqual(self.parsed_data["Europe"]["Azure"], 0.0036)
        # Original: China - AWS: 5.11%
        self.assertAlmostEqual(self.parsed_data["China"]["AWS"], 0.0511)
        # Original: North America - GCP: 0.20%
        self.assertAlmostEqual(self.parsed_data["North America"]["GCP"], 0.0020)

if __name__ == "__main__":
    unittest.main()