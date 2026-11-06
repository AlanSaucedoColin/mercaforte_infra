"""Recorte real de geometrías MVT: extract --bbox/--region solo selecciona teselas completas."""
import gzip
import math

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import Compression, zxy_to_tileid
from pmtiles.writer import Writer
from shapely import make_valid, set_precision
from shapely.affinity import affine_transform
from shapely.geometry import LineString, box, mapping, shape
from shapely.ops import polygonize, transform, unary_union


def polygon_parts(geometry):
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if geometry.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [part for child in geometry.geoms for part in polygon_parts(child)]
    return []


def relation_geometry(relation):
    def rings(role):
        lines = []
        for member in relation['members']:
            coordinates = member.get('geometry', [])
            if member.get('role') == role and member['type'] == 'way' and len(coordinates) >= 2:
                lines.append(LineString([(point['lon'], point['lat']) for point in coordinates]))
        return unary_union(list(polygonize(unary_union(lines))))
    outer = rings('outer')
    if outer.is_empty:
        raise ValueError(f'No se pudo reconstruir el límite de {relation["tags"].get("name")}')
    return unary_union(polygon_parts(make_valid(outer.difference(rings('inner')))))


def municipal_coverage(boundaries, municipalities):
    state = [element for element in boundaries['elements'] if element['tags'].get('ISO3166-2') == 'MX-MOR']
    municipal = [element for element in boundaries['elements'] if element['tags'].get('admin_level') == '6']
    assert len(state) == 1, 'Falta el límite estatal de Morelos'
    assert sorted(element['tags']['name'] for element in municipal) == sorted(municipalities), 'Faltan municipios'
    assert all(element['tags'].get('INEGI:MUNID', '').startswith('17') for element in municipal), 'Municipio fuera de Morelos'
    region = unary_union([relation_geometry(element) for element in municipal]).intersection(relation_geometry(state[0]))
    region = unary_union(polygon_parts(make_valid(region)))
    assert not region.is_empty and region.is_valid
    return region


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


def clip_archive(source, destination, region, municipalities):
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
                      center_lon_e7=round((west + east) / 2 * 1e7),
                      center_lat_e7=round((south + north) / 2 * 1e7), center_zoom=10)
        metadata['mercaforte:coverage'] = 'municipal-polygons'
        metadata['mercaforte:municipalities'] = municipalities
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
                    if name == 'places':
                        for key in ['name', 'name:es']:
                            assert str(feature.get('properties', {}).get(key, '')).casefold() not in (
                                'toluca', 'toluca de lerdo', 'ciudad de méxico', 'mexico city'), 'Ciudad externa en el archivo'
                    count += 1
    return count
