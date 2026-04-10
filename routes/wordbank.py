"""Word bank API – serves words for assessment and learning."""
import json
import os
from flask import Blueprint, jsonify, request, current_app
from models import db, WordBank

wb_bp = Blueprint('wordbank', __name__, url_prefix='/api/words')

LEVEL_MAP = {'primary': '小学', 'middle': '初中', 'high': '高中'}


def load_words(level: str):
    """Return enabled words for a level, preferring DB over JSON file."""
    words = WordBank.query.filter_by(level=level, enabled=True).order_by(WordBank.freq_rank).all()
    if words:
        return [_word_dict(w) for w in words]
    # fallback: read from JSON seed
    data_dir = os.path.join(current_app.root_path, 'static', 'data')
    path = os.path.join(data_dir, f'{level}.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return []


def _word_dict(w):
    return {
        'id': w.id,
        'word': w.word,
        'meaning': w.meaning,
        'phonetic': w.phonetic,
        'level': w.level,
        'freq_rank': w.freq_rank,
    }


@wb_bp.route('/<level>', methods=['GET'])
def get_words(level):
    if level not in ('primary', 'middle', 'high', 'all'):
        return jsonify({'error': '无效词库'}), 400

    if level == 'all':
        result = []
        for lvl in ('primary', 'middle', 'high'):
            result.extend(load_words(lvl))
        return jsonify(result)

    return jsonify(load_words(level))


@wb_bp.route('/sample/<level>', methods=['GET'])
def sample_words(level):
    """Return a small random sample for quick preview."""
    import random
    n = int(request.args.get('n', 10))
    if level == 'all':
        words = []
        for lvl in ('primary', 'middle', 'high'):
            words.extend(load_words(lvl))
    else:
        words = load_words(level)
    sample = random.sample(words, min(n, len(words)))
    return jsonify(sample)
