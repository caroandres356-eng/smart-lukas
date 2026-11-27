"""Explicaciones en lenguaje simple (Persona 2).

Orden:
    1) Plantilla (siempre funciona, sin internet). Es el modo por defecto: IA_PROVEEDOR=plantillas.
    2) IA OPCIONAL (IA_PROVEEDOR=gemini|groq + IA_API_KEY en el .env) solo para redactar más natural.
       Pendiente: conectar IA_PROVEEDOR=deepseek con agente.deepseek_cliente.DeepSeekCliente
       (hoy "deepseek" cae a la plantilla).
    3) Si la IA falla, tarda más de 5 s o cambia algún número -> se usa la plantilla.

La IA NUNCA cambia montos: recibe el texto con los números ya calculados y formateados, y se
verifica que la respuesta tenga exactamente los mismos números que la plantilla.
"""

from __future__ import annotations

import os
import re
from decimal import Decimal

from dotenv import load_dotenv

from core.modelos import Propuesta, Veredicto
from motor.rutas import RUTA_A, fmt_cop, fmt_usd

load_dotenv()  # una sola vez al importar; no pisa variables que ya existan

TIMEOUT_IA_S = 5.0
PROVEEDORES_IA = ("gemini", "groq")
MODELO_POR_DEFECTO = {"gemini": "gemini-2.5-flash", "groq": "llama-3.3-70b-versatile"}

_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


# --------------------------------------------------------------------------- plantilla


def _minuscula_inicial(texto: str) -> str:
    return texto[:1].lower() + texto[1:] if texto else texto


def _describir(v: Veredicto) -> str:
    op = v.operacion
    accion = "la conversión" if op.tipo == "conversion" else "el pago"
    return f"{accion} de {fmt_usd(op.monto)} {op.desde} para {op.categoria}"


def plantilla(propuesta: Propuesta) -> str:
    ingreso = propuesta.ingreso.monto
    elegida = propuesta.ruta_elegida()

    impuestos = sum((v.operacion.monto for v in propuesta.veredictos if v.operacion.categoria == "impuestos"), Decimal(0))
    disponible = sum((o.monto for o in elegida.operaciones if o.desde == "USD"), Decimal(0))
    colchon = ingreso - impuestos - disponible

    frases = [f"Te llegaron {fmt_usd(ingreso)} {propuesta.ingreso.moneda}."]

    frases.append(
        f"Primero apartamos {fmt_usd(impuestos)} USD para impuestos (quedan guardados en USDT) y dejamos "
        f"{fmt_usd(colchon)} USD de colchón, así que quedaron {fmt_usd(disponible)} USD para pasar a pesos."
    )

    descartadas = [r for r in propuesta.rutas if not r.valida and r.nota]
    porque = (
        "es la que te deja más pesos y alcanza a tiempo para tus gastos fijos"
        if elegida.valida
        else "ninguna ruta alcanza a tiempo para tus gastos fijos y esta es la que más convierte de entrada"
    )
    frase_ruta = f"Elegimos «{elegida.nombre}» porque {porque}: {fmt_cop(elegida.cop_final)} pesos"
    if descartadas:
        detalles = "; ".join(f"«{r.nombre}» quedó por fuera porque {_minuscula_inicial(r.nota)}" for r in descartadas)
        frase_ruta += f" ({detalles})"
    frases.append(frase_ruta + ".")

    autos = [v for v in propuesta.veredictos if v.estado == "auto"]
    pendientes = [v for v in propuesta.veredictos if v.estado == "requiere_aprobacion"]
    bloqueadas = [v for v in propuesta.veredictos if v.estado == "bloqueada"]

    if autos:
        n = len(autos)
        frases.append(
            "Una operación se hace sola porque está dentro de tus reglas."
            if n == 1
            else f"{n} operaciones se hacen solas, cada una en su fecha, porque están dentro de tus reglas."
        )

    partes = []
    if pendientes:
        partes.append(
            "Necesita tu aprobación "
            + "; también ".join(f"{_describir(v)}, porque {_minuscula_inicial(v.motivo)}" for v in pendientes)
        )
    if bloqueadas:
        texto = "; tampoco ".join(f"{_describir(v)}, porque {_minuscula_inicial(v.motivo)}" for v in bloqueadas)
        partes.append(("y no haremos " if partes else "No haremos ") + texto)
    frases.append((", ".join(partes) + ".") if partes else "No hace falta que apruebes nada.")

    ahorro = propuesta.ahorro_cop
    if propuesta.elegida == RUTA_A or ahorro == 0:
        frases.append("Comparado con convertir todo hoy, quedas con los mismos pesos.")
    elif ahorro > 0:
        frases.append(f"Frente a convertir todo hoy, ganas {fmt_cop(ahorro)} pesos más.")
    else:
        frases.append(
            f"Son {fmt_cop(-ahorro)} pesos menos que convertir todo hoy, pero «{RUTA_A}» no cumple tus gastos fijos."
        )

    return " ".join(frases)


# --------------------------------------------------------------------------- IA opcional


def numeros(texto: str) -> list[str]:
    """Los números tal como aparecen en el texto (ej. '1.000', '454,55', '5')."""
    return _NUMERO.findall(texto)


def _mismos_numeros(original: str, reescrito: str) -> bool:
    return sorted(set(numeros(original))) == sorted(set(numeros(reescrito)))


def _instrucciones(texto: str) -> str:
    return (
        "Reescribe este mensaje para una persona freelancer en Colombia, en español natural, cercano y claro, "
        "en 4 a 6 frases y tuteando. REGLA ESTRICTA: no cambies, no redondees, no quites y no agregues ningún número; "
        "copia cada número exactamente como aparece (con sus puntos y comas). No agregues datos nuevos. "
        "Responde solo con el mensaje reescrito.\n\n"
        f"Mensaje:\n{texto}"
    )


def _pedir_a_ia(proveedor: str, llave: str, texto: str) -> str:
    import httpx

    modelo = os.getenv("IA_MODELO") or MODELO_POR_DEFECTO[proveedor]
    if proveedor == "gemini":
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
            headers={"x-goog-api-key": llave},
            json={"contents": [{"parts": [{"text": _instrucciones(texto)}]}], "generationConfig": {"temperature": 0.3}},
            timeout=TIMEOUT_IA_S,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {llave}"},
        json={"model": modelo, "temperature": 0.3, "messages": [{"role": "user", "content": _instrucciones(texto)}]},
        timeout=TIMEOUT_IA_S,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def explicar(propuesta: Propuesta) -> str:
    """Texto en lenguaje simple: qué llegó, qué se reservó, qué ruta y por qué, qué necesita aprobación y cuánto se gana."""
    texto = plantilla(propuesta)
    proveedor = (os.getenv("IA_PROVEEDOR") or "plantillas").strip().lower()
    llave = (os.getenv("IA_API_KEY") or "").strip()
    if proveedor not in PROVEEDORES_IA or not llave:
        return texto
    try:
        reescrito = _pedir_a_ia(proveedor, llave, texto)
    except Exception:  # red, timeout, cuota, respuesta rara: la plantilla siempre funciona
        return texto
    return reescrito if reescrito and _mismos_numeros(texto, reescrito) else texto
