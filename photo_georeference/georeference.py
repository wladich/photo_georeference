# coding: utf-8
import argparse
import calendar
import datetime
import json
import subprocess
from dataclasses import dataclass
from typing import TypedDict

import pyproj

from .gpx import LatLonTime, parse_gpx


@dataclass
class Segment:
    track_names: list[str]
    points: list[LatLonTime]


class PhotoPosition(TypedDict, total=False):
    timestamp: float
    track_points_dist: float
    track_points_time_delta: float
    lat: float
    lon: float
    heading: float
    sources: list[str]


def get_photo_local_timestamp(filename: str) -> int:
    res = subprocess.check_output(["exiftool", "-j", "-DateTimeOriginal", filename])
    tags: list[dict[str, str]] = json.loads(res)
    datetime_str: str = tags[0]["DateTimeOriginal"]
    datetime_ = datetime.datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
    timestamp = calendar.timegm(datetime_.timetuple())
    return timestamp


def interpolate_latlon(
    timestamp: float, point1: LatLonTime, point2: LatLonTime
) -> tuple[float, float]:
    if point1.timestamp == point2.timestamp:
        q = 0.0
    else:
        q = float(timestamp - point1.timestamp) / (point2.timestamp - point1.timestamp)
    lat = point1.lat + (point2.lat - point1.lat) * q
    lon = point1.lon + (point2.lon - point1.lon) * q
    return lat, lon


def load_tracks_flatten_segments(filenames: list[str]) -> list[Segment]:
    segments = []
    for filename in filenames:
        with open(filename, "rb") as f:
            for track_seg in parse_gpx(f):
                if len(track_seg) > 1:
                    segments.append(Segment([filename], track_seg))

    def start_time(segment: Segment) -> float:
        return segment.points[0].timestamp

    segments.sort(key=start_time)
    return segments


class GeoReferencer:
    heading_smoothing_target_distance = 4
    heading_smoothing_max_time_delta = 10

    def __init__(self, track_files: list[str]):
        self.segments = load_tracks_flatten_segments(track_files)
        self.add_virtual_segments()
        self.geod = pyproj.Geod(ellps="WGS84")

    def add_virtual_segments(self) -> None:
        for i in range(len(self.segments) - 1):
            seg = self.segments[i]
            next_seg = self.segments[i + 1]
            point1 = seg.points[-1]
            point2 = next_seg.points[0]
            if point2.timestamp > point1.timestamp:
                self.segments.append(
                    Segment(seg.track_names + next_seg.track_names, [point1, point2])
                )

    def calc_dist(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        res: tuple[float, ...] = self.geod.inv(lon1, lat1, lon2, lat2)
        return res[2]

    def calc_azimuth(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        res: tuple[float, ...] = self.geod.inv(lon1, lat1, lon2, lat2)
        return res[0]

    # pylint: disable-next=too-many-arguments
    def calculate_heading(
        self, lat: float, lon: float, timestamp: float, segment: Segment, ind: int
    ) -> float:
        segment_points = segment.points

        def is_point_in_range(ind: int) -> bool:
            point = segment_points[ind]
            time_delta = abs(timestamp - point.timestamp)
            if time_delta > self.heading_smoothing_max_time_delta:
                return False

            dist = self.calc_dist(lon, lat, point.lon, point.lat)
            return dist < self.heading_smoothing_target_distance

        ind2 = ind + 1

        while ind > 0 and is_point_in_range(ind):
            ind -= 1
        while ind2 < len(segment.points) - 1 and is_point_in_range(ind2):
            ind2 += 1
        point1 = segment_points[ind]
        point2 = segment_points[ind2]
        heading = self.calc_azimuth(point1.lon, point1.lat, point2.lon, point2.lat)
        return heading

    def get_position_from_timestamp(
        self, timestamp: float, time_offset: float
    ) -> PhotoPosition:
        timestamp += time_offset
        position: PhotoPosition = {
            "timestamp": timestamp,
        }
        segment_for_point = None
        for segment in self.segments:
            if segment.points[0].timestamp <= timestamp <= segment.points[-1].timestamp:
                segment_for_point = segment
                break
        if segment_for_point:
            for i in range(len(segment_for_point.points) - 1):
                point1 = segment_for_point.points[i]
                point2 = segment_for_point.points[i + 1]
                if point1[2] <= timestamp <= point2[2]:
                    track_points_dist = self.calc_dist(
                        point1.lon, point1.lat, point2.lon, point2.lat
                    )
                    track_points_time_delta = point2.timestamp - point1.timestamp
                    position["track_points_dist"] = track_points_dist
                    position["track_points_time_delta"] = track_points_time_delta
                    lat, lon = interpolate_latlon(timestamp, point1, point2)
                    heading = self.calculate_heading(
                        lat, lon, timestamp, segment_for_point, i
                    )
                    position["lat"] = lat
                    position["lon"] = lon
                    position["heading"] = heading
                    position["sources"] = segment_for_point.track_names
                    break
        return position


def calculate_offset(
    camera_time_zone_hours: float, camera_minus_gps_seconds: int
) -> float:
    return -camera_time_zone_hours * 3600 + camera_minus_gps_seconds


def georefence_images_from_exif(
    images: list[str], tracks: list[str], time_offset: float
) -> dict[str, PhotoPosition]:
    """
    :param images: list of file names
    :param tracks: list of gpx files
    :param time_offset: GPS time (UTC) - camera time (local), in seconds,
        combined from time zone and camera clock skew
    :return: list of dicts with keys:
        lat, lon, heading, track_points_dist, track_points_time_delta
        track_points_dist - distance between track points prior and after the photo
        track_points_time_delta - time between track points prior and after the photo
    """
    referencer = GeoReferencer(tracks)
    positions = {}
    for filename in images:
        timestamp = get_photo_local_timestamp(filename)
        positions[filename] = referencer.get_position_from_timestamp(
            timestamp, time_offset
        )
    return positions


# pylint: disable-next=too-few-public-methods
class Args(argparse.Namespace):
    images: list[str]
    tracks: list[str]
    timezone: float
    offset: int


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--tracks", nargs="+", required=True)
    parser.add_argument(
        "-z",
        "--timezone",
        required=True,
        type=float,
        help="Time offset from UTC in hours",
    )
    parser.add_argument(
        "-o", "--offset", default=0, type=int, help="GPS time - camera time, in seconds"
    )
    conf = parser.parse_args(namespace=Args())
    refs = georefence_images_from_exif(
        conf.images, conf.tracks, calculate_offset(conf.timezone, conf.offset)
    )
    print(json.dumps(refs, indent=2))


if __name__ == "__main__":
    main()
