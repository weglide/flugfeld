import json
from typing import List

import requests
from timezonefinder import TimezoneFinder

from .csv import write_airports
from .logger import logger
from .types import Airport

CONTINENTS = "geo/continents.json"
COUNTRIES = "geo/countries.json"
NOMINATIM_ENDPOINT_URL = "https://nominatim.openstreetmap.org/reverse"


def _new_zealand_region(airport: Airport) -> str:
    """
    Get North- or South Island region of New Zealand airport based on coordinates.
    """
    assert airport["region"] == "NZ"
    if (
        airport["longitude"] > 165.410156
        and airport["longitude"] < 174.495850
        and airport["latitude"] > -48.389419
        and airport["latitude"] < -40.171149
    ):
        return "NZ-S"  # South Island
    else:
        return "NZ-N"  # North Island


def _get_airport_region(airport: Airport) -> str:
    """
    Makes a reverse geocoding request to OpenStreetMaps Nominatim service.
    Requests per second should be limited to 1.
    Send informative User-Agent header.
    """
    assert len(airport["region"]) == 2

    # Special case for New Zealand
    # for which North/South Island is used instead of regions.
    if airport["region"] == "NZ":
        return _new_zealand_region(airport)

    params = {
        "lon": airport["longitude"],
        "lat": airport["latitude"],
        "format": "json",
        "zoom": 15,
    }
    headers = {"User-Agent": "WeGlide/1.0 Match airport to country and region"}
    response = requests.get(NOMINATIM_ENDPOINT_URL, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    address = data.get("address", {})
    nominatim_region = address.get("ISO3166-2-lvl4") or address.get("ISO3166-2-lvl6")
    assert response.status_code == 200, (
        f"Failed request for region (status code {response.status_code}) for {airport['weglide_name']}. Please try again. \n {response.url}"
    )
    assert nominatim_region is not None, (
        f"Could not find region for {airport['weglide_name']}. Please add manually. \n {response.url}"
    )
    assert nominatim_region[:2] == airport["region"], (
        f"Found region country ({nominatim_region}) differs from existing one ({airport['region']}) for {airport['weglide_name']}. Please verify manually. \n {response.url}"
    )
    return nominatim_region


def _missing_region_airport_indices(airports: List[Airport]) -> List[int]:
    """
    Search in countries.json file for all countries we need regions for.
    Only regions that are searchable on WeGlide need to be added.
    Returns a list of airport indices which do not yet have a region but need one.
    """
    missing_regions: List[int] = []  # List of indices of airports missing a region.
    with open(COUNTRIES) as json_file:
        continents = json.load(json_file).get("data")
        for i in range(len(airports)):
            country = airports[i]["region"]
            continent = airports[i]["continent"]
            if len(country) != 2:
                continue  # Already has a region specified.

            found_continent = continents.get(continent)
            if found_continent is None:
                continue  # Continent not in the countries.json list.

            found_country = found_continent["regions"].get(country)
            if found_country is None:
                continue  # Country not in the countries.json list.

            if "regions" in found_country:
                missing_regions.append(i)

    return missing_regions


def assign_region(airports: List[Airport]) -> List[Airport]:
    """
    Add region to country string (append separated by dash)
    for countries with regions specified in countries.json.
    Region is reverse geocoded by coordinates because it is not present in OpenAIP.
    Overwrites existing region string if there should be a more detailed one.
    """
    # Clone list before modifying.
    airports = list(airports)
    missing_regions = _missing_region_airport_indices(airports)
    for i in range(len(missing_regions)):
        missing_airport = airports[missing_regions[i]]
        nominatim_region = _get_airport_region(missing_airport)
        missing_airport["region"] = nominatim_region
        logger.info(
            f"Update region {i + 1}/{len(missing_regions)} to {nominatim_region} for {missing_airport['weglide_name']}."
        )
        # Intermediate save in case script or api have problems.
        write_airports(airports)
        # Sleep for responsible API usage.
        # sleep(1)

    return airports


def assign_timezone(airports: List[Airport]) -> List[Airport]:
    """
    Add timezone to airports by coordinates.
    Does override existing timezones.
    """
    # Clone list before modifying.
    airports = list(airports)
    tz = TimezoneFinder()
    for airport in airports:
        lng = airport["longitude"]
        lat = airport["latitude"]
        airport["timezone"] = tz.timezone_at(lng=lng, lat=lat)

    return airports


def assign_continent(airports: List[Airport]) -> List[Airport]:
    """
    Add continent based on country part of the region (first two letters) to airports.
    Overwrites existing continent.
    """
    # Clone list before modifying.
    airports = list(airports)
    with open(CONTINENTS) as json_file:
        items = json.load(json_file).items()
        for airport in airports:
            country = airport["region"][:2]
            for continent, countries in items:
                if country in countries:
                    airport["continent"] = continent
                    break
            else:
                raise AssertionError(f"No continent found for country {country}.")

    return airports
