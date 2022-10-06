# coding: utf-8
import calendar
import math
import re
from typing import IO
from typing import NamedTuple
from xml.dom import minidom
from xml.parsers.expat import ExpatError


class LatLonTime(NamedTuple):
    lat: float
    lon: float
    timestamp: float


def check_segment_time_order(points: list[LatLonTime]) -> None:
    if not points:
        return
    for i in range(len(points) - 1):
        time_delta = points[i + 1].timestamp < points[i].timestamp
        if time_delta < 0:
            raise Exception(
                "points time out of order (point #%s, %s seconds)" % (i + 2, time_delta)
            )


def parse_time(time_str: str) -> float:
    match = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)Z$", time_str
    )
    if match:
        groups = match.groups("INVALID")
        year, month, day, hour, minutes = map(int, groups[:-1])
        seconds = float(groups[-1])
        int_seconds, frac_seconds = math.modf(seconds)
        return (
            calendar.timegm((year, month, day, hour, minutes, int(int_seconds)))
            + frac_seconds
        )
    raise Exception("Invalid time string %r" % time_str)


def extract_text(element: minidom.Element) -> str | None:
    children: list[minidom.Element] = element.childNodes
    if len(children) != 1:
        return None
    text_node = children[0]
    if not isinstance(text_node, minidom.Text):
        return None
    result: str = text_node.data
    assert isinstance(result, str)
    return result


def parse_track_point(trkpt: minidom.Element) -> LatLonTime:
    lat = float(trkpt.getAttribute("lat"))
    lon = float(trkpt.getAttribute("lon"))
    time_elements: list[minidom.Element] = trkpt.getElementsByTagName("time")
    if not time_elements:
        raise Exception("No time in track point")

    time_str = extract_text(time_elements[0])
    if time_str is None:
        raise Exception("Invalid time element")
    timestamp = parse_time(time_str)
    return LatLonTime(lat, lon, timestamp)


def parse_track_segment(trkseg: minidom.Element) -> list[LatLonTime]:
    linestring = []
    points: list[minidom.Element] = trkseg.getElementsByTagName("trkpt")
    for trkpt in points:
        linestring.append(parse_track_point(trkpt))
    check_segment_time_order(linestring)
    return linestring


def parse_gpx(fp: IO[bytes]) -> list[list[LatLonTime]]:
    segments = []
    try:
        gpx: minidom.Document = minidom.parse(fp)
    except ExpatError as e:
        raise Exception("Invalid gpx file: %s" % e) from e
    else:
        tracks: list[minidom.Element] = gpx.getElementsByTagName("trk")
        for trk in tracks:
            segment_nodes: list[minidom.Element] = trk.getElementsByTagName("trkseg")
            for trkseg in segment_nodes:
                linestring = parse_track_segment(trkseg)
                if linestring:
                    segments.append(linestring)
    return segments
