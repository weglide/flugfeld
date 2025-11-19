import json
from typing import List

from src.csv import read_airports
from src.region import CONTINENTS, COUNTRIES


def _continents() -> List[str]:
    with open(CONTINENTS) as file:
        items = json.load(file).items()
        return [item[0] for item in items]


def test_continent():
    """
    Each continent from the csv must exist in continents.json
    """
    continents = _continents()
    for airport in read_airports():
        assert airport["continent"] in continents, (
            f"Continent {airport['continent']} for {airport['weglide_name']} not found in {continents}."
        )


def _countries() -> List[str]:
    with open(CONTINENTS) as file:
        values = json.load(file).values()
        return [code for continent in values for code in continent]


def _regions() -> List[str]:
    with open(COUNTRIES) as file:
        results = []
        # Iterate through continents
        for _, continent_data in json.load(file).get("data", {}).items():
            # Check for regions (countries) within the continent
            if "regions" in continent_data:
                for country_code, country_data in continent_data["regions"].items():
                    # Check if the country has sub-regions
                    if "regions" in country_data:
                        # If sub-regions exist, add the sub-region codes
                        for region_code in country_data["regions"].keys():
                            results.append(region_code)
                    else:
                        # If no sub-regions, add the country code
                        results.append(country_code)

        return results


def test_region():
    """
    Each region from the csv must exist in countries.json
    Regions with sub region in countries.json (e.g. DE-BY) must have the sub region assigned.
    Not all countries are in the countries.json file, therefore also search the complete continent file for them.
    """
    all_countries = _countries()
    full_regions = list(filter(lambda region: "-" in region, _regions()))
    for airport in read_airports():
        if airport["region"][:2] in [r[:2] for r in full_regions]:
            assert airport["region"] in full_regions, (
                f"{airport['weglide_name']} must have a known full region but has {airport['region']}."
            )
        else:
            assert airport["region"] in all_countries, (
                f"{airport['weglide_name']} must have a know country but has {airport['region']}."
            )


def _multi_regions() -> dict:
    with open("geo/multi_regions.json") as file:
        return json.load(file).get("data", {}).values()


def test_multi_regions():
    all_regions = _regions() + _countries()
    for multi_region in _multi_regions():
        for single_region in multi_region["regions"]:
            assert single_region in all_regions, (
                f"Multi-region {single_region} not found in countries.json {all_regions}."
            )
