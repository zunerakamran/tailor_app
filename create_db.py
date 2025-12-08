from app import db, app

# Create the database and all tables
with app.app_context():
    db.create_all()
    print("Database created successfully!")
