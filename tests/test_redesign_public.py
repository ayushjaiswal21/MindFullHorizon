"""Redesigned public pages: landing, logged-in home, AI explainer, counsellor note tool, blog."""
import os
import re
from datetime import date, timedelta

import pytest

from core.extensions import db
from models import Appointment, BlogPost, MoodLog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = ["landing.html", "index.html", "how_ai_works.html", "ai_documentation.html", "blog_list.html",
             "blog_detail.html", "blog_create.html", "blog_edit.html", "_blog_form.html"]
SCRIPTS = ["home.js", "blog_list.js", "blog_detail.js", "blog_editor.js", "ai_documentation.js"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐️‍]")
EM_DASH = "—"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def login_as(app, uid, role="patient"):
    c = app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=uid, user_email=f"u{uid}@t.l", user_role=role, user_name="Asha Rao",
                 user_institution="Test University")
    return c


def make_post(app, author_id, published=True, title="Sleep and exams"):
    with app.app_context():
        post = BlogPost(title=title, content="word " * 450, author_id=author_id, is_published=published, tags="sleep, study")
        db.session.add(post)
        db.session.commit()
        return post.id


# ---- landing -----------------------------------------------------------------

def test_landing_has_real_hero_and_no_fake_claims(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Create an account" in html and "Log in" in html
    assert html.count("<h1") == 1
    assert 'href="/privacy"' in html and 'href="/terms"' in html
    for fake in ("10,000", "trusted by", "Trusted by", "testimonial", "Testimonial", "AI-powered", "Powered by AI"):
        assert fake not in html, fake
    assert EM_DASH not in html
    assert not EMOJI.search(html)


def test_landing_helplines_come_from_config_and_page_is_indexable(client):
    from utils.helplines import HELPLINES
    html = client.get("/").get_data(as_text=True)
    for h in HELPLINES:
        assert h["number"] in html
    assert re.search(r'name="robots"\s+content="index, follow"', html)
    assert 'rel="canonical"' in html


# ---- logged-in home ----------------------------------------------------------

def test_patient_home_empty_states_and_mood_form(patient_client):
    c, _ = patient_client
    html = c.get("/").get_data(as_text=True)
    assert 'id="home-mood-form"' in html
    assert "empty-state" in html
    assert "No upcoming appointments" in html
    assert "Nothing yet" in html


def test_patient_home_shows_real_data(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        db.session.add(MoodLog(user_id=uid, mood_score=7))
        db.session.add(Appointment(user_id=uid, date=date.today() + timedelta(days=2), time="10:30",
                                   appointment_type="counselling", status="accepted"))
        db.session.commit()
    html = c.get("/").get_data(as_text=True)
    assert "Mood 7 of 10" in html
    assert "10:30" in html and "Confirmed" in html
    assert "Nothing yet" not in html


def test_provider_home_renders(provider_client):
    c, _ = provider_client
    r = c.get("/")
    assert r.status_code == 200
    assert "Today's sessions" in r.get_data(as_text=True)


# ---- AI pages ----------------------------------------------------------------

def test_how_ai_works_is_honest_and_public(client):
    r = client.get("/ai")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count("<h1") == 1
    assert "not a therapist" in html and "crisis check" in html and "14416" in html
    assert EM_DASH not in html and not EMOJI.search(html)


def test_counsellor_note_tool_renders_for_provider(provider_client):
    c, _ = provider_client
    html = c.get("/provider/ai-documentation").get_data(as_text=True)
    assert 'name="transcript"' in html and 'name="patient_email"' in html and 'name="csrf_token"' in html


# ---- blog --------------------------------------------------------------------

def test_blog_list_empty_and_with_posts(app, make_user, client):
    assert "No posts yet" in client.get("/blog/").get_data(as_text=True)
    author = make_user("patient")
    pid = make_post(app, author)
    html = client.get("/blog/").get_data(as_text=True)
    assert "Sleep and exams" in html and f"/blog/{pid}" in html
    assert "min read" in html and "views<" not in html
    assert "confirm-delete-btn" not in html  # not the author, not logged in


def test_blog_list_shows_author_controls(app, make_user):
    author = make_user("patient")
    pid = make_post(app, author)
    html = login_as(app, author).get("/blog/").get_data(as_text=True)
    assert "confirm-delete-btn" in html and f"/blog/{pid}/edit" in html
    assert 'id="deleteModal"' in html and 'id="deleteForm"' in html


def test_blog_detail_keeps_script_hooks(app, make_user, client):
    author = make_user("patient")
    pid = make_post(app, author)
    anon = client.get(f"/blog/{pid}").get_data(as_text=True)
    assert 'id="commentsList"' in anon and 'id="commentCount"' in anon
    assert f"/blog/api/{pid}/like" in anon and "Log in</a> to leave a comment" in anon
    mine = login_as(app, author).get(f"/blog/{pid}").get_data(as_text=True)
    for hook in ('id="likeBtn"', 'id="likeCount"', 'id="commentText"', 'data-action="comment"',
                 'data-action="delete-open"', 'id="comment-template"', 'class="prose'):
        assert hook in mine, hook
    assert "3 min read" in mine


def test_blog_create_and_edit_forms(app, make_user):
    author = make_user("patient")
    pid = make_post(app, author)
    c = login_as(app, author)
    create = c.get("/blog/create")
    edit = c.get(f"/blog/{pid}/edit")
    assert create.status_code == 200 and edit.status_code == 200
    for html in (create.get_data(as_text=True), edit.get_data(as_text=True)):
        for field in ('name="title"', 'name="content"', 'name="category"', 'name="tags"', 'name="is_published"',
                      'name="csrf_token"', 'id="toggle-preview-btn"', 'id="wordCount"', 'for="title"', 'for="content"'):
            assert field in html, field
    assert 'id="save-draft-btn"' in create.get_data(as_text=True)
    assert "Sleep and exams" in edit.get_data(as_text=True)


def test_blog_create_requires_login(client):
    assert client.get("/blog/create").status_code == 302


# ---- source rules ------------------------------------------------------------

@pytest.mark.parametrize("name", TEMPLATES)
def test_templates_follow_design_rules(name):
    text = read("templates", name)
    assert EM_DASH not in text and not EMOJI.search(text)
    assert "|safe" not in text and "| safe" not in text
    assert not re.search(r"\son[a-z]+\s*=", text), "inline event handler"
    assert not re.search(r"\b(bg|text|border|from|to)-(gray|blue|red|green|purple|indigo|pink|yellow)-\d", text)
    assert "rounded-full" not in text and "gradient" not in text


@pytest.mark.parametrize("name", SCRIPTS)
def test_page_scripts_clean(name):
    text = read("static", "js", name)
    assert "{{" not in text and "{%" not in text
    assert "innerHTML" not in text and "alert(" not in text and "confirm(" not in text.replace("MFH.confirm(", "")
    assert EM_DASH not in text and not EMOJI.search(text)
