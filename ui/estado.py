"""Estado de la app en st.session_state + utilidades comunes de la interfaz (Persona 3).

Claves en st.session_state:
    banco, mercado, reloj   -> adaptadores (desde banco.fabrica; si fallan, fakes)
    modo                    -> BANCO_MODO efectivo
    politica                -> Politica vigente (cambia cuando el usuario responde "Siempre"/"Nunca")
    bandeja                 -> aprobaciones.bandeja.Bandeja
    avisos                  -> {clave: mensaje} de módulos aún no implementados
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

import streamlit as st

from core.modelos import Politica, Propuesta, Solicitud
from fakes import fakes


# --------------------------------------------------------------------------- utilidades


def intentar(fn: Callable[..., Any], *args: Any, respaldo: Callable[[], Any] | None = None, **kwargs: Any) -> Any:
    """Llama fn; si lanza NotImplementedError muestra quién la tiene pendiente y usa el respaldo."""
    try:
        return fn(*args, **kwargs)
    except NotImplementedError as e:
        aviso_pendiente(str(e))
        return respaldo() if respaldo else None


def aviso_pendiente(mensaje: str) -> None:
    st.warning(f"🚧 Pendiente: {mensaje or 'módulo sin implementar'} — se muestran datos de ejemplo.")


def pendiente_diseno() -> None:
    st.info("Persona 3: pendiente diseño final")


def etiqueta_fuente(fuente: str) -> None:
    if fuente == "simulado":
        st.caption("🧪 **Datos simulados**")


def fmt_cop(valor: Decimal) -> str:
    return "$" + f"{valor:,.0f}".replace(",", ".")


def fmt_usd(valor: Decimal, moneda: str = "USD") -> str:
    return f"{valor:,.2f} {moneda}"


# --------------------------------------------------------------------------- inicialización


def inicializar() -> None:
    """Crea el estado una sola vez por sesión."""
    if "banco" in st.session_state:
        return
    from banco import fabrica

    avisos: dict[str, str] = {}
    try:
        modo = fabrica.modo_actual()
        reloj = fabrica.obtener_reloj()
        mercado = fabrica.obtener_mercado()
        banco = fabrica.obtener_banco(reloj)
    except NotImplementedError as e:
        avisos["fabrica"] = f"{e}. Se usan fakes."
        modo = "fakes"
        reloj, mercado, banco = fakes.RelojFalso(), fakes.MercadoFalso(), fakes.BancoFalso()

    from motor.politica import cargar_politica

    try:
        politica = cargar_politica()
    except NotImplementedError as e:
        avisos["politica"] = str(e)
        politica = fakes.cargar_politica_ejemplo()

    from aprobaciones.bandeja import Bandeja

    st.session_state.update(
        banco=banco,
        mercado=mercado,
        reloj=reloj,
        modo=modo,
        politica=politica,
        bandeja=Bandeja(reloj, politica.vence_en_segundos, politica.max_interrupciones_dia),
        avisos=avisos,
    )


def politica() -> Politica:
    return st.session_state["politica"]


def propuesta() -> Propuesta:
    """Propuesta del motor (Persona 2); si aún no existe, la de ejemplo."""
    from motor.decisor import proponer

    s = st.session_state
    ingreso = fakes.cargar_ingreso_ejemplo()
    return intentar(
        proponer, ingreso, s["banco"], s["mercado"], s["reloj"], s["politica"],
        respaldo=fakes.cargar_propuesta_ejemplo,
    )


def solicitudes() -> list[Solicitud]:
    """Historial de la bandeja (Persona 3); si aún no existe, las de ejemplo."""
    return intentar(st.session_state["bandeja"].historial, respaldo=fakes.cargar_solicitudes_ejemplo)


def fuente_actual() -> str:
    saldos = st.session_state["banco"].saldos()
    return saldos[0].fuente if saldos else "simulado"
