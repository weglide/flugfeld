from time import sleep
from typing import List

import numpy as np
import requests
from scipy.spatial.distance import cdist

from src.csv import write_airports
from src.logger import logger
from src.types import Airport

WGS_84_SRID: int = 4326
EARTH_RADIUS_KM: float = 6371.0
METER_PER_FEET: float = 0.3048
WEGLIDE_ENDPOINT_URL = "https://api.weglide.org/v1/airport"


def _get_airport_launches(airport: Airport) -> int | None:
    """
    Request airport information from WeGlide and extract number of launches.
    Returns None when airport does not (yet) exist on WeGlide or on error.
    """
    assert airport["weglide_id"] is not None

    headers = {"User-Agent": "WeGlide/1.0 Airport launches"}
    url = f"{WEGLIDE_ENDPOINT_URL}/{airport['weglide_id']}"
    response = requests.get(url, headers=headers)
    data = response.json()
    launches = data.get("stats", {}).get("count")
    assert response.status_code == 200 or response.status_code == 404, (
        f"Failed request for launches (status code {response.status_code}) for {airport['weglide_name']}. Please try again. \n {response.url}"
    )
    return launches


def assign_launches(airports: List[Airport], force=False) -> List[Airport]:
    """
    Assign the number of glider launches to each aiport.
    Fetched from WeGlide API and used for reign calculation.
    Overwrites existing launch number and None if airport could not be found on WeGlide.
    """
    # Clone list before modifying.
    airports = list(airports)

    for airport in airports:
        if not force and airport["launches"] is not None:
            continue  # Do not update existing values.

        name = airport["weglide_name"]
        launches = _get_airport_launches(airport)
        if launches is not None:
            airport["launches"] = launches
            logger.info(f"Added {launches} launches to {name}.")
            # Intermediate save in case script or api have problems.
            write_airports(airports)
        else:
            logger.info(f"Skipped launches for {name} (not found on WeGlide).")

        # Sleep for responsible API usage.
        sleep(0.2)

    return airports


def assign_reign(airports: List[Airport]) -> List[Airport]:
    """
    Assign a reign for each airport in the given list.
    Reign is based on number of launches and distance to nearby airports.
    """
    # Clone list before modifying.
    airports = list(airports)

    lon = [a["longitude"] for a in airports]
    lat = [a["latitude"] for a in airports]
    lonlat = np.column_stack((np.array(lon), np.array(lat)))

    # Distance matrix between airports.
    lonlatrad = np.radians(lonlat)
    theta = np.cos(np.mean(lonlat[:, 1]))
    lonlatrad[:, 0] *= theta
    dist_matrix = cdist(lonlatrad, lonlatrad, "euclidean") * EARTH_RADIUS_KM

    # Start with a large reign for every airport.
    reign = [1000] * len(lonlat)

    # Build reign for each airport from distance matrix and number of launches.
    for i in range(len(lonlat)):
        for j in range(len(lonlat)):
            # Only traverse upper triangle.
            if j >= i:
                continue

            dist = dist_matrix[i, j]
            if dist >= max(reign[i], reign[j]):
                continue

            launches1 = airports[i]["launches"]
            assert launches1 is not None

            launches2 = airports[j]["launches"]
            assert launches2 is not None

            if launches1 >= launches2:
                if reign[j] > dist:
                    reign[j] = round(dist)
                continue

            if reign[i] > dist:
                reign[i] = round(dist)

    # Update the airport list with the reign.
    for i, r in enumerate(reign):
        airports[i]["reign"] = r

    return airports
