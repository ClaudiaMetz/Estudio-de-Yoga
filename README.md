# Estudio de yoga: reservas con saldo y lista de espera

Feature 1 del estudio de Andrea: saldo de clases verificable, cupo de 12 y lista de espera.
Metodología: Spec Driven Development.

| Qué | Dónde |
|---|---|
| Contexto persistente del agente | `CLAUDE.md` |
| Spec del feature | `specs/001-reserva-cupo-lista-espera.md` |
| Skill de marca | `.claude/skills/marca-estudio/SKILL.md` |
| Reglas de negocio | `app/service.py` |
| Pruebas (una por criterio de aceptación) | `tests/test_reservas.py` |

## Ejecutar en local
```bash
pip install -r requirements.txt
python seed.py            # crea yoga.db con datos de ejemplo e imprime los enlaces
flask --app wsgi run
pytest -q                 # 8 pruebas
```

`seed.py` se detiene si `yoga.db` ya existe; no sobrescribe datos. Para sembrar otra base,
indica una ruta nueva con `YOGA_DB`.

## Configuración (variables de entorno)
`YOGA_DB` (ruta de la base), `ADMIN_KEY` (clave de `/admin`; define una propia fuera del entorno local), `STUDIO_TZ`, `CANCEL_HOURS` (6), `OFFER_MINUTES` (30).

## Desplegar
Cualquier host con Python (Render, Railway, Fly.io): comando `gunicorn wsgi:app`, volumen persistente para `YOGA_DB`.
