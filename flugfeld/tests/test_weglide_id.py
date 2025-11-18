from src.csv import read_airports


def test_weglide_id_set():
    for airport in read_airports():
        assert airport["weglide_id"] is not None


def test_weglide_id_unique():
    seen = set()
    for airport in read_airports():
        assert airport["weglide_id"] not in seen
        seen.add(airport["weglide_id"])


def test_weglide_id_strictly_ascending():
    weglide_id = 139283
    for airport in read_airports():
        assert airport["weglide_id"] is not None
        assert airport["weglide_id"] > weglide_id
        weglide_id = airport["weglide_id"]
