# Caché de fuentes de Text (parte Ursina; la decisión y la bandera están en frontend/fuentes_texto_calculos.py).
#
# Ursina genera las propiedades de Text con `property(font_getter, font_setter)` al crear la clase
# (ursina/scripts/property_generator.py), así que reemplazar `Text.font_setter` no basta: se reemplaza la propiedad
# `Text.font` entera por una con el mismo getter y un setter que es el de Ursina 8.3.0 línea a línea salvo el
# `append_path`, que solo se hace si la carpeta no está ya en el model path, y la búsqueda de FontPool, que se hace una
# vez por archivo (el pool devuelve el mismo objeto). Llamar a `instalar()` antes del primer Text.

from panda3d.core import FontPool, getModelPath
from ursina import Text, application
from ursina import text as modulo_text
from ursina.string_utilities import print_warning

from frontend import fuentes_texto_calculos as fc

_original = []          # la propiedad de Ursina (para desinstalar)
# Fuente ya cargada por archivo. FontPool.load_font devuelve SIEMPRE el mismo objeto para el mismo archivo (es un pool),
# pero cada llamada vuelve a resolver el nombre en el disco (~1 ms): con ~1.700 Text eran ~1,7 s.
_cargadas = {}


def _carpetas_model_path():
    ruta = getModelPath().getValue()
    return [ruta.getDirectory(i).toOsSpecific() for i in range(ruta.getNumDirectories())] + \
           [ruta.getDirectory(i).getFullpath() for i in range(ruta.getNumDirectories())]


_registro = fc.RegistroCarpetas(_carpetas_model_path)
_limpiezas = fc.RegistroLimpiezas()     # R6: con qué resolución quedó limpia cada fuente
_estado = {"cache": False, "una_limpieza": False}


def _font_setter(self, value):
    font_file_types = ('.ttf', '.otf') if '.' not in value else ('', )
    folders = (application.fonts_folder, application.asset_folder, application.internal_fonts_folder)
    font_file_path = modulo_text._search_for_file(value, folders, font_file_types)

    if not font_file_path:
        print_warning('missing font:', value)

    font = _cargadas.get(font_file_path) if _estado["cache"] else None
    if font is None:
        carpeta = str(font_file_path.parent.resolve())
        if not _estado["cache"] or _registro.hay_que_agregar(carpeta):
            getModelPath().append_path(carpeta)
        font = FontPool.load_font(font_file_path.name)
        if font and _estado["cache"]:
            _cargadas[font_file_path] = font

    if font:
        self._font = font
        # R6: Ursina limpia la fuente COMPARTIDA en cada Text; con los hilos de dibujo eso choca con el hilo de cull, que
        # regenera glifos a la vez (aserciones de dynamicTextFont). Con ALCALDE_FUENTE_UNA_LIMPIEZA solo se limpia cuando
        # cambia la resolución, y entonces se precargan los glifos comunes aquí, en el hilo principal.
        if not _estado["una_limpieza"] or _limpiezas.hay_que_limpiar(font, self.resolution):
            self._font.clear()  # remove assertion warning
            self._font.setPixelsPerUnit(self.resolution)
            if _estado["una_limpieza"]:
                _precargar(font)
        self._font.setLineHeight(self.line_height)
        if self.text:
            self.text = self.raw_text   # update text


def _resolution_setter(self, value):
    """R6: el de Ursina hace setPixelsPerUnit sin limpiar (Panda exige 0 páginas). Solo se toca si cambia la resolución,
    y entonces se limpia y se precarga en el hilo principal."""
    if self.font is None:
        return
    if _limpiezas.hay_que_limpiar(self._font, value):
        self._font.clear()
        self._font.setPixelsPerUnit(value)
        _precargar(self._font)


def _precargar(font):
    """Genera en el hilo principal los glifos de fc.CARACTERES_PRECARGA (el hilo de cull ya no tiene que crearlos)."""
    try:
        from panda3d.core import TextNode
        nodo = TextNode("precarga")
        nodo.setFont(font)
        nodo.calcWidth(fc.CARACTERES_PRECARGA)
    except Exception:       # noqa: BLE001 — sin precarga se generan al pedirlos, como antes
        pass


def instalar():
    """Pone el setter propio si ALCALDE_FUENTE_CACHE o ALCALDE_FUENTE_UNA_LIMPIEZA (R6) lo piden. Devuelve True si quedó
    instalado. Con las dos en 0 queda el setter de Ursina, como antes."""
    if _original:
        return True
    _estado["cache"], _estado["una_limpieza"] = fc.fuente_cache_activa(), fc.fuente_una_limpieza_activa()
    if not _estado["cache"] and not _estado["una_limpieza"]:
        return False
    _original.append(Text.__dict__["font"])
    Text.font = property(Text.font_getter, _font_setter, _original[0].fdel)
    if _estado["una_limpieza"]:
        _original_resolucion.append(Text.__dict__["resolution"])
        Text.resolution = property(Text.resolution_getter, _resolution_setter, _original_resolucion[0].fdel)
    return True


_original_resolucion = []


def desinstalar():
    if _original:
        Text.font = _original.pop()
    if _original_resolucion:
        Text.resolution = _original_resolucion.pop()
