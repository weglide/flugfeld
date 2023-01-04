![WeGlide flugfeld](./logo-flugfeld.png)

![Tests](https://github.com/weglide/flugfeld/workflows/Tests/badge.svg)

# flugfeld

Maintained list of worldwide airfields with gliding activity with number of launches and link to [OpenAIP](https://www.openaip.net).

This list is used internally at WeGlide to make airports appear on the map based on their 'importance' in the gliding world.
We are syncing the number of flights from the airfields (uploaded on WeGlide) on a yearly basis.

Additionally, this repo contains all kinds of sectors/regions one might want to filter for. Contributions are always welcomed!

## OpenAIP Link

To link **flugfeld** to OpenAIP, you first need to register at OpenAIP and get a custom API client.
Then you can download and parse the data

```bash
export X-OPENAIP-CLIENT-ID=your_client_id
python -m src.openaip.py
```

## Contributing

### Missing airfield

If you find an airfield with gliding activity missing, there are two steps.

- make sure it is available on [OpenAIP](https://www.openaip.net/) - if not, you can add it there
- add the missing row and open a pull request

### Airfield not in administrative region

OpenAIP does not provide administrative regions. All airfields that are not in this list (For example EDDF) only belong to a country,
not to a particular region. If there is in fact gliding activity on this airfield, you can add it here.

### Number of launches

The provided number of launches is used as an indicator as to when airports appear on the map. If you add a new airfield, you may add a reasonable number.
Number of launches is only important in comparison with near by airfields, as we compute a 'reign' parameter.

### Naming

Naming of the gliding sites is following local conventions, so if you spot an error, please open a pull request.

### Missing

Areas with missing information include:

- Russia
- South America
- Japan

This in parts due to airport information missing on OpenAIP

### Sectors

The sectors.json file describes all sectors that do not match administrative regions. You may add relevant sectors of your choice.
Just copy and paste the content of the file [here](https://geojson.io/) or look at the GitHub preview to get an overview of already existing sectors.

Order of languages is German, English, French, Dutch, Czech, Italian, Polish.

### Multi Regions

Multi regions are filters that combine multiple regions or countries. You may add relevant multi regions of your choice.
Multi regions can contain both, countries and regions.

## Tiles

To render mbtiles from geojson, we suggest using [tippecanoe](https://github.com/mapbox/tippecanoe). Install on OS X with

```bash
brew install tippecanoe
```

or on Ubuntu with

```bash
git clone https://github.com/mapbox/tippecanoe.git
cd tippecanoe
make -j
make install
```

Then, to render the tiles

```bash
tippecanoe -Z3 -z14 -f -r1 -pk -pf -J airport_filter.json -o airport.mbtiles airport.geojson
```

To only include important fields, run

```bash
tippecanoe -Z3 -z14 -f -r1 -pk -pf -y id -y openaip_id -y name -y reign -y elevation -y runway_rotation -J airport_filter.json -o airport.mbtiles airport.geojson
```

To have a look at the tiles, run the code below and open `localhost:8080` in your browser.

```bash
docker run --rm -it -v $(pwd):/data -p 8080:80 maptiler/tileserver-gl
```
