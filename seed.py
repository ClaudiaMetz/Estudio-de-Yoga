"""Datos de ejemplo: 2 instructoras, 15 alumnas, una clase llena con lista de espera."""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.service import Studio

DB = os.environ.get("YOGA_DB", "yoga.db")
TZ = ZoneInfo(os.environ.get("STUDIO_TZ", "America/Mexico_City"))
if os.path.exists(DB):
    raise SystemExit(f"La base {DB} ya existe; seed.py no la sobrescribió. Elige otra ruta con YOGA_DB.")
e = Studio(DB)

nombres = ["Ana", "Beatriz", "Carla", "Daniela", "Elena", "Fernanda", "Gabriela", "Hilda", "Irene",
           "Julia", "Karla", "Lucía", "Marta", "Natalia", "Olivia"]
ids = []
for n in nombres:
    sid = e.crear_alumna(n, "5512345678")
    e.vender_paquete(sid, 10, "Andrea")
    ids.append(sid)

hoy = datetime.now(TZ).replace(hour=18, minute=0, second=0, microsecond=0)
llena = e.crear_clase("Vinyasa de la tarde", "Mariana", hoy + timedelta(days=1))
e.crear_clase("Yin al atardecer", "Paola", hoy + timedelta(days=2))
e.crear_clase("Hatha suave", "Mariana", (hoy + timedelta(days=3)).replace(hour=9))

for sid in ids[:12]:
    e.reservar(sid, llena)
for sid in ids[12:14]:
    e.reservar(sid, llena)  # entran a la lista de espera

port = os.environ.get("PORT", "5000")
print("Admin: http://localhost:%s/admin?key=%s\n" % (port, os.environ.get("ADMIN_KEY", "cambia-esto")))
for a in e.lista_alumnas():
    if a["name"] in ("Ana", "Marta", "Olivia"):
        print(f"{a['name']:8} -> http://localhost:{port}/a/{a['token']}")
print("\nAna: confirmada en la clase llena. Marta: lista de espera. Olivia: sin reservas.")
