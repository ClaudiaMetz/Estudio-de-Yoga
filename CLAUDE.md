# Estudio de yoga de Andrea: instrucciones para el agente

## Qué estamos construyendo
Una web app mobile-first para un estudio de yoga pequeño (Andrea, 2 instructoras, ~100 alumnas).
Reemplaza las tarjetas de papel selladas a mano y resuelve cupos llenos sin lista de espera.
Las usuarias no son técnicas: usan celular y WhatsApp, no instalan apps ni recuerdan contraseñas.

## Cómo trabajamos (Spec Driven Development)
1. Toda funcionalidad nace de una spec en `specs/`. Si no hay spec, no se programa.
2. Si el resultado no cumple un criterio de aceptación, **se corrige primero la spec**, después el código.
3. Cada criterio de aceptación tiene al menos una prueba en `tests/` con su nombre (`test_ca1_...`).
4. Una tarea está terminada solo cuando `pytest` pasa en verde y los criterios están cubiertos.
5. Antes de cualquier trabajo visual, lee la skill `.claude/skills/marca-estudio/SKILL.md`.

## Stack (no cambiar sin actualizar la spec)
- Python 3.11+, Flask, SQLite (módulo estándar `sqlite3`), pytest.
- HTML con plantillas Jinja y CSS propio. Sin frameworks de frontend ni build.
- Comandos: `pip install -r requirements.txt`, `python seed.py`, `flask --app wsgi run`, `pytest -q`.

## Arquitectura
- `app/service.py`: **todas** las reglas de negocio. Sin Flask, sin HTML.
- `app/web.py`: rutas finas que llaman al servicio y traducen resultados a mensajes.
- `app/templates/`, `app/static/`: presentación. Prohibido poner reglas de negocio aquí.
- Hora: se guarda siempre en UTC (ISO 8601); se muestra en `STUDIO_TZ`.
- Toda función del servicio que depende de la hora recibe `now` opcional para poder probarla.

## Invariantes que nunca se rompen
- El saldo de una alumna es **siempre** la suma de `ledger.delta`. No existe una columna de saldo.
- `ledger` es inmutable (triggers lo imponen): nunca UPDATE ni DELETE, solo INSERT.
- Todo ajuste manual exige motivo.
- Una clase nunca tiene más reservas `confirmada` + `ofrecida` que su cupo, ni con peticiones simultáneas.
- Nunca se confirma un lugar a alguien sin saldo.
- Cada alumna solo ve sus propios datos; el acceso es por token largo en el enlace, sin contraseña.

## Fuera de alcance (rechaza estas peticiones)
Videos, rutinas, tienda en línea, facturación, pasarela de pagos, expediente de alumnas.

## Convenciones
- Interfaz y mensajes en español, tuteo, oraciones cortas, voz de la skill de marca.
- Código y nombres del dominio en español (`reservar`, `lista_espera`) para que Andrea y el equipo lo lean igual.
- Errores de regla de negocio: `ReglaError` con mensaje listo para mostrar a la usuaria.
- No agregar dependencias sin justificarlo en la spec.
