import pytest
from percival.operations.health import Check, approved_endpoint_check, disk_check, render_json
from percival.operations.poller import poll


def test_disk_check():
    assert disk_check("/").status in ("healthy", "warning")


def test_invalid_endpoints_rejected():
    for url in ("http://example.com", "https://user:pass@example.com", "file:///tmp/file"):
        with pytest.raises(ValueError):
            approved_endpoint_check("test", url)


def test_poller_is_bounded():
    seen = []
    waits = []
    probe = lambda: [Check("synthetic", "healthy", "test", 0)]
    poll(5, iterations=3, probe=probe, emit=lambda c: seen.append(c), sleep=waits.append)
    assert len(seen) == 3
    assert waits == [5, 5]
    assert '"synthetic"' in render_json(seen[0])


def test_poller_rejects_busy_loop():
    with pytest.raises(ValueError):
        poll(0, iterations=1)
