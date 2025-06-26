""" LLM Scenario Generator Node

This node reads a geo_polygon (list of lat, lon positions defining a polygon) and
a GSD (Ground Sample Distance) value from configured message keys, then makes a
REST request to an LLM server to generate a description of what would be visible
in an image of that area with the given resolution.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime, timezone
import logging
import json
import requests
import time

from nodes.core.base import BaseNode


class LLMScenario(BaseNode):
    """LLM Scenario Generator Node"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize LLM Scenario node"""
        super().__init__(env, name, configuration, self.execute())

        # Initialize logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{name}")

        # Node Reserve Time
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        # Message Delay Time
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )

        # Configuration parameters
        self._geo_polygon_key = self.setStringFromConfig("geo_polygon_key", "geo_polygon")
        self._gsd_key = self.setStringFromConfig("gsd_key", "gsd_m_per_px")
        self._response_key = self.setStringFromConfig("response_key", "llm_scenario_response")
        self._error_key = self.setStringFromConfig("error_key", "llm_scenario_error")
        self._interested_locations_key = self.setStringFromConfig("interested_locations_key", "interested_locations")

        # LLM server configuration
        self._llm_server_url = self.setStringFromConfig("llm_server_url", "http://localhost:8080/v1/chat/completions")
        self._llm_model = self.setStringFromConfig("llm_model", "gpt-3.5-turbo")
        self._llm_api_key = self.setStringFromConfig("llm_api_key", "")
        self._llm_timeout = self.setFloatFromConfig("llm_timeout", 30.0)
        self._llm_max_tokens = self.setFloatFromConfig("llm_max_tokens", 500)
        self._llm_temperature = self.setFloatFromConfig("llm_temperature", 0.7)

        # Request configuration
        self._include_coordinates = self.setBoolFromConfig("include_coordinates", True)
        self._include_area_estimate = self.setBoolFromConfig("include_area_estimate", True)
        self._custom_prompt_suffix = self.setStringFromConfig("custom_prompt_suffix", "")
        self._use_interested_locations = self.setBoolFromConfig("use_interested_locations", False)

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def geo_polygon_key(self) -> Optional[str]:
        return self._geo_polygon_key()

    @property
    def gsd_key(self) -> Optional[str]:
        return self._gsd_key()

    @property
    def response_key(self) -> Optional[str]:
        return self._response_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def llm_server_url(self) -> Optional[str]:
        return self._llm_server_url()

    @property
    def llm_model(self) -> Optional[str]:
        return self._llm_model()

    @property
    def llm_api_key(self) -> Optional[str]:
        return self._llm_api_key()

    @property
    def llm_timeout(self) -> float:
        return self._llm_timeout()

    @property
    def include_coordinates(self) -> bool:
        return self._include_coordinates()

    @property
    def include_area_estimate(self) -> bool:
        return self._include_area_estimate()

    @property
    def custom_prompt_suffix(self) -> Optional[str]:
        return self._custom_prompt_suffix()

    @property
    def interested_locations_key(self) -> Optional[str]:
        return self._interested_locations_key()

    @property
    def use_interested_locations(self) -> bool:
        return self._use_interested_locations()

    def format_polygon_coordinates(self, geo_polygon: List[List[float]]) -> str:
        """
        Format polygon coordinates for the prompt.

        Args:
            geo_polygon: List of [lat, lon] coordinate pairs

        Returns:
            Formatted string representation of the polygon
        """
        if not geo_polygon or len(geo_polygon) < 3:
            return "invalid polygon"

        coords_str = ", ".join([f"({lat:.6f}, {lon:.6f})" for lat, lon in geo_polygon])
        return f"polygon with vertices: {coords_str}"

    def estimate_polygon_area(self, geo_polygon: List[List[float]]) -> float:
        """
        Estimate the area of a polygon using the shoelace formula (approximate for small areas).

        Args:
            geo_polygon: List of [lat, lon] coordinate pairs

        Returns:
            Approximate area in square kilometers
        """
        if not geo_polygon or len(geo_polygon) < 3:
            return 0.0

        # Convert degrees to approximate meters (rough approximation)
        # 1 degree latitude ≈ 111 km
        # 1 degree longitude ≈ 111 km * cos(latitude)

        # Calculate centroid latitude for longitude conversion
        avg_lat = sum(coord[0] for coord in geo_polygon) / len(geo_polygon)
        lat_to_km = 111.0
        lon_to_km = 111.0 * abs(cos(radians(avg_lat))) if avg_lat != 0 else 111.0

        # Apply shoelace formula
        area = 0.0
        n = len(geo_polygon)

        for i in range(n):
            j = (i + 1) % n
            x1, y1 = geo_polygon[i][1] * lon_to_km, geo_polygon[i][0] * lat_to_km
            x2, y2 = geo_polygon[j][1] * lon_to_km, geo_polygon[j][0] * lat_to_km
            area += x1 * y2 - x2 * y1

        return abs(area) / 2.0

    def point_in_polygon(self, point: List[float], polygon: List[List[float]]) -> bool:
        """
        Check if a point is inside a polygon using the ray casting algorithm.

        Args:
            point: [lat, lon] coordinate pair
            polygon: List of [lat, lon] coordinate pairs defining the polygon

        Returns:
            True if point is inside polygon, False otherwise
        """
        if len(point) < 2 or len(polygon) < 3:
            return False

        lat, lon = point[0], point[1]
        n = len(polygon)
        inside = False

        p1_lat, p1_lon = polygon[0][0], polygon[0][1]
        for i in range(1, n + 1):
            p2_lat, p2_lon = polygon[i % n][0], polygon[i % n][1]

            if lat > min(p1_lat, p2_lat):
                if lat <= max(p1_lat, p2_lat):
                    if lon <= max(p1_lon, p2_lon):
                        if p1_lat != p2_lat:
                            xinters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                        if p1_lon == p2_lon or lon <= xinters:
                            inside = not inside
            p1_lat, p1_lon = p2_lat, p2_lon

        return inside

    def check_interested_locations_in_polygon(self, interested_locations: List[List[float]], geo_polygon: List[List[float]]) -> Tuple[bool, List[List[float]]]:
        """
        Check if any interested locations are within the geo-polygon.

        Args:
            interested_locations: List of [lat, lon] coordinate pairs
            geo_polygon: List of [lat, lon] coordinate pairs defining the polygon

        Returns:
            Tuple of (any_locations_inside, list_of_locations_inside)
        """
        if not interested_locations or not geo_polygon:
            return False, []

        locations_inside = []
        for location in interested_locations:
            if isinstance(location, list) and len(location) >= 2:
                if self.point_in_polygon(location, geo_polygon):
                    locations_inside.append(location)

        return len(locations_inside) > 0, locations_inside

    def build_prompt(self, geo_polygon: List[List[float]], gsd_value: float) -> str:
        """
        Build the prompt for the LLM request.

        Args:
            geo_polygon: List of [lat, lon] coordinate pairs
            gsd_value: Ground Sample Distance in meters per pixel

        Returns:
            Formatted prompt string
        """
        # Get current simulation time
        current_simtime = self.env.now_datetime().isoformat()

        # Base prompt with simulation time and satellite imagery context
        prompt = f"Describe what would be visible in satellite imagery captured over this geopolygon area with a Ground Sample Distance (GSD) of {gsd_value:.3f} meters per pixel at {current_simtime}. Consider the time of day for lighting conditions (daylight/darkness/shadows), seasonal vegetation patterns, weather effects, and any time-specific human activities or infrastructure that would be observable at this resolution. Include details about terrain features, urban/rural characteristics, vegetation cover, water bodies, transportation networks, and any other distinguishing features that would be detectable in the satellite image."

        # Add coordinate details if configured
        if self.include_coordinates and geo_polygon:
            polygon_str = self.format_polygon_coordinates(geo_polygon)
            prompt += f" The polygon area is defined by: {polygon_str}."

        # Add area estimate if configured
        if self.include_area_estimate and geo_polygon:
            try:
                from math import cos, radians
                area_km2 = self.estimate_polygon_area(geo_polygon)
                if area_km2 > 0:
                    prompt += f" The approximate area is {area_km2:.2f} square kilometers."
            except Exception as e:
                self.logger.warning(f"Failed to calculate area estimate: {e}")

        # Add custom suffix if provided
        if self.custom_prompt_suffix:
            prompt += f" {self.custom_prompt_suffix}"

        return prompt

    def make_llm_request(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Make REST request to LLM server.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            Tuple of (response_text, error_message)
        """
        try:
            # Prepare headers
            headers = {
                "Content-Type": "application/json"
            }

            # Add API key if provided
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"

            # Prepare request payload
            payload = {
                "model": self.llm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": int(self._llm_max_tokens()),
                "temperature": self._llm_temperature()
            }

            # Make the request
            response = requests.post(
                self.llm_server_url,
                headers=headers,
                json=payload,
                timeout=self.llm_timeout
            )

            # Check if request was successful
            if response.status_code == 200:
                response_data = response.json()

                # Extract the response text (OpenAI API format)
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    response_text = response_data["choices"][0]["message"]["content"]
                    return response_text.strip(), None
                else:
                    return None, f"Invalid response format: {response_data}"
            else:
                return None, f"HTTP {response.status_code}: {response.text}"

        except requests.exceptions.Timeout:
            return None, f"Request timeout after {self.llm_timeout} seconds"
        except requests.exceptions.ConnectionError:
            return None, f"Connection error to LLM server: {self.llm_server_url}"
        except Exception as e:
            return None, f"Error making LLM request: {str(e)}"

    def create_timestamped_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Create a timestamped response object.

        Args:
            llm_response: The response from the LLM

        Returns:
            Dictionary containing the response with timestamp
        """
        return {
            "response": llm_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulation_time": self.env.now_datetime().isoformat() if hasattr(self.env, 'now_datetime') else None,
            "gsd_meters_per_pixel": None,  # Will be filled in execute()
            "polygon_coordinates": None,   # Will be filled in execute()
            "request_duration_seconds": None  # Will be filled in execute()
        }

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []

        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay = self.time_delay

                # Get configuration values from input or defaults
                # import pudb;pu.db
                geo_polygon_key = msg.get('geo_polygon_key', self.geo_polygon_key)
                gsd_key = msg.get('gsd_key', self.gsd_key)
                response_key = msg.get('response_key', self.response_key)
                error_key = msg.get('error_key', self.error_key)
                interested_locations_key = msg.get('interested_locations_key', self.interested_locations_key)

                # Check if required keys exist in the message
                if geo_polygon_key not in msg:
                    error_msg = f"Geo polygon key '{geo_polygon_key}' not found in message"
                    msg[error_key] = error_msg
                    print(self.log_prefix(msg.get("ID", "unknown")) + f"ERROR: {error_msg}")
                elif gsd_key not in msg:
                    error_msg = f"GSD key '{gsd_key}' not found in message"
                    msg[error_key] = error_msg
                    print(self.log_prefix(msg.get("ID", "unknown")) + f"ERROR: {error_msg}")
                else:
                    # Extract data from message
                    geo_polygon = msg[geo_polygon_key]
                    gsd_value = msg[gsd_key]

                    # Validate inputs
                    if not isinstance(geo_polygon, list) or len(geo_polygon) < 3:
                        error_msg = f"Invalid geo_polygon format. Expected list of at least 3 coordinate pairs, got: {type(geo_polygon)}"
                        msg[error_key] = error_msg
                        print(self.log_prefix(msg.get("ID", "unknown")) + f"ERROR: {error_msg}")
                    elif not isinstance(gsd_value, (int, float)) or gsd_value <= 0:
                        error_msg = f"Invalid GSD value. Expected positive number, got: {gsd_value}"
                        msg[error_key] = error_msg
                        print(self.log_prefix(msg.get("ID", "unknown")) + f"ERROR: {error_msg}")
                    else:
                        # Check interested locations if filtering is enabled
                        if self.use_interested_locations and interested_locations_key in msg:
                            interested_locations = msg[interested_locations_key]

                            if isinstance(interested_locations, list) and len(interested_locations) > 0:
                                any_inside, locations_inside = self.check_interested_locations_in_polygon(
                                    interested_locations, geo_polygon
                                )

                                if not any_inside:
                                    # No interested locations in polygon, skip LLM request
                                    print(self.log_prefix(msg.get("ID", "unknown")) +
                                          f"No interested locations found within geo-polygon. Skipping LLM request.")
                                    print(self.log_prefix(msg.get("ID", "unknown")) +
                                          f"Interested locations: {interested_locations}")
                                    print(self.log_prefix(msg.get("ID", "unknown")) +
                                          f"Geo-polygon: {geo_polygon}")

                                    # Clear any previous error and pass through
                                    if error_key in msg:
                                        del msg[error_key]

                                    processing_time = self._processing_delay()
                                    data_out_list = [msg]
                                    continue
                                else:
                                    print(self.log_prefix(msg.get("ID", "unknown")) +
                                          f"Found {len(locations_inside)} interested location(s) within geo-polygon: {locations_inside}")
                            else:
                                print(self.log_prefix(msg.get("ID", "unknown")) +
                                      f"Interested locations filtering enabled but no valid locations found in key '{interested_locations_key}'")
                        # Build prompt and make LLM request
                        prompt = self.build_prompt(geo_polygon, gsd_value)

                        print(self.log_prefix(msg.get("ID", "unknown")) + f"Making LLM request with prompt: {prompt[:100]}...")

                        # Record start time for duration calculation
                        request_start_time = time.time()

                        # Make the LLM request
                        llm_response, llm_error = self.make_llm_request(prompt)

                        # Calculate request duration
                        request_duration = time.time() - request_start_time

                        if llm_error:
                            # LLM request failed
                            msg[error_key] = llm_error
                            self.logger.error(f"LLM request failed: {llm_error}")
                            print(self.log_prefix(msg.get("ID", "unknown")) + f"ERROR: {llm_error}")
                        else:
                            # LLM request successful
                            timestamped_response = self.create_timestamped_response(llm_response)
                            timestamped_response["gsd_meters_per_pixel"] = gsd_value
                            timestamped_response["polygon_coordinates"] = geo_polygon
                            timestamped_response["request_duration_seconds"] = request_duration

                            msg[response_key] = timestamped_response

                            # Clear any previous error
                            if error_key in msg:
                                del msg[error_key]

                            print(self.log_prefix(msg.get("ID", "unknown")) +
                                  f"Successfully received LLM response ({len(llm_response)} chars) in {request_duration:.2f}s")
                            print(self.log_prefix(msg.get("ID", "unknown")) +
                                  f"LLM Response preview: {llm_response[:150]}...")

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
