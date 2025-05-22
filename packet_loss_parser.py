def parse_packet_loss(file_path):
    """
    Parse the US_east_packet_loss.txt file into a dictionary of dictionaries.
    
    Args:
        file_path (str): Path to the US_east_packet_loss.txt file
        
    Returns:
        dict: A dictionary where:
            - keys are continent names
            - values are dictionaries with cloud provider names as keys and packet loss values as float values
              (converted from percentage strings to decimal values)
    """
    result = {}
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            print(f"File opened successfully, contains {len(lines)} lines")
            if len(lines) == 0:
                raise ValueError(f"File {file_path} is empty")
            
            # Parse headers (skipping the first column which is Continent Name)
            headers = lines[0].strip().split('\t')
            cloud_providers = headers[1:]
            
            # Parse data rows
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                parts = line.strip().split('\t')
                continent = parts[0]
                
                # Convert percentage strings (e.g., "0.82%") to float values (e.g., 0.0082)
                values = [float(val.strip('%')) / 100 for val in parts[1:]]
                
                # Create inner dictionary mapping cloud providers to values
                result[continent] = {provider: value for provider, value in zip(cloud_providers, values)}
        
        return result
    
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
        import os
        print(f"Current directory: {os.getcwd()}")
        print(f"File exists: {os.path.exists(file_path)}")
        raise

if __name__ == "__main__":
    # Example usage
    import os
    # Get absolute path to the data file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_path = os.path.join(project_root, "source", "models", "MathisThroughputExample", "US_east_packet_loss.txt")
    
    data = parse_packet_loss(data_path)
    
    # Print the parsed data structure
    for continent, providers in data.items():
        print(f"{continent}:")
        for provider, value in providers.items():
            print(f"  {provider}: {value:.4f}")