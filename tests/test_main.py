from pathlib import Path

import pytest

from photo_georeference.georeference import (
    GeoReferencer,
    calculate_offset,
    get_photo_local_timestamp,
    interpolate_latlon,
)
from photo_georeference.gpx import LatLonTime


@pytest.fixture(name="jpg_filename")
def fixture_jpg_filename() -> str:
    return str(Path(__file__).parent / "photo.jpg")


@pytest.fixture(name="tracks")
def fixture_tracks() -> list[str]:
    tests_dir = Path(__file__).parent
    return [
        str(tests_dir / "2021-10-24 07.37.25 Week.gpx"),
        str(tests_dir / "2021-10-24 07.37.30 Week.gpx"),
        str(tests_dir / "Current.gpx"),
    ]


@pytest.mark.parametrize(
    "zone_offset, camera_offset, expected",
    [
        (0, 0, 0),
        (1, 0, -3600),
        (2, 0, -7200),
        (-2, 0, 7200),
        (0, 10, 10),
        (0, -10, -10),
        (3, 10, -10790),
        (-3, 10, 10810),
        (1.25, -10, -4510),
    ],
)
def test_calculate_offset(
    zone_offset: float, camera_offset: int, expected: float
) -> None:
    assert calculate_offset(zone_offset, camera_offset) == expected


def test_get_photo_local_timestamp(jpg_filename: str) -> None:
    assert get_photo_local_timestamp(jpg_filename) == 1635693474


def test_georeference_precise(tracks: list[str]) -> None:
    referencer = GeoReferencer(tracks)
    assert referencer.get_position_from_timestamp(1635693474, -3600) == {
        "heading": -135.84117399896272,
        "lat": 49.223688785,
        "lon": 16.4897198696,
        "sources": [tracks[2]],
        "timestamp": 1635689874,
        "track_points_dist": 0.5348440319325724,
        "track_points_time_delta": 1.0,
    }


def test_georefercne_missing(tracks: list[str]) -> None:
    referencer = GeoReferencer(tracks)
    assert referencer.get_position_from_timestamp(1635693474, 0) == {
        "timestamp": 1635693474
    }


def test_georefercne_approx(tracks: list[str]) -> None:
    referencer = GeoReferencer(tracks)
    assert referencer.get_position_from_timestamp(1635681600, 0) == {
        "heading": 100.61736534330599,
        "lat": 49.230591764502385,
        "lon": 16.487560006114137,
        "sources": [tracks[1], tracks[2]],
        "timestamp": 1635681600,
        "track_points_dist": 201850.08802551116,
        "track_points_time_delta": 610634.0,
    }


@pytest.mark.parametrize(
    "timestamp,point1,point2,expected",
    [
        (10, LatLonTime(110, 330, 10), LatLonTime(140, 390, 40), (110, 330)),
        (40, LatLonTime(110, 330, 10), LatLonTime(140, 390, 40), (140, 390)),
        (20, LatLonTime(110, 330, 10), LatLonTime(140, 390, 40), (120, 350)),
        (30, LatLonTime(110, 330, 10), LatLonTime(140, 390, 40), (130, 370)),
        (30, LatLonTime(110, 330, 30), LatLonTime(140, 390, 40), (110, 330)),
    ],
)
def test_interpolation(
    timestamp: int,
    point1: LatLonTime,
    point2: LatLonTime,
    expected: tuple[float, float],
) -> None:
    assert interpolate_latlon(timestamp, point1, point2) == expected
