import pytest

from .georeference import interpolate_latlon
from .gpx import LatLonTime


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
