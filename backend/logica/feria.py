# Disposición de la feria (zona «mercado» del barrio) y bandera de los puestos fijos. Python puro, sin ursina.
#
# Con PUESTOS_FIJOS (ALCALDE_PUESTOS_FIJOS=1, por defecto) la losa de la feria se alarga RESERVA_FONDO m por el lado
# contrario a la calle (el «fondo»; la entrada queda del lado de la calle, donde está Seu Zé). En ese fondo van la
# Banca da Feira y la Tienda Geral, lado a lado y mirando a la entrada; las dos filas de puestos decorativos con toldo
# se quedan en la parte de la entrada (la losa de siempre) mirando al pasillo central. Todo mira hacia adentro.
# La zona guarda cuánto se alargó (Zona.reserva, m) y hacia qué extremo de su eje largo (Zona.lado_reserva: -1 = el
# extremo de coordenada menor, +1 = el de mayor). Con reserva 0 (bandera apagada) todo queda como antes.
#
# Lo usan: backend/datos/barrio_favela.py (alarga la zona), backend/logica/comercios.py (anclas {"zona", "fondo"}),
# frontend/favela_detalles.mercadito (dibujo), frontend/favela_calculos.obstaculos_de_zonas (colisión) y
# frontend/comercios_calculos.huellas_mercadito (lo que los puestos nuevos no pisan): los tres describen lo mismo.
# ALCALDE_PUESTOS_FIJOS=0: posiciones y feria de antes (y elegir_puesto vuelve a corregir cada puesto).

import math
import os

PUESTOS_FIJOS = True
VARIABLE = "ALCALDE_PUESTOS_FIJOS"

SEPARACION_DECORATIVOS = 3.2     # m entre puestos decorativos de una fila (como siempre)
MARGEN_FILA = 1.3                # m del borde largo de la losa al centro de una fila decorativa
RESERVA_FONDO = 4.0              # m que se alarga la losa por el fondo
MARGEN_FONDO = 0.3               # m del borde del fondo a la espalda de los puestos del fondo
ATRAS_PUESTO_FONDO = 0.95        # m de la espalda del puesto al dependiente (comercios_calculos.ATRAS_PUESTO)
SEPARACION_FONDO = 0.4           # m entre los dos puestos del fondo (lado a lado)
ANCHO_PUESTO_FONDO = 2.6         # m del mostrador (comercios_calculos.ANCHO_PUESTO)

_ENCENDIDO = ("1", "true", "si", "sí", "on")
_APAGADO = ("0", "false", "no", "off")


def puestos_fijos_activo():
    """¿Puestos en su sitio fijo y feria nueva? ALCALDE_PUESTOS_FIJOS=1/0 manda sobre la constante."""
    valor = os.environ.get(VARIABLE, "").strip().lower()
    if valor in _ENCENDIDO:
        return True
    if valor in _APAGADO:
        return False
    return bool(PUESTOS_FIJOS)


def _ejes(zona):
    """(largo_x, largo, ancho): ¿el eje largo es x?, su largo y el ancho de la losa."""
    largo_x = zona.ancho >= zona.fondo
    return (largo_x, zona.ancho, zona.fondo) if largo_x else (largo_x, zona.fondo, zona.ancho)


def _punto(zona, a, b):
    """(x, z) de las coordenadas locales (a lo largo del eje largo, a lo ancho) respecto al centro de la losa."""
    return (zona.cx + a, zona.cz + b) if _ejes(zona)[0] else (zona.cx + b, zona.cz + a)


def reserva_de(zona):
    return float(getattr(zona, "reserva", 0.0) or 0.0)


def lado_de(zona):
    return -1 if getattr(zona, "lado_reserva", -1) < 0 else 1


def region_decorativa(zona):
    """(centro_a, largo) de la parte de la losa con los puestos decorativos, sobre el eje largo (a=0 es el centro)."""
    _, largo, _ = _ejes(zona)
    r = reserva_de(zona)
    return (-lado_de(zona) * r / 2, largo - r)


def puestos_decorativos(zona):
    """[(x, z, rumbo)] de los puestos con toldo: dos filas por el eje largo, el frente al pasillo central. Con reserva 0
    son exactamente los de siempre (favela_detalles.mercadito)."""
    largo_x, _, ancho = _ejes(zona)
    centro, largo = region_decorativa(zona)
    cuantos = max(2, int(largo // SEPARACION_DECORATIVOS))
    salida = []
    for fila in (-1, 1):
        for k in range(cuantos):
            a = centro - largo / 2 + (k + 0.5) * largo / cuantos
            b = fila * (ancho / 2 - MARGEN_FILA)
            x, z = _punto(zona, a, b)
            rumbo = (0 if fila > 0 else 180) if largo_x else (90 if fila > 0 else 270)
            salida.append((x, z, (rumbo + 180) % 360))         # el frente mira al pasillo central
    return salida


def puestos_del_fondo(zona):
    """[(x, z, rumbo)] de los dos puestos del fondo (dependiente de pie, mirando a la entrada), o [] sin reserva."""
    if reserva_de(zona) <= 0:
        return []
    largo_x, largo, _ = _ejes(zona)
    s = lado_de(zona)
    a = s * (largo / 2 - MARGEN_FONDO - ATRAS_PUESTO_FONDO)
    fx, fz = ((-s, 0) if largo_x else (0, -s))                 # hacia la entrada
    rumbo = math.degrees(math.atan2(fx, fz))
    rumbo = ((rumbo + 180.0) % 360.0) - 180.0
    salida = []
    for b in (-(ANCHO_PUESTO_FONDO + SEPARACION_FONDO) / 2, (ANCHO_PUESTO_FONDO + SEPARACION_FONDO) / 2):
        x, z = _punto(zona, a, b)
        salida.append((round(x, 3), round(z, 3), rumbo))
    return salida


def punto_entrada(zona, dentro=1.0):
    """(x, z) de la entrada de la feria: en el eje, `dentro` m hacia adentro desde el borde del lado de la calle."""
    _, largo, _ = _ejes(zona)
    return _punto(zona, -lado_de(zona) * (largo / 2 - dentro), 0.0)


# NPC clave (backend/datos/npc_clave.json) que con la losa alargada quedarían en el pasillo delante de los puestos del
# fondo: con reserva se les da otra ancla (el borde sur de la losa, junto al fondo, mirando adentro, como Inés y el
# Fiscal). Sin reserva (bandera en 0 o feria sin alargar) se usa el ancla del JSON.
ANCLAS_NPC_FERIA = {
    "marcos": {"zona": "mercado", "dx": -9.0, "dz": -5.0, "rumbo": 0.0},     # antes dx -8, dz -2: frente a la Banca
}


def ancla_npc(mundo, npc_id, ancla):
    """El ancla con la que aparece el NPC clave `npc_id` en `mundo` (la suya o la de ANCLAS_NPC_FERIA)."""
    nueva = ANCLAS_NPC_FERIA.get(npc_id)
    if nueva is None or not isinstance(ancla, dict) or ancla.get("zona") != nueva["zona"]:
        return ancla
    zona = next((z for z in getattr(mundo, "zonas", lambda: [])() if z.tipo == nueva["zona"]), None)
    return dict(nueva) if zona is not None and reserva_de(zona) > 0 else ancla
