# coding: utf-8
import calendar
import re
from xml.dom import minidom
from xml.parsers.expat import ExpatError


def check_segment_time_order(points):
    if not points:
        return
    for i in range(len(points) - 1):
        delta = points[i + 1][2] < points[i][2]
        if delta < 0:
            raise Exception(
                "points time out of order (point #%s, %s seconds)" % (i + 2, delta)
            )


def parse_time(time_str):
    match = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)Z$", time_str
    )
    groups = match.groups()
    year, month, day, hour, minutes = map(int, groups[:-1])
    seconds = float(groups[-1])
    return calendar.timegm((year, month, day, hour, minutes, seconds))


def parse_gpx(fp):
    segments = []
    try:
        gpx = minidom.parse(fp)
    except ExpatError as e:
        raise Exception("Invalid gpx file: %s" % e) from e
    else:
        for trk_i, trk in enumerate(gpx.getElementsByTagName("trk"), 1):
            for seg_i, trkseg in enumerate(trk.getElementsByTagName("trkseg"), 1):
                linestring = []
                for pt_i, trkpt in enumerate(trkseg.getElementsByTagName("trkpt"), 1):
                    lat = float(trkpt.getAttribute("lat"))
                    lon = float(trkpt.getAttribute("lon"))
                    time_ = trkpt.getElementsByTagName("time")
                    if not time_:
                        raise Exception(
                            "No time in track point (track #%s, segment #%s, point #%s)"
                            % (trk_i, seg_i, pt_i)
                        )
                    time_ = time_[0].childNodes[0].data
                    timestamp = parse_time(time_)
                    linestring.append((lat, lon, timestamp))
                if linestring:
                    check_segment_time_order(linestring)
                    segments.append(linestring)
    return segments
