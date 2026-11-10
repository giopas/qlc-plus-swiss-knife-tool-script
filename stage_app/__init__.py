"""QLC+ Stage Monitor: the companion app of QLC+ Swiss Knife (3.18.0).

At the gig it serves a Stage Monitor page that Swiss Knife exported, shows
whether QLC+ is ready for it, gives the address and a QR code for the band,
and prints the setlist.  It never edits a show or a page: Swiss Knife does.

The package lives in Swiss Knife's repository and ships as its own app.  It
may import only these modules of Swiss Knife (``tests/test_stage_app.py``
checks it), and nothing in Swiss Knife imports it:

* ``core.stage_monitor``: the page server and this computer's addresses;
* ``core.qr``: the QR code;
* ``core.pdf``: the PDF writer;
* ``core.workspace``: ``VERSION`` only (one release, one version).

Standard library only, plus ``pywebview`` for the window when it is there.
"""

ALLOWED_CORE = ("core.stage_monitor", "core.qr", "core.pdf", "core.workspace")
APP_NAME = "QLC+ Stage Monitor"
FILE_NAME = "QLC Stage Monitor"
