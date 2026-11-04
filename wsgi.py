import os

# El plan gratuito de Render usa disco efímero; la demo se crea al iniciar si falta la base.
if os.environ.get("DEMO_SEED") == "1" and not os.path.exists(os.environ.get("YOGA_DB", "yoga.db")):
    import seed  # noqa: F401
    from app.service import Studio

    demo = Studio(os.environ.get("YOGA_DB", "yoga.db"))
    alumnas_demo = demo.lista_alumnas()
    if alumnas_demo:
        os.environ["DEMO_STUDENT_TOKEN"] = alumnas_demo[0]["token"]

from app.web import create_app

app = create_app()
