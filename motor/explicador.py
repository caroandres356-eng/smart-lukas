"""Explicaciones en lenguaje simple (Persona 2).

Orden:
    1) Plantillas (siempre funcionan, sin internet). Es el modo por defecto: IA_PROVEEDOR=plantillas.
    2) IA OPCIONAL (ej. IA_PROVEEDOR=deepseek usando agente.deepseek_cliente.DeepSeekCliente + DEEPSEEK_API_KEY)
       solo para redactar más bonito.
    3) Si la IA falla, tarda o devuelve algo raro -> se usa la plantilla.

La IA NUNCA cambia montos: recibe los números ya calculados y formateados, y se valida
que cada número del texto de la IA exista en la propuesta; si no, se descarta y se usa la plantilla.

Debe responder: qué hizo, por qué y con cuánta plata. Ejemplo:
    "Convertimos hoy 480 USD para pagar arriendo e internet. Los otros 170 USD quedaron
     en USDT rindiendo y se convierten en 4 tramos semanales. Guardamos 150 USD para
     impuestos y 200 USD de colchón. Ahorraste $6.949 pesos frente a convertir todo el día 1.
     La conversión de 450 USD necesita tu aprobación porque supera tu límite de 300 USD."
"""

from __future__ import annotations

from core.modelos import Propuesta

P2 = "Persona 2 (motor): "


def explicar(propuesta: Propuesta) -> str:
    raise NotImplementedError(P2 + "explicar")
