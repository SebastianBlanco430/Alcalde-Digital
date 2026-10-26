# Cálculos PUROS de la tienda (sin ursina, con tests): las filas del comercio y ControlTienda, que lleva el cursor
# y el mensaje de la última compra sobre un PerfilEconomia. La vista (tienda_ui.py) solo dibuja. La compra es la de
# backend/logica/dinero.comprar (atómica: dinero, espacio y peso); aquí solo se traducen sus rechazos a mensajes.

from dataclasses import dataclass

from backend.logica import dinero
from backend.logica.comercios import stock_de
from frontend.inventario_calculos import NOMBRE_TAMANO, texto_peso_item

DIRECCIONES = {"up arrow": -1, "w": -1, "down arrow": 1, "s": 1}
TECLAS_COMPRAR = ("enter", "return", "enter (numpad)")
MENSAJES = {"sin_dinero": "Sin dinero.", "sin_billetera": "No llevas billetera para pagar."}


@dataclass(frozen=True)
class FilaTienda:
    item_id: str
    nombre: str
    precio: int
    descripcion: str
    detalle: str            # «Mediano · 0,3 kg»

    @property
    def texto_precio(self):
        return f"R$ {self.precio}"


def texto_saldo(saldo):
    return f"Saldo: R$ {int(saldo)}"


def filas_de(comercio, catalogo=None):
    filas = []
    for defitem, precio in stock_de(comercio, catalogo):
        detalle = f"{NOMBRE_TAMANO.get(defitem.tamano, '')} · {texto_peso_item(defitem)}"
        filas.append(FilaTienda(defitem.id, defitem.nombre, precio, defitem.descripcion or detalle, detalle))
    return filas


class ControlTienda:

    def __init__(self, perfil, comercio, catalogo=None, al_comprar=None):
        self.perfil = perfil
        self.comercio = comercio
        self.filas = filas_de(comercio, catalogo if catalogo is not None else perfil.inventario.catalogo)
        self.seleccion = 0
        self.mensaje = ""
        self.error = False
        self.version = 0
        self._al_comprar = al_comprar

    @property
    def inv(self):
        return self.perfil.inventario

    def saldo(self):
        return self.inv.saldo()

    def fila_seleccionada(self):
        return self.filas[self.seleccion] if self.filas else None

    def _avisar(self, texto, error=False):
        self.mensaje, self.error = texto, error
        self.version += 1

    def mover(self, delta):
        if not self.filas:
            return
        nueva = (self.seleccion + delta) % len(self.filas)
        if nueva != self.seleccion:
            self.seleccion = nueva
            self.version += 1

    # Compra una unidad de la fila elegida. Devuelve el ResultadoCompra (o None si no hay nada que comprar).
    def comprar(self):
        fila = self.fila_seleccionada()
        if fila is None:
            self._avisar("Aquí no hay nada a la venta.", True)
            return None
        resultado = dinero.comprar(self.perfil, self.comercio, fila.item_id)
        if resultado.ok:
            self._avisar(resultado.mensaje)
            if self._al_comprar is not None:
                self._al_comprar(resultado)
        else:
            self._avisar(MENSAJES.get(resultado.codigo, resultado.mensaje), True)
        return resultado

    # Una tecla: devuelve "cerrar" si hay que cerrar la tienda, o None.
    def tecla(self, key):
        if key == "escape":
            return "cerrar"
        if key in DIRECCIONES:
            self.mover(DIRECCIONES[key])
        elif key in TECLAS_COMPRAR:
            self.comprar()
        return None

    # Todo lo que se ve: si no cambia, la vista no redibuja.
    def firma(self):
        return (self.version, self.seleccion, self.saldo(), len(self.filas))
