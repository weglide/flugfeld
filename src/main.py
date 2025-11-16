import os

from dotenv import load_dotenv

from src.arrange import filter_airports, merge_airports, sort_airports
from src.csv import read_airports as read_csv
from src.csv import write_airports as write_csv
from src.download import download_airports
from src.geojson import write_airports as write_geojson
from src.id import assign_weglide_id
from src.name import assign_weglide_name
from src.region import assign_continent, assign_region, assign_timezone
from src.reign import assign_launches, assign_reign

if __name__ == "__main__":
    # Setup.
    load_dotenv()
    api_key = os.environ.get("OPENAIP_API_KEY")

    # Read data.
    remote_airports = download_airports(api_key)
    remote_airports = filter_airports(remote_airports)
    existing_airports = read_csv()
    airports = merge_airports(existing_airports, remote_airports)
    airports = sort_airports(airports)

    # Augment data.
    airports = assign_weglide_id(airports)
    airports = assign_weglide_name(airports)
    airports = assign_continent(airports)
    airports = assign_timezone(airports)
    airports = assign_region(airports)
    airports = assign_launches(airports, force=False)
    airports = assign_reign(airports)

    # Write data.
    write_csv(airports)
    write_geojson(airports)
