import csv
import json
import os
from typing import Optional, Any, Callable
from xml.etree import ElementTree as ET  # type: ignore

import numpy as np
from geojson import Feature, FeatureCollection
from geojson import Point as GeoJsonPoint
from geojson import dump
from scipy.spatial.distance import cdist
from timezonefinder import TimezoneFinder


EARTH_RADIUS_KM: float = 6371.0
METER_PER_FEET: float = 0.3048

AIRPORT_DATA = "data/"
CONTINENTS = "continents.json"
GEOJSON_DUMP = "airport.geojson"


def text_or_none(el, attr: str) -> Optional[str]:
    return el.find(attr).text if el.find(attr) is not None else None

def and_then(arg: Optional[Any], f: Callable):
    return f(arg) if arg is not None else None


class OpenAipParser:
    help = "Read .aip or .xml files from Openaip into geojson"

    def __init__(self):
        self.tf = TimezoneFinder()
        self.suggested = []
        self.identifiers = []
        self.lat = []
        self.lon = []

        with open(CONTINENTS) as json_file:
            self.continents = json.load(json_file)

    def find_continent(self, country: str) -> str:
        for k, v in self.continents.items():
            if country in v:
                return k
        assert False, "no continent found"

    def dist_matrix(self, lonlat):
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
        with open("flugfeld.csv", encoding="utf8") as csv_file:
            reader = csv.reader(csv_file, delimiter=",")
            next(reader)

            self.airports = {
                int(row[3]): {
                    "name": row[1],
                    "openaip_name": row[2],
                    "country": row[0][:2],
                    "region": row[0],
                    "launches": int(row[4]),
                } for row in reader if not row[5]
            }

    def parse(self, filename: Optional[str] = None) -> None:
        self.read_csv()
        self.features = {}

        if filename is not None:
            print(f"Parsing: {filename}")
            self.parse_file(os.path.join(AIRPORT_DATA, filename))
        else:
            assert os.path.isdir(AIRPORT_DATA), "no data dir"
            for filename in os.listdir(AIRPORT_DATA):
                if "wpt" in filename and filename.endswith(".aip"):
                    print(f"Parsing: {filename}")
                    self.parse_file(os.path.join(AIRPORT_DATA, filename))

        if self.features:
            print("Assigning reign...")
            self.assign_reign()
            print("Assigned reign")

    def parse_file(self, file):
        airports = ET.parse(file)
        root = airports.getroot()
        for airport in root[0]:
            kind = airport.attrib["TYPE"]
            if kind == "HELI_CIVIL":
                continue

            openaip_name = airport.find("NAME").text
            if not (id_str := airport.find("IDENTIFIER").text):
                continue
            identifier = int(id_str)
            icao = text_or_none(airport, "ICAO")
            country = airport.find("COUNTRY").text
            assert country is not None

            radio = {}
            if (radio_xml := airport.find("RADIO")) is not None:
                radio = {
                    "radio_category": radio_xml.attrib["CATEGORY"],
                    "radio_frequency": radio_xml.find("FREQUENCY").text,
                    "radio_type": radio_xml.find("TYPE").text,
                    "radio_description": text_or_none(radio_xml, "DESCRIPTION"),
                }

            geolocation = airport.find("GEOLOCATION")
            lon = round(float(geolocation.find("LON").text), 5)
            lat = round(float(geolocation.find("LAT").text), 5)
            geometry = GeoJsonPoint((lon, lat))

            elevation = geolocation.find("ELEV").text
            assert elevation is not None
            elevation_unit = geolocation.find("ELEV").attrib["UNIT"]
            if elevation_unit == "F":
                elevation = round(float(elevation) * METER_PER_FEET, 1)

            rwy = {}
            if (rwy_xml := airport.find("RWY"))is not None:
                rwy = {
                    "rwy_name": text_or_none(rwy_xml, "NAME"),
                    "rwy_sfc": text_or_none(rwy_xml, "SFC"),
                    "rwy_rotation": int(rwy_xml.find("DIRECTION").attrib["TC"]),
                    "rwy_length": and_then(text_or_none(rwy_xml, "LENGTH"), float),
                    "rwy_width":  and_then(text_or_none(rwy_xml, "WIDTH"), float),
                    "rwy_strength": text_or_none(rwy_xml, "STRENGTH"),
                }
                assert rwy["rwy_rotation"] <= 360

            match = self.airports.get(identifier)
            if match is not None:
                self.lat.append(lat)
                self.lon.append(lon)
                self.identifiers.append(identifier)

            name = match["name"] if match is not None else openaip_name.title()
            properties = {
                "id": identifier,
                "latitude": lat,
                "longitude": lon,
                "name": name,
                "openaip_name": openaip_name,
                "kind": kind,
                "country": country,
                "region": match["region"] if match is not None else country,
                "continent": self.find_continent(country),
                "launches": match["launches"] if match is not None else None,
                "icao": icao,
                "style": kind.lower(),
                "reign": 256 if match is not None else 0,
                "openaip_elevation": elevation,
                "elevation": elevation,
                "timezone": self.tf.timezone_at(lng=lon, lat=lat),
                **radio,
                **rwy,
            }

            self.features[identifier] = Feature(
                geometry=geometry, properties=properties
            )

    def assign_reign(self):
        self.lonlat = np.column_stack((np.array(self.lon), np.array(self.lat)))
        self.dist_matrix = self.dist_matrix(self.lonlat)
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
