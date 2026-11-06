"""Recorte real de geometrías MVT: extract --bbox/--region solo selecciona teselas completas."""
import gzip
import math

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import Compression, zxy_to_tileid
from pmtiles.writer import Writer
from geographiclib.geodesic import Geodesic
from shapely import make_valid, set_precision
from shapely.affinity import affine_transform
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union


def square_coverage(center, side_meters):
    """Cuadrado norte/sur/este/oeste con distancias WGS84 medidas desde el centro."""
    latitude, longitude = center['latitude'], center['longitude']
    assert -85 < latitude < 85 and -180 < longitude < 180 and 0 < side_meters <= 200000
    half = side_meters / 2
    north = Geodesic.WGS84.Direct(latitude, longitude, 0, half)['lat2']
    south = Geodesic.WGS84.Direct(latitude, longitude, 180, half)['lat2']
    east = Geodesic.WGS84.Direct(latitude, longitude, 90, half)['lon2']
    west = Geodesic.WGS84.Direct(latitude, longitude, 270, half)['lon2']
    return box(west, south, east, north)


def world_coordinates(region):
    def project(longitude, latitude, z=None):
        return ((longitude + 180) / 360,
                (1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2)
    return transform(project, region)


def tile_region(world_region, z, x, y, extent):
    scale = 2 ** z * extent
    return affine_transform(world_region, [scale, 0, 0, scale, -x * extent, -y * extent])


def keep_geometry_family(geometry, family):
    if geometry.is_empty:
        return None
    if geometry.geom_type == 'GeometryCollection':
        pieces = [keep_geometry_family(child, family) for child in geometry.geoms]
        pieces = [piece for piece in pieces if piece is not None]
        return unary_union(pieces) if pieces else None
    return geometry if family in geometry.geom_type else None


def clip_tile(data, z, x, y, world_region):
    layers = mapbox_vector_tile.decode(data, default_options={'y_coord_down': True})
    result, options, regions = [], {}, {}
    before = after = 0
    for name, layer in layers.items():
        extent = layer['extent']
        if extent not in regions:
            # Conservar el buffer propio de MVT para evitar costuras entre teselas.
            padding = extent / 16
            regions[extent] = tile_region(world_region, z, x, y, extent).intersection(
                box(-padding, -padding, extent + padding, extent + padding))
        region = regions[extent]
        retained = []
        for feature in layer['features']:
            before += 1
            geometry = shape(feature['geometry'])
            if not geometry.is_valid:
                geometry = make_valid(geometry)
            if region.is_empty or geometry.is_empty or not region.intersects(geometry):
                continue
            family = 'Polygon' if 'Polygon' in feature['geometry']['type'] else (
                'LineString' if 'LineString' in feature['geometry']['type'] else 'Point')
            clipped = geometry if region.covers(geometry) else geometry.intersection(region)
            clipped = keep_geometry_family(clipped, family)
            if clipped is not None:
                # MVT usa coordenadas enteras; descartar fragmentos que colapsan al redondear.
                clipped = set_precision(clipped, 1)
            if clipped is not None and not clipped.is_empty:
                retained.append({**feature, 'geometry': clipped})
                after += 1
        if retained:
            result.append({'name': name, 'features': retained})
            options[name] = {'extents': extent, 'y_coord_down': True}
    encoded = mapbox_vector_tile.encode(result, per_layer_options=options, default_options={'y_coord_down': True})
    return encoded, before, after


def clip_archive(source, destination, region, definition):
    world_region = world_coordinates(region)
    statistics = {'inputTiles': 0, 'outputTiles': 0, 'inputFeatures': 0, 'retainedFeatures': 0}
    with source.open('rb') as input_file, destination.open('wb') as output_file:
        get_bytes = MmapSource(input_file)
        reader = Reader(get_bytes)
        header = reader.header()
        metadata = reader.metadata()
        assert header['tile_compression'] == Compression.GZIP
        writer = Writer(output_file)
        for (z, x, y), compressed in all_tiles(get_bytes):
            encoded, before, after = clip_tile(gzip.decompress(compressed), z, x, y, world_region)
            statistics['inputTiles'] += 1
            statistics['inputFeatures'] += before
            statistics['retainedFeatures'] += after
            if encoded or z == 0:
                writer.write_tile(zxy_to_tileid(z, x, y), gzip.compress(encoded, mtime=0))
                statistics['outputTiles'] += 1
        west, south, east, north = region.bounds
        header.update(min_lon_e7=round(west * 1e7), min_lat_e7=round(south * 1e7),
                      max_lon_e7=round(east * 1e7), max_lat_e7=round(north * 1e7),
                      center_lon_e7=round(definition['center']['longitude'] * 1e7),
                      center_lat_e7=round(definition['center']['latitude'] * 1e7), center_zoom=10)
        metadata['mercaforte:coverage'] = 'square'
        metadata['mercaforte:center'] = definition['center']
        metadata['mercaforte:side_meters'] = definition['sideMeters']
        writer.finalize(header, metadata)
    return statistics


def verify_clipped_archive(archive, region):
    """Comprobar cada geometría, también en zooms generales, con tolerancia MVT de redondeo."""
    world_region = world_coordinates(region)
    count = 0
    with archive.open('rb') as file:
        for (z, x, y), compressed in all_tiles(MmapSource(file)):
            regions = {}
            for name, layer in mapbox_vector_tile.decode(gzip.decompress(compressed),
                                                       default_options={'y_coord_down': True}).items():
                extent = layer['extent']
                if extent not in regions:
                    regions[extent] = tile_region(world_region, z, x, y, extent).buffer(1)
                for feature in layer['features']:
                    geometry = make_valid(shape(feature['geometry']))
                    assert not geometry.is_empty, f'Geometría vacía: {z}/{x}/{y} {name}'
                    assert regions[extent].covers(geometry), f'Geometría externa: {z}/{x}/{y} {name}'
                    count += 1
    return count
