from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    test_records = db.relationship('TestRecord', backref='user', lazy=True, cascade='all, delete-orphan')


class TestRecord(db.Model):
    __tablename__ = 'test_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # nullable for anonymous
    session_id = db.Column(db.String(64), nullable=True)  # for anonymous tracking
    level = db.Column(db.String(20), nullable=False)  # primary/middle/high/all
    algo = db.Column(db.String(20), default='binary')  # binary / irt
    score = db.Column(db.Integer, nullable=False)       # estimated vocab size
    accuracy = db.Column(db.Float, nullable=False)      # correct ratio
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    estimated_level = db.Column(db.String(20))          # 小学/初中/高中/大学
    details = db.Column(db.Text)                        # JSON: per-question breakdown
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class WordBank(db.Model):
    __tablename__ = 'word_bank'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.Text, nullable=False)
    phonetic = db.Column(db.String(200))
    level = db.Column(db.String(20), nullable=False)    # primary/middle/high
    freq_rank = db.Column(db.Integer)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('word', 'level', name='uq_word_level'),)


class LearningRecord(db.Model):
    """Spaced repetition learning records per user per word."""
    __tablename__ = 'learning_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_bank_id = db.Column(db.Integer, db.ForeignKey('word_bank.id'), nullable=False)
    correct_count = db.Column(db.Integer, default=0)
    wrong_count = db.Column(db.Integer, default=0)
    ease_factor = db.Column(db.Float, default=2.5)      # SM-2 ease factor
    interval_days = db.Column(db.Integer, default=1)
    next_review = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_reviewed = db.Column(db.DateTime)

    user = db.relationship('User', backref='learning_records')
    word = db.relationship('WordBank', backref='learning_records')
