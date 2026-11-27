"""Banco simulado (Persona 1). Cumple core.puertos.BancoPort.

Imita a Belo mientras no tengamos acceso a su API/MCP.

Fórmula de conversión del día d (USD o USDT -> COP):
    COP = monto × TRM_d × (1 − spread)          spread simulado de Belo = 0.01
Conversión USD -> USDT: 1 a 1 (sin spread, simplificación de la demo).

Rendimiento del USDT:
    cada día: saldo_usdt *= (1 + tasa_anual / 365)   tasa simulada = 0.10
    y se registra un Movimiento tipo "rendimiento".

Idempotencia:
    ejecutar(op) guarda op.id en banco.registro.Registro (SQLite).
    Si el id ya se ejecutó -> Resultado(ok=False, mensaje="Operación ya ejecutada (id repetido)")
    y NO cambia saldos ni movimientos.
    Si no hay saldo suficiente -> ok=False con el motivo.

Todos los Saldo/Cotizacion/Rendimiento devuelven fuente="simulado".
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from banco.mandatos import FirmadorMandatosAP2, MandatoPort, PaymentMandate
from banco.mercado import MercadoSocrata
from banco.registro import Registro
from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo
from core.puertos import MercadoPort, Reloj

_ORDEN_MONEDAS: tuple[Moneda, ...] = ("USD", "COP", "USDT")
_SPREAD_COP = Decimal("0.01")
_TASA_ANUAL_USDT = Decimal("0.10")
_CENTAVOS = Decimal("0.01")
_PRECISION_RENDIMIENTO = Decimal("0.0001")


def _copiar_decimal(valor: Decimal) -> Decimal:
    """Normaliza montos a Decimal sin pasar nunca por float."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def _cotizacion_en_serie(serie: list[Cotizacion], hoy: date) -> Cotizacion:
    """Devuelve la cotización vigente para `hoy` desde una serie ordenada o sin ordenar."""
    if not serie:
        raise ValueError("No hay cotizaciones disponibles para USD->COP")
    ordenadas = sorted(serie, key=lambda c: c.fecha)
    elegida = ordenadas[0]
    for cot in ordenadas:
        if cot.fecha <= hoy:
            elegida = cot
        else:
            break
    return elegida


class BancoSimulado:
    """Adaptador de banco simulado con saldos en memoria e idempotencia persistente."""

    def __init__(
        self,
        reloj: Reloj,
        mercado: MercadoPort | None = None,
        registro: Registro | None = None,
        saldos_iniciales: dict[Moneda, Decimal] | None = None,
        firmador: MandatoPort | None = None,
        exigir_mandato: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self.reloj = reloj
        self.mercado: MercadoPort = mercado if mercado is not None else MercadoSocrata()
        self.registro: Registro = registro if registro is not None else Registro(":memory:")
        self.firmador: MandatoPort = firmador if firmador is not None else FirmadorMandatosAP2()
        self.exigir_mandato: bool = exigir_mandato

        if saldos_iniciales is None:
            self._saldos: dict[Moneda, Decimal] = {
                "USD": Decimal("1000.00"),
                "COP": Decimal("0.00"),
                "USDT": Decimal("0.00"),
            }
        else:
            self._saldos = {moneda: Decimal("0.00") for moneda in _ORDEN_MONEDAS}
            for moneda, monto in saldos_iniciales.items():
                self._saldos[moneda] = _copiar_decimal(monto)

        self._movimientos: list[Movimiento] = []

    def saldos(self) -> list[Saldo]:
        """Saldos actuales en orden USD, COP, USDT."""
        with self._lock:
            return [
                Saldo(moneda=moneda, monto=self._saldos[moneda], fuente="simulado")
                for moneda in _ORDEN_MONEDAS
            ]

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        """Cotización vigente para el día `self.reloj.hoy()`."""
        hoy = self.reloj.hoy()
        if (desde == "USD" and hacia == "USDT") or (desde == "USDT" and hacia == "USD"):
            return Cotizacion(
                desde=desde,
                hacia=hacia,
                tasa=Decimal("1"),
                spread=Decimal("0"),
                fecha=hoy,
                fuente="simulado",
            )

        if desde in ("USD", "USDT") and hacia == "COP":
            if hasattr(self.mercado, "cotizacion_para_fecha"):
                cot = self.mercado.cotizacion_para_fecha(hoy, "USD", "COP")
            else:
                serie = self.mercado.historico("USD", "COP", 30)
                cot = _cotizacion_en_serie(serie, hoy)
            return Cotizacion(
                desde=desde,
                hacia="COP",
                tasa=cot.tasa,
                spread=_SPREAD_COP,
                fecha=hoy,
                fuente="simulado",
            )

        raise ValueError(f"Par de cotización no soportado: {desde}->{hacia}")

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        """USDT -> tasa_anual 0.10. Otras monedas -> 0."""
        tasa = _TASA_ANUAL_USDT if moneda == "USDT" else Decimal("0")
        return Rendimiento(moneda=moneda, tasa_anual=tasa, fuente="simulado")

    def ejecutar(self, op: Operacion, *, mandato: PaymentMandate | None = None) -> Resultado:
        """Serializa cada operación para proteger saldo, idempotencia y movimientos."""
        with self._lock:
            return self._ejecutar_bajo_lock(op, mandato=mandato)

    def _ejecutar_bajo_lock(
        self, op: Operacion, *, mandato: PaymentMandate | None = None
    ) -> Resultado:
        """Aplica la conversión o pago. Idempotente por `op.id` y verifica mandato AP2 si aplica."""
        if self.registro.ya_ejecutada(op.id):
            return Resultado(
                operacion_id=op.id,
                ok=False,
                mensaje="Operación ya ejecutada (id repetido)",
            )

        mandato_id: str | None = None
        mandato_verificado: bool | None = None
        if self.exigir_mandato and mandato is None:
            return self._fallar(
                op,
                "Mandato AP2 requerido para ejecutar",
                mandato_verificado=False,
            )
        if mandato is not None:
            if not self.firmador.verificar(mandato, self.reloj.ahora(), op):
                return self._fallar(
                    op,
                    "Mandato AP2 inválido o expirado",
                    mandato_id=mandato.id,
                    mandato_verificado=False,
                )
            mandato_id = mandato.id
            mandato_verificado = True

        disponible = self._saldos[op.desde]
        if disponible < op.monto:
            return self._fallar(
                op,
                f"Saldo insuficiente en {op.desde}: disponible {disponible}, requerido {op.monto}",
                mandato_id=mandato_id,
                mandato_verificado=mandato_verificado,
            )

        if op.tipo == "conversion":
            resultado_conv = self._aplicar_conversion(op)
            if resultado_conv is None:
                return self._fallar(
                    op,
                    f"Conversión no soportada: {op.desde}->{op.hacia}",
                    mandato_id=mandato_id,
                    mandato_verificado=mandato_verificado,
                )
            descripcion, mensaje = resultado_conv
        elif op.tipo == "pago":
            self._saldos[op.desde] -= op.monto
            descripcion = f"Pago {op.categoria} en {op.desde}"
            mensaje = f"Pago de {op.monto} {op.desde} ({op.categoria}) ejecutado"
        else:
            return self._fallar(
                op,
                f"Tipo de operación no soportado: {op.tipo}",
                mandato_id=mandato_id,
                mandato_verificado=mandato_verificado,
            )

        self._movimientos.append(
            Movimiento(
                fecha=self.reloj.hoy(),
                tipo=op.tipo,
                moneda=op.desde,
                monto=op.monto,
                descripcion=descripcion,
            )
        )
        res = Resultado(
            operacion_id=op.id,
            ok=True,
            mensaje=mensaje,
            mandato_id=mandato_id,
            mandato_verificado=mandato_verificado,
        )
        self.registro.guardar(op, res)
        return res

    def movimientos(self) -> list[Movimiento]:
        """Historial de movimientos, del más antiguo al más reciente."""
        with self._lock:
            return [m.model_copy() for m in self._movimientos]

    # ---- solo para la demo (no están en el puerto) ----

    def recibir_pago(self, monto_usd: Decimal, descripcion: str = "Pago recibido") -> Movimiento:
        """Simula que llega un pago en USD: suma al saldo y registra un Movimiento 'ingreso'."""
        monto = _copiar_decimal(monto_usd)
        if monto <= Decimal("0"):
            raise ValueError("El monto del pago debe ser mayor a cero")
        with self._lock:
            self._saldos["USD"] += monto
            mov = Movimiento(
                fecha=self.reloj.hoy(),
                tipo="ingreso",
                moneda="USD",
                monto=monto,
                descripcion=descripcion,
            )
            self._movimientos.append(mov)
            return mov

    def aplicar_rendimiento_diario(self) -> Movimiento | None:
        """Aplica un día de rendimiento al saldo USDT y registra el movimiento."""
        with self._lock:
            saldo_usdt = self._saldos["USDT"]
            if saldo_usdt <= Decimal("0"):
                return None

            tasa_anual = self.rendimiento("USDT").tasa_anual
            interes = (saldo_usdt * (tasa_anual / Decimal("365"))).quantize(
                _PRECISION_RENDIMIENTO,
                rounding=ROUND_HALF_UP,
            )
            if interes <= Decimal("0"):
                return None

            self._saldos["USDT"] += interes
            mov = Movimiento(
                fecha=self.reloj.hoy(),
                tipo="rendimiento",
                moneda="USDT",
                monto=interes,
                descripcion=f"Rendimiento diario USDT ({(tasa_anual * Decimal('100')).quantize(_CENTAVOS)}% anual)",
            )
            self._movimientos.append(mov)
            return mov

    # ---- helpers internos ----

    def _fallar(
        self,
        op: Operacion,
        mensaje: str,
        *,
        mandato_id: str | None = None,
        mandato_verificado: bool | None = None,
    ) -> Resultado:
        res = Resultado(
            operacion_id=op.id,
            ok=False,
            mensaje=mensaje,
            mandato_id=mandato_id,
            mandato_verificado=mandato_verificado,
        )
        self.registro.guardar(op, res)
        return res

    def _aplicar_conversion(self, op: Operacion) -> tuple[str, str] | None:
        if op.desde == "USD" and op.hacia == "USDT":
            self._saldos["USD"] -= op.monto
            self._saldos["USDT"] += op.monto
            return (
                f"Conversión USD->USDT ({op.categoria})",
                f"Convertidos {op.monto} USD a USDT (1:1)",
            )

        if op.desde in ("USD", "USDT") and op.hacia == "COP":
            cot = self.cotizacion(op.desde, "COP")
            cop = (op.monto * cot.tasa * (Decimal("1") - cot.spread)).quantize(
                _CENTAVOS,
                rounding=ROUND_HALF_UP,
            )
            self._saldos[op.desde] -= op.monto
            self._saldos["COP"] += cop
            return (
                f"Conversión {op.desde}->COP ({op.categoria})",
                f"Convertidos {op.monto} {op.desde} a {cop} COP",
            )

        return None
