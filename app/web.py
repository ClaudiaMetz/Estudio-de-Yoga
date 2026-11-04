import hmac
import os
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from flask import Flask, abort, redirect, render_template, request, session, url_for

from .service import ReglaError, Studio, enlace_whatsapp, parse

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def create_app(db_path=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    studio = Studio(db_path or os.environ.get("YOGA_DB", "yoga.db"),
                    cancel_hours=int(os.environ.get("CANCEL_HOURS", 6)),
                    offer_minutes=int(os.environ.get("OFFER_MINUTES", 30)))
    tz = ZoneInfo(os.environ.get("STUDIO_TZ", "America/Mexico_City"))
    admin_key = os.environ.get("ADMIN_KEY", "cambia-esto")

    @app.template_filter("fecha")
    def fecha(s):
        d = parse(s).astimezone(tz)
        return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}, {d:%H:%M}"

    @app.template_filter("hora")
    def hora(s):
        return f"{parse(s).astimezone(tz):%H:%M}"

    def volver(token, msg):
        return redirect(url_for("alumna", token=token) + "?" + urlencode({"msg": msg}))

    @app.get("/a/<token>")
    def alumna(token):
        sid = studio.alumna_id(token)
        if not sid:
            abort(404)
        return render_template("alumna.html", v=studio.vista_alumna(sid), token=token,
                               msg=request.args.get("msg"))

    @app.post("/a/<token>/<accion>/<int:class_id>")
    def accion(token, accion, class_id):
        sid = studio.alumna_id(token)
        if not sid:
            abort(404)
        try:
            if accion == "reservar":
                r = studio.reservar(sid, class_id)
                msg = ("Lugar reservado." if r["estado"] == "confirmada"
                       else f"La clase está llena. Quedaste en la lista de espera, lugar {r['posicion']}.")
            elif accion == "cancelar":
                r = studio.cancelar(sid, class_id)
                msg = {"devuelta": "Lugar cancelado. Te devolvimos la clase.",
                       "perdida": f"Lugar cancelado. Faltaban menos de {studio.cancel_hours} horas, la clase no se devuelve.",
                       "sin_cargo": "Saliste de la lista."}[r["resultado"]]
            elif accion == "confirmar":
                r = studio.confirmar_oferta(sid, class_id)
                msg = {"confirmada": "Lugar confirmado.",
                       "sin_saldo": "No te quedan clases para confirmar este lugar.",
                       "vencida": "La oferta venció. El lugar pasó a la siguiente alumna."}[r["estado"]]
            else:
                abort(404)
        except ReglaError as err:
            msg = str(err)
        return volver(token, msg)

    def admin_ok():
        return session.get("admin_authenticated") is True

    @app.post("/admin/login")
    def admin_login():
        if not hmac.compare_digest(request.form.get("key", ""), admin_key):
            abort(403)
        session.clear()
        session["admin_authenticated"] = True
        return redirect(url_for("admin"))

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("inicio"))

    @app.get("/admin")
    def admin():
        if not admin_ok():
            abort(403)
        return render_template("admin.html", alumnas=studio.lista_alumnas(),
                               msg=request.args.get("msg"), base=request.host_url.rstrip("/"))

    @app.post("/admin/paquete")
    def admin_paquete():
        if not admin_ok():
            abort(403)
        try:
            studio.vender_paquete(int(request.form["alumna"]), int(request.form.get("tamano") or 10), "Andrea")
            msg = "Paquete registrado."
        except (ReglaError, ValueError) as err:
            msg = str(err)
        return redirect(url_for("admin") + "?" + urlencode({"msg": msg}))

    @app.get("/")
    def inicio():
        token_demo = os.environ.get("DEMO_STUDENT_TOKEN")
        demo_url = url_for("alumna", token=token_demo) if token_demo else None
        return render_template("index.html", demo_url=demo_url)

    @app.get("/admin/clases")
    def admin_clases():
        if not admin_ok():
            abort(403)
        return render_template("admin_clases.html", d=studio.clases_admin(), msg=request.args.get("msg"))

    @app.post("/admin/clases/<int:class_id>/cancelar")
    def admin_cancelar_clase(class_id):
        if not admin_ok():
            abort(403)
        try:
            studio.cancelar_clase(class_id, request.form.get("mensaje"))
        except ReglaError as err:
            return redirect(url_for("admin_clases") + "?" + urlencode({"msg": str(err)}))
        return redirect(url_for("admin_avisos", class_id=class_id))

    @app.get("/admin/clases/<int:class_id>/avisos")
    def admin_avisos(class_id):
        if not admin_ok():
            abort(403)
        d = studio.avisos(class_id)
        if not d:
            abort(404)
        cl = d["clase"]
        for a in d["avisos"]:
            extra = ("Ya te devolvimos la clase a tu saldo." if a["estado_previo"] == "confirmada"
                     else "No se te cobró nada.")
            a["enlace"] = enlace_whatsapp(
                a["phone"], f"Hola {a['name']}, se canceló {cl['title']} del {fecha(cl['starts_at'])}. "
                            f"{cl['message']} {extra} Estudio de Andrea")
        pendientes = sum(1 for a in d["avisos"] if not a["sent_at"])
        return render_template("admin_avisos.html", d=d, class_id=class_id,
                               pendientes=pendientes)

    @app.post("/admin/clases/<int:class_id>/avisos/<int:student_id>/enviado")
    def admin_aviso_enviado(class_id, student_id):
        if not admin_ok():
            abort(403)
        studio.marcar_aviso(class_id, student_id)
        return redirect(url_for("admin_avisos", class_id=class_id))

    return app
