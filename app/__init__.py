"""ZR Fabrication — iron store bill ledger."""

from pathlib import Path

from flask import Flask

from app.db import init_db, seed_if_empty


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "zr-fabrication-ledger"
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    app.config["DATABASE"] = db_path or str(data_dir / "ledger.db")

    from app import routes

    app.register_blueprint(routes.bp)

    with app.app_context():
        init_db()
        seed_if_empty()

    return app
