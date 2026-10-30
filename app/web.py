import hmac
import os
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from flask import Flask, abort, redirect, render_template, request, url_for

from .service import ReglaError, Studio, parse

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def create_app(db_path=None):
    app = Flask(__name__)
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

    def admin_ok(key):
        return hmac.compare_digest(key or "", admin_key)

    @app.get("/admin")
    def admin():
        if not admin_ok(request.args.get("key")):
            abort(403)
        return render_template("admin.html", alumnas=studio.lista_alumnas(), key=request.args["key"],
                               msg=request.args.get("msg"), base=request.host_url.rstrip("/"))

    @app.post("/admin/paquete")
    def admin_paquete():
        key = request.form.get("key")
        if not admin_ok(key):
            abort(403)
        try:
            studio.vender_paquete(int(request.form["alumna"]), int(request.form.get("tamano") or 10), "Andrea")
            msg = "Paquete registrado."
        except (ReglaError, ValueError) as err:
            msg = str(err)
        return redirect(url_for("admin") + "?" + urlencode({"key": key, "msg": msg}))

    return app
