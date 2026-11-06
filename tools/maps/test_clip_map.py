import unittest

import mapbox_vector_tile
from shapely.geometry import Point, LineString, box, shape

from clip_map import clip_tile, world_coordinates


class ClipMapTests(unittest.TestCase):
    def test_general_tile_drops_toluca_and_mexico_city(self):
        features = []
        for name, coordinate in [('Cuernavaca', (-99.234, 18.924)), ('Toluca', (-99.656, 19.283)),
                                 ('Ciudad de México', (-99.133, 19.433))]:
            point = world_coordinates(Point(coordinate))
            features.append({'geometry': Point(point.x * 4096, point.y * 4096), 'properties': {'name': name}})
        data = mapbox_vector_tile.encode({'name': 'places', 'features': features}, default_options={'y_coord_down': True})
        region = world_coordinates(box(-99.35, 18.70, -98.93, 19.13))
        output, before, after = clip_tile(data, 0, 0, 0, region)
        self.assertEqual(before, 3)
        self.assertEqual(after, 1)
        self.assertEqual([feature['properties']['name'] for feature in mapbox_vector_tile.decode(output)['places']['features']], ['Cuernavaca'])

    def test_roads_and_polygons_are_cut_at_the_boundary(self):
        data = mapbox_vector_tile.encode([
            {'name': 'roads', 'features': [{'geometry': LineString([(0, 2048), (4096, 2048)]), 'properties': {}}]},
            {'name': 'earth', 'features': [{'geometry': box(0, 0, 4096, 4096), 'properties': {}}]},
        ], default_options={'y_coord_down': True})
        output, _, _ = clip_tile(data, 0, 0, 0, box(.25, .25, .75, .75))
        decoded = mapbox_vector_tile.decode(output, default_options={'y_coord_down': True})
        self.assertEqual(shape(decoded['roads']['features'][0]['geometry']).bounds, (1024, 2048, 3072, 2048))
        self.assertEqual(shape(decoded['earth']['features'][0]['geometry']).bounds, (1024, 1024, 3072, 3072))

    def test_excluded_holes_and_whole_external_tiles_are_removed(self):
        data = mapbox_vector_tile.encode({'name': 'places', 'features': [
            {'geometry': Point(2048, 2048), 'properties': {'name': 'Excluded'}},
            {'geometry': Point(1024, 1024), 'properties': {'name': 'Included'}},
        ]}, default_options={'y_coord_down': True})
        region = box(0, 0, 1, 1).difference(box(.4, .4, .6, .6))
        output, _, after = clip_tile(data, 0, 0, 0, region)
        self.assertEqual(after, 1)
        self.assertEqual(mapbox_vector_tile.decode(output)['places']['features'][0]['properties']['name'], 'Included')
        empty, _, after = clip_tile(data, 0, 0, 0, box(2, 2, 3, 3))
        self.assertEqual(empty, b'')
        self.assertEqual(after, 0)


if __name__ == '__main__':
    unittest.main()
