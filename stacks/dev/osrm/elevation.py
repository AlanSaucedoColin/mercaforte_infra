"""Precalcula alturas y pendiente neta visual sin modificar el grafo ni sus costos"""

import hashlib
import math
from pathlib import Path

from osgeo import gdal, osr


gdal.UseExceptions()
EARTH_RADIUS_M = 6371008.8


class ElevationSampler:
    """Lee pixeles locales y conserva una huella independiente de la identidad del mapa OSM"""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.tiles = []
        self.source_stamps = []
        digest = hashlib.sha256(b"routing-elevation-v1-nearest-haversine-net")
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(4326)
        try:
            for path in sorted(self.directory.glob("*.tif")):
                stamp = path.stat()
                self.source_stamps.append((path, stamp.st_size, stamp.st_mtime_ns))
                digest.update(path.name.encode())
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
                if dataset is None or dataset.RasterCount < 1:
                    raise ValueError("The elevation raster has no readable height band")
                spatial_reference = dataset.GetSpatialRef()
                if spatial_reference is None or not spatial_reference.IsSame(reference):
                    raise ValueError("Elevation rasters must use EPSG:4326")
                inverse = gdal.InvGeoTransform(dataset.GetGeoTransform())
                if inverse is None:
                    raise ValueError("The elevation raster has no invertible geotransform")
                self.tiles.append((dataset, dataset.GetRasterBand(1), inverse))
            self.fingerprint = digest.hexdigest()
            self.verify_unchanged()
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.close()

    def close(self):
        self.tiles.clear()

    def verify_unchanged(self):
        current = [(path, path.stat().st_size, path.stat().st_mtime_ns)
                   for path in sorted(self.directory.glob("*.tif"))]
        if current != self.source_stamps:
            raise RuntimeError("The elevation source changed during preprocessing")

    def sample(self, longitude, latitude):
        for dataset, band, inverse in self.tiles:
            x, y = gdal.ApplyGeoTransform(inverse, longitude, latitude)
            column, row = math.floor(x), math.floor(y)
            if not (0 <= column < dataset.RasterXSize and 0 <= row < dataset.RasterYSize):
                continue
            pixels = band.ReadAsArray(column, row, 1, 1)
            if pixels is None:
                raise RuntimeError("An elevation pixel could not be read")
            value = float(pixels[0, 0])
            nodata = band.GetNoDataValue()
            if not math.isfinite(value) or (nodata is not None and value == nodata):
                continue
            mask = band.GetMaskBand().ReadAsArray(column, row, 1, 1)
            if mask is None:
                raise RuntimeError("An elevation validity mask could not be read")
            if not mask[0, 0]:
                continue
            scale = band.GetScale()
            offset = band.GetOffset()
            value = value * (1 if scale is None else scale) + (0 if offset is None else offset)
            if math.isfinite(value):
                return value
        return None

    def metrics(self, coordinates):
        if len(coordinates) < 2:
            raise ValueError("A road geometry needs at least two coordinates")
        start = self.sample(*coordinates[0][:2])
        end = self.sample(*coordinates[-1][:2])
        percent = degrees = None
        if start is not None and end is not None:
            distance = math.fsum(horizontal_distance(a, b) for a, b in zip(coordinates, coordinates[1:]))
            if distance > 0.000001:
                rise = end - start
                percent = round(100 * rise / distance, 3)
                degrees = round(math.degrees(math.atan2(rise, distance)), 3)
        return (None if start is None else round(start, 2),
                None if end is None else round(end, 2), percent, degrees)


def horizontal_distance(start, end):
    longitude1, latitude1 = map(math.radians, start[:2])
    longitude2, latitude2 = map(math.radians, end[:2])
    haversine = (math.sin((latitude2 - latitude1) / 2) ** 2
                 + math.cos(latitude1) * math.cos(latitude2) * math.sin((longitude2 - longitude1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(max(0.0, min(1.0, haversine))))
