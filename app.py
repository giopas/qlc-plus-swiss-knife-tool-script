#!/usr/bin/env python3
"""
================================================================================
  QLC+ Swiss Knife — Flask / SPA Edition  (v1.0-dev)
================================================================================
  Run:
      pip install flask
      python3 app.py

  Opens http://localhost:5731 in your browser automatically.
  Press Ctrl+C in the terminal to shut down.
================================================================================
"""

import threading
import webbrowser
from flask import Flask

from routes.workspace_routes  import bp as workspace_bp
from routes.id_browser_routes import bp as id_browser_bp
from routes.setlist_routes    import bp as setlist_bp
from routes.dictionary_routes import bp as dictionary_bp
from routes.checklist_routes  import bp as checklist_bp
from routes.triggers_routes   import bp as triggers_bp
from routes.fixture_routes    import bp as fixture_bp

PORT = 5731


def create_app():
    app = Flask(__name__)

    app.register_blueprint(workspace_bp)
    app.register_blueprint(id_browser_bp)
    app.register_blueprint(setlist_bp)
    app.register_blueprint(dictionary_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(triggers_bp)
    app.register_blueprint(fixture_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    url = f'http://localhost:{PORT}'

    # Open the browser one second after the server starts
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n⚡  QLC+ Swiss Knife  →  {url}")
    print("   Press Ctrl+C to quit.\n")

    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
