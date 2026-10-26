# Dinero (modelo puro): pago de misiones, compras y descanso. Todo en R$ enteros, con la billetera del
# inventario. Las compras son atómicas: si algo falla, el inventario queda como estaba.

from dataclasses import dataclass

from backend.logica.inventario import Inventario, Resultado, _entero_valido, SALDO_MAX

FATIGA_POR_MISION = 30
MAX_COMPRA = 99


@dataclass(frozen=True)
class ResultadoCompra:
    ok: bool
    codigo: str = "ok"
    mensaje: str = ""
    total: int = 0
    item_id: str = ""
    cantidad: int = 0


# Pago (entero >= 0) de una misión; las que no tienen el campo (o lo tienen raro) pagan 0.
def pago_de_mision(mision):
    pago = getattr(mision, "pago", 0)
    return pago if _entero_valido(pago, 0, SALDO_MAX) else 0


# Ingresa el pago de la misión en la billetera. Pago 0 = ok sin cambios.
def pagar_mision(perfil, mision):
    pago = pago_de_mision(mision)
    if pago == 0:
        return Resultado(True, "ok", "")
    resultado = perfil.inventario.ingresar(pago)
    if resultado.ok:
        perfil.ganado += pago
        perfil.registrar(f"Misión: {getattr(mision, 'titulo', 'misión')}", pago)
    return resultado


# Compra `cantidad` unidades de `item_id` en el comercio (su `stock` = ids a la venta, al precio del catálogo).
def comprar(perfil, comercio, item_id, cantidad=1):
    inv = perfil.inventario
    if not isinstance(item_id, str) or item_id not in tuple(getattr(comercio, "stock", ())):
        return ResultadoCompra(False, "no_vende", "Aquí no venden eso.")
    if not _entero_valido(cantidad, 1, MAX_COMPRA):
        return ResultadoCompra(False, "cantidad_invalida", f"La cantidad debe ser de 1 a {MAX_COMPRA}.")
    defitem = inv.catalogo.get(item_id)
    if defitem is None or defitem.precio is None or defitem.fijo:
        return ResultadoCompra(False, "no_vende", "Aquí no venden eso.")
    total = defitem.precio * cantidad
    snap = inv._snapshot()
    puede = inv.puede_guardar(item_id, cantidad)
    if not puede.ok:
        return ResultadoCompra(False, puede.codigo, puede.mensaje)
    cobro = inv.cobrar(total)
    if not cobro.ok:
        return ResultadoCompra(False, cobro.codigo, cobro.mensaje)
    guardado = inv.guardar(item_id, cantidad)
    if not guardado.ok:
        inv._restaurar(snap)         # revierte el cobro (snapshot interno, sin pasar por la carga tolerante)
        return ResultadoCompra(False, guardado.codigo, guardado.mensaje)
    perfil.registrar(f"Compra: {defitem.nombre} ×{cantidad}", -total)
    return ResultadoCompra(True, "ok", f"Compraste {cantidad} × {defitem.nombre} por R$ {total}.",
                           total, item_id, cantidad)


# Baja la fatiga `cantidad` puntos (mínimo 0) y devuelve la fatiga nueva.
def recuperar_fatiga(perfil, cantidad=FATIGA_POR_MISION):
    perfil.fatiga = max(0, perfil.fatiga - max(0, int(cantidad)))
    return perfil.fatiga
