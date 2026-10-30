# Spec 001: Reservar clase con saldo verificable, cupo y lista de espera

Estado: revisada para entrega | Prioridad: la más alta

## 1. Definición del problema

**Quién:** las alumnas del estudio (usuaria principal) y Andrea (dueña).

**Dolor hoy**
- Las clases se cuentan con tarjetas de papel selladas a mano. Se pierden y generan discusiones sobre cuántas clases quedan, sin forma de comprobarlo.
- Las clases de la tarde tienen cupo de 12 y se llenan. Quien llega sin lugar se va molesta y no existe lista de espera.

**Qué resultado necesitamos**
Que una alumna pueda, desde su celular y sin contraseña, ver cuántas clases le quedan (con el detalle que lo explica), reservar un lugar y, si la clase está llena, quedar en una lista de espera que se resuelve sola cuando alguien cancela.

**Por qué es un solo feature:** el saldo y el cupo son inseparables. Reservar es el momento en que se descuenta una clase y se ocupa un lugar; sin ambos, ninguno de los dos dolores se resuelve.

**Fuera de alcance de esta spec:** avisos masivos por cambio o ausencia de instructora, asistencia, panel de estadísticas, videos, rutinas, tienda, facturación, pagos en línea.

## 2. Diseño de la solución

### 2.1 Flujo de la alumna
1. Entra con su enlace personal (`/a/<token>`). Ve su saldo y las próximas clases.
2. **Reservar:** si hay lugar, queda `confirmada` y se descuenta 1 clase. Si la clase está llena, queda en `espera` sin descuento y ve su posición.
3. **Cancelar:** con al menos `CANCEL_HOURS` de anticipación (por defecto 6) se le devuelve la clase. Con menos, no se devuelve.
4. **Oferta de lugar:** cuando se libera un lugar, la primera en espera con saldo pasa a `ofrecida` y tiene `OFFER_MINUTES` (por defecto 30) para confirmar. Al confirmar se descuenta 1 clase. Si no confirma antes del vencimiento (incluido el instante exacto del límite), o la clase ya empezó, pasa a `vencida`, pierde su lugar en la lista y la oferta pasa a la siguiente.

### 2.2 Estados de una reserva
`espera` → `ofrecida` → `confirmada`; cualquiera puede terminar en `cancelada`; `ofrecida` puede terminar en `vencida`.

### 2.3 Reglas
- R1. Saldo = suma de movimientos del libro (`ledger`). No hay columna de saldo.
- R2. Cada movimiento (compra, reserva, devolución, pérdida, ajuste) es un registro inmutable con fecha, motivo y quién lo hizo.
- R3. Ocupación de una clase = reservas `confirmada` + `ofrecida`. Nunca supera el cupo (12 por defecto, configurable por clase).
- R4. No se puede reservar con saldo 0, ni reservar dos veces la misma clase, ni reservar una clase que ya empezó.
- R5. La lista de espera es FIFO. Se salta (sin sacarla de la lista) a quien no tenga saldo al momento de ofrecer. No se ofrecen lugares para clases que ya empezaron.
- R6. Las operaciones son atómicas: dos reservas simultáneas no pueden ocupar el mismo último lugar.

### 2.4 Modelo de datos
`students(id, name, phone, token)`, `classes(id, title, instructor, starts_at, capacity)` con capacidad positiva, `bookings(id, class_id, student_id, status, offer_expires_at, created_at)` con índice único parcial sobre reservas activas, `ledger(id, student_id, kind, delta, class_id, reason, actor, created_at)` con triggers que impiden UPDATE y DELETE.

### 2.5 Interfaz
- Móvil primero, una sola pantalla para la alumna: saldo, clases próximas con una acción clara por clase, historial de movimientos.
- Textos y reglas visuales: ver `.claude/skills/marca-estudio/SKILL.md`.
- Acciones: `Reservar lugar`, `Cancelar lugar`, `Anotarme en la lista de espera`, `Salir de la lista`, `Confirmar lugar`.

## 3. Criterios de aceptación (verificables)

| # | Dado / Cuando / Entonces | Prueba |
|---|---|---|
| CA1 | **Dado** una alumna con 10 clases, **cuando** reserva una clase con lugar, **entonces** queda `confirmada`, su saldo es 9 y el historial muestra los movimientos `compra +10` y `reserva -1`, cuya suma coincide con el saldo. | `test_ca1_reserva_descuenta_y_saldo_sale_del_historial` |
| CA2 | **Dado** una clase con cupo 12 y 12 lugares ocupados, **cuando** la alumna 13 intenta reservar, **entonces** entra a `espera` en posición 1, su saldo no cambia y la 14 queda en posición 2. | `test_ca2_la_clase_13_va_a_lista_de_espera` |
| CA3 | **Dado** una reserva confirmada, **cuando** cancela con 6 horas o más de anticipación, **entonces** recupera la clase (`devolucion +1`); **cuando** cancela con menos, **entonces** no se devuelve y se registra `perdida` con motivo. | `test_ca3_cancelar_a_tiempo_devuelve_y_tarde_no` |
| CA4 | **Dado** una clase llena con alumnas en espera, **cuando** una confirmada cancela, **entonces** la primera en espera con saldo recibe una oferta de 30 minutos sin descuento; al confirmar queda `confirmada` con 1 clase menos; si la oferta vence, pasa a la siguiente; nunca se ofrece a quien tiene saldo 0. | `test_ca4_oferta_confirmacion_vencimiento_y_sin_saldo` |
| CA5 | **Dado** 20 alumnas reservando a la vez una clase de cupo 12, **entonces** exactamente 12 quedan `confirmada`, 8 en `espera` y el libro tiene exactamente 12 movimientos de reserva. | `test_ca5_reservas_simultaneas_respetan_el_cupo` |

Pruebas complementarias: reservar sin saldo, reservar dos veces y la inmutabilidad del libro.

## 4. Supuestos y decisiones

- Zona horaria por defecto `America/Mexico_City`, configurable con `STUDIO_TZ`; las fechas almacenadas se normalizan a UTC.
- El acceso de alumna es un enlace con token no adivinable (`secrets.token_urlsafe`). Revocar = regenerar token (pendiente de UI).
- La pérdida por cancelación tardía se registra con delta 0 y motivo, porque la clase ya se descontó al reservar. El movimiento documenta la decisión sin volver a descontar.
- Una oferta vencida saca a la alumna de la lista (vuelve a anotarse si quiere). Se eligió para que cada oferta tenga un plazo claro y el lugar pueda seguir avanzando en FIFO.
- El plazo termina en `offer_expires_at`: confirmar exactamente a esa hora ya es tarde. Una oferta tampoco puede confirmarse después de que empiece la clase.
- Los vencimientos se procesan al consultar o escribir (sin tareas en segundo plano), suficiente para este volumen.
