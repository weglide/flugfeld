# Flugfeld

Maintained list of worldwide airfields with gliding activity with number of launches and link to [OpenAIP](https://www.openaip.net).

This list is used internally at WeGlide to make airports appear on the map based on their 'importance' in the gliding world. It is also used for loading airports into the Database.

Additionally, this repo contains all kinds of sectors/regions one might want to filter for. They are copied across projects but these here are the most up-to date ones.

## Run

To fetch new data from OpenAIP and add WeGlide specific information, you first need to register at OpenAIP and get a custom API client.
Then you can download, parse and augment/update the data automatically with this command:

```sh
export OPENAIP_API_KEY=your_api_key
uv run python -m flugfeld.src.main
```

## Pre-Commit Hook

Install the pre-commit hook for tests.

```sh
cp pre-commit .git/hooks/ && chmod +x .git/hooks/pre-commit
```

## Testing

```sh
uv run pytest
```

## Tile generation

To render mbtiles from geojson, we suggest using [tippecanoe](https://github.com/felt/tippecanoe). Install on OS X with

```sh
git clone https://github.com/felt/tippecanoe.git
cd tippecanoe
make -j
make install
```

Then, to render the tiles

```sh
tippecanoe -Z3 -z14 -f -r1 -pk -pf -y id -y openaip_id -y name -y reign -y elevation -y runway_rotation -y lng -y lat -y radio_frequency -y radio_description -J airport_filter.json -o airport.pmtiles airport.geojson

```

To have a look at the tiles, run the code below and open `localhost:8080` in your browser.

```sh
docker run --rm -it -v $(pwd):/data -p 8080:80 maptiler/tileserver-gl
```

## CI

The airport.geojson is automatically uploaded to S3 and then ready to be loaded from other applications.

The tiles are also automatically uploaded to S3 with the current date in the filename, e.g. airport-2024-04-10.pmtiles
AWS Lambda functions is then serving individual tiles on the fly from this .pmtiles file.

## Contributing

### Missing airfield

If you find an airfield with gliding activity missing, there are two steps.

1. make sure it is available on [OpenAIP](https://www.openaip.net/) - if not, you can add it there
2. update this repo by performing the actions under the **Run** section
3. GitHub actions will automatically deploy the changes on push

### Naming

Naming of the gliding sites is following local conventions, so if you spot an error, please open a pull request with the updated `weglide_name` in the `airport.csv`.

### Sectors

The `geo/sectors.json` file describes all sectors that do not match administrative regions. You may add relevant sectors of your choice.
Just copy and paste the content of the file [here](https://geojson.io/) or look at the GitHub preview to get an overview of already existing sectors.

Order of languages is German, English, French, Dutch, Czech, Italian, Polish.

### Multi Regions

The `geo/multi_regions.json` file contains filters that combine multiple regions or countries. You may add relevant multi regions of your choice.

### Countries and Regions

The `geo/countries.json` file contains all the countries with regions that can be filtered for on WeGlide. The list does not contain all existing countries as some are not interesting for gliders and therefore not translated. The `geo/continents.json` file contains a more complete list of countries.

### Structure

The `airport.csv` is a human-readable intermediate representation that get's converted 1:1 into `airport.geojson`. This generated file is deployed to the database and tiles are generated from it. Manual edits can be done here if it is not possible to do them upstream on OpenAIP.

#### weglide_id

WeGlide ID, used for https://www.weglide.org/airport/{weglide_id}
Auto-incrementing integer, needed because OpenAIP changed their primary key from integer to UUID.
Written automatically.

#### openaip_id

The new OpenAIP ID format, used for https://www.openaip.net/data/airports/{openaip_id} UUID.
Written automatically.

#### weglide_name

Sanitized airport name in title case.
Written automatically on add but can be overwritten.

#### openaip_name

Original airport name coming from OpenAIP.
Written automatically.

#### kind

Airport kind/type coming from OpenAIP. Some types are filtered.
Written automatically.

#### longitude, latitude

Coordinates in decimal coming from OpenAIP.
Written automatically.

#### elevation

Elevation in meters coming from OpenAIP
Written automatically.

#### region

Country the airport is located in with optional region specifier (e.g. DE-BY). 
Retrieved from reverse geocoding API and tested against `countries.json` and `continents.json`.
Written automatically on add but can be overwritten.

#### continent

Continent the airport is located in.
Retrieved from `continents.json`.
Written automatically on add but can be overwritten.

#### timezone

Timezone of flights originating from this airport.
Written automatically on add but can be overwritten.

#### launches

Number of gliding launches done from this airport according to WeGlide uploads.
Written automatically for new entries, to update all entries set the `force` flag in `main.py`.

#### reign

Importance of the airport calculated from the number of launches and the nearby airports.
The value is the number of kilometers to the next more important airport, capped at 1000.
Written automatically.

#### radio_*

Radio information of the primary/first radio entry in OpenAIP.
Written automatically.

#### rwy_*

Runway information of the primary/first runway entry in OpenAIP.
Written automatically.
