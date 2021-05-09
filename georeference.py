#!/usr/bin/env python2
# coding: utf-8
import argparse

import datetime
import calendar
import time
from PIL import Image
import json
import os
import pyproj

from lib import PhotoSettingsStorage
from lib.tracks import parse_gpx

geod = pyproj.Geod(ellps='WGS84')


def load_tracks(filenames):
    all_segments = []
    for fn in filenames:
        segments, errors = parse_gpx(open(fn))
        for er in errors:
            print '%s: %s' % (fn, er)
        segments = [seg for seg in segments if len(seg) > 1]
        all_segments.extend(segments)
    all_segments.sort(key=lambda seg: seg[0][2])
    return all_segments


def add_virtual_segments(segments):
    for i in xrange(len(segments) - 1):
        seg = segments[i]
        next_seg = segments[i + 1]
        segments.append([seg[-1], next_seg[0]])


def get_photo_local_timestamp(filename):
    tags = Image.open(filename)._getexif()
    datetime_original = tags[36867]
    dt = datetime.datetime.strptime(datetime_original, '%Y:%m:%d %H:%M:%S')
    timestamp = calendar.timegm(dt.timetuple())
    return timestamp


def interpolate_position(timestamp, seg_start, seg_end):
    if seg_end[2] == seg_start[2]:
        q = 0
    else:
        q = float(timestamp - seg_start[2]) / (seg_end[2] - seg_start[2])
    lat = seg_start[0] + (seg_end[0] - seg_start[0]) * q
    lon = seg_start[1] + (seg_end[1] - seg_start[1]) * q
    return lat, lon


def get_photo_reference(filename, linestrings, time_offset, force_precise):
    precise_reference_max_distance = 50
    precise_reference_max_time_delta = 60
    approx_reference_max_distance = 30000

    timestamp = get_photo_local_timestamp(filename)
    timestamp += time_offset
    ref = {
        'timestamp': timestamp,
        'coords_precision': None,
        'track_heading': None,
        'lat': None,
        'lon': None
    }
    for linestring in linestrings:
        if linestring[0][2] <= timestamp <= linestring[-1][2]:
            prev_point = linestring[0]
            for p in linestring[1:]:
                if prev_point[2] <= timestamp <= p[2]:
                    az,_, dist = geod.inv(prev_point[1], prev_point[0], p[1], p[0])
                    if az < 0:
                        az += 360
                    time_delta = p[2] - prev_point[2]
                    if dist <= approx_reference_max_distance:
                        lat, lon = interpolate_position(timestamp, prev_point, p)
                        ref['lat'] = lat
                        ref['lon'] = lon
                        ref['trkpt_dist'] = dist
                        ref['trkpt_time_delta'] = time_delta
                        if ((time_delta <= precise_reference_max_time_delta and dist <= precise_reference_max_distance)
                            or force_precise):
                            ref['coords_precision'] = 'precise'
                            ref['track_heading'] = az
                        else:
                            ref['coords_precision'] = 'approx'
                    return ref
                prev_point = p
    return ref


def store_tracks(segments, dir_):
    tracks_filename = os.path.join(dir_, '_tracks.json')
    with open(tracks_filename, 'w') as f:
        json.dump(segments, f)


def main():
    default_timezone = -time.timezone / 3600
    parser = argparse.ArgumentParser()
    parser.add_argument('src_dir')
    parser.add_argument('track', nargs='+')
    parser.add_argument('-z', '--timezone', default=default_timezone, type=float, help='default=%s' % default_timezone)
    parser.add_argument('-o', '--offset', default=0, type=int, help='GPS time - camera time')
    parser.add_argument('-f', '--force-precise', action='store_true')
    conf = parser.parse_args()

    dir_ = conf.src_dir

    segments = load_tracks(conf.track)
    store_tracks(segments, dir_)
    add_virtual_segments(segments)
    # FIXME: проверить знак offset, сделать как в других утилитах
    offset = -conf.timezone * 3600 + conf.offset

    photo_setting = PhotoSettingsStorage(dir_)
    for filename in sorted(os.listdir(dir_)):
        if os.path.splitext(filename)[1].lower() == '.jpg':
            ref = get_photo_reference(os.path.join(dir_, filename), segments, offset, conf.force_precise)
            stored_record = photo_setting.get(filename)
            if stored_record and stored_record.get('coords_precision') == 'manual':
                print 'Photo %s has coordinates set manually, refusing to update' % filename
                continue
            precision = ref['coords_precision']
            time_delta = ref.pop('trkpt_time_delta', None)
            trkpt_dist = ref.pop('trkpt_dist', None)
            if not precision:
                print 'Photo %s: could not get reference from track' % filename
            elif precision == 'precise':
                pass
            elif precision == 'approx':
                print 'Photo %s: approximate coordinates written, dt=%s, dl=%s' % (filename, time_delta, trkpt_dist)
            else:
                raise Exception(ref)
            photo_setting.set(filename, ref)


if __name__ == '__main__':
    main()
