from flask import Flask
from models import db, User
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# Basic app configuration
app.config['SECRET_KEY'] = 'emp_secure_university_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions with the app
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect unauthorized users here

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback to fetch user by ID from session."""
    return db.session.get(User, int(user_id))

def seed_admin():
    """Programmatically seed default admin user on startup if not present."""
    with app.app_context():
        db.create_all() 
        admin_user = User.query.filter_by(role='admin').first()
        if not admin_user:
            hashed_pw = generate_password_hash('Admin@123')
            admin = User(
                username='admin',
                email='admin@emp.com',
                password_hash=hashed_pw,
                role='admin',
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin / Admin@123")

if __name__ == '__main__':
    seed_admin()
    app.run(debug=True)