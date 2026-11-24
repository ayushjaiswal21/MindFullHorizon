"""Every sign-in path must stamp the cookie session (utils/session_stamp.py).

Tests may use stamp-less sessions (TESTING is lenient), so this checks the stamp directly. A missing stamp means the
next request is treated as signed out in development and production (found by driving the real admin login in a browser).
"""
from tests.conftest import PASSWORD


def _post_login(client, path, **data):
    return client.post(path, data=data, follow_redirects=False)


def test_admin_login_sets_stamp(client, make_user):
    make_user("admin", email="stamp.admin@test.local")
    r = _post_login(client, "/admin/login", email="stamp.admin@test.local", password=PASSWORD)
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("user_role") == "admin" and sess.get("stamp")


def test_password_login_sets_stamp(client, make_user):
    for role in ("patient", "provider"):
        email = f"stamp.{role}@test.local"
        make_user(role, email=email)
        c = client.application.test_client()
        r = _post_login(c, "/login", email=email, password=PASSWORD, role=role)
        assert r.status_code == 302
        with c.session_transaction() as sess:
            assert sess.get("stamp"), role


def test_stamped_admin_session_survives_next_request(app, make_user):
    make_user("admin", email="stamp.admin2@test.local")
    app.config["TESTING"] = False  # the lenient test mode would hide a missing stamp
    try:
        c = app.test_client()
        c.post("/admin/login", data={"email": "stamp.admin2@test.local", "password": PASSWORD})
        r = c.get("/admin/", follow_redirects=False)
        assert r.status_code == 200
    finally:
        app.config["TESTING"] = True
