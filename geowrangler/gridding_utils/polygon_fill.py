# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/15_polygon_fill.ipynb.

# %% auto 0
__all__ = ['voxel_traversal_2d', 'scanline_fill', 'voxel_traversal_scanline_fill', 'polygons_to_vertices', 'fast_polygon_fill']

# %% ../../notebooks/15_polygon_fill.ipynb 5
from typing import List, Tuple, Set, Optional, Dict, Union

import numpy as np
import pandas as pd
import geopandas as gpd
import polars as pl

# %% ../../notebooks/15_polygon_fill.ipynb 11
def voxel_traversal_2d(
    start_vertex: Tuple[int, int],
    end_vertex: Tuple[int, int],
    debug: bool = False,  # if true, prints diagnostic info for the algorithm
) -> Dict[str, List[Tuple[int, int]]]:
    """
    Returns all pixels between two points as inspired by Amanatides & Woo's “A Fast Voxel Traversal Algorithm For Ray Tracing”

    Implementation adapted from https://www.redblobgames.com/grids/line-drawing/ in the supercover lines section

    This also returns the off-diagonal pixels that can be useful for correcting errors at the corners of polygons during polygon fill
    """

    # Setup initial conditions
    x1, y1 = start_vertex
    x2, y2 = end_vertex

    direction_x = 1 if x2 > x1 else -1
    direction_y = 1 if y2 > y1 else -1

    result = {"line_pixels": [], "off_diagonal_pixels": []}

    # Single point
    if (x1 == x2) and (y1 == y2):
        pixels = [(x1, y1)]
        result["line_pixels"].extend(pixels)
        return result

    # Vertical line
    elif x1 == x2:
        pixels = [(x1, y) for y in range(y1, y2 + direction_y, direction_y)]
        result["line_pixels"].extend(pixels)
        return result

    # Horizontal line
    elif y1 == y2:
        pixels = [(x, y1) for x in range(x1, x2 + direction_x, direction_x)]
        result["line_pixels"].extend(pixels)
        return result

    dy = y2 - y1
    dx = x2 - x1

    pixel_x, pixel_y = x1, y1
    pixels = [(pixel_x, pixel_y)]
    off_diagonal_pixels = []

    is_finished = False

    if debug:
        print(f"\nTraversing from ({x1},{y1}) to ({x2},{y2})")

    ix = 0
    iy = 0

    nx = abs(dx)
    ny = abs(dy)
    max_steps = nx + ny
    n_steps = 0
    while not is_finished:
        # this prevents infinite loops
        n_steps += 1
        if n_steps > max_steps:
            raise Exception(
                f"Traversal has exceeded steps limit {max_steps:,}. Please recheck inputs"
            )

        decision = (1 + 2 * ix) * ny - (1 + 2 * iy) * nx
        if decision == 0:

            off_diagonal_pixels.append((pixel_x + direction_x, pixel_y))
            off_diagonal_pixels.append((pixel_x, pixel_y + direction_y))

            # diagonal step
            pixel_x += direction_x
            pixel_y += direction_y
            ix += 1
            iy += 1
        elif decision < 0:
            # horizontal step
            pixel_x += direction_x
            ix += 1
        else:
            # vetical step
            pixel_y += direction_y
            iy += 1

        pixels.append((pixel_x, pixel_y))

        if debug:
            print(f"Next tile coords are ({pixel_x}, {pixel_y})")

        # checks to see if the loop is finished
        if direction_x == 1:
            is_x_finished = pixel_x >= x2
        elif direction_x == -1:
            is_x_finished = pixel_x <= x2

        if direction_y == 1:
            is_y_finished = pixel_y >= y2
        elif direction_y == -1:
            is_y_finished = pixel_y <= y2

        if is_x_finished and is_y_finished:
            break

    result = {"line_pixels": pixels, "off_diagonal_pixels": off_diagonal_pixels}
    return result

# %% ../../notebooks/15_polygon_fill.ipynb 15
def interpolate_x(
    start_vertex: Tuple[int, int],
    end_vertex: Tuple[int, int],
    y: int,
) -> float:
    """Interpolate x value for a given y along the line segment defined by start_vertex and end_vertex."""
    x1, y1 = start_vertex
    x2, y2 = end_vertex
    if y1 == y2:
        # case when there is a horizontal line segment
        raise ValueError(f"The y value of the 2 vertices should not be the same")

    inverse_slope = (x2 - x1) / (y2 - y1)
    interpolated_x = x1 + (y - y1) * inverse_slope
    return interpolated_x

# %% ../../notebooks/15_polygon_fill.ipynb 16
def scanline_fill(
    vertices: List[
        Tuple[int, int]
    ],  # list of polygon vertices in order (either clockwise or counterclockwise)
    debug: bool = False,  # if true, prints diagnostic info for the algorithm
) -> Set[Tuple[int, int]]:
    """Returns all pixels within the interior of a polygon defined by vertices"""

    offset_vertices = vertices[1:] + vertices[:1]

    if not vertices:
        return set()

    if len(vertices) == 1:
        return set(vertices)

    # Calculate the bounding box for the polygon
    min_y, max_y = min(y for x, y in vertices), max(y for x, y in vertices)

    filled_pixels = set()
    # Process each horizontal scanline within the bounding box
    for scanline_y in range(min_y, max_y + 1):
        intersection_points = []

        # Find intersections of the polygon with the current scanline
        for start_vertex, end_vertex in zip(vertices, offset_vertices):
            start_x, start_y = start_vertex
            end_x, end_y = end_vertex

            if (end_y < scanline_y <= start_y) or (start_y < scanline_y <= end_y):
                # Calculate x-coordinate of intersection
                intersection_x = interpolate_x(start_vertex, end_vertex, scanline_y)
                intersection_points.append(intersection_x)

        # Fill pixels between pairs of intersections
        if intersection_points:
            intersection_points.sort()

            filled_pixels_in_row = set()
            for start_x, end_x in zip(
                intersection_points[::2], intersection_points[1::2]
            ):
                start_x, end_x = int(round(start_x)), int(round(end_x))

                _filled_pixels_in_row = [
                    (x, scanline_y) for x in range(start_x, end_x + 1)
                ]
                filled_pixels_in_row.update(_filled_pixels_in_row)

            filled_pixels.update(filled_pixels_in_row)

        if debug:
            print(f"Scanline y = {scanline_y}, Intersections: {intersection_points}")

    return filled_pixels

# %% ../../notebooks/15_polygon_fill.ipynb 20
def voxel_traversal_scanline_fill(
    vertices_df: Union[
        pd.DataFrame, pl.DataFrame
    ],  # dataframe with x_col and y_col for the polygon vertices
    x_col: str = "x",
    y_col: str = "y",
    debug: bool = False,  # if true, prints diagnostic info for both voxel traversal and scanline fill algorithms
) -> Dict[str, Set[Tuple[int, int]]]:
    """
    Returns pixels that intersect a polygon.

    This uses voxel traversal to fill the boundary, and scanline fill for the interior. All coordinates are assumed to be integers.

    This also returns the off-boundary pixels that can be useful for correcting errors at the corners of polygons during polygon fill
    """

    vertices = list(zip(vertices_df[x_col].to_list(), vertices_df[y_col].to_list()))
    offset_vertices = vertices[1:] + vertices[:1]

    polygon_pixels = set()
    off_boundary_pixels = set()

    for start_vertex, end_vertex in zip(vertices, offset_vertices):
        voxel_traversal_results = voxel_traversal_2d(start_vertex, end_vertex, debug)
        polygon_pixels.update(voxel_traversal_results["line_pixels"])
        off_boundary_pixels.update(voxel_traversal_results["off_diagonal_pixels"])

    polygon_pixels.update(scanline_fill(vertices, debug))

    # removing off boundary tiles that are actually in the interior
    off_boundary_pixels = off_boundary_pixels - polygon_pixels

    result = {
        "polygon_pixels": polygon_pixels,
        "off_boundary_pixels": off_boundary_pixels,
    }
    return result

# %% ../../notebooks/15_polygon_fill.ipynb 27
SUBPOLYGON_ID_COL = "__subpolygon_id__"
PIXEL_DTYPE = pl.Int32

# %% ../../notebooks/15_polygon_fill.ipynb 28
def polygons_to_vertices(
    polys_gdf: gpd.GeoDataFrame,
    unique_id_col: Optional[
        str
    ] = None,  # the ids under this column will be preserved in the output tiles
) -> pl.DataFrame:

    if unique_id_col is not None:
        duplicates_bool = polys_gdf[unique_id_col].duplicated()
        if duplicates_bool.any():
            raise ValueError(
                f"""{unique_id_col} is not unique!
                Found {duplicates_bool.sum():,} duplicates"""
            )
        polys_gdf = polys_gdf.set_index(unique_id_col)
    else:
        # reset index if it is not unique
        if polys_gdf.index.nunique() != len(polys_gdf.index):
            polys_gdf = polys_gdf.reset_index(drop=True)
        unique_id_col = polys_gdf.index.name

    polys_gdf = polys_gdf.explode(index_parts=True)

    is_poly_bool = polys_gdf.type == "Polygon"
    if not is_poly_bool.all():
        raise ValueError(
            f"""
        All geometries should be polygons or multipolygons but found
        {is_poly_bool.sum():,} after exploding the GeoDataFrame"""
        )

    polys_gdf.index.names = [unique_id_col, SUBPOLYGON_ID_COL]
    vertices_df = polys_gdf.get_coordinates().reset_index()
    vertices_df = pl.from_pandas(vertices_df)

    return vertices_df

# %% ../../notebooks/15_polygon_fill.ipynb 32
def fast_polygon_fill(
    vertices_df: pl.DataFrame,  # integer vertices of all polygons in the AOI
    unique_id_col: Optional[
        str
    ] = None,  # the ids under this column will be preserved in the output tiles
) -> Dict[str, pl.DataFrame]:

    if unique_id_col is not None:
        id_cols = [SUBPOLYGON_ID_COL, unique_id_col]
        has_unique_id_col = True
    else:
        complement_cols = ["x", "y", SUBPOLYGON_ID_COL]
        unique_id_col = list(set(vertices_df.columns) - set(complement_cols))
        assert len(unique_id_col) == 1
        unique_id_col = unique_id_col[0]
        id_cols = [SUBPOLYGON_ID_COL, unique_id_col]
        has_unique_id_col = False

    for col in id_cols:
        assert col in vertices_df, f"{col} should be column in vertices_df"

    polygon_ids = vertices_df.select(id_cols).unique(maintain_order=True).rows()

    tiles_in_geom = set()
    tiles_off_boundary = set()
    for polygon_id in polygon_ids:
        subpolygon_id, unique_id = polygon_id
        filter_expr = (pl.col(SUBPOLYGON_ID_COL) == subpolygon_id) & (
            pl.col(unique_id_col) == unique_id
        )
        poly_vertices = vertices_df.filter(filter_expr)

        poly_vertices = poly_vertices.unique(maintain_order=True)
        voxel_traversal_results = voxel_traversal_scanline_fill(
            poly_vertices, x_col="x", y_col="y"
        )
        _tiles_in_geom = voxel_traversal_results["polygon_pixels"]
        _tiles_off_boundary = voxel_traversal_results["off_boundary_pixels"]

        if has_unique_id_col:
            _tiles_in_geom = [(x, y, unique_id) for (x, y) in _tiles_in_geom]
            _tiles_off_boundary = [(x, y, unique_id) for (x, y) in _tiles_off_boundary]

        tiles_in_geom.update(_tiles_in_geom)
        tiles_off_boundary.update(_tiles_off_boundary)

    # removing off boundary tiles that are actually in the interior
    tiles_off_boundary = tiles_off_boundary - tiles_in_geom

    schema = {"x": PIXEL_DTYPE, "y": PIXEL_DTYPE}
    if has_unique_id_col:
        schema[unique_id_col] = vertices_df[unique_id_col].dtype

    tiles_in_geom = pl.from_records(
        data=list(tiles_in_geom),
        orient="row",
        schema=schema,
    )

    tiles_off_boundary = pl.from_records(
        data=list(tiles_off_boundary),
        orient="row",
        schema=schema,
    )

    result = {"tiles_in_geom": tiles_in_geom, "tiles_off_boundary": tiles_off_boundary}

    return result
