"""Pruebas de specs/002-cancelar-clase-y-avisar.md"""
from datetime import datetime, timedelta, timezone

import pytest

from app.service import ReglaError, Studio, enlace_whatsapp
from app.web import create_app

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def e(tmp_path):
    return Studio(str(tmp_path / "t.db"))


def alumna(e, n):
    sid = e.crear_alumna(n, "55 1234 5678")
    e.vender_paquete(sid, 10, "test", NOW)
    return sid


def escenario(e, horas=2):
    """Cupo 2: A y B confirmadas, C en espera. La clase empieza en `horas`."""
    cid = e.crear_clase("Vinyasa", "Mariana", NOW + timedelta(hours=horas), 2)
    a, b, c = alumna(e, "Ana"), alumna(e, "Beto"), alumna(e, "Caro")
    for s in (a, b, c):
        e.reservar(s, cid, NOW)
    return cid, a, b, c


def test_ca1_cancelar_clase_devuelve_a_todas_las_confirmadas_aunque_falten_menos_de_6h(e):
    cid, a, b, c = escenario(e, horas=2)
    assert e.saldo(a) == 9
    e.cancelar_clase(cid, "Mariana está enferma", "Andrea", NOW)
    assert e.saldo(a) == 10 and e.saldo(b) == 10
    mov = e.historial(a)[0]
    assert (mov["kind"], mov["delta"], mov["actor"]) == ("devolucion", 1, "Andrea")
    assert "cancelada" in mov["reason"]


def test_ca2_nadie_queda_con_reserva_y_la_clase_no_se_puede_reservar(e):
    cid, a, b, c = escenario(e)
    e.cancelar_clase(cid, "Mariana está enferma", now=NOW)
    assert e.conteo_estados(cid) == {"cancelada": 3}
    assert e.saldo(c) == 10
    assert all(x["id"] != cid for x in e.vista_alumna(a, NOW)["clases"])
    with pytest.raises(ReglaError):
        e.reservar(alumna(e, "Dani"), cid, NOW)


def test_ca3_un_aviso_por_inscrita_con_enlace_de_whatsapp(e):
    cid, a, b, c = escenario(e)
    assert e.cancelar_clase(cid, "Mariana está enferma", now=NOW) == 3
    d = e.avisos(cid)
    assert sorted(x["name"] for x in d["avisos"]) == ["Ana", "Beto", "Caro"]
    assert {x["name"]: x["estado_previo"] for x in d["avisos"]}["Caro"] == "espera"
    link = enlace_whatsapp("55 1234 5678", "Hola Ana")
    assert link == "https://wa.me/525512345678?text=Hola%20Ana"


def test_ca4_no_se_cancela_dos_veces_ni_sin_mensaje(e):
    cid, a, b, c = escenario(e)
    with pytest.raises(ReglaError):
        e.cancelar_clase(cid, "  ", now=NOW)
    assert e.saldo(a) == 9
    e.cancelar_clase(cid, "Mariana está enferma", now=NOW)
    with pytest.raises(ReglaError):
        e.cancelar_clase(cid, "otra vez", now=NOW)
    assert e.saldo(a) == 10


def test_ca5_marcar_aviso_registra_fecha_y_baja_los_pendientes(e):
    cid, a, b, c = escenario(e)
    e.cancelar_clase(cid, "Mariana está enferma", now=NOW)
    e.marcar_aviso(cid, a, NOW + timedelta(minutes=3))
    e.marcar_aviso(cid, a, NOW + timedelta(minutes=9))  # idempotente: conserva la primera fecha
    enviados = [x for x in e.avisos(cid)["avisos"] if x["sent_at"]]
    assert len(enviados) == 1 and enviados[0]["sent_at"].startswith("2026-11-02T12:03")
    assert e.clases_admin(NOW)["canceladas"][0]["pendientes"] == 2


def test_panel_autentica_por_post_y_no_exhibe_clave_en_la_url(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "clave-de-prueba")
    monkeypatch.setenv("FLASK_SECRET_KEY", "secreto-de-sesion-para-pruebas")
    monkeypatch.setenv("DEMO_STUDENT_TOKEN", "alumna-demo")
    app = create_app(str(tmp_path / "web.db"))
    app.testing = True
    client = app.test_client()

    assert b"/a/alumna-demo" in client.get("/").data
    assert client.get("/admin").status_code == 403
    assert client.post("/admin/login", data={"key": "incorrecta"}).status_code == 403
    respuesta = client.post("/admin/login", data={"key": "clave-de-prueba"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/admin"
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/clases").status_code == 200
    assert client.post("/admin/logout").headers["Location"] == "/"
    assert client.get("/admin").status_code == 403
