"""User profile & history API."""
import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, TestRecord, WordBank, LearningRecord

user_bp = Blueprint('user', __name__, url_prefix='/api/user')


@user_bp.route('/history', methods=['GET'])
@login_required
def history():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    records = (TestRecord.query
               .filter_by(user_id=current_user.id)
               .order_by(TestRecord.created_at.desc())
               .offset((page-1)*per_page).limit(per_page).all())
    total = TestRecord.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        'total': total,
        'page': page,
        'records': [_record_dict(r) for r in records],
    })


@user_bp.route('/stats', methods=['GET'])
@login_required
def stats():
    records = TestRecord.query.filter_by(user_id=current_user.id).order_by(TestRecord.created_at).all()
    if not records:
        return jsonify({'total_tests': 0, 'best_score': 0, 'avg_accuracy': 0, 'trend': []})

    best_score = max(r.score for r in records)
    avg_acc = sum(r.accuracy for r in records) / len(records)
    trend = [{'date': r.created_at.strftime('%m-%d'), 'score': r.score} for r in records[-20:]]

    # Breakdown by level
    by_level = {}
    for r in records:
        lvl = r.level
        if lvl not in by_level:
            by_level[lvl] = {'count': 0, 'best': 0}
        by_level[lvl]['count'] += 1
        by_level[lvl]['best'] = max(by_level[lvl]['best'], r.score)

    return jsonify({
        'total_tests': len(records),
        'best_score': best_score,
        'avg_accuracy': round(avg_acc, 3),
        'trend': trend,
        'by_level': by_level,
    })


@user_bp.route('/learning/due', methods=['GET'])
@login_required
def due_words():
    """Words due for spaced-repetition review."""
    now = datetime.now(timezone.utc)
    records = (LearningRecord.query
               .filter_by(user_id=current_user.id)
               .filter(LearningRecord.next_review <= now)
               .join(WordBank)
               .filter(WordBank.enabled == True)
               .limit(20).all())
    return jsonify([{
        'id': r.id,
        'word': r.word.word,
        'meaning': r.word.meaning,
        'phonetic': r.word.phonetic,
        'correct_count': r.correct_count,
        'wrong_count': r.wrong_count,
        'interval_days': r.interval_days,
    } for r in records])


@user_bp.route('/learning/review', methods=['POST'])
@login_required
def review_word():
    """Submit a spaced-repetition review result."""
    data = request.get_json() or {}
    record_id = data.get('record_id')
    quality = int(data.get('quality', 3))  # SM-2 quality 0-5

    rec = LearningRecord.query.get_or_404(record_id)
    if rec.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403

    # SM-2 algorithm
    if quality < 3:
        rec.interval_days = 1
        rec.wrong_count += 1
    else:
        rec.correct_count += 1
        if rec.interval_days == 1:
            rec.interval_days = 6
        else:
            rec.interval_days = int(rec.interval_days * rec.ease_factor)

    rec.ease_factor = max(1.3, rec.ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    from datetime import timedelta
    rec.next_review = datetime.now(timezone.utc) + timedelta(days=rec.interval_days)
    rec.last_reviewed = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'message': '已记录', 'next_review_days': rec.interval_days})


def _record_dict(r):
    return {
        'id': r.id,
        'level': r.level,
        'algo': r.algo,
        'score': r.score,
        'accuracy': r.accuracy,
        'correct': r.correct_answers,
        'total': r.total_questions,
        'estimated_level': r.estimated_level,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    }
