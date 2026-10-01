"""routes/compare_routes.py — Compare (WORKPLAN 2.8): the show in progress
against another .qxw, by what they do (core.compare).  Read-only."""

import copy
import os
import re

from flask import Blueprint, jsonify, request

from core import compare as cmp, qxw_io
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('compare', __name__, url_prefix='/api/compare')
_last: dict = {}


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


@bp.route('/run', methods=['POST'])
def run():
    """Body: {path: other .qxw}.  Returns the comparison and its report."""
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'Open a show first (📂 Open… top right).'}), 400
    other = str((request.get_json(force=True) or {}).get('path') or '').strip()
    if not other or not other.lower().endswith('.qxw') or not os.path.isfile(other):
        return jsonify({'error': 'Pick the other .qxw file.'}), 400
    try:
        a = qxw_io.strip_ns(copy.deepcopy(root))
        b = qxw_io.strip_ns(qxw_io.loads_qxw(open(other, 'rb').read()))
        defs = dict(_defs(path))
        for k, v in _defs(other).items():
            defs.setdefault(k, v)
        res = cmp.compare(a, b, defs)
        bname = os.path.basename(other)
        text = cmp.report(res, f"{name} (the show in progress)", bname)
        _last.clear()
        _last.update({'report': text, 'a': name, 'b': bname})
        return jsonify({'result': res, 'report': text, 'sections': cmp.SECTIONS,
                        'a': name, 'b': bname})
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/report')
def last_report():
    if not _last:
        return jsonify({'error': 'Nothing compared yet.'}), 400
    return jsonify(_last)
