# Caché de fuentes de Text (Python puro: NO importa ursina ni panda3d). La parte Ursina está en frontend/fuentes_texto.py.
#
# Problema (M7.2, perfil de arranque): el `font_setter` de ursina/text.py (Ursina 8.3.0) hace
# `getModelPath().append_path(carpeta_de_la_fuente)` en CADA Text creado. El model path de Panda crecía con ~1.700
# copias de la misma carpeta y cada FontPool.load_font (y cada loadModel posterior que no está en la caché) recorría
# esa lista entera: ~4,5 s del arranque (perfilado).
# Arreglo: la carpeta solo se agrega si NO está ya en el model path. La búsqueda de Panda devuelve la PRIMERA carpeta
# que tiene el archivo, y añadir al final una carpeta que ya está nunca cambia cuál es la primera: el resultado de cada
# búsqueda es idéntico, solo más corto.
# ALCALDE_FUENTE_CACHE=0 deja el setter original de Ursina (con su model path creciente), como antes.

import os

FUENTE_CACHE = True


def fuente_cache_activa(valor=None):
    valor = (os.environ.get("ALCALDE_FUENTE_CACHE", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(FUENTE_CACHE)


def _clave(carpeta):
    # Panda guarda las carpetas con '/' y Windows es insensible a mayúsculas: se comparan normalizadas.
    return str(carpeta).replace("\\", "/").rstrip("/").lower()


class RegistroCarpetas:
    """Recuerda qué carpetas ya están en el model path para no agregarlas otra vez.

    `existentes` es una función sin argumentos que devuelve las carpetas actuales del model path (solo se consulta la
    primera vez que aparece cada carpeta: luego basta el conjunto en memoria)."""

    def __init__(self, existentes):
        self._existentes = existentes
        self._vistas = set()

    def hay_que_agregar(self, carpeta):
        clave = _clave(carpeta)
        if clave in self._vistas:
            return False
        self._vistas.add(clave)
        return clave not in {_clave(c) for c in self._existentes()}


# -- R6 (retoques): la aserción de fuentes de Panda ----------------------------------------------------------------------
# «glyph->_page->get_num_components() == 1» (dynamicTextFont.cxx:797). El setter de Ursina hace `font.clear()` en CADA
# Text que se crea (con la misma resolución: no hace falta), lo que tira todas las páginas de glifos de la fuente
# COMPARTIDA; los glifos se vuelven a generar cuando se piden, y con «threading-model Cull/Draw» (rendimiento.py, solo
# Windows) muchos se generan en el hilo de cull mientras el hilo principal mide texto (calcWidth): una página creada en
# un hilo todavía no está en la etapa del otro y Panda la ve con 0 componentes. Arreglo: limpiar la fuente solo cuando
# cambia la resolución pedida (la primera vez) y precargar los glifos comunes en el hilo principal.
# ALCALDE_FUENTE_UNA_LIMPIEZA=0 = como antes (clear en cada Text).
FUENTE_UNA_LIMPIEZA = True
# Glifos que se precargan: ASCII imprimible, Latin-1 (acentos, ñ, ¿¡, «», ·) y los signos que usa el juego.
CARACTERES_PRECARGA = (
    "".join(chr(c) for c in range(0x20, 0x7F))
    + "".join(chr(c) for c in range(0xA0, 0x100))
    + "—–…‘’“”•→←↑↓✓★€"
)


def fuente_una_limpieza_activa(valor=None):
    valor = (os.environ.get("ALCALDE_FUENTE_UNA_LIMPIEZA", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(FUENTE_UNA_LIMPIEZA)


class RegistroLimpiezas:
    """Recuerda con qué píxeles por unidad quedó limpia cada fuente: solo hay que limpiarla si cambia. FontPool devuelve
    el mismo objeto C++ con envoltorios Python distintos (id() no sirve): la clave es su puntero (`this` de Panda), o su
    nombre, o su id."""

    def __init__(self):
        self._ppu = {}

    def hay_que_limpiar(self, fuente, ppu):
        clave = _clave_fuente(fuente)
        if self._ppu.get(clave) == ppu:
            return False
        self._ppu[clave] = ppu
        return True


def _clave_fuente(fuente):
    puntero = getattr(fuente, "this", None)
    if isinstance(puntero, int):
        return ("puntero", puntero)
    try:
        nombre = fuente.getName()
        if nombre:
            return ("nombre", str(nombre))
    except Exception:       # noqa: BLE001 — objetos sin nombre (pruebas)
        pass
    return ("id", id(fuente))
