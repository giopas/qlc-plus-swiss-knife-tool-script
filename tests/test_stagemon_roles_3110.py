"""3.11.0 Tablet on stage: the views by role can be switched off."""
from core import stage_monitor as sm


def test_roles_on_by_default_and_off_when_asked():
    assert "roles" not in sm.clean_config({})
    assert "roles" not in sm.clean_config({"roles": True})
    assert sm.clean_config({"roles": False})["roles"] is False


def test_page_has_no_views_when_roles_are_off():
    on = sm.page_data(sm.clean_config({}), [])
    off = sm.page_data(sm.clean_config({"roles": False}), [])
    assert on["views"] and off["views"] == []
