def parse_data(file_path):
    """
    Parse the data.txt file into a dictionary of dictionaries.
    
    Args:
        file_path (str): Path to the data.txt file
        
    Returns:
        dict: A dictionary where:
            - keys are continent names
            - values are dictionaries with cloud provider names as keys and throughput values as float values
    """
    result = {}
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
        # Parse headers (skipping the first column which is Continent_Name)
        headers = lines[0].strip().split('\t')
        cloud_providers = headers[1:]
        
        # Parse data rows
        for line in lines[1:]:
            if not line.strip():
                continue
                
            parts = line.strip().split('\t')
            continent = parts[0]
            values = [float(val) for val in parts[1:]]
            
            # Create inner dictionary mapping cloud providers to values
            result[continent] = {provider: value for provider, value in zip(cloud_providers, values)}
    
    return result

if __name__ == "__main__":
    # Example usage
    data = parse_data("source/models/MathisThroughputExample/data.txt")
    
    # Print the parsed data structure
    for continent, providers in data.items():
        print(f"{continent}:")
        for provider, value in providers.items():
            print(f"  {provider}: {value}")