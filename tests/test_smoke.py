def test_landing_for_guest_has_helpline(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"14416" in r.data


def test_public_pages_render(client):
    for url in ("/login", "/signup", "/blog/"):
        assert client.get(url).status_code == 200, url


def test_login_with_form(client, make_user):
    from conftest import PASSWORD
    make_user("patient", email="p@test.local")
    r = client.post("/login", data={"email": "p@test.local", "password": PASSWORD, "role": "patient"})
    assert r.status_code == 302


def test_logged_in_home_is_app_home(patient_client):
    c, _ = patient_client
    assert c.get("/").status_code == 200
