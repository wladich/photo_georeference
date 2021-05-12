# coding: utf-8
import argparse

import datetime
import calendar
import time
import json
import pyproj
import subprocess


from .gpx import parse_gpx


def get_photo_local_timestamp(filename):
    res = subprocess.check_output(['exiftool', '-j', '-DateTimeOriginal', filename])
    datetime_str = json.loads(res)[0]['DateTimeOriginal']
    dt = datetime.datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
    timestamp = calendar.timegm(dt.timetuple())
    return timestamp


def interpolate_latlon(timestamp, p1, p2):
    if p1[2] == p2[2]:
        q = 0
    else:
        q = float(timestamp - p1[2]) / (p2[2] - p1[2])
    lat = p1[0] + (p2[0] - p1[0]) * q
    lon = p1[1] + (p2[1] - p1[1]) * q
    return lat, lon


class GeoReferencer:
    def __init__(self, track_files):
        self.segments = []
        self.load_tracks(track_files)
        self.add_virtual_segments()
        self.geod = pyproj.Geod(ellps='WGS84')

    def load_tracks(self, filenames):
        for fn in filenames:
            with open(fn) as f:
                segments = parse_gpx(f)
            self.segments += [seg for seg in segments if len(seg) > 1]
        self.segments.sort(key=lambda seg: seg[0][2])

    def add_virtual_segments(self):
        for i in range(len(self.segments) - 1):
            seg = self.segments[i]
            next_seg = self.segments[i + 1]
            p1 = seg[-1]
            p2 = next_seg[0]
            if p2[2] > p1[2]:
                self.segments.append([seg[-1], next_seg[0]])

    def get_position_from_timestamp(self, timestamp, time_offset):
        timestamp += time_offset
        position = {
            'timestamp': timestamp,
        }
        segment_for_point = None
        for segment in self.segments:
            if segment[0][2] <= timestamp <= segment[-1][2]:
                segment_for_point = segment
                break
        if segment_for_point:
            for i in range(len(segment_for_point) - 1):
                p1 = segment_for_point[i]
                p2 = segment_for_point[i + 1]
                if p1[2] <= timestamp <= p2[2]:
                    az, _, track_points_dist = self.geod.inv(p1[1], p1[0], p2[1], p2[0])
                    track_points_time_delta = p2[2] - p1[2]
                    position['track_points_dist'] = track_points_dist
                    position['track_points_time_delta'] = track_points_time_delta
                    lat, lon = interpolate_latlon(timestamp, p1, p2)
                    position['lat'] = lat
                    position['lon'] = lon
                    position['heading'] = az
                    break
        return position


def get_default_timezone():
    return -time.timezone / 3600


def calculate_offset(camera_time_zone_hours, camera_minus_gps_seconds):
    return -camera_time_zone_hours * 3600 + camera_minus_gps_seconds


def georefence_images_from_exif(images, tracks, time_offset):
    """
    :param images: list of file names
    :param tracks: list of gpx files
    :param time_offset: GPS time (UTC) - camera time (local), in seconds, combined from time zone and camera clock skew
    :return: list of dicts with keys: lat, lon, heading, track_points_dist, track_points_time_delta
        track_points_dist - distance between track points prior and after the photo
        track_points_time_delta - time between track points prior and after the photo
    """
    referencer = GeoReferencer(tracks)
    positions = {}
    for filename in images:
        timestamp = get_photo_local_timestamp(filename)
        positions[filename] = referencer.get_position_from_timestamp(timestamp, time_offset)
    return positions


def main():
    default_timezone = get_default_timezone()
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', nargs='+', required=True)
    parser.add_argument('--tracks', nargs='+', required=True)
    parser.add_argument('-z', '--timezone', default=default_timezone, type=float, help='default=%s' % default_timezone)
    parser.add_argument('-o', '--offset', default=0, type=int, help='GPS time - camera time, in seconds')
    conf = parser.parse_args()

    refs = georefence_images_from_exif(conf.images, conf.tracks, calculate_offset(conf.timezone, conf.offset))
    print(json.dumps(refs, indent=2))


if __name__ == '__main__':
    main()
