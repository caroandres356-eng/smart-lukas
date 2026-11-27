"""Bandeja de aprobaciones (Persona 3): control humano antes de operaciones importantes.

REGLAS DE LA BANDEJA:

| Situación                                         | Resultado                                                    |
|---------------------------------------------------|--------------------------------------------------------------|
| crear_solicitud y quedan interrupciones hoy       | "pendiente", vence = ahora + vence_en_segundos               |
| crear_solicitud y ya hubo max_interrupciones_dia  | "en_cola" (no interrumpe al usuario)                         |
| Nadie responde antes de `vence`                   | "vencida" y NO se ejecuta nada                               |
| Respuesta "solo_esta_vez"                         | "aprobada", devuelve None (la política no cambia)            |
| Respuesta "siempre"                               | "aprobada" + CambioPolitica("permitir_hasta", tipo, categoria,|
|                                                   |   monto redondeado a la siguiente centena: 450 -> 500)       |
| Respuesta "nunca"                                 | "rechazada" + CambioPolitica("bloquear", tipo, categoria)    |
| Responder una solicitud vencida o ya resuelta     | ValueError                                                   |

Notas:
- Las interrupciones se cuentan por día (reloj.hoy()); al cambiar de día el contador vuelve a 0
  y las "en_cola" pueden promoverse a "pendiente" (con un nuevo `vence`).
- La bandeja NO ejecuta operaciones ni modifica la política: devuelve el CambioPolitica
  y quien la usa llama a motor.politica.aplicar_cambio y a banco.ejecutar.
- Nota (Idea 3 · AP2): al aprobar una solicitud, puede asociarse un mandato firmado
  mediante `banco.mandatos` (llenando `Solicitud.mandato_id` / `Operacion.mandato_firma`).
- Todo con el Reloj inyectado (nunca datetime.now()), para poder probar el vencimiento.
"""

from __future__ import annotations

from typing import Literal

from core.modelos import CambioPolitica, Operacion, Solicitud
from core.puertos import Reloj

P3 = "Persona 3 (bandeja): "

Respuesta = Literal["solo_esta_vez", "siempre", "nunca"]


class Bandeja:
    def __init__(self, reloj: Reloj, vence_en_segundos: int, max_interrupciones_dia: int) -> None:
        self.reloj = reloj
        self.vence_en_segundos = vence_en_segundos
        self.max_interrupciones_dia = max_interrupciones_dia

    def crear_solicitud(self, op: Operacion, motivo: str) -> Solicitud:
        raise NotImplementedError(P3 + "Bandeja.crear_solicitud")

    def responder(self, solicitud_id: str, respuesta: Respuesta) -> CambioPolitica | None:
        raise NotImplementedError(P3 + "Bandeja.responder")

    def actualizar_vencidas(self) -> list[Solicitud]:
        """Marca como "vencida" toda pendiente con vence <= reloj.ahora(). Devuelve las que vencieron."""
        raise NotImplementedError(P3 + "Bandeja.actualizar_vencidas")

    def pendientes(self) -> list[Solicitud]:
        raise NotImplementedError(P3 + "Bandeja.pendientes")

    def en_cola(self) -> list[Solicitud]:
        raise NotImplementedError(P3 + "Bandeja.en_cola")

    def historial(self) -> list[Solicitud]:
        """Todas las solicitudes (cualquier estado), en orden de creación."""
        raise NotImplementedError(P3 + "Bandeja.historial")
