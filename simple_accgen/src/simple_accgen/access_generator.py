from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable
import numpy as np
from datetime import datetime

from simple_accgen.geometry import ObserverTargetGeometry
import numba


@dataclass
class AccessFilter:
    """Base class for filters that can be applied to geometry data"""

    name: str

    def apply(self, mask: np.ndarray, geometry: ObserverTargetGeometry) -> np.ndarray:
        """
        Apply this filter to update the access mask

        Parameters:
        -----------
        mask : np.ndarray
            Boolean array indicating valid access points (True = valid)
        geometry : ObserverTargetGeometry
            Geometry data to evaluate

        Returns:
        --------
        np.ndarray
            Updated boolean mask with this filter applied
        """
        raise NotImplementedError("Subclasses must implement apply()")


class GrazingAngleFilter(AccessFilter):
    """Filter for minimum grazing angle requirement"""

    def __init__(self, min_angle: float, name: str = "Grazing Angle", degrees=False):
        super().__init__(name)
        self.min_angle_rad = np.radians(min_angle) if degrees else min_angle

    def apply(self, mask: np.ndarray, geometry: ObserverTargetGeometry) -> np.ndarray:
        """Apply grazing angle filter to mask"""
        return mask & (geometry.grazing_angle > self.min_angle_rad)


class TargetSunElevationAngleFilter(AccessFilter):
    """Filter for sun elevation angle"""

    def __init__(
        self,
        min_angle: float,
        max_angle: float,
        name: str = "Sun Elevation Angle",
        degrees=False,
    ):
        super().__init__(name)
        self.min_angle_rad = np.radians(min_angle) if degrees else min_angle
        self.max_angle_rad = np.radians(max_angle) if degrees else max_angle

    def apply(self, mask: np.ndarray, geometry: ObserverTargetGeometry) -> np.ndarray:
        """Apply grazing angle filter to mask"""
        e = geometry.sun_elevation_angle
        return mask & (
            (e >= self.min_angle_rad) & (e <= self.max_angle_rad)
        )


class RangeFilter(AccessFilter):
    """Filter for maximum range requirement"""

    def __init__(self, max_range_km: float, name: str = "Range"):
        super().__init__(name)
        self.max_range_km = max_range_km

    def apply(self, mask: np.ndarray, geometry: ObserverTargetGeometry) -> np.ndarray:
        """Apply range filter to mask"""
        return mask & (geometry.range <= self.max_range_km)


# You can add more filter types as needed for other criteria


@numba.njit
def find_regions_from_mask(mask: np.ndarray) -> np.ndarray:
    """
    Numba-optimized function to find contiguous regions where mask is True

    Parameters:
    -----------
    mask : np.ndarray
        Boolean array indicating valid access points

    Returns:
    --------
    np.ndarray
        2D array with shape (n, 2) containing start and end indices of regions
    """
    n = mask.shape[0]
    # Pre-allocate a maximum possible number of regions (n/2 in worst case)
    regions = np.empty((n // 2 + 1, 2), dtype=np.int64)
    region_count = 0

    start_idx = -1

    for i in range(n):
        if mask[i]:
            # Start of a region or continuation
            if start_idx == -1:
                start_idx = i
        elif start_idx != -1:
            # End of a region
            regions[region_count, 0] = start_idx
            regions[region_count, 1] = i - 1
            region_count += 1
            start_idx = -1

    # Handle case where we end while in a region
    if start_idx != -1:
        regions[region_count, 0] = start_idx
        regions[region_count, 1] = n - 1
        region_count += 1

    # Return only the filled portion of the array
    return regions[:region_count]


class AccessGenerator:
    """
    Class to generate access intervals by applying filters to a geometry
    """

    def __init__(self, geometry: ObserverTargetGeometry):
        """
        Initialize with a geometry object

        Parameters:
        -----------
        geometry : ObserverTargetGeometry
            The geometry to analyze for access periods
        """
        self.geometry = geometry
        self.filters = []

    def add_filter(self, filter_obj: AccessFilter) -> "AccessGenerator":
        """
        Add a filter to be applied

        Parameters:
        -----------
        filter_obj : AccessFilter
            Filter to add

        Returns:
        --------
        AccessGenerator
            Self, for method chaining
        """
        self.filters.append(filter_obj)
        return self

    def generate_access_mask(self) -> np.ndarray:
        """
        Generate a boolean mask by applying all filters

        Returns:
        --------
        np.ndarray
            Boolean array where True indicates valid access
        """
        # Start with all True
        n_times = len(self.geometry.timestamps)
        mask = np.ones(n_times, dtype=bool)

        # Apply each filter
        for filter_obj in self.filters:
            mask = filter_obj.apply(mask, self.geometry)

        return mask

    def generate_access_regions(self) -> List[Tuple[int, int]]:
        """
        Generate a list of contiguous access regions

        Returns:
        --------
        List[Tuple[int, int]]
            List of (start_index, end_index) tuples for valid access periods
        """
        mask = self.generate_access_mask()
        regions_array = find_regions_from_mask(mask)

        # Convert to list of tuples
        return [(int(start), int(end)) for start, end in regions_array]

    def get_access_timestamps(
        self, regions: Optional[List[Tuple[int, int]]] = None
    ) -> List[Tuple[datetime, datetime]]:
        """
        Get the start and end timestamps for each access region

        Returns:
        --------
        List[Tuple[datetime, datetime]]
            List of (start_time, end_time) tuples for valid access periods
        """
        if regions is None:
            regions = self.generate_access_regions()

        timestamps = self.geometry.timestamps

        return [(timestamps[start], timestamps[end]) for start, end in regions]
