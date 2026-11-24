from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, abort
from models import BlogPost, BlogComment, BlogLike, db, User
from decorators import login_required, api_login_required
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

_TRUE = ('1', 'true', 'on', 'yes', 'y')


def _can_manage(post):
    """Author or admin may edit/delete."""
    return session.get('user_id') == post.author_id or session.get('user_role') == 'admin'


def _visible_post_or_404(post_id):
    """Drafts are visible only to their author (or an admin)."""
    post = BlogPost.query.get_or_404(post_id)
    if not post.is_published and not (session.get('user_id') and _can_manage(post)):
        abort(404)
    return post


def _published_flag(default):
    """Checkbox value from the form; `default` when the field is absent."""
    values = request.form.getlist('is_published')
    if not values:
        return default
    return any(v.strip().lower() in _TRUE for v in values)


@blog_bp.route('/')
def blog_list():
    try:
        posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
        # Get blog insights for display
        insights = {
            'total_posts': len(posts),
            'total_likes': 0,
            'total_comments': 0,
            'total_views': sum([post.views or 0 for post in posts]) if posts else 0,
            'most_popular_post': None
        }
        if posts:
            insights['most_popular_post'] = max(posts, key=lambda p: p.views or 0)
    except SQLAlchemyError:
        posts = []
        insights = None
    return render_template('blog_list.html', posts=posts, insights=insights)

@blog_bp.route('/<int:post_id>')
def blog_detail(post_id):
    post = _visible_post_or_404(post_id)

    # Increment view count
    post.views = (post.views or 0) + 1
    db.session.commit()

    # Top-level comments; replies are loaded under their parent
    comments = BlogComment.query.filter_by(post_id=post_id, parent_id=None).order_by(BlogComment.created_at.asc()).all()
    comment_total = BlogComment.query.filter_by(post_id=post_id).count()
    # BlogComment has no `user` relationship, so look the names up in one query.
    authors = {u.id: u.name for u in User.query.filter(User.id.in_({c.user_id for c in comments})).all()} if comments else {}

    # Check if current user has liked this post
    user_has_liked = False
    if session.get('user_id'):
        user_has_liked = BlogLike.query.filter_by(
            user_id=session['user_id'],
            post_id=post_id
        ).first() is not None

    return render_template('blog_detail.html',
                         post=post,
                         comments=comments,
                         comment_total=comment_total,
                         authors=authors,
                         can_manage=bool(session.get('user_id')) and _can_manage(post),
                         user_has_liked=user_has_liked)

@blog_bp.route('/create', methods=['GET', 'POST'])
@login_required
def blog_create():
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        content = (request.form.get('content') or '').strip()
        if not title or not content:
            flash('Title and content are required.', 'error')
            return render_template('blog_create.html')
        try:
            post = BlogPost(
                title=title,
                content=content,
                category=request.form.get('category'),
                tags=request.form.get('tags'),
                is_published=_published_flag(True),
                author_id=session.get('user_id'),
                created_at=datetime.now()
            )
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('blog.blog_list'))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Failed to create blog post.', 'error')
    return render_template('blog_create.html')

@blog_bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if not _can_manage(post):
        abort(403)
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        post.tags = request.form.get('tags')
        post.is_published = _published_flag(post.is_published)
        try:
            db.session.commit()
            flash('Blog post updated successfully!', 'success')
            return redirect(url_for('blog.blog_detail', post_id=post.id))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Failed to update blog post.', 'error')
    return render_template('blog_edit.html', post=post)

@blog_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def blog_delete(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if not _can_manage(post):
        abort(403)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted successfully!', 'success')
    except SQLAlchemyError:
        db.session.rollback()
        flash('Failed to delete blog post.', 'error')
    return redirect(url_for('blog.blog_list'))

@blog_bp.route('/api/<int:post_id>/like', methods=['POST'])
@api_login_required
def blog_like(post_id):
    """Toggle like for a blog post"""
    user_id = session['user_id']
    _visible_post_or_404(post_id)

    existing_like = BlogLike.query.filter_by(user_id=user_id, post_id=post_id).first()

    try:
        if existing_like:
            db.session.delete(existing_like)
            liked = False
        else:
            db.session.add(BlogLike(user_id=user_id, post_id=post_id))
            liked = True

        db.session.commit()

        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': BlogLike.query.filter_by(post_id=post_id).count()
        })

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to update like'}), 500

@blog_bp.route('/api/<int:post_id>/comment', methods=['POST'])
@api_login_required
def blog_comment(post_id):
    """Add a comment (or a reply, with parent_id) to a blog post"""
    user_id = session['user_id']
    _visible_post_or_404(post_id)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    content = data.get('content')
    content = content.strip() if isinstance(content, str) else ''

    if not content:
        return jsonify({'success': False, 'message': 'Comment content is required'}), 400

    if len(content) > 1000:
        return jsonify({'success': False, 'message': 'Comment is too long (max 1000 characters)'}), 400

    parent_id = data.get('parent_id')
    if parent_id is not None:
        parent = db.session.get(BlogComment, parent_id) if isinstance(parent_id, int) else None
        if parent is None or parent.post_id != post_id:
            return jsonify({'success': False, 'message': 'Comment to reply to was not found'}), 404

    try:
        new_comment = BlogComment(
            user_id=user_id,
            post_id=post_id,
            parent_id=parent_id,
            content=content
        )
        db.session.add(new_comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': _comment_json(new_comment, db.session.get(User, user_id)),
            'comment_count': BlogComment.query.filter_by(post_id=post_id).count()
        })

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to add comment'}), 500

@blog_bp.route('/api/<int:post_id>/comments/<int:comment_id>/replies', methods=['GET'])
def blog_replies(post_id, comment_id):
    """Replies to one comment (public, like the post itself)."""
    _visible_post_or_404(post_id)
    replies = BlogComment.query.filter_by(post_id=post_id, parent_id=comment_id).order_by(BlogComment.created_at.asc()).all()
    users = {u.id: u for u in User.query.filter(User.id.in_({r.user_id for r in replies})).all()} if replies else {}
    return jsonify({'success': True, 'replies': [_comment_json(r, users.get(r.user_id)) for r in replies]})


def _comment_json(comment, user):
    return {
        'id': comment.id,
        'content': comment.content,
        'author_name': user.name if user else 'Unknown',
        'created_at': comment.created_at.strftime('%B %d, %Y • %I:%M %p')
    }
