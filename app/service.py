"""Reglas de negocio de reservas. Spec: specs/001-reserva-cupo-lista-espera.md

Sin Flask ni HTML. Toda hora se guarda en UTC (ISO 8601).
"""
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

ACTIVAS = "('confirmada','espera','ofrecida')"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS students(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, token TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS classes(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, instructor TEXT NOT NULL,
  starts_at TEXT NOT NULL, capacity INTEGER NOT NULL DEFAULT 12);
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id INTEGER NOT NULL REFERENCES classes(id),
  student_id INTEGER NOT NULL REFERENCES students(id),
  status TEXT NOT NULL CHECK(status IN ('confirmada','espera','ofrecida','cancelada','vencida')),
  offer_expires_at TEXT, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reserva_activa ON bookings(class_id, student_id)
  WHERE status IN {ACTIVAS};
CREATE TABLE IF NOT EXISTS ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  kind TEXT NOT NULL, delta INTEGER NOT NULL, class_id INTEGER,
  reason TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS class_cancellations(
  class_id INTEGER PRIMARY KEY REFERENCES classes(id), message TEXT NOT NULL,
  actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS avisos(
  class_id INTEGER NOT NULL, student_id INTEGER NOT NULL, estado_previo TEXT NOT NULL,
  sent_at TEXT, PRIMARY KEY(class_id, student_id));
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger inmutable'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger inmutable'); END;
"""


class ReglaError(Exception):
    """Regla de negocio incumplida. El mensaje se muestra tal cual a la usuaria."""


def utcnow():
    return datetime.now(timezone.utc)


def iso(d):
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(s):
    return datetime.fromisoformat(s)


def enlace_whatsapp(phone, texto, pais="52"):
    d = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(d) == 10:
        d = pais + d
    return f"https://wa.me/{d}?text={quote(texto)}"


class Studio:
    def __init__(self, path, cancel_hours=6, offer_minutes=30):
        self.path = path
        self.cancel_hours = cancel_hours
        self.offer_minutes = offer_minutes
        con = sqlite3.connect(path)
        con.executescript(SCHEMA)
        con.close()

    @contextmanager
    def _tx(self):
        """Transacción exclusiva: serializa escrituras y evita sobreventa de cupos (R6)."""
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    # ---------- helpers internos ----------
    @staticmethod
    def _saldo(c, sid):
        return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE student_id=?", (sid,)).fetchone()[0]

    @staticmethod
    def _log(c, sid, kind, delta, class_id, reason, actor, now):
        c.execute(
            "INSERT INTO ledger(student_id,kind,delta,class_id,reason,actor,created_at) VALUES(?,?,?,?,?,?,?)",
            (sid, kind, delta, class_id, reason, actor, iso(now)))

    @staticmethod
    def _ocupados(c, class_id):
        return c.execute(
            "SELECT COUNT(*) FROM bookings WHERE class_id=? AND status IN ('confirmada','ofrecida')",
            (class_id,)).fetchone()[0]

    @staticmethod
    def _posicion(c, class_id, booking_id):
        return c.execute(
            "SELECT COUNT(*) FROM bookings WHERE class_id=? AND status='espera' AND id<=?",
            (class_id, booking_id)).fetchone()[0]

    def _promover(self, c, class_id, now):
        """Ofrece lugares libres a la lista de espera en orden FIFO, saltando a quien no tiene saldo (R5)."""
        clase = c.execute("SELECT capacity, starts_at FROM classes WHERE id=?", (class_id,)).fetchone()
        if not clase or parse(clase["starts_at"]) <= now:
            return
        cap = clase["capacity"]
        while self._ocupados(c, class_id) < cap:
            fila = c.execute(
                """SELECT b.id FROM bookings b
                   WHERE b.class_id=? AND b.status='espera'
                     AND (SELECT COALESCE(SUM(delta),0) FROM ledger WHERE student_id=b.student_id) >= 1
                   ORDER BY b.id LIMIT 1""", (class_id,)).fetchone()
            if not fila:
                break
            c.execute("UPDATE bookings SET status='ofrecida', offer_expires_at=? WHERE id=?",
                      (iso(now + timedelta(minutes=self.offer_minutes)), fila["id"]))

    def _vencer(self, c, now):
        filas = c.execute(
            """SELECT b.id, b.class_id FROM bookings b JOIN classes cl ON cl.id=b.class_id
               WHERE b.status='ofrecida' AND (b.offer_expires_at <= ? OR cl.starts_at <= ?)""",
            (iso(now), iso(now))).fetchall()
        for f in filas:
            c.execute("UPDATE bookings SET status='vencida', offer_expires_at=NULL WHERE id=?", (f["id"],))
        for class_id in {f["class_id"] for f in filas}:
            self._promover(c, class_id, now)

    # ---------- administración ----------
    def crear_alumna(self, name, phone=""):
        with self._tx() as c:
            return c.execute("INSERT INTO students(name,phone,token) VALUES(?,?,?)",
                             (name, phone, secrets.token_urlsafe(24))).lastrowid

    def crear_clase(self, title, instructor, starts_at, capacity=12):
        if capacity < 1:
            raise ReglaError("El cupo debe ser de al menos 1 lugar.")
        if starts_at.tzinfo is None or starts_at.utcoffset() is None:
            raise ReglaError("La fecha de la clase debe incluir una zona horaria.")
        with self._tx() as c:
            return c.execute("INSERT INTO classes(title,instructor,starts_at,capacity) VALUES(?,?,?,?)",
                             (title, instructor, iso(starts_at), capacity)).lastrowid

    def vender_paquete(self, student_id, size=10, actor="Andrea", now=None):
        now = now or utcnow()
        if size < 1:
            raise ReglaError("El paquete debe tener al menos 1 clase.")
        with self._tx() as c:
            self._log(c, student_id, "compra", size, None, f"Paquete de {size} clases", actor, now)

    def ajustar(self, student_id, delta, reason, actor, now=None):
        if not reason or not reason.strip():
            raise ReglaError("Todo ajuste de saldo necesita un motivo.")
        now = now or utcnow()
        with self._tx() as c:
            self._log(c, student_id, "ajuste", delta, None, reason.strip(), actor, now)

    def lista_alumnas(self):
        with self._tx() as c:
            return [dict(r) for r in c.execute(
                """SELECT s.id, s.name, s.phone, s.token,
                          (SELECT COALESCE(SUM(delta),0) FROM ledger WHERE student_id=s.id) AS saldo
                   FROM students s ORDER BY s.name""")]

    def alumna_id(self, token):
        with self._tx() as c:
            r = c.execute("SELECT id FROM students WHERE token=?", (token,)).fetchone()
            return r["id"] if r else None

    # ---------- consultas ----------
    def saldo(self, student_id):
        with self._tx() as c:
            return self._saldo(c, student_id)

    def historial(self, student_id, limite=50):
        with self._tx() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM ledger WHERE student_id=? ORDER BY id DESC LIMIT ?", (student_id, limite))]

    def conteo_estados(self, class_id):
        with self._tx() as c:
            return {r["status"]: r["n"] for r in c.execute(
                "SELECT status, COUNT(*) n FROM bookings WHERE class_id=? GROUP BY status", (class_id,))}

    def vista_alumna(self, student_id, now=None):
        now = now or utcnow()
        with self._tx() as c:
            self._vencer(c, now)
            s = c.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
            clases = []
            for cl in c.execute("SELECT * FROM classes WHERE starts_at > ? AND id NOT IN (SELECT class_id FROM class_cancellations) ORDER BY starts_at", (iso(now),)).fetchall():
                b = c.execute(
                    f"SELECT * FROM bookings WHERE class_id=? AND student_id=? AND status IN {ACTIVAS}",
                    (cl["id"], student_id)).fetchone()
                estado = b["status"] if b else "libre"
                libres = cl["capacity"] - self._ocupados(c, cl["id"])
                clases.append({
                    "id": cl["id"], "title": cl["title"], "instructor": cl["instructor"],
                    "starts_at": cl["starts_at"], "libres": max(libres, 0), "estado": estado,
                    "posicion": self._posicion(c, cl["id"], b["id"]) if estado == "espera" else None,
                    "oferta_hasta": b["offer_expires_at"] if estado == "ofrecida" else None})
            historial = [dict(r) for r in c.execute(
                "SELECT * FROM ledger WHERE student_id=? ORDER BY id DESC LIMIT 30", (student_id,))]
            return {"nombre": s["name"], "saldo": self._saldo(c, student_id),
                    "clases": clases, "historial": historial}

    # ---------- acciones de la alumna ----------
    def reservar(self, student_id, class_id, now=None):
        now = now or utcnow()
        with self._tx() as c:
            self._vencer(c, now)
            cl = c.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
            if not cl:
                raise ReglaError("Esa clase no existe.")
            if c.execute("SELECT 1 FROM class_cancellations WHERE class_id=?", (class_id,)).fetchone():
                raise ReglaError("Esa clase fue cancelada.")
            if parse(cl["starts_at"]) <= now:
                raise ReglaError("Esa clase ya empezó.")
            if c.execute(f"SELECT 1 FROM bookings WHERE class_id=? AND student_id=? AND status IN {ACTIVAS}",
                         (class_id, student_id)).fetchone():
                raise ReglaError("Ya tienes un lugar o estás en la lista de espera de esta clase.")
            if self._saldo(c, student_id) < 1:
                raise ReglaError("No te quedan clases. Pide un paquete nuevo a Andrea.")
            hay_lugar = self._ocupados(c, class_id) < cl["capacity"]
            bid = c.execute("INSERT INTO bookings(class_id,student_id,status,created_at) VALUES(?,?,?,?)",
                            (class_id, student_id, "confirmada" if hay_lugar else "espera", iso(now))).lastrowid
            if hay_lugar:
                self._log(c, student_id, "reserva", -1, class_id, f"Reserva: {cl['title']}", "alumna", now)
                return {"estado": "confirmada"}
            return {"estado": "espera", "posicion": self._posicion(c, class_id, bid)}

    def cancelar(self, student_id, class_id, now=None):
        now = now or utcnow()
        with self._tx() as c:
            self._vencer(c, now)
            b = c.execute(f"SELECT * FROM bookings WHERE class_id=? AND student_id=? AND status IN {ACTIVAS}",
                          (class_id, student_id)).fetchone()
            if not b:
                raise ReglaError("No tienes un lugar en esta clase.")
            cl = c.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
            if parse(cl["starts_at"]) <= now:
                raise ReglaError("Esa clase ya empezó.")
            c.execute("UPDATE bookings SET status='cancelada', offer_expires_at=NULL WHERE id=?", (b["id"],))
            resultado = "sin_cargo"
            if b["status"] == "confirmada":
                horas = (parse(cl["starts_at"]) - now).total_seconds() / 3600
                if horas >= self.cancel_hours:
                    self._log(c, student_id, "devolucion", 1, class_id,
                              f"Cancelación con al menos {self.cancel_hours} h de anticipación", "alumna", now)
                    resultado = "devuelta"
                else:
                    self._log(c, student_id, "perdida", 0, class_id,
                              f"Cancelación con menos de {self.cancel_hours} h: la clase no se devuelve", "alumna", now)
                    resultado = "perdida"
            self._promover(c, class_id, now)
            return {"resultado": resultado}

    def confirmar_oferta(self, student_id, class_id, now=None):
        now = now or utcnow()
        with self._tx() as c:
            oferta = c.execute(
                """SELECT b.id, b.offer_expires_at, cl.starts_at FROM bookings b
                   JOIN classes cl ON cl.id=b.class_id
                   WHERE b.class_id=? AND b.student_id=? AND b.status='ofrecida'""",
                (class_id, student_id)).fetchone()
            if oferta and (oferta["offer_expires_at"] <= iso(now) or parse(oferta["starts_at"]) <= now):
                c.execute("UPDATE bookings SET status='vencida', offer_expires_at=NULL WHERE id=?", (oferta["id"],))
                self._vencer(c, now)
                self._promover(c, class_id, now)
                return {"estado": "vencida"}
            self._vencer(c, now)
            b = c.execute("SELECT * FROM bookings WHERE class_id=? AND student_id=? AND status='ofrecida'",
                          (class_id, student_id)).fetchone()
            if not b:
                raise ReglaError("Esta oferta venció o ya no está disponible.")
            cl = c.execute("SELECT title FROM classes WHERE id=?", (class_id,)).fetchone()
            if self._saldo(c, student_id) < 1:
                c.execute("UPDATE bookings SET status='vencida', offer_expires_at=NULL WHERE id=?", (b["id"],))
                self._promover(c, class_id, now)
                return {"estado": "sin_saldo"}
            c.execute("UPDATE bookings SET status='confirmada', offer_expires_at=NULL WHERE id=?", (b["id"],))
            self._log(c, student_id, "reserva", -1, class_id, f"Lugar confirmado: {cl['title']}", "alumna", now)
            return {"estado": "confirmada"}
    # ---------- Spec 002: cancelar clase y avisar ----------
    def cancelar_clase(self, class_id, mensaje, actor="Andrea", now=None):
        now = now or utcnow()
        mensaje = (mensaje or "").strip()
        if not mensaje:
            raise ReglaError("Escribe un mensaje corto para las alumnas.")
        with self._tx() as c:
            cl = c.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
            if not cl:
                raise ReglaError("Esa clase no existe.")
            if c.execute("SELECT 1 FROM class_cancellations WHERE class_id=?", (class_id,)).fetchone():
                raise ReglaError("Esta clase ya estaba cancelada.")
            if parse(cl["starts_at"]) <= now:
                raise ReglaError("Esa clase ya empezó.")
            c.execute("INSERT INTO class_cancellations VALUES(?,?,?,?)", (class_id, mensaje, actor, iso(now)))
            filas = c.execute(f"SELECT * FROM bookings WHERE class_id=? AND status IN {ACTIVAS} ORDER BY id",
                              (class_id,)).fetchall()
            for b in filas:
                if b["status"] == "confirmada":
                    self._log(c, b["student_id"], "devolucion", 1, class_id,
                              f"Clase cancelada: {cl['title']}", actor, now)
                c.execute("UPDATE bookings SET status='cancelada', offer_expires_at=NULL WHERE id=?", (b["id"],))
                c.execute("INSERT INTO avisos(class_id,student_id,estado_previo) VALUES(?,?,?)",
                          (class_id, b["student_id"], b["status"]))
            return len(filas)

    def avisos(self, class_id):
        with self._tx() as c:
            cl = c.execute("""SELECT cl.title, cl.starts_at, k.message FROM classes cl
                              JOIN class_cancellations k ON k.class_id=cl.id WHERE cl.id=?""", (class_id,)).fetchone()
            if not cl:
                return None
            filas = [dict(r) for r in c.execute(
                """SELECT a.student_id, a.estado_previo, a.sent_at, s.name, s.phone FROM avisos a
                   JOIN students s ON s.id=a.student_id WHERE a.class_id=? ORDER BY s.name""", (class_id,))]
            return {"clase": dict(cl), "avisos": filas}

    def marcar_aviso(self, class_id, student_id, now=None):
        now = now or utcnow()
        with self._tx() as c:
            c.execute("UPDATE avisos SET sent_at=COALESCE(sent_at, ?) WHERE class_id=? AND student_id=?",
                      (iso(now), class_id, student_id))

    def clases_admin(self, now=None):
        now = now or utcnow()
        with self._tx() as c:
            proximas = [dict(r) for r in c.execute(
                """SELECT cl.*,
                     (SELECT COUNT(*) FROM bookings WHERE class_id=cl.id AND status IN ('confirmada','ofrecida')) AS ocupadas,
                     (SELECT COUNT(*) FROM bookings WHERE class_id=cl.id AND status='espera') AS espera
                   FROM classes cl WHERE starts_at > ? AND id NOT IN (SELECT class_id FROM class_cancellations)
                   ORDER BY starts_at""", (iso(now),))]
            canceladas = [dict(r) for r in c.execute(
                """SELECT cl.id, cl.title, cl.starts_at,
                     (SELECT COUNT(*) FROM avisos WHERE class_id=cl.id AND sent_at IS NULL) AS pendientes
                   FROM classes cl JOIN class_cancellations k ON k.class_id=cl.id ORDER BY k.created_at DESC""")]
            return {"proximas": proximas, "canceladas": canceladas}
