from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from models import BlogPost, BlogComment, BlogLike, db, User
from decorators import login_required
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

@blog_bp.route('/')
def blog_list():
    try:
        posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
        # Get blog insights for display
        insights = {
            'total_posts': BlogPost.query.count(),
            'total_likes': 0,
            'total_comments': 0,
            'total_views': sum([post.views for post in posts]) if posts else 0,
            'most_popular_post': None
        }
        if posts:
            insights['most_popular_post'] = max(posts, key=lambda p: p.views) if posts else None
    except SQLAlchemyError as e:
        posts = []
        insights = None
    return render_template('blog_list.html', posts=posts, insights=insights)

@blog_bp.route('/<int:post_id>')
def blog_detail(post_id):
    post = BlogPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    db.session.commit()
    
    # Get comments for this post
    comments = BlogComment.query.filter_by(post_id=post_id).order_by(BlogComment.created_at.asc()).all()
    
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
                         user_has_liked=user_has_liked)

@blog_bp.route('/create', methods=['GET', 'POST'])
@login_required
def blog_create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        tags = request.form.get('tags')
        is_published = bool(request.form.get('is_published', 'True'))
        author_id = session.get('user_id')
        try:
            post = BlogPost(
                title=title,
                content=content,
                category=category,
                tags=tags,
                is_published=is_published,
                author_id=author_id,
                created_at=datetime.now()
            )
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('blog.blog_list'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Failed to create blog post.', 'error')
    return render_template('blog_create.html')

@blog_bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.category = request.form.get('category')
        post.tags = request.form.get('tags')
        post.is_published = bool(request.form.get('is_published'))
        try:
            db.session.commit()
            flash('Blog post updated successfully!', 'success')
            return redirect(url_for('blog.blog_detail', post_id=post.id))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Failed to update blog post.', 'error')
    return render_template('blog_edit.html', post=post)

@blog_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def blog_delete(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.author_id != session.get('user_id'):
        abort(403)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete blog post.', 'error')
    return redirect(url_for('blog.blog_list'))

@blog_bp.route('/api/<int:post_id>/like', methods=['POST'])
@login_required
def blog_like(post_id):
    """Toggle like for a blog post"""
    user_id = session['user_id']
    post = BlogPost.query.get_or_404(post_id)
    
    existing_like = BlogLike.query.filter_by(user_id=user_id, post_id=post_id).first()
    
    try:
        if existing_like:
            db.session.delete(existing_like)
            liked = False
        else:
            new_like = BlogLike(user_id=user_id, post_id=post_id)
            db.session.add(new_like)
            liked = True
        
        db.session.commit()
        
        like_count = BlogLike.query.filter_by(post_id=post_id).count()
        
        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to update like'}), 500

@blog_bp.route('/api/<int:post_id>/comment', methods=['POST'])
@login_required
def blog_comment(post_id):
    """Add a comment to a blog post"""
    user_id = session['user_id']
    post = BlogPost.query.get_or_404(post_id)
    
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': 'Comment content is required'}), 400
    
    if len(content) > 1000:
        return jsonify({'success': False, 'message': 'Comment is too long (max 1000 characters)'}), 400
    
    try:
        new_comment = BlogComment(
            user_id=user_id,
            post_id=post_id,
            content=content
        )
        db.session.add(new_comment)
        db.session.commit()
        
        comment_count = BlogComment.query.filter_by(post_id=post_id).count()
        
        user = User.query.get(user_id)
        
        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'content': new_comment.content,
                'author_name': user.name,
                'created_at': new_comment.created_at.strftime('%B %d, %Y • %I:%M %p')
            },
            'comment_count': comment_count
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Failed to add comment'}), 500
