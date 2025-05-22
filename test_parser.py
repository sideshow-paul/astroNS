import unittest
from parser import parse_data
import os

class TestParser(unittest.TestCase):
    def setUp(self):
        # Define the path to the data file
        self.data_path = os.path.join("source", "models", "MathisThroughputExample", "US_east_Latency.txt")
        # Parse the data
        self.parsed_data = parse_data(self.data_path)
    
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
    
    def test_specific_values(self):
        """Test a few specific values to ensure correct parsing"""
        self.assertAlmostEqual(self.parsed_data["Africa"]["AWS"], 213.40)
        self.assertAlmostEqual(self.parsed_data["Europe"]["Azure"], 98.50)
        self.assertAlmostEqual(self.parsed_data["North America"]["GCP"], 35.46)
        self.assertAlmostEqual(self.parsed_data["China"]["IBM"], 245.33)

if __name__ == "__main__":
    unittest.main()