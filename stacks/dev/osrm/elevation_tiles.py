"""Sirve una capa visual XYZ desde los GeoTIFF locales sin modificar sus archivos"""

from collections import OrderedDict
import math
from pathlib import Path
import threading
import uuid

from osgeo import gdal, osr


gdal.UseExceptions()
TILE_SIZE = 256
MAX_ZOOM = 16
MERCATOR_RADIUS_M = 6378137.0
NODATA = -32768.0
PALETTE = """0 33 102 172 255
1000 26 152 80 255
2000 166 217 106 255
3000 254 224 139 255
4000 244 109 67 255
5000 158 103 80 255
6000 245 245 245 255
nv 0 0 0 0
"""


class ElevationTiles:
    """Serializa el acceso GDAL y conserva hasta 128 imagenes en memoria por proceso"""

    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.signature = None
        self.source = None
        self.datasets = []
        self.bounds = None
        self.blank = None
        prefix = "/vsimem/routing-elevation-" + uuid.uuid4().hex
        self.vrt_path = prefix + ".vrt"
        self.palette_path = prefix + ".txt"
        self.png_path = prefix + ".png"

    def tile(self, zoom, x, y):
        if not 0 <= zoom <= MAX_ZOOM or not 0 <= x < (1 << zoom) or not 0 <= y < (1 << zoom):
            raise ValueError("Invalid XYZ tile coordinates")
        with self.lock:
            paths = sorted(self.directory.glob("*.tif"))
            if not paths:
                raise FileNotFoundError("The local elevation rasters are not available")
            signature = tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in paths)
            if signature != self.signature:
                self.reload(paths, signature)
            key = (zoom, x, y)
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            bounds = tile_bounds(zoom, x, y)
            west, south, east, north = geographic_bounds(bounds)
            source_west, source_south, source_east, source_north = self.bounds
            if east <= source_west or west >= source_east or north <= source_south or south >= source_north:
                if self.blank is None:
                    blank = gdal.GetDriverByName("MEM").Create("", TILE_SIZE, TILE_SIZE, 4, gdal.GDT_Byte)
                    colors = (gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand, gdal.GCI_AlphaBand)
                    for index, color in enumerate(colors, 1):
                        band = blank.GetRasterBand(index)
                        band.Fill(0)
                        band.SetColorInterpretation(color)
                    self.blank = self.png_bytes(blank)
                payload = self.blank
            else:
                warped = gdal.Warp(
                    "", self.source, format="MEM", dstSRS="EPSG:3857", outputBounds=bounds,
                    width=TILE_SIZE, height=TILE_SIZE, resampleAlg="bilinear", dstNodata=NODATA,
                    outputType=gdal.GDT_Float32, multithread=False, warpMemoryLimit=16,
                )
                if warped is None:
                    raise RuntimeError("Elevation reprojection failed")
                colored = gdal.DEMProcessing(
                    "", warped, "color-relief", format="MEM", colorFilename=self.palette_path, addAlpha=True,
                )
                if colored is None:
                    raise RuntimeError("Elevation color rendering failed")
                payload = self.png_bytes(colored)
            self.cache[key] = payload
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
            return payload

    def reload(self, paths, signature):
        self.source = None
        self.datasets.clear()
        self.cache.clear()
        self.blank = None
        self.signature = None
        unlink_virtual(self.vrt_path)
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(4326)
        try:
            for path in paths:
                if not path.resolve().is_relative_to(self.directory):
                    raise ValueError("Elevation sources must remain inside the configured directory")
                dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
                if dataset is None or dataset.RasterCount != 1:
                    raise ValueError("The elevation raster must contain one height band")
                spatial_reference = dataset.GetSpatialRef()
                if spatial_reference is None or not spatial_reference.IsSame(reference):
                    raise ValueError("Elevation rasters must use EPSG:4326")
                band = dataset.GetRasterBand(1)
                if band.GetScale() not in (None, 1) or band.GetOffset() not in (None, 0):
                    raise ValueError("The elevation band must contain heights directly in meters")
                self.datasets.append(dataset)
            self.source = gdal.BuildVRT(
                self.vrt_path, self.datasets, options=gdal.BuildVRTOptions(
                    resolution="highest", bandList=[1], VRTNodata=NODATA, strict=True,
                ),
            )
            if self.source is None:
                raise RuntimeError("The elevation mosaic could not be prepared")
            transform = self.source.GetGeoTransform()
            if transform[2] or transform[4] or transform[1] <= 0 or transform[5] >= 0:
                raise ValueError("The elevation mosaic must be north-up")
            self.bounds = (transform[0], transform[3] + transform[5] * self.source.RasterYSize,
                           transform[0] + transform[1] * self.source.RasterXSize, transform[3])
            gdal.FileFromMemBuffer(self.palette_path, PALETTE.encode("ascii"))
            # No se publica una cache armada con archivos que cambiaron durante la apertura
            current = tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns)
                            for path in sorted(self.directory.glob("*.tif")))
            if current != signature:
                raise RuntimeError("Elevation rasters changed while opening the mosaic")
            self.signature = signature
        except Exception:
            self.source = None
            self.datasets.clear()
            unlink_virtual(self.vrt_path)
            raise

    def png_bytes(self, dataset):
        handle = None
        try:
            output = gdal.Translate(self.png_path, dataset, format="PNG")
            if output is None:
                raise RuntimeError("The elevation PNG could not be encoded")
            output.FlushCache()
            output = None
            handle = gdal.VSIFOpenL(self.png_path, "rb")
            if handle is None:
                raise RuntimeError("The elevation PNG could not be read")
            gdal.VSIFSeekL(handle, 0, 2)
            length = gdal.VSIFTellL(handle)
            gdal.VSIFSeekL(handle, 0, 0)
            payload = bytes(gdal.VSIFReadL(1, length, handle))
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Invalid elevation PNG output")
            return payload
        finally:
            if handle is not None:
                gdal.VSIFCloseL(handle)
            unlink_virtual(self.png_path)
            unlink_virtual(self.png_path + ".aux.xml")


def tile_bounds(zoom, x, y):
    half_world = math.pi * MERCATOR_RADIUS_M
    span = 2 * half_world / (1 << zoom)
    west = -half_world + x * span
    north = half_world - y * span
    return west, north - span, west + span, north


def geographic_bounds(bounds):
    west, south, east, north = bounds
    return (math.degrees(west / MERCATOR_RADIUS_M),
            math.degrees(math.atan(math.sinh(south / MERCATOR_RADIUS_M))),
            math.degrees(east / MERCATOR_RADIUS_M),
            math.degrees(math.atan(math.sinh(north / MERCATOR_RADIUS_M))))


def unlink_virtual(path):
    if gdal.VSIStatL(path) is not None:
        gdal.Unlink(path)
