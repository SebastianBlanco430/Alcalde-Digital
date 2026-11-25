# Dinero del mostrador 3D (modelo puro, sin ursina): reales de Brasil en CENTAVOS enteros (sin errores de coma).
# Billetes de R$ 2, 5, 10, 20, 50, 100 y 200; monedas de R$ 0,05, 0,10, 0,25, 0,50 y 1. Con esto se calcula cuánto
# paga el cliente, cuánto cambio le toca y si el que da el jugador es correcto. Lo usa backend/logica/mostrador3d_turno.py;
# los datos de cada local (productos y precios) están en backend/datos/mostrador3d_locales.json.

import json
from pathlib import Path

BILLETES = (20000, 10000, 5000, 2000, 1000, 500, 200)
MONEDAS = (100, 50, 25, 10, 5)
# de mayor a menor
DENOMINACIONES = BILLETES + MONEDAS
RUTA_LOCALES = Path(__file__).resolve().parent.parent / "datos" / "mostrador3d_locales.json"
# paga billete + los centavos, para que el cambio salga en reales enteros (el resto, solo con el billete). Nunca paga
# justo: la gracia del mostrador es dar el cambio, así que siempre hay cambio que devolver.
PROB_REDONDEA = 0.35


def es_billete(valor):
    return valor in BILLETES


def formatear(centavos):
    """«R$ 5,00», «R$ 0,35», «R$ 124,90» (coma decimal, como en Brasil)."""
    signo = "-" if centavos < 0 else ""
    centavos = abs(int(centavos))
    return f"R$ {signo}{centavos // 100},{centavos % 100:02d}"


def nombre_denominacion(valor):
    """«R$ 5» para billetes y monedas enteras; «R$ 0,25» para las de centavos."""
    return f"R$ {valor // 100}" if valor % 100 == 0 else formatear(valor)


def descomponer(centavos):
    """Lista de billetes y monedas (mayor primero) que suma `centavos` con el menor número de piezas."""
    if centavos < 0 or centavos % 5:
        raise ValueError(f"Cantidad no representable con monedas de R$ 0,05: {centavos}")
    piezas = []
    for valor in DENOMINACIONES:
        while centavos >= valor:
            piezas.append(valor)
            centavos -= valor
    return piezas


def total_pedido(pedido, precios):
    """Precio de `pedido` ({producto: unidades}) con `precios` ({producto: centavos})."""
    return sum(precios[p] * n for p, n in pedido.items())


def pago_cliente(total, azar):
    """Billetes y monedas con que paga el cliente un `total` (centavos): el billete justo por encima del total o ese
    billete más los centavos sueltos (así el cambio sale redondo, como hace mucha gente). Siempre paga de más: hay
    cambio que dar. `azar`: random.Random."""
    if total <= 0:
        return []
    tirada = azar.random()
    billete = next((b for b in reversed(BILLETES) if b > total), None)
    # más de R$ 200: billetes de 200 hasta cubrirlo
    if billete is None:
        return [BILLETES[0]] * (total // BILLETES[0] + 1)
    sueltos = total % 100
    if tirada < PROB_REDONDEA and sueltos:
        return [billete] + descomponer(sueltos)
    return [billete]


def cambio(total, pagado):
    """Cambio que corresponde (centavos) a quien pagó `pagado` (lista o número) por `total`."""
    pagado = sum(pagado) if isinstance(pagado, (list, tuple)) else pagado
    return max(0, pagado - total)


def cambio_correcto(dado, total, pagado):
    """True si la suma de `dado` (lista de denominaciones) es exactamente el cambio."""
    return sum(dado) == cambio(total, pagado)


def cargar_locales(ruta=None):
    """{trabajo_id: local} de backend/datos/mostrador3d_locales.json, validado (4 productos con precio múltiplo de 5)."""
    datos = json.loads(Path(ruta or RUTA_LOCALES).read_text(encoding="utf-8"))
    locales = {}
    for clave, local in datos.items():
        if clave.startswith("_"):
            continue
        productos = local.get("productos", [])
        if len(productos) != 4:
            raise ValueError(f"Local {clave!r}: necesita 4 productos.")
        for p in productos:
            precio = p.get("precio")
            if not isinstance(precio, int) or isinstance(precio, bool) or precio <= 0 or precio % 5:
                raise ValueError(f"Local {clave!r}: precio inválido para {p.get('nombre')!r}: {precio!r}")
        locales[clave] = local
    return locales
