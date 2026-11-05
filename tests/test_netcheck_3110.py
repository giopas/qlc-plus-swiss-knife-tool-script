"""3.11.0: the internet dot (green, orange, red)."""
from core import netcheck


def test_classify():
    ok, slow = (True, True, 0.2), (True, True, 2.0)
    dns_only, nothing = (True, False, 0.1), (False, False, 0.0)
    assert netcheck.classify({"claude": ok, "gh": nothing}) == "online"
    assert netcheck.classify({"claude": slow, "gh": ok}) == "limited"
    assert netcheck.classify({"claude": nothing, "gh": ok}) == "limited"
    assert netcheck.classify({"claude": dns_only, "gh": nothing}) == "limited"
    assert netcheck.classify({"claude": nothing, "gh": nothing}) == "offline"


def test_check_is_kept_for_a_while():
    calls = []

    def reach(h, p, t):
        calls.append(h)
        return (False, False, 0.0)
    netcheck._cache.update({"at": 0.0, "result": None})
    a = netcheck.check(now=1000.0, reach=reach)
    b = netcheck.check(now=1005.0, reach=reach)
    assert a["state"] == b["state"] == "offline" and len(calls) == len(netcheck.HOSTS)
    netcheck.check(now=1005.0, reach=reach, force=True)
    assert len(calls) == 2 * len(netcheck.HOSTS)
    netcheck._cache.update({"at": 0.0, "result": None})


def test_route_stays_offline_in_tests():
    import app
    a = app.create_app()
    a.config["TESTING"] = True
    c = a.test_client()
    assert c.get("/api/net/status").get_json()["state"] == "unknown"


def test_library_folders_list_my_kit():
    from routes import library_routes
    from core.cabling import kit
    assert library_routes.folders()["My kit (Cabling)"] == kit.kit_path()
