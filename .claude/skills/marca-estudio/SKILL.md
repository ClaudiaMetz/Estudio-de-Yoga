---
name: marca-estudio
description: Diseño de marca del estudio de yoga de Andrea. Úsala siempre que crees o modifiques cualquier pantalla, plantilla HTML, CSS, componente, mensaje de la interfaz, correo o texto de WhatsApp de esta aplicación, aunque la persona no mencione "marca" o "diseño". Define paleta, tipografía, forma, voz y reglas de accesibilidad.
---

# Marca del estudio

## Idea central
La marca nace de lo que la app reemplaza: **la tarjeta de papel con sellos**. El saldo de clases se muestra como un sello circular, lo más memorable de la interfaz. Todo lo demás es callado y claro. El estudio se siente tranquilo, nunca "wellness genérico": nada de beige con terracota, ni hojas, ni lotos, ni degradados.

## Color (tokens en `app/static/tokens.css`, única fuente de verdad)
| Token | Hex | Uso |
|---|---|---|
| `--anil` | `#1F2A44` | Texto, títulos, borde del sello |
| `--bruma` | `#E3ECE8` | Fondo de página (verde grisáceo frío) |
| `--papel` | `#FAFBF9` | Superficies y tarjetas |
| `--hibisco` | `#B23A5B` | Acción principal y sello |
| `--musgo` | `#3F6B58` | Confirmado, éxito |
| `--ambar` | `#8A5A0B` | Oferta de lugar y avisos que requieren acción |

Reglas: hibisco solo para una acción principal por tarjeta. Contraste mínimo 4.5:1 en texto. El color nunca es la única señal: acompáñalo siempre con texto.

## Tipografía
- Títulos y número del sello: **Young Serif** (fallback Georgia).
- Texto y botones: **Figtree** (fallback system-ui).
- Base 18 px en móvil, interlineado 1.5, líneas de máximo 60 caracteres.
- Sin mayúsculas sostenidas, sin etiquetas decorativas sobre los títulos, sin resaltar una sola palabra del título.

## Forma y componentes
- Esquinas: 14 px en tarjetas, 999 px en el sello y los botones tipo píldora.
- Sin sombras decorativas. La jerarquía se marca con borde de 2 px en `--anil` y espacio.
- Botones: alto mínimo 52 px, ancho completo en móvil, una acción principal por tarjeta.
- Foco visible siempre (anillo de 3 px en `--hibisco`). Respetar `prefers-reduced-motion`.
- Movimiento: ninguno automático. Solo respuesta a una acción (el sello cambia de número al reservar).

## Voz y textos
- Español, tuteo, oraciones cortas, verbos simples. Sin signos de exclamación ni emojis.
- Botones con el verbo exacto: `Reservar lugar`, `Cancelar lugar`, `Anotarme en la lista de espera`, `Salir de la lista`, `Confirmar lugar`. El aviso posterior usa el mismo verbo ("Lugar reservado.").
- Los errores dicen qué pasó y qué hacer; no piden perdón. Ej: "No te quedan clases. Pide un paquete nuevo a Andrea."
- Los estados vacíos invitan a actuar. Ej: "No hay clases próximas. Vuelve pronto."
- Mensajes de WhatsApp: saludo con nombre, un dato, una acción, firma "Estudio de Andrea".

## Checklist antes de entregar una pantalla
1. ¿Usa solo tokens, sin hex sueltos?
2. ¿El sello de saldo es lo más prominente?
3. ¿Hay una sola acción principal por tarjeta?
4. ¿Funciona a 360 px de ancho con el pulgar?
5. ¿Los textos siguen la voz y los verbos fijos?
6. ¿Quité un adorno antes de entregar?
