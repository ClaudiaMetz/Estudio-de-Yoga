# Estudio de yoga: reservas con saldo y lista de espera

Feature 1 del estudio de Andrea: saldo de clases verificable, cupo de 12 y lista de espera.
Metodología: Spec Driven Development.

| Qué | Dónde |
|---|---|
| Contexto persistente del agente | `CLAUDE.md` |
| Spec del feature | `specs/001-reserva-cupo-lista-espera.md` |
| Spec de cancelación y avisos | `specs/002-cancelar-clase-y-avisar.md` |
| Skill de marca | `.claude/skills/marca-estudio/SKILL.md` |
| ICP y persona (con hipótesis identificadas) | `docs/icp-persona.md` |
| Reglas de negocio | `app/service.py` |
| Pruebas | `tests/test_reservas.py`, `tests/test_avisos.py` |

## Ejecutar en local
```bash
pip install -r requirements.txt
python seed.py            # crea yoga.db con datos de ejemplo e imprime los enlaces
flask --app wsgi run
pytest -q                 # 14 pruebas
```

`seed.py` se detiene si `yoga.db` ya existe; no sobrescribe datos. Para sembrar otra base,
indica una ruta nueva con `YOGA_DB`.

## Configuración (variables de entorno)
`YOGA_DB` (ruta de la base), `ADMIN_KEY` (clave de `/admin`; define una propia fuera del entorno local), `FLASK_SECRET_KEY` (firma la sesión del panel), `STUDIO_TZ`, `CANCEL_HOURS` (6), `OFFER_MINUTES` (30).

## Desplegar
Cualquier host con Python (Render, Railway, Fly.io): comando `gunicorn wsgi:app`, volumen persistente para `YOGA_DB`.

## Feature 2: cancelar clase y avisar
Spec: `specs/002-cancelar-clase-y-avisar.md`. ICP: `docs/icp-persona.md`. Tras iniciar sesión, el panel de clases está en `/admin/clases`.

## Producción en Render
1. Repo: <https://github.com/ClaudiaMetz/Estudio-de-Yoga>.
2. En Render, crea el Blueprint desde `render.yaml`. Render genera `ADMIN_KEY` y `FLASK_SECRET_KEY`; consulta `ADMIN_KEY` en **Environment** para entrar al panel.
3. URL pública: <https://estudio-yoga-ohk2.onrender.com>. La página inicial ofrece un enlace de demo de alumna.
Nota: el plan gratis se duerme tras 15 minutos sin uso y pierde la base local al reiniciarse. `DEMO_SEED=1` vuelve a crear datos ficticios al iniciar; no guardes datos reales ahí. Para uso real: plan de pago con disco persistente en `YOGA_DB` y `DEMO_SEED` apagado.
