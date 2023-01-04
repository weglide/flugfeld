import csv
import json

NAME_MAPPING = "data/flugfeld.csv"

with open("geo/countries.json") as file:
    data = json.load(file)["data"]
    countries = {}
    for el in data.values():
        countries.update(el["regions"])


with open("geo/multi_regions.json") as file:
    multi_regions = json.load(file)["data"]


def assert_region(region: str, countries: dict):
    country_str = region.split("-")[0]
    country = countries.get(country_str)
    assert country is not None, f"Country {country_str} not found"
    if "-" in region:
        assert country.get("regions") is not None, f"No regions for country {country}"
        assert (
            country["regions"].get(region) is not None
        ), f"No region {region} for country {country}"


def test_countries_and_regions():
    with open(NAME_MAPPING) as file:
        reader = csv.reader(file, delimiter=",")
        next(reader)
        for row in reader:
            assert_region(row[0], countries)


def test_unique_id():
    with open(NAME_MAPPING) as file:
        reader = csv.reader(file, delimiter=",")
        next(reader)
        seen = set()
        for row in reader:
            if row[5] == "x":
                continue
            assert row[3] not in seen
            seen.add(row[3])


def test_multi_regions():
    for v in multi_regions.values():
        for r in v["regions"]:
            assert_region(r, countries)
