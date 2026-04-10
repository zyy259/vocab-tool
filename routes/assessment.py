"""Assessment API.

Two algorithms available:
  binary  – classic binary search over frequency rank
  irt     – Item Response Theory (2PL logistic model) adaptive testing

Session flow:
  POST /api/assess/start   → { session_id, question }
  POST /api/assess/answer  → { session_id, word_id, correct } → { question | result }
  GET  /api/assess/result/<session_id>
"""
import json
import math
import random
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, session as flask_session
from flask_login import current_user
from models import db, TestRecord, WordBank
from routes.wordbank import load_words

assess_bp = Blueprint('assess', __name__, url_prefix='/api/assess')

# In-memory session store (fine for single-process dev; swap for Redis in prod)
_sessions: dict[str, dict] = {}

# ──────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────

def _build_pool(level: str) -> list[dict]:
    """Build an ordered word pool.  primary→middle→high with global rank."""
    if level == 'all':
        pool = []
        offset = 0
        for lvl in ('primary', 'middle', 'high'):
            words = load_words(lvl)
            for w in words:
                w = dict(w)
                w['global_rank'] = offset + w.get('freq_rank', 1)
                pool.append(w)
            offset += len(words)
    else:
        pool = []
        for w in load_words(level):
            w = dict(w)
            w['global_rank'] = w.get('freq_rank', 1)
            pool.append(w)
    return pool


def _make_choices(word: dict, pool: list[dict], n: int = 4) -> list[dict]:
    """Return n multiple-choice options including the correct one."""
    others = random.sample([w for w in pool if w['word'] != word['word']], min(n - 1, len(pool) - 1))
    choices = others + [word]
    random.shuffle(choices)
    return [{'word': c['word'], 'meaning': c['meaning']} for c in choices]


def _question_payload(word: dict, pool: list[dict]) -> dict:
    return {
        'word_id': word.get('id') or word.get('global_rank'),
        'word': word['word'],
        'phonetic': word.get('phonetic', ''),
        'choices': _make_choices(word, pool),
        'level_hint': word.get('level', ''),
    }


# ──────────────────────────────────────────────────
# Binary Search Algorithm
# ──────────────────────────────────────────────────

def _binary_next(state: dict) -> dict | None:
    pool = state['pool']
    lo, hi = state['lo'], state['hi']
    if hi - lo <= 1 or state['answered'] >= state['max_q']:
        return None
    mid = (lo + hi) // 2
    # avoid repeating
    tried = state['tried']
    for delta in range(0, (hi - lo) // 2 + 1):
        for idx in (mid - delta, mid + delta):
            if 0 <= idx < len(pool) and idx not in tried:
                return pool[idx]
    return None


def _binary_update(state: dict, word_idx: int, correct: bool):
    pool = state['pool']
    state['tried'].add(word_idx)
    state['answered'] += 1
    if correct:
        state['correct'] += 1
        state['lo'] = max(state['lo'], word_idx + 1)
    else:
        state['hi'] = min(state['hi'], word_idx)


# ──────────────────────────────────────────────────
# IRT (2PL) Adaptive Algorithm
# ──────────────────────────────────────────────────

def _irt_prob(theta: float, b: float, a: float = 1.0) -> float:
    """P(correct | theta, a, b) using 2-PL logistic model."""
    return 1.0 / (1.0 + math.exp(-a * (theta - b)))


def _irt_information(theta: float, b: float, a: float = 1.0) -> float:
    p = _irt_prob(theta, a, b)
    return a * a * p * (1 - p)


def _b_for_word(w: dict, pool_size: int) -> float:
    """Map freq_rank to difficulty parameter b ∈ [-3, 3]."""
    rank = w.get('global_rank', w.get('freq_rank', 1))
    return -3.0 + 6.0 * rank / pool_size


def _irt_update_theta(theta: float, responses: list[tuple]) -> float:
    """Newton-Raphson MLE update of theta."""
    for _ in range(20):
        grad = 0.0
        hess = 0.0
        for b, a, correct in responses:
            p = _irt_prob(theta, b, a)
            grad += a * (correct - p)
            hess -= a * a * p * (1 - p)
        if abs(hess) < 1e-9:
            break
        step = -grad / hess
        theta += step
        if abs(step) < 1e-4:
            break
    return max(-4.0, min(4.0, theta))


def _irt_select_next(state: dict) -> dict | None:
    pool = state['pool']
    theta = state.get('theta', 0.0)
    tried = state['tried']
    if state['answered'] >= state['max_q']:
        return None
    # pick word with highest information
    best_info = -1
    best_word = None
    best_idx = None
    for idx, w in enumerate(pool):
        if idx in tried:
            continue
        b = _b_for_word(w, len(pool))
        info = _irt_information(theta, b)
        if info > best_info:
            best_info = info
            best_word = w
            best_idx = idx
    return best_word


# ──────────────────────────────────────────────────
# Score estimation
# ──────────────────────────────────────────────────

LEVEL_THRESHOLDS = [
    (505, '小学'),
    (1615, '初中'),
    (3481, '高中'),
    (5000, '大学及以上'),
]


def _estimate_level(score: int) -> str:
    for threshold, label in LEVEL_THRESHOLDS:
        if score <= threshold:
            return label
    return '大学及以上'


def _binary_score(state: dict) -> int:
    pool = state['pool']
    lo, hi = state['lo'], state['hi']
    mid = (lo + hi) // 2
    acc = state['correct'] / max(state['answered'], 1)
    # Estimate: words up to mid-point that user likely knows
    known = int(mid * acc * 1.2)
    return max(0, min(known, len(pool)))


def _irt_score(state: dict) -> int:
    pool = state['pool']
    theta = state.get('theta', 0.0)
    # theta in [-4,4]: map to [0, pool_size]
    norm = (theta + 4) / 8.0
    return int(norm * len(pool))


# ──────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────

@assess_bp.route('/start', methods=['POST'])
def start():
    data = request.get_json() or {}
    level = data.get('level', 'all')
    algo = data.get('algo', 'binary')
    max_q = int(data.get('max_q', 20))

    if level not in ('primary', 'middle', 'high', 'all'):
        return jsonify({'error': '无效词库'}), 400
    if algo not in ('binary', 'irt'):
        algo = 'binary'
    max_q = max(5, min(50, max_q))

    pool = _build_pool(level)
    if not pool:
        return jsonify({'error': '词库为空'}), 500

    sess_id = str(uuid.uuid4())
    state = {
        'pool': pool,
        'level': level,
        'algo': algo,
        'max_q': max_q,
        'answered': 0,
        'correct': 0,
        'tried': set(),
        'details': [],
        # binary
        'lo': 0,
        'hi': len(pool),
        # irt
        'theta': 0.0,
        'responses': [],
    }
    _sessions[sess_id] = state

    word = _get_next_word(state)
    if word is None:
        return jsonify({'error': '无法选词'}), 500

    idx = _word_idx(state, word)
    state['current_word'] = word
    state['current_idx'] = idx

    return jsonify({
        'session_id': sess_id,
        'total': max_q,
        'question': _question_payload(word, pool),
    })


@assess_bp.route('/answer', methods=['POST'])
def answer():
    data = request.get_json() or {}
    sess_id = data.get('session_id')
    chosen_meaning = data.get('chosen_meaning', '')  # meaning user selected
    correct_flag = data.get('correct')  # boolean override (for typed-answer mode)

    state = _sessions.get(sess_id)
    if state is None:
        return jsonify({'error': '会话不存在或已过期'}), 404

    word = state.get('current_word')
    if word is None:
        return jsonify({'error': '没有待回答的问题'}), 400

    # Determine correctness
    if correct_flag is not None:
        correct = bool(correct_flag)
    else:
        correct = (chosen_meaning.strip() == word['meaning'].strip())

    idx = state['current_idx']
    state['details'].append({
        'word': word['word'],
        'meaning': word['meaning'],
        'correct': correct,
        'rank': word.get('global_rank', idx),
    })

    # Update algorithm state
    if state['algo'] == 'irt':
        b = _b_for_word(word, len(state['pool']))
        state['responses'].append((b, 1.0, int(correct)))
        state['theta'] = _irt_update_theta(state['theta'], state['responses'])
        state['tried'].add(idx)
        state['answered'] += 1
        if correct:
            state['correct'] += 1
    else:
        _binary_update(state, idx, correct)

    # Next question or finish
    next_word = _get_next_word(state)
    if next_word is None:
        return _finish(sess_id, state)

    state['current_word'] = next_word
    state['current_idx'] = _word_idx(state, next_word)

    return jsonify({
        'correct': correct,
        'answered': state['answered'],
        'total': state['max_q'],
        'question': _question_payload(next_word, state['pool']),
    })


@assess_bp.route('/result/<sess_id>', methods=['GET'])
def result(sess_id):
    state = _sessions.get(sess_id)
    if state is None:
        return jsonify({'error': '会话不存在'}), 404
    if state.get('answered', 0) == 0:
        return jsonify({'error': '测评未完成'}), 400
    return jsonify(_build_result(sess_id, state))


def _finish(sess_id: str, state: dict):
    result = _build_result(sess_id, state)
    # Persist to DB
    _save_record(state, result)
    del _sessions[sess_id]
    return jsonify({'done': True, 'result': result})


def _build_result(sess_id: str, state: dict) -> dict:
    if state['algo'] == 'irt':
        score = _irt_score(state)
    else:
        score = _binary_score(state)

    accuracy = state['correct'] / max(state['answered'], 1)
    est_level = _estimate_level(score)

    return {
        'session_id': sess_id,
        'score': score,
        'accuracy': round(accuracy, 3),
        'correct': state['correct'],
        'answered': state['answered'],
        'estimated_level': est_level,
        'algo': state['algo'],
        'level': state['level'],
        'details': state['details'],
    }


def _save_record(state: dict, result: dict):
    user_id = current_user.id if current_user.is_authenticated else None
    record = TestRecord(
        user_id=user_id,
        level=state['level'],
        algo=state['algo'],
        score=result['score'],
        accuracy=result['accuracy'],
        total_questions=state['answered'],
        correct_answers=state['correct'],
        estimated_level=result['estimated_level'],
        details=json.dumps(result['details'], ensure_ascii=False),
    )
    db.session.add(record)
    db.session.commit()


def _get_next_word(state: dict) -> dict | None:
    if state['algo'] == 'irt':
        return _irt_select_next(state)
    else:
        return _binary_next(state)


def _word_idx(state: dict, word: dict) -> int:
    pool = state['pool']
    for i, w in enumerate(pool):
        if w['word'] == word['word']:
            return i
    return 0
