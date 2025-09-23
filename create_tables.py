import os
import sys
sys.path.append('c:\\Users\\dell\\Desktop\\MindFullHorizon')

from flask import Flask
from models import db

# Create Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/mindful_horizon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def create_tables():
    """Create all database tables"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ All database tables created successfully!")

            # List all created tables
            tables = [table.name for table in db.metadata.sorted_tables]
            print("📋 Created tables:", tables)

            # Check if prescriptions table exists
            if 'prescriptions' in tables:
                print("✅ 'prescriptions' table created successfully!")
            else:
                print("❌ 'prescriptions' table not found in created tables")

        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False

    return True

if __name__ == "__main__":
    print("🔧 Creating database tables...")
    success = create_tables()

    if success:
        print("\n🎉 Database setup completed successfully!")
        print("💡 Your Flask application should now work without the 'prescriptions' table error.")
    else:
        print("\n❌ Database setup failed. Please check the error message above.")
