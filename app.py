"""Vocabulary Assessment Tool - Main Flask Application."""
import os
from flask import Flask, jsonify, send_from_directory
from flask_login import LoginManager
from models import db, User

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'vocab-tool-secret-2024-change-in-prod'),
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(BASE_DIR, 'vocab.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SAMESITE='Lax',
    )

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = None  # API-only: return 401 instead of redirect

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'error': '请先登录'}), 401

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.assessment import assess_bp
    from routes.admin import admin_bp
    from routes.wordbank import wb_bp
    from routes.user import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(assess_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(wb_bp)
    app.register_blueprint(user_bp)

    # SPA catch-all: serve index.html for all non-API routes
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        if path.startswith('api/') or path.startswith('static/'):
            return jsonify({'error': 'Not found'}), 404
        return send_from_directory(app.static_folder, 'index.html')

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


def _seed_admin():
    """Create a default admin account if none exists."""
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(is_admin=True).first():
        admin = User(
            username='admin',
            email='admin@vocab.local',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()
        print('[seed] Admin account created: admin / admin123')


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
