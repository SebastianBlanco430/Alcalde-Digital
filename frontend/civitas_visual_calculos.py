# Cálculos de la bandeja de CIVITAS visual (frontend/civitas_visual.py). Python puro, sin ursina, con tests en
# tests/test_civitas_visual.py. El modelo (backend/logica/habitos_digitales.py) no cambia.
#
#   - estafas: el mensaje como notificación real; cuántas monedas salen de la billetera y por dónde vuelan;
#   - publicar foto: en qué zona de la ilustración va cada elemento, qué quedó expuesto y la lupa del desconocido;
#   - tiempo de pantalla: el feed que se desliza solo, la batería y la luz del día que bajan con los minutos.

import math

TIPOS = ("estafa", "publicar")
CLAVE_CUENTA_ROBADA = "cuenta_robada"

# Zonas de la foto (x, y relativas al centro de la ilustración, en unidades de camera.ui) por orden de elemento.
ZONAS_FOTO = ((-0.09, 0.06), (0.09, 0.07), (-0.07, -0.07), (0.1, -0.06), (0.0, 0.0))


def zonas_foto(n):
    """Posición de la zona de cada uno de los `n` elementos de la foto (se reparten las zonas fijas)."""
    return [ZONAS_FOTO[i % len(ZONAS_FOTO)] for i in range(max(0, n))]


def expuestos(resultado):
    """Índices de los elementos que quedaron A LA VISTA al publicar (debían taparse y no se taparon)."""
    if not resultado or resultado.get("decision") != "publicar":
        return []
    return [i for i, f in enumerate(resultado.get("revision", ())) if f.get("debia_marcarse") and not f.get("marcado")]


def monedas(perdida, por_moneda=5, maximo=10):
    """Cuántas monedas salen volando de la billetera al perder `perdida` reales (al menos una si se perdió algo)."""
    if not perdida or perdida <= 0:
        return 0
    return max(1, min(maximo, int(math.ceil(perdida / por_moneda))))


def trayectoria_moneda(t, i, origen, intervalo=0.15, dur=0.8):
    """(x, y, alfa) de la moneda `i` a los `t` s: salen de una en una de la billetera, suben y se van."""
    tl = t - i * intervalo
    if tl < 0:
        return origen[0], origen[1], 0.0
    p = min(1.0, tl / dur)
    x = origen[0] + 0.05 * math.sin(i * 1.7) * p
    y = origen[1] + 0.22 * p - 0.08 * p * p
    return x, y, max(0.0, 1.0 - p)


def duracion_monedas(n, intervalo=0.15, dur=0.8):
    return 0.0 if n <= 0 else (n - 1) * intervalo + dur


# -- Tiempo de pantalla --

MINUTOS_BATERIA = 240        # con este tiempo de pantalla al día, batería vacía


def bateria(minutos):
    return max(0.0, min(1.0, 1.0 - minutos / MINUTOS_BATERIA))


def oscuridad(minutos, reducir=False, maximo=0.55):
    """Opacidad del oscurecido de la pantalla (la luz del día baja mientras se desliza el feed)."""
    a = maximo * max(0.0, min(1.0, minutos / MINUTOS_BATERIA))
    return a * (0.8 if reducir else 1.0)


def desplazamiento_feed(t, alto_tarjeta, velocidad=0.05, reducir=False):
    """Cuánto ha subido el feed (se desliza solo); vuelve a empezar cada tarjeta para reutilizar 3 tarjetas."""
    if reducir:
        return 0.0
    return (t * velocidad) % alto_tarjeta


def es_cuenta_robada(aviso):
    return str((aviso or {}).get("clave") or "") == CLAVE_CUENTA_ROBADA


def recortar(texto, largo):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"
