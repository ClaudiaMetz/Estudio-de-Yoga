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
1. Sube el proyecto a GitHub.
2. En render.com: **New > Blueprint** y elige el repositorio (usa `render.yaml`). Render genera `ADMIN_KEY` solo: cópiala en **Environment**.
3. Abre la URL pública `https://estudio-yoga.onrender.com`. Entra con la clave desde la página de inicio.
Nota: el plan gratis tiene disco efímero y se duerme tras 15 minutos sin uso. Con `DEMO_SEED=1` se cargan datos de ejemplo al arrancar; es solo una demo, no guardes datos reales ahí. Para uso real: plan de pago con disco persistente en `YOGA_DB` y `DEMO_SEED` apagado.
