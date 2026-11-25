"""Blog system and public contact-form models."""
from datetime import datetime
from extensions import db

__all__ = ["BlogPost", "BlogLike", "BlogComment", "BlogInsight", "ContactMessage"]


# BlogPost model for blog system (enhanced with relationships)
class BlogPost(db.Model):
    """Blog post model for storing blog entries."""
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category = db.Column(db.String(50), default='general')
    tags = db.Column(db.Text, nullable=True)  # Comma-separated tags
    views = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref=db.backref('blog_posts', cascade='all, delete-orphan', passive_deletes=True))
    likes = db.relationship('BlogLike', backref='post', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    comments = db.relationship('BlogComment', backref='post', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)

    @property
    def like_count(self):
        """Get total number of likes for this post"""
        return self.likes.count()

    @property
    def comment_count(self):
        """Get total number of comments for this post"""
        return self.comments.count()

    def is_liked_by(self, user_id):
        """Check if a user has liked this post"""
        return self.likes.filter_by(user_id=user_id).first() is not None

    @property
    def engagement_score(self):
        """Calculate engagement score based on likes, comments, and views"""
        return (self.like_count * 2) + (self.comment_count * 3) + (self.views * 0.1)

    def __repr__(self):
        return f'<BlogPost {self.title}>'


class BlogLike(db.Model):
    """Blog like model for tracking post likes."""
    __tablename__ = 'blog_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('blog_likes', cascade='all, delete-orphan', passive_deletes=True))

    # Ensure a user can only like a post once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),)

    def __repr__(self):
        return f'<BlogLike user:{self.user_id} post:{self.post_id}>'


class BlogComment(db.Model):
    """Blog comment model for storing post comments."""
    __tablename__ = 'blog_comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('blog_comments.id', ondelete='CASCADE'), nullable=True)  # For reply functionality
    content = db.Column(db.Text, nullable=False)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - Fixed: self-referencing relationship should use delete instead of delete-orphan
    parent = db.relationship('BlogComment', remote_side=[id], backref=db.backref('replies', cascade='all, delete-orphan', passive_deletes=True))
    user = db.relationship('User', backref=db.backref('blog_comments', cascade='all, delete-orphan', passive_deletes=True))

    @property
    def author_name(self):
        return self.user.name if self.user else 'Deleted user'

    def __repr__(self):
        return f'<BlogComment {self.id} by {self.user_id}>'


class BlogInsight(db.Model):
    """Blog insight model for tracking analytics and insights."""
    __tablename__ = 'blog_insights'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    total_posts = db.Column(db.Integer, default=0)
    total_views = db.Column(db.Integer, default=0)
    total_likes = db.Column(db.Integer, default=0)
    total_comments = db.Column(db.Integer, default=0)
    top_categories = db.Column(db.JSON, nullable=True)  # Store popular categories
    engagement_rate = db.Column(db.Float, default=0.0)
    most_popular_post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    most_popular_post = db.relationship('BlogPost', backref=db.backref('insights', passive_deletes=True))

    def __repr__(self):
        return f'<BlogInsight {self.date}>'


class ContactMessage(db.Model):
    """Message from the public contact form. Always stored first; email is a job."""
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(15), nullable=False, default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (db.CheckConstraint("status IN ('new','emailed','email_failed','read')", name='ck_contact_status'),)
