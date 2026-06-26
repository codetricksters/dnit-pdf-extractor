from a2wsgi import WSGIMiddleware
from dash import Dash
import dash_bootstrap_components as dbc

from .layout import build_layout
from .callbacks import register_callbacks


def create_dash_app() -> WSGIMiddleware:
    dash_app = Dash(
        __name__,
        requests_pathname_prefix="/dashboard/",
        external_stylesheets=[dbc.themes.DARKLY],
        suppress_callback_exceptions=True,
    )
    dash_app.layout = build_layout()
    register_callbacks(dash_app)
    return WSGIMiddleware(dash_app.server)
