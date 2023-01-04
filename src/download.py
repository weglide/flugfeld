import csv
import datetime as dt
import json
import os
from typing import Any

import numpy as np
import requests
from dotenv import load_dotenv
from geojson import Feature, FeatureCollection
from geojson import Point as GeoJsonPoint
from geojson import dump
from scipy.spatial.distance import cdist
from timezonefinder import TimezoneFinder

from .api_types import FrequencyKind, OpenAipKind, RunwayComposition

WGS_84_SRID: int = 4326
EARTH_RADIUS_KM: float = 6371.0
METER_PER_FEET: float = 0.3048
MAX_DB_ID: int = 3218781

CONTINENTS = "geo/continents.json"
PK_MAPPING = "data/pk_mapping.json"
NAME_MAPPING = "data/flugfeld.csv"
GEOJSON_DUMP = "airport.geojson"
AIRPORT_URL = "https://api.core.openaip.net/api/airports"

load_dotenv()
CLIENT_ID = os.environ["X-OPENAIP-CLIENT-ID"]


class OpenAipParser:
    def __init__(self):
        self.tf = TimezoneFinder()
        self.identifiers: list[int] = []
        self.lat: list[int] = []
        self.lon: list[int] = []
        self.no_existing_ids: list[tuple[int, str, str]] = []

        with open(CONTINENTS) as json_file:
            self.continents = json.load(json_file)

        with open(PK_MAPPING) as json_file:
            self.items = json.load(json_file)
            self.max_id = max(max([v["id"] for v in self.items]), MAX_DB_ID)
            self.pk_mapping = {v["openaip_id"]: v for v in self.items}

    def find_continent(self, country: str) -> str:
        for k, v in self.continents.items():
            if country in v:
                return k

        raise AssertionError(f"No continent found for country {country}")

    def create_dist_matrix(self) -> np.ndarray:
        """Simple 2d projection"""
        lonlat = np.radians(self.lonlat)
        theta = np.cos(np.mean(lonlat[:, 1]))
        lonlat[:, 0] *= theta

        return cdist(lonlat, lonlat, "euclidean") * EARTH_RADIUS_KM

    def dump_to_geojson(self):
        print(f"Dumping to {GEOJSON_DUMP}...")
        feature_collection = FeatureCollection(list(self.features.values()))
        with open(GEOJSON_DUMP, "w") as f:
            dump(feature_collection, f, indent=4)
        print(f"Dumped to {GEOJSON_DUMP}")

    def read_csv(self):
        self.airports = {}
        with open(NAME_MAPPING, encoding="utf8") as csv_file:
            reader = csv.reader(csv_file, delimiter=",")
            next(reader)

            self.airports = {
                int(row[3]): {
                    "name": row[1],
                    "openaip_name": row[2],
                    "country": row[0][:2],
                    "region": row[0],
                    "launches": int(row[4]),
                }
                for row in reader
                if not row[5]
            }

    def parse(self) -> None:
        self.read_csv()
        self.download()
        if self.features:
            print("Assigning reign...")
            self.assign_reign()
            print("Assigned reign")

        self.write_new_mapping()

    def write_new_mapping(self) -> None:
        # write new ids
        with open(PK_MAPPING, "w") as json_file:
            created = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_items = [
                {
                    "name": item[2],
                    "id": item[0],
                    "openaip_id": item[1],
                    "created": created,
                }
                for item in self.no_existing_ids
            ]
            combined = self.items + new_items
            json.dump(combined, json_file, indent=4)
        print(f"Wrote new mappings for {len(new_items)} airports")

    def download(self):
        airports: list[Any] = []
        headers = {"x-openaip-client-id": CLIENT_ID}
        response = requests.get(AIRPORT_URL, headers=headers)
        data = response.json()
        total_count = data["totalCount"]
        for i in range(1, 2 + (total_count // 1000)):
            response = requests.get(AIRPORT_URL, params={"page": i}, headers=headers)
            data = response.json()
            print(f"{len(data['items'])} airports on page {i}")
            airports.extend(data["items"])
        print(f"Downloaded {len(airports)} airports")

        features = [self.as_feature(item) for item in airports]
        features = [f for f in features if f is not None]
        print(f"Converted {len(features)} to features (HELIPORTS are excluded)")
        print(f"No old ids for {len(self.no_existing_ids)} airports")

        self.features: dict[int, Any] = {f["properties"]["id"]: f for f in features}

    def as_feature(self, item: dict[str, Any]) -> Feature | None:
        if not item["approved"]:
            return None
        openaip_id = item["_id"]
        kind = OpenAipKind(int(item["type"]))
        if kind in (OpenAipKind.HELIPORT_CIVIL, OpenAipKind.HELIPORT_MILITARY):
            return None

        openaip_name = item["name"]
        icao = item.get("icaoCode")
        country = item["country"]

        radio = {}
        if len(item.get("frequencies", [])) > 0:
            # check if there is a primary one, else take first
            frequency = next(
                (f for f in item["frequencies"] if f["primary"]), item["frequencies"][0]
            )
            radio = {
                "radio_frequency": frequency["value"],
                "radio_type": FrequencyKind(int(frequency["type"])).name,
                "radio_description": frequency.get("name"),
            }

        rwy = {}
        if len(item.get("runways", [])) > 0:
            # check if there is a main runway, else take first
            runway = next(
                (f for f in item["runways"] if f["mainRunway"]), item["runways"][0]
            )
            assert runway["dimension"]["length"]["unit"] == 0
            assert runway["dimension"]["width"]["unit"] == 0
            assert int(runway["trueHeading"]) <= 360
            rwy = {
                "rwy_name": runway["designator"],
                "rwy_sfc": RunwayComposition(
                    int(runway["surface"]["mainComposite"])
                ).name,
                "rwy_direction": int(runway["trueHeading"]),
                "runway_rotation": int(runway["trueHeading"]),
                "rwy_length": runway["dimension"]["length"]["value"],
                "rwy_width": runway["dimension"]["width"]["value"],
            }

        geometry = GeoJsonPoint(item["geometry"]["coordinates"])
        elevation = item["elevation"]["value"]
        lon, lat = item["geometry"]["coordinates"]
        assert item["elevation"]["unit"] == 0

        match = None
        db_id = self.pk_mapping.get(openaip_id, {}).get("id")
        if db_id is None:
            self.max_id += 1
            db_id = self.max_id
            self.no_existing_ids.append((db_id, openaip_id, openaip_name))

        match = self.airports.get(db_id)
        if match is not None:
            self.lon.append(lon)
            self.lat.append(lat)
            self.identifiers.append(db_id)

        name = match["name"] if match is not None else openaip_name.title()
        if (timezone := self.tf.timezone_at(lng=lon, lat=lat)) is None:
            return None
        properties: dict[str, Any] = {
            "id": db_id,
            "openaip_id": openaip_id,
            "name": name,
            "openaip_name": openaip_name,
            "kind": kind.name,
            "region": match["region"] if match is not None else country,
            "continent": self.find_continent(country),
            "launches": match["launches"] if match is not None else None,
            "icao": icao,
            "reign": 256 if match is not None else 0,
            "openaip_elevation": elevation,
            "elevation": elevation,
            "timezone": timezone,
            **radio,
            **rwy,
        }
        return Feature(geometry=geometry, properties=properties)

    def assign_reign(self):
        self.lonlat = np.column_stack((np.array(self.lon), np.array(self.lat)))
        self.dist_matrix = self.create_dist_matrix()
        reign = [1000] * len(self.lonlat)

        for i in range(len(self.lonlat)):
            for j in range(len(self.lonlat)):
                # only traverse upper triangle
                if j >= i:
                    continue

                dist = self.dist_matrix[i, j]
                if dist >= max(reign[i], reign[j]):
                    continue

                identifier1 = self.identifiers[i]
                identifier2 = self.identifiers[j]

                launches1 = self.features[identifier1]["properties"]["launches"]
                launches2 = self.features[identifier2]["properties"]["launches"]

                if launches1 >= launches2:
                    if reign[j] > dist:
                        reign[j] = round(dist)
                    continue

                if reign[i] > dist:
                    reign[i] = round(dist)

        for i in range(len(reign)):
            identifier = self.identifiers[i]
            r = reign[i]
            self.features[identifier]["properties"]["reign"] = r


if __name__ == "__main__":
    aip_parser = OpenAipParser()
    aip_parser.parse()
    aip_parser.dump_to_geojson()
