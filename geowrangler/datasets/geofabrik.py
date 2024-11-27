# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/16_datasets_modis.ipynb.

# %% auto 0
__all__ = ['list_geofabrik_regions', 'get_osm_download_url', 'get_download_filepath', 'download_geofabrik_region',
           'download_osm_region_data', 'OsmDataManager']

# %% ../../notebooks/16_datasets_modis.ipynb 4
import os
from functools import lru_cache
from pathlib import Path
from typing import Union
from urllib.parse import urlparse
from urllib.request import HTTPError

import geopandas as gpd
import requests
from fastcore.all import patch, urlcheck
from loguru import logger

from geowrangler.datasets.utils import make_report_hook, urlretrieve

# %% ../../notebooks/16_datasets_modis.ipynb 5
DEFAULT_CACHE_DIR = "~/.cache/geowrangler"

# %% ../../notebooks/16_datasets_modis.ipynb 6
@lru_cache(maxsize=None)
def load_geofabrik_data():
    return requests.get("https://download.geofabrik.de/index-v1-nogeom.json").json()

# %% ../../notebooks/16_datasets_modis.ipynb 7
def list_geofabrik_regions() -> dict:
    """Get list of regions from geofabrik index"""
    geofabrik_data = load_geofabrik_data()
    return {
        k["properties"]["id"]: k["properties"]["urls"].get("shp")
        for k in geofabrik_data["features"]
        if k["properties"]["urls"].get("shp")
    }

# %% ../../notebooks/16_datasets_modis.ipynb 8
def get_osm_download_url(region, year=None):
    geofabrik_info = list_geofabrik_regions()
    if region not in geofabrik_info:
        raise ValueError(
            f"{region} not found in geofabrik. Run list_geofabrik_regions() to learn more about available areas"
        )
    url = geofabrik_info[region]
    if year is not None:
        short_year = str(year)[-2:]  # take last 2 digits
        year_prefix = f"{short_year}0101"
        url = url.replace("latest", year_prefix)
    return url

# %% ../../notebooks/16_datasets_modis.ipynb 9
def get_download_filepath(url, directory):
    parsed_url = urlparse(url)
    filename = Path(os.path.basename(parsed_url.path))
    filepath = directory / filename
    return filepath

# %% ../../notebooks/16_datasets_modis.ipynb 10
def download_geofabrik_region(
    region: str,
    directory: str = "data/",
    overwrite=False,
    year=None,
    show_progress=True,
    chunksize=8192,
) -> Union[Path, None]:
    """Download geofabrik region to path"""
    if not os.path.isdir(directory):
        os.makedirs(directory)
    url = get_osm_download_url(region, year=year)
    filepath = get_download_filepath(url, directory)

    if not filepath.exists() or overwrite:
        reporthook = make_report_hook(show_progress)

        try:
            filepath, _, _ = urlretrieve(
                url, filepath, reporthook=reporthook, chunksize=chunksize
            )
        except HTTPError as err:
            if err.code == 404:
                if year is not None:
                    logger.warning(
                        f"No data found for year {year} in region {region} : {url}"
                    )
                else:
                    logger.warning(f"No url found for region {region} : {url} ")
                return None
            else:
                raise err

    return filepath

# %% ../../notebooks/16_datasets_modis.ipynb 11
def download_osm_region_data(
    region,
    year=None,
    cache_dir=DEFAULT_CACHE_DIR,
    use_cache=True,
    chunksize=8192,
    show_progress=True,
):

    osm_cache_dir = os.path.join(os.path.expanduser(cache_dir), "osm/")

    url = get_osm_download_url(region, year)
    region_zip_file = get_download_filepath(url, osm_cache_dir)
    logger.info(
        f"OSM Data: Cached data available for {region} at {region_zip_file}? {region_zip_file.exists()}"
    )
    if use_cache and region_zip_file.exists():
        return region_zip_file

    # Download if cache is invalid or user specified use_cache = False
    if not urlcheck(url):
        if year is None:
            logger.warning(f"OSM data for {region} is not available")
        else:
            logger.warning(f"OSM data for {region} and year {year} is not available")
        return None

    logger.info(
        f"OSM Data: Re-initializing OSM region zip file at {region_zip_file}..."
    )
    if region_zip_file.exists():
        region_zip_file.unlink()

    # This downloads a zip file to the region cache dir
    logger.info(f"OSM Data: Downloading Geofabrik in {region_zip_file}...")
    zipfile_path = download_geofabrik_region(
        region,
        year=year,
        directory=osm_cache_dir,
        overwrite=not use_cache,
        show_progress=show_progress,
        chunksize=chunksize,
    )
    if zipfile_path is None:
        return None
    if year is None:
        logger.info(
            f"OSM Data: Successfully downloaded and cached OSM data for {region} at {zipfile_path}!"
        )
    else:
        logger.info(
            f"OSM Data: Successfully downloaded and cached OSM data for {region} and {year} at {zipfile_path}!"
        )

    return zipfile_path

# %% ../../notebooks/16_datasets_modis.ipynb 12
class OsmDataManager:
    """An instance of this class provides convenience functions for loading and caching OSM data"""

    def __init__(self, cache_dir=DEFAULT_CACHE_DIR):
        self.cache_dir = os.path.expanduser(cache_dir)
        self.pois_cache = {}
        self.roads_cache = {}

# %% ../../notebooks/16_datasets_modis.ipynb 13
@patch
def load_pois(
    self: OsmDataManager,
    region,
    year=None,
    use_cache=True,
    chunksize=1024 * 1024,
    show_progress=True,
):
    # Get from RAM cache if already available
    if year is None:
        if region in self.pois_cache:
            logger.debug(f"OSM POIs for {region} found in cache.")
            return self.pois_cache[region]
    else:
        short_year = str(year)[-2:]
        lookup = f"{region}_{short_year}"
        if lookup in self.pois_cache:
            logger.debug(f"OSM POIs for {region} and year {year} found in cache.")
            return self.pois_cache[lookup]

    # Otherwise, load from file and add to cache
    region_zip_file = download_osm_region_data(
        region,
        year=year,
        cache_dir=self.cache_dir,
        use_cache=use_cache,
        chunksize=chunksize,
        show_progress=show_progress,
    )
    if region_zip_file is None:
        return None

    osm_pois_filepath = f"{region_zip_file}!gis_osm_pois_free_1.shp"
    if year is None:
        logger.debug(f"OSM POIs for {region} being loaded from {region_zip_file}")
    else:
        logger.debug(
            f"OSM POIs for {region} and year {year} being loaded from {region_zip_file}"
        )
    gdf = gpd.read_file(osm_pois_filepath)

    if year is None:
        self.pois_cache[region] = gdf
    else:
        short_year = str(year)[-2:]
        lookup = f"{region}_{short_year}"
        self.pois_cache[lookup] = gdf

    return gdf

# %% ../../notebooks/16_datasets_modis.ipynb 14
@patch
def load_roads(
    self: OsmDataManager,
    region,
    year=None,
    use_cache=True,
    chunksize=1024 * 1024,
    show_progress=True,
):
    # Get from RAM cache if already available
    if year is None:
        if region in self.roads_cache:
            logger.debug(f"OSM POIs for {region} found in cache.")
            return self.roads_cache[region]
    else:
        short_year = str(year)[-2:]
        lookup = f"{region}_{short_year}"
        if lookup in self.roads_cache:
            logger.debug(f"OSM POIs for {region} and year {year} found in cache.")
            return self.roads_cache[lookup]

    # Otherwise, load from file and add to cache
    region_zip_file = download_osm_region_data(
        region,
        year=year,
        cache_dir=self.cache_dir,
        use_cache=use_cache,
        chunksize=chunksize,
        show_progress=show_progress,
    )

    if region_zip_file is None:
        return None

    osm_roads_filepath = f"{region_zip_file}!gis_osm_roads_free_1.shp"
    if year is None:
        logger.debug(f"OSM Roads for {region} being loaded from {region_zip_file}")
    else:
        logger.debug(
            f"OSM Roads for {region} and year {year} being loaded from {region_zip_file}"
        )
    gdf = gpd.read_file(osm_roads_filepath)

    if year is None:
        self.roads_cache[region] = gdf
    else:
        short_year = str(year)[-2:]
        lookup = f"{region}_{short_year}"
        self.roads_cache[lookup] = gdf

    return gdf
