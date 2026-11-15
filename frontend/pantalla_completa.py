# Pantalla completa (Ursina/Panda3D): el ajuste «Pantalla completa» de Gráficos y la tecla F11 van por el mismo sitio,
# el almacén de ajustes (backend/logica/ajustes.py, clave `pantalla_completa`), así quedan siempre iguales.
#
# Por qué no basta con el F11 de Ursina (ursina/window.py):
#   1. Solo agranda la ventana al tamaño del monitor con su borde y su barra de título (no quita la decoración).
#   2. La primera pulsación no hace nada: `fullscreen` vale True por defecto aunque la ventana arranque normal.
#   3. No pasa por los ajustes: no se guarda ni se ve en la pantalla de Ajustes.
# Aquí la ventana pasa a «sin borde del tamaño del monitor» (WindowProperties: undecorated + origen + tamaño) y vuelve
# a su tamaño y posición de antes. La interfaz se reajusta sola: diseno_adaptable sondea el tamaño cada frame.
#
# F11 guarda al momento si no hay otros cambios pendientes en Ajustes; si los hay (pantalla abierta con cambios),
# queda como un cambio pendiente más, igual que el interruptor.
#
# Reversible: PANTALLA_COMPLETA_AJUSTE = False (o ALCALDE_PANTALLA_COMPLETA_AJUSTE=0) deja el F11 de Ursina y no
# toca la ventana al arrancar (el ajuste guardado se ignora).

import os

PANTALLA_COMPLETA_AJUSTE = True
TECLA = "f11"


def activo():
    valor = os.environ.get("ALCALDE_PANTALLA_COMPLETA_AJUSTE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PANTALLA_COMPLETA_AJUSTE)


class GestorPantallaCompleta:

    def __init__(self, almacen):
        self.almacen = almacen
        self.aplicada = False
        self._previo = None           # (x, y, ancho, alto) de la ventana normal
        from ursina import window
        window._fullscreen = False    # que el F11 de Ursina (si quedara) no empiece al revés
        self._enganchar_tecla(window)
        almacen.suscribir(self._reaccionar)

    # Sustituye solo la rama F11 del manejador de teclas de Ursina; F10, F12 y el resto siguen igual.
    def _enganchar_tecla(self, window):
        entidad = getattr(window, "input_entity", None)
        if entidad is None:
            return
        original = entidad.input

        def entrada(key):
            if key == TECLA:
                self.alternar()
                return
            if original is not None:
                original(key)

        entidad.input = entrada

    def alternar(self):
        pendientes = self.almacen.hay_cambios_sin_guardar()
        self.almacen.cambiar(pantalla_completa=not self.almacen.actual.pantalla_completa)
        if not pendientes:
            self.almacen.guardar()

    def _reaccionar(self, ajustes, cambiadas):
        if "pantalla_completa" in cambiadas:
            self.aplicar(bool(ajustes.pantalla_completa))

    def aplicar(self, valor):
        if valor == self.aplicada:
            return
        from panda3d.core import WindowProperties
        from ursina import application, window
        base = application.base
        if base is None or getattr(base, "win", None) is None:
            return
        actuales = base.win.getProperties()
        propiedades = WindowProperties()
        if valor:
            self._previo = (actuales.getXOrigin(), actuales.getYOrigin(), actuales.getXSize(), actuales.getYSize())
            monitor = getattr(window, "main_monitor", None)
            if monitor is not None:
                x, y, ancho, alto = monitor.x, monitor.y, monitor.width, monitor.height
            else:
                x, y = 0, 0
                ancho, alto = int(window.fullscreen_size[0]), int(window.fullscreen_size[1])
            propiedades.setUndecorated(True)
            propiedades.setOrigin(int(x), int(y))
            propiedades.setSize(int(ancho), int(alto))
        else:
            propiedades.setUndecorated(False)
            if self._previo is not None:
                x, y, ancho, alto = self._previo
                propiedades.setOrigin(int(x), int(y))
                propiedades.setSize(int(ancho), int(alto))
            else:
                ancho, alto = int(window.windowed_size[0]), int(window.windowed_size[1])
                propiedades.setSize(ancho, alto)
        # la ventana normal no se deja redimensionar (main.fijar_tamano_ventana); estos cambios los pide el juego
        base.win.requestProperties(propiedades)
        window._fullscreen = valor
        self.aplicada = valor


_gestor = None


# Lo llama main.crear_aplicacion() tras abrir la ventana. Aplica lo guardado (si pantalla_completa estaba activa).
def instalar(almacen):
    global _gestor
    if not activo() or _gestor is not None:
        return _gestor
    _gestor = GestorPantallaCompleta(almacen)
    return _gestor
