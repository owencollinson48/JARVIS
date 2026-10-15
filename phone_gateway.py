"""Separate, webhook-only listener. Reverse proxy this port, never the desktop application."""
from flask import request,abort
from jarvis import create_app


def create_gateway(database=None):
    app=create_app(database)
    @app.before_request
    def public_routes_only():
        if not request.path.startswith('/telephony/'):abort(404)
    return app

if __name__=='__main__':create_gateway().run(host='127.0.0.1',port=5002,debug=False,threaded=True)
