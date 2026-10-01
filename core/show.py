"""core/show.py — the show in progress (WORKPLAN Phase 2.6).

Opening a ``.qxw`` makes it the *show in progress*: the one working copy in
memory (``workspace._state['qxw_root']``) that every tool reads and changes.
Each change is a **step** in the history — which tool, what it did, the
Doctor after it — with a snapshot of the show *before* the step, so any step
can be undone (with every step after it).  Nothing is written until
**Save as new file**: the show goes to a new ``.qxw`` and one report lists
every step.  The original file is never touched.

Two ways a tool records a step:

* :func:`adopt` — the tool built a whole new tree (Doctor fixes, Rig Reducer,
  Look Builder, Stage & Meshes, Brightness …): the step keeps the old tree and
  the new one becomes the show.
* :func:`touch` — the tool edits the show in place (Trigger Manager, VC
  Editor, Setlist …).  Call it *before* the edit; consecutive edits by the
  same tool are one step ("VC Editor — 7 edits") until another tool acts.

Snapshots are the serialised show (``qxw_io.qxw_bytes``), so a step costs one
file's worth of memory; the history keeps at most :data:`MAX_STEPS`.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from typing import Callable, Optional

from core import qxw_io

MAX_STEPS = 60

TOOL_TITLES = {
    'doctor': 'Workspace Doctor', 'reducer': 'Rig Reducer', 'looks': 'Look Builder',
    'stage': 'Stage & Meshes', 'brightness': 'Brightness', 'setlist': 'Setlist',
    'triggers': 'Trigger Manager', 'vceditor': 'VC Editor', 'porter': 'Function Porter',
    'merger': 'QXW Merger', 'dictionary': 'Dictionary', 'fixtures': 'Fixtures',
    'quickstart': 'Quick Start', 'idbrowser': 'ID Browser',
}

_show: dict = {}


def _ws():
    from core import workspace
    return workspace


def reset(source_name: str = '', source_path: str = '') -> None:
    """A show was opened: it becomes the show in progress, with no steps."""
    _show.clear()
    from core import recipe
    recipe.reset(source_path)
    _show.update({
        'source_name': source_name or 'workspace.qxw',
        'source_path': source_path or '',
        'steps': [],
        'saved_upto': 0,        # steps[:saved_upto] are in the last saved file
        'saved_name': '',
        'saved_path': '',
        'version': 0,           # bumps on every change (for caches)
        'opened': time.time(),
    })


def active() -> bool:
    return bool(_show) and bool(_ws()._state.get('loaded'))


def version() -> int:
    return _show.get('version', 0)


def _root():
    return _ws()._state.get('qxw_root')


def _snapshot() -> bytes:
    return qxw_io.qxw_bytes(_root())


def _set_root(root: ET.Element) -> None:
    """Make *root* the show (namespaced like a file QLC+ wrote) and re-parse."""
    ws = _ws()
    if root.tag == 'Workspace':
        root = qxw_io.qualify_ns(root)
    ws._state['qxw_root'] = root
    ws._state['xml_tree'] = ET.ElementTree(root)
    ws.vc_undo_clear()          # the VC Editor's own undo refers to the old tree
    ws.reparse_after_vc_edit()


def _close_open_steps(except_tool: str = '') -> None:
    for s in _show.get('steps', []):
        if s.get('open') and s['tool'] != except_tool:
            s['open'] = False


def _push(step: dict) -> dict:
    _show['redo'] = None                    # a new change ends what redo could bring back
    steps = _show['steps']
    step['n'] = len(steps) + 1
    step['time'] = time.time()
    steps.append(step)
    if len(steps) > MAX_STEPS:              # forget the oldest snapshot, keep the line
        steps[len(steps) - MAX_STEPS - 1]['before'] = None
    _show['version'] += 1
    return step


def adopt(tool: str, title: str, new_root: ET.Element, report: str = '',
          detail: str = '') -> dict:
    """The tool made a new tree: record a step and make it the show."""
    if not active():
        raise RuntimeError('No show open.')
    _close_open_steps()
    step = _push({'tool': tool, 'title': title, 'detail': detail, 'report': report,
                  'edits': 1, 'open': False, 'before': _snapshot()})
    _set_root(new_root)
    return public_step(step)


def touch(tool: str, title: str = '', detail: str = '') -> dict:
    """Call before *tool* edits the show in place.  Consecutive edits by the
    same tool are counted in one step."""
    if not active():
        raise RuntimeError('No show open.')
    steps = _show['steps']
    last = steps[-1] if steps else None
    if last and last.get('open') and last['tool'] == tool and len(steps) > _show['saved_upto']:
        _show['redo'] = None
        last['edits'] += 1
        if title:
            last['title'] = title
        if detail:
            last['detail'] = detail
        _show['version'] += 1
        return public_step(last)
    _close_open_steps()
    step = _push({'tool': tool, 'title': title or f'{TOOL_TITLES.get(tool, tool)} edits',
                  'detail': detail, 'report': '', 'edits': 1, 'open': True,
                  'before': _snapshot()})
    return public_step(step)


def cancel_touch() -> None:
    """The edit announced by :func:`touch` failed and changed nothing."""
    steps = _show.get('steps') or []
    if not steps:
        return
    last = steps[-1]
    if last['edits'] > 1:
        last['edits'] -= 1
    else:
        steps.pop()
    _show['version'] += 1


def close_step() -> None:
    """End the current in-place step (the next edit starts a new one)."""
    _close_open_steps()


def undo_to(n: int) -> dict:
    """Go back to how the show was before step *n* (steps n… are dropped)."""
    steps = _show.get('steps') or []
    if not 1 <= n <= len(steps):
        raise ValueError('No such step.')
    snap = steps[n - 1].get('before')
    if snap is None:
        raise ValueError('This step is too old to undo (the history keeps '
                         f'the last {MAX_STEPS} steps).')
    _show['redo'] = {'steps': steps[n - 1:], 'after': _snapshot(),
                     'saved_upto': _show['saved_upto']}
    _set_root(qxw_io.loads_qxw(snap))
    del steps[n - 1:]
    for s in steps:
        s['open'] = False
    _show['saved_upto'] = min(_show['saved_upto'], len(steps))
    _show['version'] += 1
    return status()


def redo() -> dict:
    """Put back the steps the last undo took away (until the show changes again)."""
    r = _show.get('redo')
    if not r:
        raise ValueError('Nothing to redo.')
    _set_root(qxw_io.loads_qxw(r['after']))
    _show['steps'].extend(r['steps'])
    for s in _show['steps']:
        s['open'] = False
    _show['saved_upto'] = r['saved_upto']
    _show['redo'] = None
    _show['version'] += 1
    return status()


def undo_last() -> dict:
    steps = _show.get('steps') or []
    if not steps:
        raise ValueError('Nothing to undo.')
    return undo_to(len(steps))


def public_step(s: dict) -> dict:
    return {'n': s['n'], 'tool': s['tool'], 'tool_title': TOOL_TITLES.get(s['tool'], s['tool']),
            'title': s['title'], 'detail': s.get('detail', ''), 'edits': s.get('edits', 1),
            'time': s['time'], 'undoable': s.get('before') is not None,
            'saved': s['n'] <= _show.get('saved_upto', 0),
            'doctor': s.get('doctor')}


def changed_tools() -> dict:
    """{tool: steps not yet saved} — the orange dots in the sidebar."""
    out: dict = {}
    for s in _show.get('steps', [])[_show.get('saved_upto', 0):]:
        out[s['tool']] = out.get(s['tool'], 0) + 1
    return out


def status() -> dict:
    if not active():
        return {'active': False}
    steps = _show['steps']
    unsaved = len(steps) - _show['saved_upto']
    return {
        'active': True,
        'source_name': _show['source_name'],
        'saved_name': _show['saved_name'],
        'steps': len(steps),
        'unsaved': unsaved,
        'changed_tools': changed_tools(),
        'version': _show['version'],
        'suggested_name': suggested_name(),
        'redo': len((_show.get('redo') or {}).get('steps') or []),
    }


def history() -> list:
    return [public_step(s) for s in _show.get('steps', [])]


def set_doctor(summary: Optional[dict]) -> None:
    """Remember the Doctor's counts on the latest step (shown in History)."""
    steps = _show.get('steps') or []
    if steps and summary is not None:
        steps[-1]['doctor'] = summary


def suggested_name() -> str:
    base = _show.get('saved_name') or _show.get('source_name') or 'workspace.qxw'
    return os.path.basename(qxw_io.next_version_name(base))


def show_bytes() -> bytes:
    import copy
    root = copy.deepcopy(_root())
    ET.indent(root, space=' ')
    return qxw_io.qxw_bytes(root)


def _changes(step: dict, nxt: Optional[dict]) -> list:
    """What an in-place step changed: its snapshot against the next step's
    (or the show now)."""
    from core import show_diff
    try:
        if not step.get('before'):
            return []
        after = nxt.get('before') if nxt else _snapshot()
        if not after:
            return []
        return show_diff.summarise(qxw_io.loads_qxw(step['before']), qxw_io.loads_qxw(after))
    except Exception:  # noqa: BLE001 — the report is best-effort here
        return []


def report_path(qxw_path: str) -> str:
    return os.path.splitext(qxw_path)[0] + '_report.txt'


def report(out_name: str = '') -> str:
    """One report for the saved file: every step, oldest first."""
    from core.workspace import VERSION
    lines = [f'QLC+ Swiss Knife {VERSION} — show report',
             f'Opened:  {_show.get("source_name", "")}',
             f'Saved as: {out_name}' if out_name else '',
             time.strftime('Date:    %Y-%m-%d %H:%M'), '']
    steps = _show.get('steps', [])
    if not steps:
        lines.append('No changes.')
    for i, s in enumerate(steps):
        head = f'Step {s["n"]} — {TOOL_TITLES.get(s["tool"], s["tool"])}: {s["title"]}'
        if s.get('edits', 1) > 1:
            head += f' ({s["edits"]} edits)'
        lines += [head, '-' * min(len(head), 78)]
        if s.get('detail'):
            lines.append(s['detail'])
        if not s.get('report'):
            lines += _changes(s, steps[i + 1] if i + 1 < len(steps) else None)
        if s.get('doctor'):
            d = s['doctor']
            lines.append(f'Doctor after this step: {d.get("error", 0)} errors, '
                         f'{d.get("warning", 0)} warnings')
        if s.get('report'):
            lines += ['', s['report'].rstrip()]
        lines.append('')
    return '\n'.join(l for l in lines if l is not None) + '\n'


def mark_saved(qxw_path: str) -> dict:
    """The show was written to *qxw_path*: write the report next to it and
    remember that every step so far is saved."""
    out_name = os.path.basename(qxw_path)
    rp = ''
    folder = os.path.dirname(os.path.abspath(qxw_path)) if qxw_path else ''
    if qxw_path and os.path.isdir(folder):
        rp = report_path(os.path.abspath(qxw_path))
        qxw_io.write_bytes(report(out_name).encode('utf-8'), rp,
                           protect=[_show.get('source_path')])
    rc = ''
    if qxw_path and os.path.isfile(qxw_path):
        try:
            from core import recipe
            rc = recipe.write_next_to(os.path.abspath(qxw_path))
        except Exception:  # noqa: BLE001 — the recipe is a bonus, the save stands
            rc = ''
    _show['saved_upto'] = len(_show['steps'])
    _show['redo'] = None                    # the saved file is the new reference
    _show['saved_name'] = out_name
    _show['saved_path'] = qxw_path or ''
    _close_open_steps()
    _show['version'] += 1
    return {'report_path': rp, 'report_name': os.path.basename(rp) if rp else '',
            'recipe_path': rc, 'recipe_name': os.path.basename(rc) if rc else ''}


def save(path: str) -> dict:
    """Write the show to *path* (never the opened file) + its report."""
    ws = _ws()
    qxw_io.write_bytes(show_bytes(), path, protect=[_show.get('source_path'),
                                                    ws._state.get('path')])
    out = mark_saved(path)
    out['path'] = path
    return out


def apply_result(tool: str, title: str, new_root, report_text: str = '',
                 detail: str = '', doctor: Optional[Callable] = None) -> dict:
    """Helper for routes: adopt *new_root* and attach the Doctor's counts."""
    step = adopt(tool, title, new_root, report_text, detail)
    if doctor is not None:
        try:
            set_doctor(doctor())
        except Exception:  # noqa: BLE001 — the counts are informative only
            pass
    return {'step': step, 'show': status()}
