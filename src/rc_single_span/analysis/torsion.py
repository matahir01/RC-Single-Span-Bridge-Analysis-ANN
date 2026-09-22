from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import hypot

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from scipy.spatial import Delaunay


@dataclass(frozen=True)
class SaintVenantTorsionResult:
    torsion_constant_m4: float
    coarse_m4: float
    medium_m4: float
    fine_m4: float
    estimated_relative_error: float
    converged: bool
    method: str = "Prandtl stress-function linear FEM"


def _point_on_segment(
    x: float,
    y: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    *,
    tol: float = 1.0e-10,
) -> bool:
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > tol * max(1.0, hypot(bx - ax, by - ay)):
        return False
    dot = (x - ax) * (x - bx) + (y - ay) * (y - by)
    return dot <= tol


def _point_in_polygon(
    point: tuple[float, float],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        if _point_on_segment(x, y, ax, ay, bx, by):
            return True
        if (ay > y) != (by > y):
            x_cross = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < x_cross:
                inside = not inside
    return inside


def _dedupe(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    seen: set[tuple[int, int]] = set()
    result: list[tuple[float, float]] = []
    scale = 1.0e12
    for x, y in points:
        key = (round(x * scale), round(y * scale))
        if key in seen:
            continue
        seen.add(key)
        result.append((float(x), float(y)))
    return tuple(result)


def _sample_boundary(
    polygon: tuple[tuple[float, float], ...],
    target_size_m: float,
) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[(i + 1) % len(polygon)]
        length = hypot(bx - ax, by - ay)
        pieces = max(1, int(np.ceil(length / target_size_m)))
        for j in range(pieces):
            t = j / pieces
            points.append((ax + t * (bx - ax), ay + t * (by - ay)))
    return _dedupe(points)


def _mesh_points(
    polygon: tuple[tuple[float, float], ...],
    target_size_m: float,
) -> tuple[np.ndarray, set[int]]:
    boundary = _sample_boundary(polygon, target_size_m)
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    points: list[tuple[float, float]] = list(boundary)
    nx = max(2, int(np.ceil((xmax - xmin) / target_size_m)))
    ny = max(2, int(np.ceil((ymax - ymin) / target_size_m)))
    xgrid = np.linspace(xmin, xmax, nx + 1)
    ygrid = np.linspace(ymin, ymax, ny + 1)

    for y in ygrid[1:-1]:
        for x in xgrid[1:-1]:
            if _point_in_polygon((float(x), float(y)), polygon):
                points.append((float(x), float(y)))

    unique = _dedupe(points)
    boundary_keys = {
        (round(x * 1.0e12), round(y * 1.0e12)) for x, y in boundary
    }
    boundary_indices = {
        i
        for i, (x, y) in enumerate(unique)
        if (round(x * 1.0e12), round(y * 1.0e12)) in boundary_keys
    }
    return np.asarray(unique, dtype=float), boundary_indices


def _triangle_is_inside(
    coords: np.ndarray,
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    centroid = tuple(np.mean(coords, axis=0))
    if not _point_in_polygon(centroid, polygon):
        return False
    for i in range(3):
        midpoint = tuple(0.5 * (coords[i] + coords[(i + 1) % 3]))
        if not _point_in_polygon(midpoint, polygon):
            return False
    return True


def _solve_prandtl_fem(
    polygon: tuple[tuple[float, float], ...],
    target_size_m: float,
) -> float:
    points, boundary = _mesh_points(polygon, target_size_m)
    if len(points) < 4:
        raise ValueError("Torsion mesh contains too few points.")

    tri = Delaunay(points)
    elements: list[np.ndarray] = []
    for simplex in tri.simplices:
        coords = points[simplex]
        if _triangle_is_inside(coords, polygon):
            area = 0.5 * abs(
                (coords[1, 0] - coords[0, 0]) * (coords[2, 1] - coords[0, 1])
                - (coords[2, 0] - coords[0, 0]) * (coords[1, 1] - coords[0, 1])
            )
            if area > 1.0e-16:
                elements.append(simplex)

    if not elements:
        raise ValueError("Torsion mesh contains no valid interior triangles.")

    interior = [i for i in range(len(points)) if i not in boundary]
    if not interior:
        raise ValueError("Torsion mesh contains no interior degrees of freedom.")
    dof = {node: i for i, node in enumerate(interior)}

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rhs = np.zeros(len(interior), dtype=float)

    element_data: list[tuple[np.ndarray, float]] = []
    for simplex in elements:
        coords = points[simplex]
        x1, y1 = coords[0]
        x2, y2 = coords[1]
        x3, y3 = coords[2]
        signed_twice_area = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        area = 0.5 * abs(signed_twice_area)
        b = np.array([y2 - y3, y3 - y1, y1 - y2], dtype=float)
        c = np.array([x3 - x2, x1 - x3, x2 - x1], dtype=float)
        ke = (np.outer(b, b) + np.outer(c, c)) / (4.0 * area)
        fe = np.full(3, 2.0 * area / 3.0, dtype=float)

        for a_local, a_node in enumerate(simplex):
            if a_node not in dof:
                continue
            ia = dof[a_node]
            rhs[ia] += fe[a_local]
            for b_local, b_node in enumerate(simplex):
                if b_node not in dof:
                    continue
                rows.append(ia)
                cols.append(dof[b_node])
                vals.append(float(ke[a_local, b_local]))
        element_data.append((simplex, area))

    matrix = coo_matrix(
        (vals, (rows, cols)),
        shape=(len(interior), len(interior)),
    ).tocsr()
    phi_interior = spsolve(matrix, rhs)
    phi = np.zeros(len(points), dtype=float)
    for node, index in dof.items():
        phi[node] = phi_interior[index]

    integral_phi = 0.0
    for simplex, area in element_data:
        integral_phi += area * float(np.sum(phi[simplex])) / 3.0
    return 2.0 * integral_phi


@lru_cache(maxsize=128)
def saint_venant_torsion_constant_polygon_m4(
    polygon: tuple[tuple[float, float], ...],
    *,
    target_relative_error: float = 2.5e-3,
) -> SaintVenantTorsionResult:
    """Numerically solve the Saint-Venant torsion constant of a solid polygon.

    The exact continuum problem is the Prandtl stress-function Poisson equation
    with zero boundary stress function.  Linear triangular FEM is solved on
    three successively refined meshes and Richardson extrapolation is used to
    estimate the continuum value.  The returned value is therefore a
    numerically converged engineering solution rather than a closed-form
    approximation assembled from rectangles.
    """

    if len(polygon) < 3:
        raise ValueError("Torsion polygon requires at least three vertices.")
    if not 0.0 < target_relative_error < 0.1:
        raise ValueError("target_relative_error must lie between 0 and 0.1.")

    xs = [item[0] for item in polygon]
    ys = [item[1] for item in polygon]
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    if extent <= 0.0:
        raise ValueError("Torsion polygon has zero extent.")

    divisions = (60.0, 90.0, 135.0)
    values = tuple(
        _solve_prandtl_fem(polygon, extent / division)
        for division in divisions
    )
    coarse, medium, fine = values

    refinement = divisions[2] / divisions[1]
    denominator = refinement**2 - 1.0
    extrapolated = fine + (fine - medium) / denominator
    if extrapolated <= 0.0:
        extrapolated = fine

    estimated = abs(extrapolated - fine) / extrapolated
    return SaintVenantTorsionResult(
        torsion_constant_m4=float(extrapolated),
        coarse_m4=float(coarse),
        medium_m4=float(medium),
        fine_m4=float(fine),
        estimated_relative_error=float(estimated),
        converged=estimated <= target_relative_error,
    )
