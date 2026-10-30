"""Una prueba por criterio de aceptación de specs/001-reserva-cupo-lista-espera.md"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.service import ReglaError, Studio

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def e(tmp_path):
    return Studio(str(tmp_path / "t.db"))


def alumna(e, nombre="Ana", saldo=10):
    sid = e.crear_alumna(nombre, "5550000")
    if saldo:
        e.vender_paquete(sid, saldo, "test", NOW)
    return sid


def clase(e, horas=48, cap=12):
    return e.crear_clase("Vinyasa", "Mariana", NOW + timedelta(hours=horas), cap)


def estado(e, sid, cid, now=NOW):
    return next(c for c in e.vista_alumna(sid, now)["clases"] if c["id"] == cid)


def test_ca1_reserva_descuenta_y_saldo_sale_del_historial(e):
    sid, cid = alumna(e), clase(e)
    assert e.reservar(sid, cid, NOW)["estado"] == "confirmada"
    assert e.saldo(sid) == 9
    hist = e.historial(sid)
    assert sorted((h["kind"], h["delta"]) for h in hist) == [("compra", 10), ("reserva", -1)]
    assert sum(h["delta"] for h in hist) == e.saldo(sid)


def test_ca2_la_clase_13_va_a_lista_de_espera(e):
    cid = clase(e)
    for i in range(12):
        assert e.reservar(alumna(e, f"A{i}"), cid, NOW)["estado"] == "confirmada"
    a13, a14 = alumna(e, "A13"), alumna(e, "A14")
    r13, r14 = e.reservar(a13, cid, NOW), e.reservar(a14, cid, NOW)
    assert (r13["estado"], r13["posicion"]) == ("espera", 1)
    assert (r14["estado"], r14["posicion"]) == ("espera", 2)
    assert e.saldo(a13) == 10
    assert e.conteo_estados(cid) == {"confirmada": 12, "espera": 2}


def test_ca3_cancelar_a_tiempo_devuelve_y_tarde_no(e):
    sid = alumna(e)
    lejos, cerca = clase(e, horas=48), clase(e, horas=3)
    e.reservar(sid, lejos, NOW)
    e.reservar(sid, cerca, NOW)
    assert e.saldo(sid) == 8
    assert e.cancelar(sid, lejos, NOW)["resultado"] == "devuelta"
    assert e.saldo(sid) == 9
    assert e.cancelar(sid, cerca, NOW)["resultado"] == "perdida"
    assert e.saldo(sid) == 9
    assert e.historial(sid)[0]["kind"] == "perdida"
    assert e.historial(sid)[0]["reason"]


def test_ca4_oferta_confirmacion_vencimiento_y_sin_saldo(e):
    cid = clase(e, cap=2)
    a, b, c, d, siguiente = (alumna(e, n) for n in "ABCDE")
    e.reservar(a, cid, NOW)
    e.reservar(b, cid, NOW)
    e.reservar(c, cid, NOW)
    e.reservar(d, cid, NOW)
    e.reservar(siguiente, cid, NOW)

    # al cancelar A, la primera en espera (C) recibe oferta sin descuento
    e.cancelar(a, cid, NOW)
    assert estado(e, c, cid)["estado"] == "ofrecida"
    assert e.saldo(c) == 10
    assert estado(e, d, cid)["estado"] == "espera"

    # C confirma dentro del plazo: queda inscrita y se descuenta
    assert e.confirmar_oferta(c, cid, NOW + timedelta(minutes=10))["estado"] == "confirmada"
    assert e.saldo(c) == 9

    # B cancela; D recibe oferta y no responde: la oferta vence
    e.cancelar(b, cid, NOW)
    assert estado(e, d, cid)["estado"] == "ofrecida"
    tarde = NOW + timedelta(minutes=30)
    assert estado(e, d, cid, tarde)["estado"] == "libre"
    assert estado(e, siguiente, cid, tarde)["estado"] == "ofrecida"
    with pytest.raises(ReglaError):
        e.confirmar_oferta(d, cid, tarde)

    # nunca se ofrece a quien tiene saldo 0: se salta a la siguiente
    cid2 = clase(e, cap=1)
    x, y, z = alumna(e, "X"), alumna(e, "Y"), alumna(e, "Z")
    e.reservar(x, cid2, NOW)
    e.reservar(y, cid2, NOW)
    e.reservar(z, cid2, NOW)
    e.ajustar(y, -10, "prueba: sin saldo", "test", NOW)
    e.cancelar(x, cid2, NOW)
    assert estado(e, y, cid2)["estado"] == "espera"
    assert estado(e, z, cid2)["estado"] == "ofrecida"


def test_oferta_no_se_confirma_despues_de_iniciar_la_clase(e):
    e.offer_minutes = 120
    cid = clase(e, horas=1, cap=1)
    titular, en_espera = alumna(e, "Titular"), alumna(e, "Espera")
    e.reservar(titular, cid, NOW)
    e.reservar(en_espera, cid, NOW)
    e.cancelar(titular, cid, NOW)

    con_la_clase_iniciada = NOW + timedelta(hours=1)
    assert e.confirmar_oferta(en_espera, cid, con_la_clase_iniciada)["estado"] == "vencida"
    assert e.conteo_estados(cid) == {"cancelada": 1, "vencida": 1}


def test_ca5_reservas_simultaneas_respetan_el_cupo(e):
    cid = clase(e, cap=12)
    ids = [alumna(e, f"S{i}") for i in range(20)]
    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(lambda s: e.reservar(s, cid, NOW), ids))
    assert e.conteo_estados(cid) == {"confirmada": 12, "espera": 8}
    reservas = sum(1 for s in ids for h in e.historial(s) if h["kind"] == "reserva")
    assert reservas == 12


def test_no_se_reserva_sin_saldo_ni_dos_veces(e):
    cid = clase(e)
    sin_saldo = alumna(e, "Sin", saldo=0)
    with pytest.raises(ReglaError):
        e.reservar(sin_saldo, cid, NOW)
    sid = alumna(e)
    e.reservar(sid, cid, NOW)
    with pytest.raises(ReglaError):
        e.reservar(sid, cid, NOW)
    assert e.saldo(sid) == 9


def test_el_libro_de_movimientos_es_inmutable(e):
    sid = alumna(e)
    con = sqlite3.connect(e.path)
    with pytest.raises(sqlite3.Error):
        con.execute("UPDATE ledger SET delta=99 WHERE student_id=?", (sid,))
    with pytest.raises(sqlite3.Error):
        con.execute("DELETE FROM ledger WHERE student_id=?", (sid,))
    with pytest.raises(ReglaError):
        e.ajustar(sid, 1, "  ", "test", NOW)
