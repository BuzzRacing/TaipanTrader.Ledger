"""Build the detailed Historical-mode chart from Natural Earth coastlines."""

import argparse
import json
import re
from pathlib import Path


BOUNDS = (84.0, -11.0, 136.0, 36.0)


def _clip_edge(points, inside, intersect):
    if not points:
        return []
    output = []
    previous = points[-1]
    previous_inside = inside(previous)
    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                output.append(intersect(previous, current))
            output.append(current)
        elif previous_inside:
            output.append(intersect(previous, current))
        previous, previous_inside = current, current_inside
    return output


def _clip_ring(points):
    xmin, ymin, xmax, ymax = BOUNDS

    def vertical(x):
        def hit(a, b):
            if b[0] == a[0]:
                return [x, a[1]]
            t = (x - a[0]) / (b[0] - a[0])
            return [x, a[1] + t * (b[1] - a[1])]
        return hit

    def horizontal(y):
        def hit(a, b):
            if b[1] == a[1]:
                return [a[0], y]
            t = (y - a[1]) / (b[1] - a[1])
            return [a[0] + t * (b[0] - a[0]), y]
        return hit

    clipped = points
    clipped = _clip_edge(clipped, lambda p: p[0] >= xmin, vertical(xmin))
    clipped = _clip_edge(clipped, lambda p: p[0] <= xmax, vertical(xmax))
    clipped = _clip_edge(clipped, lambda p: p[1] >= ymin, horizontal(ymin))
    clipped = _clip_edge(clipped, lambda p: p[1] <= ymax, horizontal(ymax))
    return clipped


def _geometry_rings(geometry):
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        yield from coordinates
    elif kind == "MultiPolygon":
        for polygon in coordinates:
            yield from polygon


def _path_data(data):
    parts = []
    ring_count = 0
    point_count = 0
    for feature in data.get("features", []):
        for ring in _geometry_rings(feature.get("geometry") or {}):
            if len(ring) < 3:
                continue
            xs = [point[0] for point in ring]
            ys = [point[1] for point in ring]
            if max(xs) < BOUNDS[0] or min(xs) > BOUNDS[2] or max(ys) < BOUNDS[1] or min(ys) > BOUNDS[3]:
                continue
            clipped = _clip_ring(ring)
            if len(clipped) < 3:
                continue
            coords = [f"{point[0]:.4f},{point[1]:.4f}" for point in clipped]
            parts.append("M" + "L".join(coords) + "Z")
            ring_count += 1
            point_count += len(clipped)
    if not parts:
        raise ValueError("No coastline geometry intersected the chart bounds")
    return "".join(parts), ring_count, point_count


def build(source, template, output):
    with source.open(encoding="utf-8") as handle:
        data = json.load(handle)
    path_data, ring_count, point_count = _path_data(data)
    svg = template.read_text(encoding="utf-8")
    detailed_land = (
        '<g id="landmass"><path d="' + path_data
        + '" fill-rule="evenodd" clip-rule="evenodd"/></g>'
    )
    svg, replacements = re.subn(r'<g id="landmass">.*?</g>', detailed_land, svg, count=1, flags=re.S)
    if replacements != 1:
        raise ValueError("Template landmass group was not found")
    svg = svg.replace("The China Seas, 1860", "The China Seas, 1860 — detailed relief edition")
    svg = svg.replace('surfaceScale="6" diffuseConstant="1.08"', 'surfaceScale="2.2" diffuseConstant=".8"')
    svg = svg.replace('mode="multiply" result="relief"', 'mode="soft-light" result="relief"')
    svg = svg.replace('stroke-opacity=".10" stroke-width="3.2"', 'stroke-opacity=".11" stroke-width=".85" stroke-linejoin="round"')
    svg = svg.replace('stroke-opacity=".16" stroke-width="1.9"', 'stroke-opacity=".17" stroke-width=".45" stroke-linejoin="round"')
    svg = svg.replace('stroke-opacity=".22" stroke-width=".85"', 'stroke-opacity=".28" stroke-width=".20" stroke-linejoin="round"')
    svg = svg.replace(
        '<svg xmlns=',
        '<!-- Coastlines: Natural Earth 1:50m land, public domain. -->\n<svg xmlns=',
        1,
    )
    output.write_text(svg, encoding="utf-8")
    print(f"Wrote {output} with {ring_count} rings and {point_count} coastline points")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.template, args.output)


if __name__ == "__main__":
    main()
