"""routes/showbook_routes.py — Show Book API."""

import os
import re
from flask import Blueprint, jsonify, request, Response
from core import showbook

bp = Blueprint('showbook', __name__, url_prefix='/api/showbook')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


@bp.route('/preview', methods=['POST'])
def preview():
    """Generate the document model for UI preview.

    Body (JSON):
        sections : list[str] | null   — which sections (null = all)
        qxf_dir  : str | null         — optional QXF directory
    """
    data = request.get_json(force=True) or {}
    sections = data.get('sections') or None
    qxf_dir = (data.get('qxf_dir') or '').strip() or None

    try:
        doc = showbook.generate(sections=sections, qxf_dir=qxf_dir)
        return jsonify({'ok': True, 'document': doc})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/export/pdf', methods=['POST'])
def export_pdf():
    """Generate and download the Show Book as PDF.

    Body (JSON):
        sections : list[str] | null
        qxf_dir  : str | null
        filename : str | null  — suggested download filename
    """
    data = request.get_json(force=True) or {}
    sections = data.get('sections') or None
    qxf_dir = (data.get('qxf_dir') or '').strip() or None
    filename = (data.get('filename') or '').strip()

    try:
        doc = showbook.generate(sections=sections, qxf_dir=qxf_dir)
        pdf_bytes = showbook.export_pdf(doc)

        if not filename:
            safe_name = re.sub(r'[^\w\s-]', '', doc.get('show_name', 'showbook'))
            safe_name = safe_name.strip().replace(' ', '_') or 'showbook'
            filename = f"{safe_name}_ShowBook.pdf"

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'X-Suggested-Filename': filename,
                'Access-Control-Expose-Headers': 'X-Suggested-Filename',
            },
        )
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/export/csv', methods=['POST'])
def export_csv():
    """Generate and download the Show Book as a ZIP of CSVs.

    Body (JSON):
        sections : list[str] | null
        qxf_dir  : str | null
        filename : str | null
    """
    data = request.get_json(force=True) or {}
    sections = data.get('sections') or None
    qxf_dir = (data.get('qxf_dir') or '').strip() or None
    filename = (data.get('filename') or '').strip()

    try:
        doc = showbook.generate(sections=sections, qxf_dir=qxf_dir)
        zip_bytes = showbook.export_csv(doc)

        if not filename:
            safe_name = re.sub(r'[^\w\s-]', '', doc.get('show_name', 'showbook'))
            safe_name = safe_name.strip().replace(' ', '_') or 'showbook'
            filename = f"{safe_name}_ShowBook.zip"

        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'X-Suggested-Filename': filename,
                'Access-Control-Expose-Headers': 'X-Suggested-Filename',
            },
        )
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/sections')
def list_sections():
    """Return the list of available section names."""
    return jsonify({'sections': list(showbook.ALL_SECTIONS)})
