"""Dev-only: create one demo patient and one demo provider with random passwords (printed once).

Usage:  python scripts/seed_demo.py        (refuses to run when FLASK_ENV=production)
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def seed():
    if os.getenv('FLASK_ENV') == 'production':
        sys.exit('Refusing to seed demo users when FLASK_ENV=production.')
    from app import app
    from extensions import db
    from models import User

    created = []
    with app.app_context():
        for role in ('patient', 'provider'):
            email = f'demo.{role}@example.com'
            if User.query.filter_by(email=email).first():
                print(f'{email} already exists; left unchanged (password not shown).')
                continue
            password = secrets.token_urlsafe(12)
            user = User(email=email, name=f'Demo {role.title()}', role=role, institution='Demo University')
            user.set_password(password)
            db.session.add(user)
            created.append((email, password))
        db.session.commit()
    for email, password in created:
        print(f'{email}  password: {password}')
    if created:
        print('Passwords are shown only once.')


if __name__ == '__main__':
    seed()
