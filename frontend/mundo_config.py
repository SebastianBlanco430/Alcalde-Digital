# Bandera del mapa grande y sus parámetros de vista (módulo mínimo, SIN importaciones del juego: se puede leer desde
# main.py y las escenas sin arrastrar nada).
#
# MAPA_GRANDE = False  -> el juego de siempre (Ciudad3D con el mundo chico de ~280 x 230 m), idéntico.
# MAPA_GRANDE = True   -> el mapa extenso (~900 x 650 m): CiudadGrande (frontend/ciudad_chunks.py) con terreno, casas y
#                         props por chunks de 64 m que se construyen y se sueltan según dónde está el jugador.
# La variable de entorno ALCALDE_MAPA_GRANDE=1/0 manda sobre la constante (se lee en cada llamada, así las pruebas
# pueden cambiarla). Por defecto está ENCENDIDA (integración final): ALCALDE_MAPA_GRANDE=0 vuelve al mundo chico de siempre.

import os

MAPA_GRANDE = True

# -- Vista en modo grande (el mundo chico conserva FIN_NIEBLA = 260 y PLANO_LEJANO = 500) --
FIN_NIEBLA_GRANDE = 330.0      # m a los que la niebla llega a su máximo
PLANO_LEJANO_GRANDE = 420      # m del plano lejano de la cámara

# -- Anillos de detalle (distancia del foco al chunk más cercano, en m) --
RADIO_LOD0 = 110.0             # casas completas, calles, escaleras, props
RADIO_LOD1 = 300.0             # cajas con techo y terreno a 4 m
HISTERESIS = 25.0              # se suelta un chunk al pasar de radio + histéresis (no se construye y descarta en bucle)
ADELANTO = 30.0                # m extra de radio de CARGA de LOD0 (prefetch ~ 2 chunks hacia donde se avanza)
SEGUNDOS_DE_ADELANTO = 2.0     # el foco se adelanta tantos s a la velocidad del jugador (se carga antes lo que viene)
PRESUPUESTO_MS = 1.6           # ms por frame que el gestor gasta construyendo chunks (con el mundo en reposo)
PRESUPUESTO_URGENTE_MS = 4.0   # ms por frame si falta un chunk LOD0 a menos de RADIO_URGENTE m o la cola es larga
RADIO_URGENTE = 75.0           # m
COLA_LARGA = 12                # tareas pendientes a partir de las que se sube el presupuesto
PRECARGAR_CHUNKS = True        # prepare_scene de cada chunk al instalarlo (sube la malla a la GPU antes de verla)
RADIO_ARRANQUE = 70.0          # m del anillo que se construye BLOQUEANDO (con barra de progreso) al entrar a jugar


# Multitud del mapa grande (frontend/multitud.py): con MAPA_GRANDE sustituye a los 12 peatones del mundo chico por
# cientos de agentes con tres niveles de detalle. ALCALDE_MULTITUD=1/0 manda sobre la constante. No afecta al mundo chico.
MULTITUD_GRANDE = True


def multitud_grande_activo():
    """¿Se usa la multitud en el mapa grande? (solo tiene sentido con mapa_grande_activo())."""
    valor = os.environ.get("ALCALDE_MULTITUD", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(MULTITUD_GRANDE)


def mapa_grande_activo():
    """¿Está encendido el mapa grande? ALCALDE_MAPA_GRANDE=1/0 manda sobre MAPA_GRANDE."""
    valor = os.environ.get("ALCALDE_MAPA_GRANDE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(MAPA_GRANDE)


def construir_mundo_activo(semilla):
    """El mundo que usa main.py: el grande con la bandera encendida; si no, el de siempre (construir_mundo_3d)."""
    if mapa_grande_activo():
        from backend.datos.ciudad_grande import construir_mundo_grande
        return construir_mundo_grande(semilla=semilla)
    from backend.datos.ciudad_3d import construir_mundo_3d
    return construir_mundo_3d(semilla=semilla)


def es_mundo_grande(mundo):
    """¿Es un MundoGrande (con chunks)? Duck typing para no importar el backend aquí."""
    return hasattr(mundo, "contenido_de_chunk") and hasattr(mundo, "muros_de_chunk")


def catalogo_misiones(mundo):
    """El catálogo de misiones del mundo: con un MundoGrande el grande (los 24 lugares); si no, el de siempre."""
    from backend.datos.misiones_semilla import catalogo_de_mundo
    return catalogo_de_mundo(mundo)


def mundo_para_red(semilla, grande=None):
    """Construye el mundo que usan anfitrión y clientes online: el MISMO que el juego local (coherente con
    mapa_grande_activo()). `grande` fuerza el modo (None = la bandera)."""
    if grande is None:
        grande = mapa_grande_activo()
    if grande:
        from backend.datos.ciudad_grande import construir_mundo_grande
        return construir_mundo_grande(semilla=semilla)
    from backend.datos.ciudad_3d import construir_mundo_3d
    return construir_mundo_3d(semilla=semilla)
