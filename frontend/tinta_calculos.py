# Peso de línea unificado (T1 del bloque T del plan ambiente y pulseras; ALCALDE_TINTA_UNIFICADA=0 = grosores de antes).
# FUENTE ÚNICA del grosor de los cascos de tinta (m que el casco asoma por cada lado). Cada módulo que tenía su GROSOR_*
# lo lee de aquí con grosor(familia). Puro: sin ursina.
#
# Regla: a 1280 px y FOV 65 la línea mide ≈ 1005·g/d px (pixeles_contorno). La meta es 2,5–4 px en la distancia típica de
# cada familia (personajes a ~6 m, vehículos a ~8 m, carteles y piezas de etapa a ~10 m, árboles a ~12 m, casas a ~15 m):
# así un personaje y una casa a sus distancias de juego tienen el mismo peso de línea. Los «finos» (detalles interiores,
# rasgos de la cara) van a ~0,6 del peso de su familia: líneas secundarias, como en el cómic.
import os

TINTA_UNIFICADA = True

# familia: (grosor de antes, grosor unificado, distancia típica en m)
FAMILIAS = {
    "personaje": (0.018, 0.019, 6.0),          # contorno_calculos.GROSOR_CUERPO (piezas procedurales)
    "personaje_fino": (0.010, 0.0115, 6.0),     # contorno_calculos.GROSOR_DETALLE
    "npc_nuevos": (0.011, 0.019, 6.0),          # npc_nuevos_calculos.GROSOR_CONTORNO (inflado por normal)
    "rostro": (0.0095, 0.0115, 6.0),            # rostro_calculos.GROSOR_CONTORNO (rasgos: peso secundario)
    "rostro_fino": (0.0045, 0.009, 6.0),        # rostro_calculos.GROSOR_CONTORNO_FINO
    "vehiculo": (0.016, 0.024, 8.0),            # vehiculo_piezas.GROSOR_CONTORNO
    "vehiculo_fino": (0.009, 0.0145, 8.0),      # vehiculo_piezas.GROSOR_FINO
    "casa": (0.12, 0.05, 15.0),                 # casas_decorativas.GROSOR_CONTORNO (copia escalada)
    "prop": (0.09, 0.04, 12.0),                 # props_mundo.GROSOR_CONTORNO_PROPS (árboles)
    "etapa": (0.035, 0.035, 10.0),              # ciudad_viva.GROSOR_TINTA_ETAPA
    "etapa_prop": (0.018, 0.03, 10.0),          # etapas_final_vista.GROSOR_TINTA_PROP
    "cartel": (0.04, 0.035, 10.0),              # trabajo_mundo.GROSOR_TINTA_CARTEL
}
PRINCIPALES = ("personaje", "npc_nuevos", "vehiculo", "casa", "prop", "etapa", "etapa_prop", "cartel")
BANDA_PX = (2.5, 4.0)
MINIMO_FINO_PX = 1.5


def activa():
    valor = os.environ.get("ALCALDE_TINTA_UNIFICADA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TINTA_UNIFICADA)


def grosor(familia, unificada=None):
    """m por lado del casco de esa familia (el unificado con la bandera; el de antes sin ella)."""
    antes, nuevo, _ = FAMILIAS[familia]
    return nuevo if (activa() if unificada is None else unificada) else antes


def distancia_tipica(familia):
    return FAMILIAS[familia][2]


# T6 (ALCALDE_TINTA_TEXTURAS): tinta dibujada en las texturas procedurales (ladrillo y suelo de la favela) y cintas de
# bordillo. Lo «entintado a mano» de Borderlands, hecho con Pillow al arrancar (va en la caché de siempre).
TINTA_TEXTURAS = True
VALOR_TINTA_TEXTURA = 46        # gris (0-255) del trazo en las texturas que MULTIPLICAN el color


def texturas_activa():
    valor = os.environ.get("ALCALDE_TINTA_TEXTURAS", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TINTA_TEXTURAS)


# Cierre (punto 2, ALCALDE_TINTA_BORDILLO_ANCHA): el verificador vio «poca tinta» en peldaños y bordillos. Con la bandera la
# cinta del bordillo pasa de 6 a 12 cm y el filo del peldaño, de una lámina de 1,2 cm sobre la huella a un listón de 6 cm de
# alto que baja por el borde de la contrahuella y asoma 5 cm (se lee como línea de cómic desde arriba y desde abajo). A
# 1280 px y FOV 65 eso es ≈ 1005·ancho/d px: ~12 px de frente a 10 m (≥ 3 px aun rasante) y ≤ 2 px a 60 m, sin ensuciar
# de lejos. Mismas piezas (siguen en los grupos combinados): 0 draw calls nuevos. =0 como antes.
TINTA_BORDILLO_ANCHA = True
ANCHO_BORDILLO = (0.06, 0.12)       # m: (antes, con la bandera)
FILO_PELDANO_ALTO = (0.012, 0.06)   # m: alto del filo del peldaño
FILO_PELDANO_SOBRE = (0.004, 0.008)  # m: cuánto asoma su cara de arriba sobre la tapa
FILO_PELDANO_FONDO = (0.06, 0.10)   # m: profundidad (a caballo del borde: la mitad vuela sobre el peldaño de abajo)


def _bandera_env(nombre, defecto, entorno=None):
    valor = (os.environ if entorno is None else entorno).get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(defecto)


def bordillo_ancho_activo(entorno=None):
    return _bandera_env("ALCALDE_TINTA_BORDILLO_ANCHA", TINTA_BORDILLO_ANCHA, entorno)


def ancho_tinta_bordillo(ancha=None):
    """Ancho (m) de la cinta de tinta del bordillo."""
    return ANCHO_BORDILLO[1 if (bordillo_ancho_activo() if ancha is None else ancha) else 0]


def filo_peldano(tapa, ancha=None):
    """(y del centro, alto, profundidad) del listón de tinta en el borde de un peldaño cuya tapa está en `tapa`."""
    i = 1 if (bordillo_ancho_activo() if ancha is None else ancha) else 0
    alto = FILO_PELDANO_ALTO[i]
    return (tapa + FILO_PELDANO_SOBRE[i] - (alto / 2 if i else 0.0), alto, FILO_PELDANO_FONDO[i])


def pixeles_linea(ancho, distancia, ancho_px=1280):
    """px que ocupa de frente una línea de `ancho` m a `distancia` m (FOV horizontal 65°)."""
    return 1005.0 * (ancho_px / 1280.0) * ancho / max(distancia, 1e-6)


def tapa_del_filo(tapa, tapa_previa, ancha=None):
    """Tapa a la que va el filo entre dos peldaños: la del MÁS ALTO (su nariz es el borde que se ve), con la bandera.
    Sin ella, la del peldaño `k` como antes (si la escalera baja en el sentido del perfil quedaba escondido abajo)."""
    if not (bordillo_ancho_activo() if ancha is None else ancha) or tapa_previa is None:
        return tapa
    return max(tapa, tapa_previa)
