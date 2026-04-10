"""Admin API – requires is_admin=True."""
import json
import os
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, TestRecord, WordBank
from routes.wordbank import load_words

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated


# ── User management ──────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    q = request.args.get('q', '')
    query = User.query
    if q:
        query = query.filter(
            (User.username.contains(q)) | (User.email.contains(q))
        )
    total = query.count()
    users = query.order_by(User.id).offset((page-1)*per_page).limit(per_page).all()
    return jsonify({
        'total': total,
        'page': page,
        'users': [_user_dict(u) for u in users],
    })


@admin_bp.route('/users/<int:uid>', methods=['PUT'])
@login_required
@admin_required
def update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}
    if 'is_admin' in data:
        user.is_admin = bool(data['is_admin'])
    if 'username' in data:
        user.username = data['username'].strip()
    db.session.commit()
    return jsonify({'message': '已更新', 'user': _user_dict(user)})


@admin_bp.route('/users/<int:uid>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(uid):
    if uid == current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': '已删除'})


# ── Word bank management ─────────────────────────

@admin_bp.route('/wordbank', methods=['GET'])
@login_required
@admin_required
def list_wordbank():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 30))
    level = request.args.get('level', '')
    q = request.args.get('q', '')
    query = WordBank.query
    if level:
        query = query.filter_by(level=level)
    if q:
        query = query.filter(
            (WordBank.word.contains(q)) | (WordBank.meaning.contains(q))
        )
    total = query.count()
    words = query.order_by(WordBank.level, WordBank.freq_rank).offset((page-1)*per_page).limit(per_page).all()
    return jsonify({
        'total': total,
        'page': page,
        'words': [_word_dict(w) for w in words],
    })


@admin_bp.route('/wordbank', methods=['POST'])
@login_required
@admin_required
def add_word():
    data = request.get_json() or {}
    word = data.get('word', '').strip()
    meaning = data.get('meaning', '').strip()
    level = data.get('level', '').strip()
    if not word or not meaning or level not in ('primary', 'middle', 'high'):
        return jsonify({'error': '请填写完整信息'}), 400
    if WordBank.query.filter_by(word=word, level=level).first():
        return jsonify({'error': '词汇已存在'}), 400
    max_rank = db.session.query(db.func.max(WordBank.freq_rank)).filter_by(level=level).scalar() or 0
    w = WordBank(
        word=word, meaning=meaning,
        phonetic=data.get('phonetic', ''),
        level=level, freq_rank=max_rank+1,
    )
    db.session.add(w)
    db.session.commit()
    return jsonify({'message': '添加成功', 'word': _word_dict(w)})


@admin_bp.route('/wordbank/<int:wid>', methods=['PUT'])
@login_required
@admin_required
def update_word(wid):
    w = WordBank.query.get_or_404(wid)
    data = request.get_json() or {}
    for field in ('word', 'meaning', 'phonetic'):
        if field in data:
            setattr(w, field, data[field])
    if 'enabled' in data:
        w.enabled = bool(data['enabled'])
    db.session.commit()
    return jsonify({'message': '已更新', 'word': _word_dict(w)})


@admin_bp.route('/wordbank/<int:wid>', methods=['DELETE'])
@login_required
@admin_required
def delete_word(wid):
    w = WordBank.query.get_or_404(wid)
    db.session.delete(w)
    db.session.commit()
    return jsonify({'message': '已删除'})


@admin_bp.route('/wordbank/seed', methods=['POST'])
@login_required
@admin_required
def seed_wordbank():
    """Import from JSON seed files into DB (idempotent)."""
    imported = 0
    for level in ('primary', 'middle', 'high'):
        words = load_words(level)
        for w in words:
            if not WordBank.query.filter_by(word=w['word'], level=level).first():
                db.session.add(WordBank(
                    word=w['word'], meaning=w['meaning'],
                    phonetic=w.get('phonetic', ''),
                    level=level,
                    freq_rank=w.get('freq_rank', 0),
                ))
                imported += 1
    db.session.commit()
    return jsonify({'message': f'导入完成，新增 {imported} 条'})


# ── Stats ────────────────────────────────────────

@admin_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def stats():
    total_users = User.query.count()
    total_tests = TestRecord.query.count()
    total_words = WordBank.query.filter_by(enabled=True).count()
    recent = TestRecord.query.order_by(TestRecord.created_at.desc()).limit(10).all()
    return jsonify({
        'total_users': total_users,
        'total_tests': total_tests,
        'total_words': total_words,
        'recent_tests': [_record_dict(r) for r in recent],
    })


# ── User test records ────────────────────────────

@admin_bp.route('/records', methods=['GET'])
@login_required
@admin_required
def list_records():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    records = TestRecord.query.order_by(TestRecord.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    total = TestRecord.query.count()
    return jsonify({'total': total, 'records': [_record_dict(r) for r in records]})


def _user_dict(u):
    return {
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'is_admin': u.is_admin,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'test_count': len(u.test_records),
    }


def _word_dict(w):
    return {
        'id': w.id,
        'word': w.word,
        'meaning': w.meaning,
        'phonetic': w.phonetic,
        'level': w.level,
        'freq_rank': w.freq_rank,
        'enabled': w.enabled,
    }


def _record_dict(r):
    return {
        'id': r.id,
        'user_id': r.user_id,
        'level': r.level,
        'algo': r.algo,
        'score': r.score,
        'accuracy': r.accuracy,
        'estimated_level': r.estimated_level,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    }
