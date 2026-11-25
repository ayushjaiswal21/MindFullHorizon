"""Query helpers that keep cost flat as tables grow (no per-row queries, no loading whole histories)."""
from sqlalchemy import func, select

from core.extensions import db


def latest_rows(model, key_col, order_cols, ids, *conditions, extra_partition=()):
    """Newest row per `key_col` value (optionally per extra column too) among `ids`, in ONE statement.

    ROW_NUMBER() OVER (PARTITION BY ...) works on SQLite 3.25+ and PostgreSQL. Returns a list of model rows.
    """
    if not ids:
        return []
    rn = func.row_number().over(partition_by=[key_col, *extra_partition], order_by=list(order_cols)).label('rn')
    ranked = select(model.id.label('pk'), rn).where(key_col.in_(ids), *conditions).subquery()
    return list(db.session.scalars(select(model).join(ranked, model.id == ranked.c.pk).where(ranked.c.rn == 1)))


class PostView:
    """A blog post plus counts computed for the whole page in two grouped queries.

    The model's like_count/comment_count properties run one COUNT per post (dynamic relationships);
    templates keep using `post.like_count`, and every other attribute is forwarded to the real post.
    """

    def __init__(self, post, likes, comments):
        self._post = post
        self.like_count = likes
        self.comment_count = comments

    def __getattr__(self, name):
        return getattr(self._post, name)


def with_blog_counts(posts):
    from models import BlogLike, BlogComment  # local: models imports extensions only
    ids = [p.id for p in posts]
    if not ids:
        return []
    likes = dict(db.session.execute(select(BlogLike.post_id, func.count()).where(BlogLike.post_id.in_(ids)).group_by(BlogLike.post_id)).all())
    comments = dict(db.session.execute(select(BlogComment.post_id, func.count()).where(BlogComment.post_id.in_(ids)).group_by(BlogComment.post_id)).all())
    return [PostView(p, likes.get(p.id, 0), comments.get(p.id, 0)) for p in posts]
