import os

# El plan gratuito de Render usa disco efímero; la demo se crea al iniciar si falta la base.
if os.environ.get("DEMO_SEED") == "1" and not os.path.exists(os.environ.get("YOGA_DB", "yoga.db")):
    import seed  # noqa: F401

from app.web import create_app

app = create_app()
