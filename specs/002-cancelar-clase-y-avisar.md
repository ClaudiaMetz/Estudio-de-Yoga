# Spec 002: Cancelar una clase y avisar a las inscritas

Estado: revisada para entrega | Persona: Andrea Robles (docs/icp-persona.md) | Depende de: spec 001

## 1. Problema
Cuando una instructora se enferma, Andrea tiene que identificar a mano quién estaba inscrita, escribir a cada una por WhatsApp, y acordarse de devolverle la clase a cada alumna. Una clase de 12 inscritas le toma más de 20 minutos y siempre se queda alguien sin enterarse y llega a una clase que no existe. Hoy no hay forma de saber a quién ya avisó.

**Resultado deseado:** Andrea cancela la clase en un paso, el sistema devuelve las clases solo y le deja listos los mensajes de WhatsApp para enviar con un toque por alumna, con registro de quién ya fue avisada.

## 2. Diseño de la solución
1. En `/admin/clases` Andrea ve las clases próximas con su ocupación y escribe un mensaje corto ("Mariana está enferma").
2. Al pulsar `Cancelar clase y avisar`, en una sola transacción:
   - la clase queda cancelada y desaparece del horario de las alumnas;
   - cada reserva `confirmada` recibe una `devolucion +1` en el libro (aunque falten menos de 6 horas, porque la causa es del estudio);
   - las reservas en `espera` u `ofrecida` se cancelan sin cargo;
   - se crea un registro de aviso pendiente por cada inscrita.
3. Andrea llega a una pantalla con un botón `Enviar por WhatsApp` por alumna (enlace `wa.me` con el mensaje ya escrito: nombre, clase, fecha, motivo y qué pasó con su clase) y `Marcar como avisada`.
4. La pantalla muestra cuántos avisos faltan. Se puede volver a ella desde la lista de clases canceladas.

**Decisiones:** canal inicial WhatsApp con enlaces precargados (sin costo ni API); el envío es un toque de Andrea por alumna, no automático. Cancelar es irreversible. Una clase ya empezada no se puede cancelar.

## 3. Criterios de aceptación
| # | Criterio | Prueba |
|---|---|---|
| CA1 | Al cancelar una clase, todas las alumnas con reserva confirmada reciben `devolucion +1` con motivo y autor, aunque falten menos de 6 horas. | `test_ca1_cancelar_clase_devuelve_a_todas_las_confirmadas_aunque_falten_menos_de_6h` |
| CA2 | Tras cancelar, ninguna reserva queda activa, la clase no aparece a las alumnas y no se puede reservar. | `test_ca2_nadie_queda_con_reserva_y_la_clase_no_se_puede_reservar` |
| CA3 | Se genera exactamente un aviso por inscrita (confirmada, ofrecida o en espera) y el enlace de WhatsApp lleva el teléfono con código de país. | `test_ca3_un_aviso_por_inscrita_con_enlace_de_whatsapp` |
| CA4 | No se puede cancelar sin mensaje ni cancelar dos veces; en ambos casos los saldos no cambian. | `test_ca4_no_se_cancela_dos_veces_ni_sin_mensaje` |
| CA5 | Marcar un aviso guarda la fecha del primer envío (idempotente) y baja el contador de pendientes. | `test_ca5_marcar_aviso_registra_fecha_y_baja_los_pendientes` |

## 4. Métricas de éxito
| Métrica | Hoy (supuesto) | Meta a 30 días | Cómo se mide |
|---|---|---|---|
| **Principal:** % de inscritas avisadas dentro de 15 min de cancelar | ~50% | ≥ 90% | `avisos.sent_at` contra `class_cancellations.created_at` |
| Tiempo de Andrea para avisar una clase de 12 | 20+ min | < 3 min | Diferencia entre la cancelación y el último `sent_at` |
| Devoluciones correctas al cancelar una clase | manual, con errores | 100% | Movimientos `devolucion` de la clase contra reservas confirmadas |
| Alumnas que llegan a una clase cancelada | 1 o 2 al mes | 0 | Reporte de Andrea al cierre de mes |
| Cancelaciones de clase hechas desde la app | 0% | ≥ 80% | `class_cancellations` contra cancelaciones reportadas |

**Señal de que importa:** Andrea deja de escribir los avisos a mano y las alumnas dejan de preguntar por su saldo después de una cancelación.
