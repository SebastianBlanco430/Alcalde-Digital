# Cálculos PUROS del inventario (sin ursina, con tests): silueta con huecos por ubicación, navegación con
# flechas, filas de la lista, textos de peso y dinero, y ControlInventario, que lleva el cursor, el modo
# «mover» y el mensaje de la última acción sobre un PerfilEconomia. La vista (inventario_ui.py) solo dibuja.

from dataclasses import dataclass

from backend.logica.inventario import GRANDE, MEDIANO, PEQUENO

# Coordenadas de la silueta: x en [0, 1] (izquierda a derecha) e y en [0, 1] (abajo a arriba). Cada hueco
# es una ranura: ubicación -> centros de sus ranuras. La mochila (hasta 8) va en dos filas bajo el cuerpo.
LAYOUT_SILUETA = {
    "espalda": ((0.50, 0.80),),
    "mano_der": ((0.10, 0.62),),
    "mano_izq": ((0.90, 0.62),),
    "cintura": ((0.37, 0.62), (0.63, 0.62)),
    "bolsillo_der": ((0.27, 0.46), (0.27, 0.34)),
    "bolsillo_izq": ((0.73, 0.46), (0.73, 0.34)),
    "bolsillo_trasero": ((0.50, 0.22),),
    "mochila": tuple((0.125 + 0.25 * (i % 4), 0.11 if i < 4 else 0.0) for i in range(8)),
}
# Etiqueta de un hueco VACÍO (corta: la posición sobre la silueta ya dice izquierda/derecha).
ETIQUETA_HUECO = {"mano_der": "Mano der.", "mano_izq": "Mano izq.", "cintura": "Cintura", "bolsillo_der": "Bolsillo",
                  "bolsillo_izq": "Bolsillo", "bolsillo_trasero": "Trasero", "espalda": "Espalda"}
ORDEN_UBICACIONES = ("mano_der", "mano_izq", "cintura", "bolsillo_der", "bolsillo_izq", "bolsillo_trasero",
                     "espalda", "mochila")
NOMBRE_TAMANO = {PEQUENO: "Pequeño", MEDIANO: "Mediano", GRANDE: "Grande"}
DIRECCIONES = {"left arrow": (-1, 0), "a": (-1, 0), "right arrow": (1, 0), "d": (1, 0),
               "up arrow": (0, 1), "w": (0, 1), "down arrow": (0, -1), "s": (0, -1)}


@dataclass(frozen=True)
class Celda:
    ubicacion: str
    indice: int            # ranura dentro de la ubicación
    x: float
    y: float
    activa: bool = True    # False = la mochila que no se lleva (hueco gris, no seleccionable)
    bloqueada: bool = False  # mano izquierda ocupada por un objeto de dos manos

    @property
    def clave(self):
        return (self.ubicacion, self.indice)


def _coma(valor, decimales=1):
    return f"{valor:.{decimales}f}".replace(".", ",")


def texto_peso(inv):
    maximo = f"{inv.peso_max():g}".replace(".", ",")
    return f"Peso {_coma(inv.peso_total())} / {maximo} kg"


def texto_dinero(saldo):
    return f"R$ {int(saldo)}"


def texto_chip(saldo):
    return f"{texto_dinero(saldo)} · [I] mochila"


def texto_pie(inv):
    return f"{texto_peso(inv)} · {texto_dinero(inv.saldo())} · I cierra"


def texto_peso_item(defitem, cantidad=1):
    return f"{_coma(defitem.peso_kg * cantidad, 2 if defitem.peso_kg * cantidad < 0.1 else 1)} kg"


# Todas las celdas de la silueta con su estado. La mochila que no se lleva se devuelve gris (activa=False).
def celdas(inv):
    activas = {u.id for u in inv.ubicaciones_activas()}
    dos_manos = inv._dos_manos_en_uso()
    lista = []
    for ub in ORDEN_UBICACIONES:
        total = len(LAYOUT_SILUETA[ub])
        if ub == "mochila" and ub in activas:
            total = min(total, inv._ranuras_totales(ub))
        for i in range(total):
            x, y = LAYOUT_SILUETA[ub][i]
            lista.append(Celda(ub, i, x, y, ub in activas, ub == "mano_izq" and dos_manos))
    return lista


# Celda vecina en la dirección (dx, dy): la más cercana dentro del cono; si no hay, se queda.
def navegar(lista, actual, direccion):
    dx, dy = direccion
    base = next((c for c in lista if c.clave == actual), None)
    if base is None:
        return lista[0].clave if lista else actual
    mejor, mejor_puntaje = None, None
    for c in lista:
        if c.clave == actual:
            continue
        vx, vy = c.x - base.x, c.y - base.y
        avance = vx * dx + vy * dy
        lateral = abs(vx * dy - vy * dx)
        if avance <= 1e-6 or lateral > avance * 2.5 + 0.02:
            continue
        puntaje = avance + 1.5 * lateral
        if mejor_puntaje is None or puntaje < mejor_puntaje:
            mejor, mejor_puntaje = c, puntaje
    return mejor.clave if mejor is not None else actual


@dataclass(frozen=True)
class Hueco:
    celda: Celda
    item_id: str | None
    cantidad: int
    texto: str            # etiqueta corta del objeto («Celular», «Pan ×2»)


def pila_en(inv, ubicacion, indice):
    lista = inv.pilas(ubicacion) if ubicacion in inv._pilas else []
    return lista[indice] if 0 <= indice < len(lista) else None


# Etiqueta de un hueco: el nombre partido en hasta 2 líneas de `ancho` caracteres (la cantidad va en una insignia
# aparte). Una palabra más larga que la línea se abrevia con punto.
def etiqueta_corta(nombre, cantidad=1, ancho=12):
    lineas, actual = [], ""
    for palabra in nombre.split():
        if len(palabra) > ancho:
            palabra = palabra[:ancho - 1] + "."
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    lineas.append(actual)
    if len(lineas) > 2:
        lineas = [lineas[0], " ".join(lineas[1:])[:ancho - 1] + "."]
    return "\n".join(lineas)


def huecos(inv):
    resultado = []
    for c in celdas(inv):
        pila = pila_en(inv, c.ubicacion, c.indice) if c.activa else None
        if pila is None:
            resultado.append(Hueco(c, None, 0, ""))
        else:
            resultado.append(Hueco(c, pila.item_id, pila.cantidad,
                                   etiqueta_corta(inv.catalogo[pila.item_id].nombre, pila.cantidad)))
    return resultado


@dataclass(frozen=True)
class Fila:
    ubicacion: str
    indice: int
    nombre: str
    cantidad: int
    tamano: str
    peso: str
    donde: str

    @property
    def clave(self):
        return (self.ubicacion, self.indice)


NOMBRES_UBICACION = {"mano_der": "Mano der.", "mano_izq": "Mano izq.", "cintura": "Cintura",
                     "bolsillo_der": "Bolsillo der.", "bolsillo_izq": "Bolsillo izq.",
                     "bolsillo_trasero": "Bolsillo tras.", "espalda": "Espalda", "mochila": "Mochila"}


def filas_lista(inv):
    filas = []
    for ub in ORDEN_UBICACIONES:
        for i, pila in enumerate(inv.pilas(ub)):
            d = inv.catalogo[pila.item_id]
            filas.append(Fila(ub, i, d.nombre, pila.cantidad, NOMBRE_TAMANO.get(d.tamano, "Mediano"),
                              texto_peso_item(d, pila.cantidad), NOMBRES_UBICACION.get(ub, ub)))
    return filas


# Descripción de la selección: (titulo, detalle) o ("Vacío", "") para un hueco sin objeto.
def detalle_de(inv, clave):
    pila = pila_en(inv, *clave)
    if pila is None:
        return ("Hueco vacío", NOMBRES_UBICACION.get(clave[0], clave[0]))
    d = inv.catalogo[pila.item_id]
    return (d.nombre, d.descripcion or NOMBRES_UBICACION.get(clave[0], clave[0]))


# Cursor, modo mover y mensaje sobre un PerfilEconomia. `al_soltar(pila)` recibe lo que se tira al suelo.
class ControlInventario:

    def __init__(self, perfil, al_soltar=None):
        self.perfil = perfil
        self.al_soltar = al_soltar
        self.seleccion = ("bolsillo_der", 0)
        self.origen = None            # clave del objeto en movimiento (modo mover)
        self.mensaje = ""
        self.error = False
        self.version = 0              # sube con cada cambio visible (la vista redibuja solo si cambia)

    @property
    def inv(self):
        return self.perfil.inventario

    @property
    def modo_mover(self):
        return self.origen is not None

    def _avisar(self, texto, error=False):
        self.mensaje, self.error = texto, error
        self.version += 1

    def pila_seleccionada(self):
        return pila_en(self.inv, *self.seleccion)

    def _validar(self):
        claves = {c.clave for c in celdas(self.inv) if c.activa}
        if self.seleccion not in claves:
            self.seleccion = ("bolsillo_der", 0)
        if self.origen is not None and pila_en(self.inv, *self.origen) is None:
            self.origen = None

    def mover_cursor(self, direccion):
        lista = [c for c in celdas(self.inv) if c.activa]
        nueva = navegar(lista, self.seleccion, direccion)
        if nueva != self.seleccion:
            self.seleccion = nueva
            self.version += 1

    def usar(self):
        if self.pila_seleccionada() is None:
            return self._avisar("No hay nada que usar ahí.", True)
        res = self.inv.usar(*self.seleccion, perfil=self.perfil)
        self._avisar(res.mensaje, not res.ok)
        self._validar()

    def soltar(self):
        res, pila = self.inv.soltar(*self.seleccion, 1)
        if res.ok and pila is not None and self.al_soltar is not None:
            recibido = self.al_soltar(pila)
            if recibido is False:                      # no se pudo dejar en el suelo: se devuelve
                self.inv.guardar(pila.item_id, pila.cantidad, self.seleccion[0], pila.datos)
                return self._avisar("Aquí no puedes soltar eso.", True)
        self._avisar(res.mensaje, not res.ok)
        self._validar()

    def alternar_mover(self):
        if self.origen is not None:
            self.origen = None
            return self._avisar("Movimiento cancelado.")
        if self.pila_seleccionada() is None:
            return self._avisar("No hay nada que mover.", True)
        self.origen = self.seleccion
        self._avisar("Elige el destino y pulsa Enter (X cancela).")

    def confirmar(self):
        if self.origen is None:
            return self.usar()
        origen = self.origen
        res = self.inv.mover(origen[0], origen[1], self.seleccion[0])
        if res.ok:
            self.origen = None
        self._avisar(res.mensaje if res.mensaje else "Listo.", not res.ok)
        self._validar()

    # Esc: cancela el modo mover (True) o no hace nada (False: la vista cierra el panel).
    def cancelar(self):
        if self.origen is None:
            return False
        self.origen = None
        self._avisar("Movimiento cancelado.")
        return True

    # Una tecla; devuelve "cerrar" cuando el panel debe cerrarse.
    def tecla(self, k):
        if k in DIRECCIONES:
            self.mover_cursor(DIRECCIONES[k])
        elif k in ("enter", "e"):
            self.confirmar()
        elif k == "q":
            self.soltar()
        elif k == "x":
            self.alternar_mover()
        elif k == "escape":
            return None if self.cancelar() else "cerrar"
        elif k == "i":
            return "cerrar"
        return None

    def firma(self):
        inv = self.inv
        return (self.version, self.seleccion, self.origen, self.mensaje, self.error, inv.saldo(),
                tuple((ub, tuple((p.item_id, p.cantidad) for p in lista)) for ub, lista in inv.pilas().items()))
