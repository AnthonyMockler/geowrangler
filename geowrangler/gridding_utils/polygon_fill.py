# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/15_polygon_fill.ipynb.

# %% auto 0
__all__ = []

# %% ../../notebooks/15_polygon_fill.ipynb 3
from typing import List, Tuple, Set, Optional, Dict, Union

import numpy as np
import pandas as pd
import polars as pl

# %% ../../notebooks/15_polygon_fill.ipynb 9
# epsilon is a constant for correcting near-misses in voxel traversal
EPSILON = 1e-14


def voxel_traversal_2d(
    start_vertex: Tuple[int, int],
    end_vertex: Tuple[int, int],
    debug: bool = False,  # if true, prints diagnostic info for the algorithm
) -> List[Tuple[int, int]]:
    """Returns all pixels between two points as inspired by Amanatides & Woo's “A Fast Voxel Traversal Algorithm For Ray Tracing”"""

    # Setup initial conditions
    x1, y1 = start_vertex
    x2, y2 = end_vertex

    direction_x = 1 if x2 > x1 else -1
    direction_y = 1 if y2 > y1 else -1

    # Single point
    if (x1 == x2) and (y1 == y2):
        pixels = [(x1, y1)]
        return pixels

    # Vertical line
    elif x1 == x2:
        pixels = [(x1, y) for y in range(y1, y2 + direction_y, direction_y)]
        return pixels

    # Horizontal line
    elif y1 == y2:
        pixels = [(x, y1) for x in range(x1, x2 + direction_x, direction_x)]
        return pixels

    dy = y2 - y1
    dx = x2 - x1
    slope = dy / dx
    inv_slope = dx / dy

    # reverse order if negative slope to preserve symmetry in floating point calculations
    if slope < 0:
        x1, y1 = end_vertex
        x2, y2 = start_vertex

        direction_x = 1 if x2 > x1 else -1
        direction_y = 1 if y2 > y1 else -1

    slope_multiplier = np.sqrt(1 + slope**2)
    inv_slope_multiplier = np.sqrt(1 + inv_slope**2)

    pixel_x, pixel_y = x1, y1
    ray_x, ray_y = pixel_x, pixel_y
    pixels = [(pixel_x, pixel_y)]

    is_finished = False

    if debug:
        print(f"\nTraversing from ({x1},{y1}) to ({x2},{y2})")

    # number of steps should not exceed the perimeter of the rectangle enclosing the line segment
    max_steps = 2 * (abs(dx) + abs(dy))
    n_steps = 0
    while not is_finished:
        # this prevents infinite loops
        n_steps += 1
        if n_steps > max_steps:
            raise Exception(
                f"Traversal has exceeded steps limit {max_steps:,}. Please recheck inputs"
            )

        # get the next x or y integer that the next ray would hit
        if direction_x == 1:
            next_ray_x = np.floor(ray_x) + 1
        elif direction_x == -1:
            next_ray_x = np.ceil(ray_x) - 1

        if direction_y == 1:
            next_ray_y = np.floor(ray_y) + 1
        elif direction_y == -1:
            next_ray_y = np.ceil(ray_y) - 1

        # get distance between the 2 candidates and check which one is closer
        # there is an epsilon to account near-misses due to floating point differences

        # y coordinate line formula is next_ray_y = ray_y + slope*(next_ray_x-ray_x)
        # squred distance is (next_ray_x - ray_x)**2 + (slope*(next_ray_x-ray_x))**2
        # distance simplifies to abs(next_ray_x - ray_x)* sqrt(1+slope**2)

        ray_candidate_1 = (
            next_ray_x,
            ray_y + slope * (next_ray_x - ray_x) + direction_y * EPSILON,
        )
        # unsimplified square distance
        # dist_1 = (ray_candidate_1[0] - ray_x)**2 + (ray_candidate_1[1] - ray_y)**2
        # simplified distance
        dist_1 = abs(next_ray_x - ray_x) * slope_multiplier

        # x coordinate line formula is next_ray_x = ray_x + inv_slope*(next_ray_y-y)
        # squared distance is (inv_slope*(next_ray_y-ray_y))**2 + (next_ray_y-ray_y)**2
        # distance simplifies to abs(next_ray_y-ray_y)* sqrt(1 + inv_slope**2)

        ray_candidate_2 = (
            ray_x + inv_slope * (next_ray_y - ray_y) + direction_x * EPSILON,
            next_ray_y,
        )
        # unsimplified square distance
        # dist_2 = (ray_candidate_2[0] - ray_x)**2 + (ray_candidate_2[1] - ray_y)**2
        # simplified distance
        dist_2 = abs(next_ray_y - ray_y) * inv_slope_multiplier

        # candidate 1 is closer
        if dist_1 < dist_2:
            pixel_x += direction_x
            ray_x, ray_y = ray_candidate_1

        # candidate 2 is closer
        elif dist_1 > dist_2:
            pixel_y += direction_y
            ray_x, ray_y = ray_candidate_2

        # line passes exactly on the corner
        elif dist_1 == dist_2:
            pixel_x += direction_x
            pixel_y += direction_y
            ray_x, ray_y = pixel_x, pixel_y
        else:
            raise ValueError(f"Erroneous distances {dist_1}, {dist_2}")

        if debug:
            print(
                f"Next ray coords are ({ray_x}, {ray_y}) and tile coords are ({pixel_x}, {pixel_y})"
            )

        pixels.append((pixel_x, pixel_y))

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

    return pixels

# %% ../../notebooks/15_polygon_fill.ipynb 13
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

# %% ../../notebooks/15_polygon_fill.ipynb 17
def voxel_traversal_scanline_fill(
    vertices_df: Union[
        pd.DataFrame, pl.DataFrame
    ],  # dataframe with x_col and y_col for the polygon vertices
    x_col: str = "x",
    y_col: str = "y",
    debug: bool = False,  # if true, prints diagnostic info for both voxel traversal and scanline fill algorithms
) -> Set[Tuple[int, int]]:
    """
    Returns pixels that intersect a polygon
    This uses voxel traversal to fill the boundary, and scanline fill for the interior. All coordinates are assumed to be nonnegative integers
    """

    vertices = list(zip(vertices_df[x_col].to_list(), vertices_df[y_col].to_list()))
    offset_vertices = vertices[1:] + vertices[:1]

    polygon_pixels = set()

    for start_vertex, end_vertex in zip(vertices, offset_vertices):
        polygon_pixels.update(voxel_traversal_2d(start_vertex, end_vertex, debug))

    polygon_pixels.update(scanline_fill(vertices, debug))

    return polygon_pixels
