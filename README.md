# flugfeld

Maintained list of worldwide airfields with gliding activity with number of launches and link to [OpenAIP](https://www.openaip.net).

This list is used internally at WeGlide to make airports appear on the map based on their 'importance' in the gliding world.

Additionally, this repo contains all kinds of sectors/regions one might want to filter for. Contributions are always welcome!

## Run

To fetch new data from OpenAIP and add WeGlide specific information, you first need to register at OpenAIP and get a custom API client.
Then you can download, parse and augment the data:

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

## Contributing

### Missing airfield

If you find an airfield with gliding activity missing, there are two steps.

1. make sure it is available on [OpenAIP](https://www.openaip.net/) - if not, you can add it there
2. update this repo by performing the actions under the **Run** section

### Naming

Naming of the gliding sites is following local conventions, so if you spot an error, please open a pull request.

### Sectors

The sectors.json file describes all sectors that do not match administrative regions. You may add relevant sectors of your choice.
Just copy and paste the content of the file [here](https://geojson.io/) or look at the GitHub preview to get an overview of already existing sectors.

Order of languages is German, English, French, Dutch, Czech, Italian, Polish.

### Multi Regions

Multi regions are filters that combine multiple regions or countries. You may add relevant multi regions of your choice.
Multi regions can contain both, countries and regions.

## Tiles

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
