"""Blog: ownership, drafts, API auth, replies, XSS-safe rendering."""
import os

from extensions import db
from models import BlogComment, BlogPost

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_post(app, author_id, published=True, title="Hello"):
    with app.app_context():
        post = BlogPost(title=title, content="body", author_id=author_id, is_published=published)
        db.session.add(post)
        db.session.commit()
        return post.id


def login_as(app, uid, role="patient"):
    c = app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=uid, user_email=f"u{uid}@t.l", user_role=role, user_name="U", user_institution="Test University")
    return c


def test_other_user_cannot_edit_or_delete(app, make_user):
    author, other = make_user("patient"), make_user("patient")
    pid = make_post(app, author)
    c = login_as(app, other)
    assert c.get(f"/blog/{pid}/edit").status_code == 403
    assert c.post(f"/blog/{pid}/edit", data={"title": "x", "content": "y"}).status_code == 403
    assert c.post(f"/blog/{pid}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(BlogPost, pid).title == "Hello"


def test_author_can_edit_and_delete_but_a_fake_admin_role_cannot(app, make_user):
    author, admin = make_user("patient"), make_user("patient")  # the DB only allows patient/provider: no admin role exists
    pid = make_post(app, author)
    assert login_as(app, author).post(f"/blog/{pid}/edit", data={"title": "Mine", "content": "y", "category": "general"}).status_code == 302
    assert login_as(app, admin, "admin").post(f"/blog/{pid}/delete").status_code == 403
    assert login_as(app, author).post(f"/blog/{pid}/delete").status_code == 302
    with app.app_context():
        assert db.session.get(BlogPost, pid) is None


def test_edit_without_checkbox_keeps_published(app, make_user):
    author = make_user("patient")
    pid = make_post(app, author)
    login_as(app, author).post(f"/blog/{pid}/edit", data={"title": "T", "content": "y"})
    with app.app_context():
        assert db.session.get(BlogPost, pid).is_published is True


def test_create_parses_is_published(app, make_user):
    c = login_as(app, make_user("patient"))
    c.post("/blog/create", data={"title": "Draft one", "content": "c", "is_published": ["false", "false"]})
    c.post("/blog/create", data={"title": "Live one", "content": "c", "is_published": ["false", "true"]})
    c.post("/blog/create", data={"title": "Default one", "content": "c"})
    with app.app_context():
        got = {p.title: p.is_published for p in BlogPost.query.all()}
    assert got == {"Draft one": False, "Live one": True, "Default one": True}


def test_draft_hidden_from_others_visible_to_author(app, make_user, client):
    author, other = make_user("patient"), make_user("patient")
    pid = make_post(app, author, published=False)
    assert client.get(f"/blog/{pid}").status_code == 404
    assert login_as(app, other).get(f"/blog/{pid}").status_code == 404
    assert login_as(app, other).post(f"/blog/api/{pid}/like").status_code == 404
    assert login_as(app, author).get(f"/blog/{pid}").status_code == 200
    assert b"Hello" not in client.get("/blog/").data


def test_anonymous_api_is_401(app, make_user, client):
    pid = make_post(app, make_user("patient"))
    assert client.post(f"/blog/api/{pid}/like").status_code == 401
    assert client.post(f"/blog/api/{pid}/comment", json={"content": "x"}).status_code == 401


def test_like_toggle_comment_and_replies(app, make_user):
    author, reader = make_user("patient"), make_user("patient")
    pid = make_post(app, author)
    c = login_as(app, reader)
    assert c.post(f"/blog/api/{pid}/like").get_json()["like_count"] == 1
    assert c.post(f"/blog/api/{pid}/like").get_json()["liked"] is False
    top = c.post(f"/blog/api/{pid}/comment", json={"content": "<b>hi</b>"}).get_json()
    assert top["success"] and top["comment"]["content"] == "<b>hi</b>"
    cid = top["comment"]["id"]
    rep = c.post(f"/blog/api/{pid}/comment", json={"content": "reply", "parent_id": cid}).get_json()
    assert rep["comment_count"] == 2
    got = c.get(f"/blog/api/{pid}/comments/{cid}/replies").get_json()
    assert [r["content"] for r in got["replies"]] == ["reply"]
    # reply parent must belong to the same post
    other_post = make_post(app, author, title="Other")
    assert c.post(f"/blog/api/{other_post}/comment", json={"content": "x", "parent_id": cid}).status_code == 404
    assert c.post(f"/blog/api/{pid}/comment", json={"content": "   "}).status_code == 400


def test_detail_escapes_comments_and_has_no_innerhtml(app, make_user):
    author = make_user("patient")
    pid = make_post(app, author, title='T"</script><i>')
    with app.app_context():
        db.session.add(BlogComment(user_id=author, post_id=pid, content="<img src=x onerror=alert(1)>"))
        db.session.commit()
    html = login_as(app, author).get(f"/blog/{pid}").get_data(as_text=True)
    assert "<img src=x onerror" not in html
    assert "&lt;img src=x" in html
    assert "</script><i>" not in html
    assert "innerHTML" not in html
    assert f"/blog/api/{pid}/like" in html and "/api/blog/" not in html
    assert "onclick=" not in html
