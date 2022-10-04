import pytest

from .georeference import interpolate_latlon


@pytest.mark.parametrize(
    "timestamp,point1,point2,expected",
    [
        (10, [110, 330, 10], [140, 390, 40], (110, 330)),
        (40, [110, 330, 10], [140, 390, 40], (140, 390)),
        (20, [110, 330, 10], [140, 390, 40], (120, 350)),
        (30, [110, 330, 10], [140, 390, 40], (130, 370)),
        (30, [110, 330, 30], [140, 390, 40], (110, 330)),
    ],
)
def test_interpolation(timestamp, point1, point2, expected):
    assert interpolate_latlon(timestamp, point1, point2) == expected
