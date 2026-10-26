# Escena de TRABAJO (Ursina, camera.ui): el turno de un puesto como minijuego 2D. Un juego visual por motor del
# modelo (backend/logica/trabajos.py):
#   ATENDER   - un cliente pide «2 pan + 1 café»; teclas 1-4 (o clic) entregan el producto.
#   SECUENCIA - flechas que hay que repetir en orden (flechas o W A S D, o los botones de abajo).
#   BARRA     - una marca va y viene; Espacio (o el botón) la detiene dentro de la zona marcada «ZONA».
# Arriba: el puesto, la barra de tiempo, los aciertos y los errores. Al acabar el tiempo, un panel con el
# resultado (aciertos, errores, pago en R$ y cansancio). Todo se entiende con texto, no solo con color.
#
# La escena no conoce al gestor ni aplica el pago: al cerrar llama a `al_terminar(resultado)` (el dict de
# TurnoTrabajo.resultado(), o None si el jugador abandonó) y ConexionFlujo.terminar_trabajo ingresa pago y fatiga.
# Estilo: estilo.py y componentes.panel_tinta; los dibujos son formas de Ursina (círculos, rectángulos, triángulos).

import math
import random

from ursina import Button, Entity, Mesh, Text, color, time

from backend.logica.perfil_economia import FATIGA_MAX, perfil_de
from backend.logica.trabajos import ATENDER, BARRA, MENSAJE_AGOTADO, SECUENCIA, TurnoTrabajo
from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import (BotonPrimario, BotonSecundario, destruir_arbol, escala_fuente, modelo_redondeado,
                                  panel_tinta, rgb)
from frontend.escenas.escena_base import Escena

ANCHO, ALTO = 1.18, 0.86
INTRO, JUGANDO, RESULTADO = "intro", "jugando", "resultado"
DT_MAX = 0.1                  # un tirón de la ventana no se come el turno
ESPERA_RESULTADO = 0.7        # s: evita cerrar el resultado con la tecla que se estaba pulsando
DURACION_FLASH = 0.25
DURACION_FEEDBACK = 1.1
ANCHO_BARRA = 0.9
ROJO_TEXTO = (240, 110, 110)

TECLAS_PRODUCTO = {str(n): n for n in range(1, 5)} | {f"numpad {n}": n for n in range(1, 5)}
TECLAS_DIRECCION = {"up arrow": "arriba", "w": "arriba", "down arrow": "abajo", "s": "abajo",
                    "left arrow": "izquierda", "a": "izquierda", "right arrow": "derecha", "d": "derecha"}
ROTACION_FLECHA = {"arriba": 0, "derecha": 90, "abajo": 180, "izquierda": 270}
NOMBRE_DIRECCION = {"arriba": "ARRIBA", "abajo": "ABAJO", "izquierda": "IZQUIERDA", "derecha": "DERECHA"}

INSTRUCCIONES = {
    ATENDER: "Pulsa 1, 2, 3 o 4 para dar cada producto del pedido. Si das de más, el pedido se reinicia.",
    SECUENCIA: "Repite las flechas en orden (flechas del teclado o W A S D). Un error reinicia la secuencia.",
    BARRA: "Pulsa Espacio cuando la marca esté dentro de la ZONA. Más aciertos, más paga.",
}
TEMAS = {   # frase extra por puesto (solo texto de ambientación)
    "taller": "Sigue los pasos de la reparación.",
    "lan_house": "Teclea el código de soporte.",
    "lanchonete": "Saca la comida en su punto.",
    "entregas": "Frena justo en la parada.",
}

PIEL = ((236, 196, 160), (205, 150, 108), (150, 100, 66), (104, 66, 44))
CAMISAS = ((214, 92, 80), (78, 150, 214), (96, 176, 110), (230, 170, 60), (160, 110, 200), (70, 190, 190))
PELO = ((40, 30, 28), (90, 56, 34), (200, 160, 80), (30, 30, 40))


def _seguro(cadena):
    return str(cadena).replace("<", "(").replace(">", ")")


def _texto(padre, cadena, px, tono, pos, origen=(0, 0), negrita=False, z=-0.01):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(_seguro(cadena), parent=padre, origin=origen, position=(pos[0], pos[1], z),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


def _caja(padre, ancho, alto, tono, pos, radio=6, z=0.0):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio),
                  color=rgb(tono) if isinstance(tono, tuple) else tono, scale=(ancho, alto),
                  position=(pos[0], pos[1], z))


def _linea(padre, ancho, pos, z=0.0):
    return Entity(parent=padre, model="quad", color=rgb(estilo.COLOR_BARRA_FONDO), scale=(ancho, 0.003),
                  position=(pos[0], pos[1], z))


def _triangulo():
    return Mesh(vertices=[(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)], triangles=[(0, 1, 2)])


# Capa de dibujo: cada forma que se añade queda un pelo delante de la anterior (orden de pintado estable).
class Capa:

    def __init__(self, padre, z=-0.002):
        self.padre = padre
        self.z = z
        self.n = 0

    def forma(self, modelo, tono, escala, pos=(0, 0), rot=0):
        self.n += 1
        e = Entity(parent=self.padre, model=_triangulo() if modelo == "triangulo" else modelo,
                   color=rgb(tono) if isinstance(tono, tuple) else tono, scale=escala,
                   position=(pos[0], pos[1], self.z - 0.0004 * self.n))
        e.rotation_z = rot
        return e

    def elipse(self, tono, w, h, pos=(0, 0), rot=0):
        return self.forma("circle", tono, (w, h), pos, rot)

    def rect(self, tono, w, h, pos=(0, 0), rot=0):
        return self.forma("quad", tono, (w, h), pos, rot)


# ---------------------------------------------------------------------------
# Iconos de producto: dibujados con formas. `k` = lado aproximado del icono en unidades de camera.ui.
# ---------------------------------------------------------------------------

def _pan(c, k):
    c.elipse((205, 140, 70), k * 1.0, k * 0.62)
    c.elipse((226, 170, 96), k * 0.8, k * 0.4, (0, k * 0.06))
    for dx in (-0.2, 0.0, 0.2):
        c.rect((150, 96, 48), k * 0.05, k * 0.2, (dx * k, k * 0.07), rot=35)


def _cafe(c, k):
    c.elipse(estilo.PAPEL, k * 0.2, k * 0.22, (k * 0.36, -k * 0.02))
    c.elipse(estilo.COLOR_TARJETA, k * 0.1, k * 0.12, (k * 0.36, -k * 0.02))
    c.rect(estilo.PAPEL, k * 0.62, k * 0.52, (0, -k * 0.06))
    c.rect((90, 56, 34), k * 0.52, k * 0.09, (0, k * 0.15))
    for dx in (-0.12, 0.12):
        c.rect(estilo.COLOR_TEXTO_TENUE, k * 0.04, k * 0.2, (dx * k, k * 0.38), rot=12)


def _bollo(c, k):
    c.elipse((214, 160, 90), k * 0.92, k * 0.82)
    c.elipse((240, 150, 180), k * 0.7, k * 0.52, (0, k * 0.06))
    c.elipse(estilo.COLOR_TARJETA, k * 0.2, k * 0.17, (0, -k * 0.02))
    for dx, dy in ((-0.2, 0.15), (0.18, 0.17), (0.0, 0.26), (-0.28, 0.0), (0.26, 0.02)):
        c.rect(estilo.PAPEL, k * 0.04, k * 0.1, (dx * k, dy * k), rot=40)


def _leche(c, k):
    c.rect((245, 245, 250), k * 0.46, k * 0.62, (0, -k * 0.05))
    c.forma("triangulo", (225, 225, 235), (k * 0.46, k * 0.2), (0, k * 0.36))
    c.rect((80, 140, 214), k * 0.46, k * 0.18, (0, -k * 0.08))
    c.elipse(estilo.PAPEL, k * 0.16, k * 0.12, (0, -k * 0.08))


def _arroz(c, k):
    c.rect((236, 226, 186), k * 0.58, k * 0.74, (0, -k * 0.02))
    c.rect((200, 188, 140), k * 0.58, k * 0.1, (0, k * 0.33))
    c.elipse((70, 150, 90), k * 0.3, k * 0.22, (0, -k * 0.02))
    for dx, dy in ((-0.1, 0.1), (0.1, 0.06), (0.0, -0.15)):
        c.elipse(estilo.PAPEL, k * 0.05, k * 0.1, (dx * k, dy * k - 0.0), rot=30)


def _feijao(c, k):
    c.elipse(estilo.COLOR_PANEL, k * 0.95, k * 0.62, (0, -k * 0.12))
    for dx, dy, r in ((-0.26, -0.02, 20), (0.0, 0.04, -15), (0.25, 0.0, 30), (-0.12, -0.2, -25), (0.14, -0.2, 10)):
        c.elipse((120, 56, 40), k * 0.28, k * 0.18, (dx * k, dy * k), rot=r)
        c.elipse((160, 92, 64), k * 0.12, k * 0.06, (dx * k, (dy + 0.03) * k), rot=r)


def _jabon(c, k):
    c.forma(modelo_redondeado(k * 0.7, k * 0.44, 4), (120, 190, 235), (k * 0.7, k * 0.44), (0, -k * 0.1))
    c.rect(estilo.PAPEL, k * 0.4, k * 0.06, (0, -k * 0.1))
    for dx, dy, r in ((-0.22, 0.3, 0.2), (0.0, 0.4, 0.14), (0.24, 0.28, 0.16)):
        c.elipse((200, 235, 250), k * r, k * r, (dx * k, dy * k))


def _mango(c, k):
    c.elipse((240, 170, 50), k * 0.74, k * 0.82)
    c.elipse((226, 96, 60), k * 0.4, k * 0.5, (k * 0.14, -k * 0.06))
    c.elipse((80, 160, 70), k * 0.3, k * 0.12, (-k * 0.02, k * 0.42), rot=-30)


def _banana(c, k):
    for dx, dy, r in ((-0.16, -0.04, 25), (0.0, 0.0, 8), (0.16, -0.04, -10)):
        c.elipse((245, 214, 70), k * 0.2, k * 0.84, (dx * k, dy * k), rot=r)
        c.elipse((200, 160, 40), k * 0.06, k * 0.14, (dx * k - k * 0.02, (dy - 0.38) * k), rot=r)
    c.rect((110, 90, 40), k * 0.12, k * 0.08, (0, k * 0.4))


def _tomate(c, k):
    c.elipse((214, 54, 48), k * 0.82, k * 0.74, (0, -k * 0.04))
    c.elipse((236, 110, 96), k * 0.2, k * 0.12, (-k * 0.18, k * 0.08), rot=30)
    for r in (0, 72, 144):
        c.elipse((70, 160, 80), k * 0.4, k * 0.1, (0, k * 0.3), rot=r)


def _yuca(c, k):
    c.elipse((190, 150, 100), k * 0.3, k * 0.95, rot=-55)
    c.elipse((226, 200, 160), k * 0.14, k * 0.7, (k * 0.04, k * 0.02), rot=-55)
    c.rect((110, 74, 46), k * 0.07, k * 0.07, (-k * 0.36, -k * 0.2), rot=-55)


def _agua(c, k):
    c.rect((150, 205, 240), k * 0.36, k * 0.66, (0, -k * 0.08))
    c.rect((150, 205, 240), k * 0.2, k * 0.16, (0, k * 0.32))
    c.rect((60, 110, 200), k * 0.24, k * 0.1, (0, k * 0.42))
    c.rect(estilo.PAPEL, k * 0.3, k * 0.18, (0, -k * 0.06))
    c.rect((90, 160, 220), k * 0.28, k * 0.03, (0, -k * 0.2))


def _refresco(c, k):
    c.rect((206, 52, 52), k * 0.44, k * 0.7)
    c.rect((200, 205, 215), k * 0.44, k * 0.07, (0, k * 0.35))
    c.rect((200, 205, 215), k * 0.44, k * 0.07, (0, -k * 0.35))
    c.rect(estilo.PAPEL, k * 0.44, k * 0.16)
    c.rect(estilo.TINTA, k * 0.2, k * 0.05)


def _salgado(c, k):
    c.elipse((222, 160, 56), k * 0.94, k * 0.7)
    c.elipse((244, 196, 100), k * 0.72, k * 0.42, (0, k * 0.07))
    for dx, dy in ((-0.2, 0.0), (0.04, 0.12), (0.22, -0.02), (-0.04, -0.14)):
        c.elipse((180, 110, 40), k * 0.06, k * 0.06, (dx * k, dy * k))


def _generico(c, k):
    c.rect((190, 160, 110), k * 0.6, k * 0.5)
    c.rect((150, 120, 76), k * 0.6, k * 0.08, (0, k * 0.2))


ICONOS = {"pan": _pan, "café": _cafe, "cafe": _cafe, "bollo": _bollo, "leche": _leche, "arroz": _arroz,
          "feijão": _feijao, "jabón": _jabon, "mango": _mango, "banana": _banana, "tomate": _tomate,
          "yuca": _yuca, "agua": _agua, "refresco": _refresco, "salgado": _salgado}


# Dibuja el icono de `producto` centrado en `pos` dentro de `padre`.
def dibujar_icono(padre, producto, pos, k=0.1, z=-0.004):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    Capa(contenedor, z=0).elipse(estilo.COLOR_PANEL, k * 1.18, k * 1.18)
    ICONOS.get(producto, _generico)(Capa(contenedor, z=-0.002), k)
    return contenedor


# Flecha dibujada con formas, apuntando a `direccion`.
def dibujar_flecha(padre, direccion, tono, lado, pos=(0, 0), z=-0.004):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    contenedor.rotation_z = ROTACION_FLECHA[direccion]
    c = Capa(contenedor, z=0)
    c.rect(tono, lado * 0.2, lado * 0.46, (0, -lado * 0.14))
    c.forma("triangulo", tono, (lado * 0.62, lado * 0.46), (0, lado * 0.2))
    return contenedor


def dibujar_marca_ok(padre, tono, lado, pos, z=-0.006):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    c = Capa(contenedor, z=0)
    c.rect(tono, lado * 0.1, lado * 0.3, (-lado * 0.09, -lado * 0.03), rot=-45)
    c.rect(tono, lado * 0.1, lado * 0.52, (lado * 0.11, lado * 0.04), rot=45)
    return contenedor


def dibujar_cliente(padre, numero, pos, escala=1.0):
    azar = random.Random(numero * 7919 + 13)
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], -0.004), scale=escala)
    c = Capa(contenedor, z=0)
    camisa, piel, pelo = azar.choice(CAMISAS), azar.choice(PIEL), azar.choice(PELO)
    c.forma(modelo_redondeado(0.15, 0.1, 8), camisa, (0.15, 0.1), (0, -0.045))
    c.rect(piel, 0.036, 0.03, (0, 0.012))
    c.elipse(piel, 0.1, 0.1, (0, 0.06))
    c.elipse(pelo, 0.108, 0.07, (0, 0.082))
    c.elipse(estilo.TINTA, 0.012, 0.014, (-0.02, 0.058))
    c.elipse(estilo.TINTA, 0.012, 0.014, (0.02, 0.058))
    c.rect(estilo.TINTA, 0.03, 0.006, (0, 0.036))
    return contenedor


class EscenaTrabajo(Escena):

    def __init__(self, **opciones):
        super().__init__(**opciones)
        # Fondo propio: tapa lo que quede detrás y no depende del color de la ventana.
        Entity(parent=self, model="quad", color=rgb(estilo.COLOR_FONDO), scale=(6, 3), z=1)
        self.raiz = Entity(parent=self)
        diseno_adaptable.ajustar_escala(self.raiz)
        self.marco = panel_tinta(self.raiz, ANCHO, ALTO, z=-0.02)
        self.estatico = Entity(parent=self.raiz, z=-0.03)
        self.juego = Entity(parent=self.raiz, z=-0.04)
        self.superpuesto = Entity(parent=self.raiz, z=-0.08)
        self.jugador = None
        self.trabajo = None
        self.turno = None
        self.fase = None
        self._al_terminar = None
        self._cerrado = True
        self._resultado = None
        self._t_resultado = 0.0
        self._feedback = ("", True, 0.0)
        self._firma_juego = None
        self._flash = {}
        self._tiles = []
        self._n_pedido = 0
        self._cliente = None
        self._barra = {}

    # -- Ciclo de vida --

    # jugador: el que trabaja. trabajo: backend Trabajo. al_terminar(resultado|None). semilla: pruebas.
    def al_entrar(self, jugador=None, trabajo=None, al_terminar=None, semilla=None, **datos):
        if trabajo is None:
            raise ValueError("EscenaTrabajo necesita un trabajo.")
        self._limpiar()
        self.jugador, self.trabajo, self._al_terminar = jugador, trabajo, al_terminar
        self.turno = TurnoTrabajo(trabajo, random.randrange(1 << 30) if semilla is None else semilla)
        self._cerrado = False
        self._resultado = None
        self._n_pedido = 0
        self._feedback = ("", True, 0.0)
        self._construir_estatico()
        self._mostrar_intro()

    def al_salir(self):
        self._limpiar()

    def _limpiar(self):
        for padre in (self.estatico, self.juego, self.superpuesto):
            for hijo in list(padre.children):
                destruir_arbol(hijo)
        self._tiles, self._flash, self._barra, self._cliente = [], {}, {}, None
        self._firma_juego = None
        self.fase = None

    # -- Bucle --

    def update(self):
        if self.fase is not None:
            self.avanzar(min(time.dt, DT_MAX))

    def avanzar(self, dt):
        if self.fase == RESULTADO:
            self._t_resultado = max(0.0, self._t_resultado - dt)
            return
        if self.fase != JUGANDO:
            return
        self.turno.avanzar(dt)
        texto, ok, restante = self._feedback
        if restante > 0:
            self._feedback = (texto, ok, max(0.0, restante - dt))
        for indice in list(self._flash):
            self._flash[indice] -= dt
            if self._flash[indice] <= 0:
                del self._flash[indice]
        self._refrescar()
        if self.turno.terminado():
            self._mostrar_resultado()

    def input(self, key):
        if self.enabled:
            self.entrada(key)

    # Entrada de teclado (también la usan las pruebas con teclas sintéticas).
    def entrada(self, key):
        if self._cerrado or self.fase is None:
            return False
        if key == "escape":
            self.abandonar()
            return True
        if self.fase == INTRO:
            if key in ("space", "enter", "return"):
                self.empezar()
                return True
            return False
        if self.fase == RESULTADO:
            if key in ("space", "enter", "return"):
                self.continuar()
                return True
            return False
        motor = self.trabajo.motor
        if motor == ATENDER and key in TECLAS_PRODUCTO:
            return self.accion(TECLAS_PRODUCTO[key])
        if motor == SECUENCIA and key in TECLAS_DIRECCION:
            return self.accion(TECLAS_DIRECCION[key])
        if motor == BARRA and key == "space":
            return self.accion(None)
        return False

    # -- Flujo --

    def empezar(self):
        if self.fase != INTRO:
            return
        for hijo in list(self.superpuesto.children):
            destruir_arbol(hijo)
        self.fase = JUGANDO
        self._firma_juego = None
        self._refrescar()

    # Una acción del jugador sobre el turno; True = acierto. Ignorada fuera de JUGANDO.
    def accion(self, entrada):
        if self.fase != JUGANDO or self.turno.terminado():
            return False
        motor = self.trabajo.motor
        antes_pos = self.turno.posicion_barra() if motor == BARRA else None
        pedido_antes = self.turno.pedido_texto() if motor == ATENDER else None
        acierto = self.turno.accion(entrada)
        if motor == ATENDER:
            indice = entrada - 1
            self._flash[indice] = DURACION_FLASH
            self._tiles_flash = acierto
            if acierto and not self.turno.entregado():
                self._n_pedido += 1
                self._decir(f"Bien: pedido completo ({pedido_antes})", True)
            elif acierto:
                self._decir(f"Bien: {self.trabajo.opciones[indice]}", True)
            else:
                self._decir("Error: de más o equivocado, el pedido empieza de nuevo", False)
        elif motor == SECUENCIA:
            if acierto:
                self._decir("Bien", True)
            else:
                self._decir("Error: empiezas la secuencia otra vez", False)
            self._flash["seq"] = DURACION_FLASH
            self._seq_ok = acierto
        else:
            self._barra_parada = (antes_pos, acierto)
            self._flash["barra"] = 0.6
            self._decir("Bien: en la zona" if acierto else "Error: fuera de la zona", acierto)
        self._firma_juego = None
        self._refrescar()
        if self.turno.terminado():
            self._mostrar_resultado()
        return acierto

    def _decir(self, texto, ok):
        self._feedback = (texto, ok, DURACION_FEEDBACK)

    def abandonar(self):
        self._cerrar(None)

    def continuar(self):
        if self.fase == RESULTADO and self._t_resultado <= 0:
            self._cerrar(self._resultado)

    def _cerrar(self, resultado):
        if self._cerrado:
            return
        self._cerrado = True
        callback = self._al_terminar
        if callback is not None:
            callback(resultado)

    def terminar_ya(self):
        # Acaba el turno en el acto (las pruebas y el botón de depuración); equivale a agotar el tiempo.
        if self.fase == JUGANDO:
            self.turno.avanzar(self.turno.tiempo_restante() + 1)
            self._mostrar_resultado()

    # -- Dibujo fijo --

    def _perfil(self):
        return perfil_de(self.jugador) if self.jugador is not None else None

    def _construir_estatico(self):
        d, t = self.estatico, self.trabajo
        izq, der = -ANCHO / 2 + 0.04, ANCHO / 2 - 0.04
        _texto(d, t.nombre, 26, estilo.COLOR_ACENTO, (izq, 0.375), (-0.5, 0), negrita=True)
        pago = f"Turno de {int(t.duracion_s)} s · paga R$ {t.pago_base} a {t.pago_max}"
        _texto(d, pago, 14, estilo.COLOR_TEXTO_TENUE, (der, 0.378), (0.5, 0))
        _linea(d, ANCHO - 0.08, (0, 0.335))
        _texto(d, "Tiempo", 14, estilo.COLOR_TEXTO_TENUE, (izq, 0.285), (-0.5, 0))
        self._ancho_t = ANCHO - 0.08 - 0.2
        self._x_t = izq + 0.1
        _caja(d, self._ancho_t, 0.034, estilo.TINTA, (self._x_t + self._ancho_t / 2, 0.285), 5)
        self._relleno_t = Entity(parent=d, model="quad", color=rgb(estilo.COLOR_BARRA_ALTO), origin=(-0.5, 0),
                                 scale=(self._ancho_t - 0.008, 0.026), position=(self._x_t + 0.004, 0.285, -0.004))
        self._t_tiempo = _texto(d, "", 16, estilo.COLOR_TEXTO, (der, 0.285), (0.5, 0), negrita=True)
        self._t_aciertos = _texto(d, "", 18, estilo.COLOR_TEXTO, (izq, 0.222), (-0.5, 0), negrita=True)
        self._t_errores = _texto(d, "", 18, estilo.COLOR_TEXTO, (izq + 0.3, 0.222), (-0.5, 0), negrita=True)
        self._t_rend = _texto(d, "", 14, estilo.COLOR_TEXTO_TENUE, (der, 0.222), (0.5, 0))
        _linea(d, ANCHO - 0.08, (0, 0.185))
        self._t_feedback = _texto(d, "", 20, estilo.COLOR_TEXTO, (0, -0.292), negrita=True)
        _linea(d, ANCHO - 0.08, (0, -0.32))
        ti = _texto(d, INSTRUCCIONES[t.motor], 15, estilo.COLOR_TEXTO, (0, -0.352))
        diseno_adaptable.ajustar_texto(ti, ANCHO - 0.1, escala_min=0.6, max_lineas=2)
        _texto(d, "Esc: abandonar el turno (sin paga)", 12, estilo.COLOR_TEXTO_TENUE, (0, -0.405))

    # -- Intro y resultado --

    def _mostrar_intro(self):
        self.fase = INTRO
        s, t = self.superpuesto, self.trabajo
        for hijo in list(s.children):
            destruir_arbol(hijo)
        self._velo(s)
        panel = panel_tinta(s, 0.9, 0.5, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX, z=0)
        _texto(panel, "Tu turno", 15, estilo.COLOR_TEXTO_TENUE, (0, 0.205), z=-0.01)
        _texto(panel, t.nombre, 28, estilo.COLOR_ACENTO, (0, 0.155), negrita=True, z=-0.01)
        texto = INSTRUCCIONES[t.motor] + (" " + TEMAS[t.id] if t.id in TEMAS else "")
        cuerpo = _texto(panel, texto, 17, estilo.COLOR_TEXTO, (0, 0.04), z=-0.01)
        diseno_adaptable.ajustar_texto(cuerpo, 0.8, escala_min=0.6, max_lineas=4)
        perfil = self._perfil()
        extra = f"Turno de {int(t.duracion_s)} s · paga R$ {t.pago_base} a {t.pago_max} · cansancio +{t.fatiga}"
        if perfil is not None:
            extra += f" (ahora {perfil.fatiga}/{FATIGA_MAX})"
        e = _texto(panel, extra, 14, estilo.COLOR_TEXTO_TENUE, (0, -0.075), z=-0.01)
        diseno_adaptable.ajustar_texto(e, 0.84, escala_min=0.6)
        BotonPrimario("Empezar (Espacio)", al_clic=self.empezar, ancho=0.46, alto=0.075, tamano_fuente_px=22,
                      parent=panel, position=(0, -0.17, -0.02))

    def _mostrar_resultado(self):
        if self.fase == RESULTADO:
            return
        self.fase = RESULTADO
        self._t_resultado = ESPERA_RESULTADO
        r = self._resultado = self.turno.resultado()
        self._refrescar()
        for hijo in list(self.juego.children):
            destruir_arbol(hijo)
        self._tiles, self._barra, self._cliente, self._firma_juego = [], {}, None, None
        s = self.superpuesto
        for hijo in list(s.children):
            destruir_arbol(hijo)
        self._velo(s)
        panel = panel_tinta(s, 0.9, 0.66, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX, z=0)
        _texto(panel, "TURNO TERMINADO", 28, estilo.COLOR_ACENTO, (0, 0.265), negrita=True, z=-0.01)
        _texto(panel, self._valoracion(r["rendimiento"]), 16, estilo.COLOR_TEXTO_TENUE, (0, 0.215), z=-0.01)
        _texto(panel, f"Aciertos: {r['aciertos']}", 20, estilo.COLOR_TEXTO, (-0.2, 0.15), negrita=True, z=-0.01)
        _texto(panel, f"Errores: {r['errores']}", 20, estilo.COLOR_TEXTO, (0.2, 0.15), negrita=True, z=-0.01)
        _linea(panel, 0.78, (0, 0.105), z=-0.01)
        _texto(panel, "Pago ganado", 15, estilo.COLOR_TEXTO_TENUE, (0, 0.07), z=-0.01)
        _texto(panel, f"+R$ {r['pago']}", 40, estilo.COLOR_ACENTO, (0, 0.012), negrita=True, z=-0.01)
        perfil = self._perfil()
        antes = perfil.fatiga if perfil is not None else 0
        despues = min(FATIGA_MAX, antes + r["fatiga"])
        _texto(panel, f"Cansancio: +{r['fatiga']} (ahora {despues}/{FATIGA_MAX})", 17, estilo.COLOR_TEXTO,
               (0, -0.07), z=-0.01)
        if despues >= FATIGA_MAX:
            aviso = _texto(panel, MENSAJE_AGOTADO, 17, ROJO_TEXTO, (0, -0.115), negrita=True, z=-0.01)
            diseno_adaptable.ajustar_texto(aviso, 0.84, escala_min=0.6)
        self._boton_continuar = BotonPrimario("Continuar (Enter)", al_clic=self.continuar, ancho=0.46, alto=0.075,
                                              tamano_fuente_px=22, parent=panel, position=(0, -0.24, -0.02))

    # Velo translúcido sobre el juego, para que el panel de intro/resultado se lea limpio.
    @staticmethod
    def _velo(padre):
        Entity(parent=padre, model=modelo_redondeado(ANCHO, ALTO, estilo.RADIO_PANEL_PX),
               color=color.rgba32(*estilo.TINTA, 215), scale=(ANCHO, ALTO), position=(0, 0, 0.01))

    @staticmethod
    def _valoracion(rendimiento):
        if rendimiento >= 0.8:
            return "Excelente turno"
        if rendimiento >= 0.5:
            return "Buen turno"
        if rendimiento >= 0.2:
            return "Turno regular"
        return "Puedes mejorar"

    # -- Refresco por fotograma --

    def _refrescar(self):
        if self.turno is None:
            return
        t = self.turno
        restante = t.tiempo_restante()
        fraccion = restante / self.trabajo.duracion_s
        self._relleno_t.scale_x = max(0.0001, (self._ancho_t - 0.008) * fraccion)
        self._relleno_t.color = rgb(estilo.rgb_por_valor(fraccion * 100))
        self._poner(self._t_tiempo, f"{math.ceil(restante)} s")
        r = t.resultado()
        self._poner(self._t_aciertos, f"Aciertos: {r['aciertos']}")
        self._poner(self._t_errores, f"Errores: {r['errores']}")
        self._poner(self._t_rend, f"Rendimiento: {round(r['rendimiento'] * 100)} %")
        texto, ok, resta = self._feedback
        tema = TEMAS.get(self.trabajo.id, "")
        self._poner(self._t_feedback, texto if resta > 0 else tema)
        self._t_feedback.color = rgb((estilo.ESTADO_EXITO if ok else ROJO_TEXTO) if resta > 0 else estilo.COLOR_TEXTO_TENUE)
        if self.fase == JUGANDO:
            motor = self.trabajo.motor
            if motor == ATENDER:
                self._juego_atender()
            elif motor == SECUENCIA:
                self._juego_secuencia()
            else:
                self._juego_barra()

    @staticmethod
    def _poner(texto, cadena):
        if texto.text != cadena:
            texto.text = _seguro(cadena)

    def _vaciar_juego(self):
        for hijo in list(self.juego.children):
            destruir_arbol(hijo)
        self._tiles, self._barra, self._cliente = [], {}, None

    # -- ATENDER --

    def _juego_atender(self):
        t = self.turno
        entregado = t.entregado()
        firma = (self._n_pedido, tuple(sorted(entregado.items())), tuple(sorted(self._flash)),
                 getattr(self, "_tiles_flash", True))
        if firma == self._firma_juego:
            return
        self._firma_juego = firma
        self._vaciar_juego()
        d = self.juego
        _cliente_x, y_cli = -0.4, 0.045
        dibujar_cliente(d, self._n_pedido, (_cliente_x, y_cli), 1.0)
        burbuja = panel_tinta(d, 0.72, 0.19, tono=estilo.PAPEL, radio_px=estilo.RADIO_TARJETA_PX, z=-0.004,
                              position=(0.17, 0.085))
        _texto(burbuja, "El cliente pide", 13, estilo.TINTA, (0, 0.06), z=-0.01)
        pedido = _texto(burbuja, t.pedido_texto(), 32, estilo.TINTA, (0, 0.008), negrita=True, z=-0.01)
        diseno_adaptable.ajustar_texto(pedido, 0.66, escala_min=0.5)
        partes = []
        for producto, n in t.pedido().items():
            dado = entregado.get(producto, 0)
            partes.append(f"{producto} {dado}/{n}" + (" (listo)" if dado >= n else ""))
        prog = _texto(burbuja, "Entregado: " + " · ".join(partes), 14, estilo.TINTA, (0, -0.062), z=-0.01)
        diseno_adaptable.ajustar_texto(prog, 0.66, escala_min=0.5)
        for i, producto in enumerate(self.trabajo.opciones):
            x = -0.39 + 0.26 * i
            self._tile_producto(d, i, producto, (x, -0.165))

    def _tile_producto(self, d, i, producto, pos):
        flash = self._flash.get(i)
        tono = estilo.COLOR_TARJETA
        if flash:
            tono = estilo.COLOR_BARRA_ALTO if getattr(self, "_tiles_flash", True) else estilo.ESTADO_ERROR
        tile = panel_tinta(d, 0.21, 0.16, tono=tono, radio_px=estilo.RADIO_TARJETA_PX, z=-0.004,
                           position=pos, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
        dibujar_icono(tile, producto, (0, 0.022), 0.09)
        n = _texto(tile, producto.capitalize(), 16, estilo.COLOR_TEXTO, (0, -0.058), negrita=True, z=-0.012)
        diseno_adaptable.ajustar_texto(n, 0.19, escala_min=0.6)
        # Insignia con el número de la tecla.
        Entity(parent=tile, model="circle", color=rgb(estilo.PAPEL), scale=(0.04, 0.04), position=(-0.078, 0.052, -0.01))
        _texto(tile, str(i + 1), 17, estilo.TINTA, (-0.078, 0.052), negrita=True, z=-0.014)
        boton = Button(parent=tile, model="quad", scale=(0.21, 0.16), color=color.clear,
                       highlight_color=color.rgba(1, 1, 1, 0.12), pressed_color=color.rgba(1, 1, 1, 0.2),
                       position=(0, 0, -0.02), on_click=lambda n=i + 1: self.accion(n))
        boton.collider = "box"
        self._tiles.append(tile)

    # -- SECUENCIA --

    def _juego_secuencia(self):
        t = self.turno
        secuencia, progreso = t.secuencia(), t.progreso()
        firma = (tuple(secuencia), progreso, "seq" in self._flash, getattr(self, "_seq_ok", True))
        if firma == self._firma_juego:
            return
        self._firma_juego = firma
        self._vaciar_juego()
        d = self.juego
        n, lado, hueco = len(secuencia), 0.13, 0.026
        total = n * lado + (n - 1) * hueco
        x0 = -total / 2 + lado / 2
        error = "seq" in self._flash and not getattr(self, "_seq_ok", True)
        for i, direccion in enumerate(secuencia):
            hecho, actual = i < progreso, i == progreso
            if error:
                tono, tinta = estilo.ESTADO_ERROR, estilo.PAPEL
            elif hecho:
                tono, tinta = estilo.COLOR_BARRA_ALTO, estilo.TINTA
            elif actual:
                tono, tinta = estilo.COLOR_ACENTO, estilo.TINTA
            else:
                tono, tinta = estilo.COLOR_TARJETA, estilo.PAPEL
            pos = (x0 + i * (lado + hueco), 0.07 + (0.012 if actual else 0))
            tile = panel_tinta(d, lado, lado, tono=tono, radio_px=estilo.RADIO_TARJETA_PX, z=-0.004, position=pos,
                               borde_px=estilo.GROSOR_BORDE_PX if actual else estilo.GROSOR_BORDE_DENSO_PX)
            dibujar_flecha(tile, direccion, tinta, lado * 0.8)
            if hecho and not error:
                dibujar_marca_ok(tile, estilo.TINTA, lado * 0.42, (lado * 0.3, lado * 0.3))
        if progreso < n:
            _texto(d, f"Ahora: {NOMBRE_DIRECCION[secuencia[progreso]]}   ({progreso}/{n})", 24, estilo.COLOR_TEXTO,
                   (0, -0.045), negrita=True, z=-0.004)
        for i, (direccion, texto) in enumerate((("izquierda", "Izquierda"), ("abajo", "Abajo"), ("arriba", "Arriba"),
                                                ("derecha", "Derecha"))):
            BotonSecundario(texto, al_clic=lambda dr=direccion: self.accion(dr), ancho=0.2, alto=0.07,
                            tamano_fuente_px=18, parent=d, position=(-0.33 + 0.22 * i, -0.17, -0.004))

    # -- BARRA --

    def _juego_barra(self):
        t = self.turno
        if not self._barra:
            self._vaciar_juego()
            self._construir_barra()
        b = self._barra
        ini, fin = t.zona_barra()
        x0 = -ANCHO_BARRA / 2
        centro = x0 + (ini + fin) / 2 * ANCHO_BARRA
        ancho = (fin - ini) * ANCHO_BARRA
        b["zona"].position = (centro, 0.03, -0.006)
        b["zona"].scale = (ancho, 0.07)
        b["borde_i"].position = (centro - ancho / 2, 0.03, -0.008)
        b["borde_d"].position = (centro + ancho / 2, 0.03, -0.008)
        b["etiqueta"].position = (centro, 0.105, -0.01)
        b["marca"].position = (x0 + t.posicion_barra() * ANCHO_BARRA, 0.03, -0.012)
        parada = getattr(self, "_barra_parada", None)
        if "barra" in self._flash and parada is not None:
            b["fantasma"].enabled = True
            b["fantasma"].position = (x0 + parada[0] * ANCHO_BARRA, 0.03, -0.011)
            b["fantasma"].color = rgb(estilo.COLOR_BARRA_ALTO if parada[1] else estilo.ESTADO_ERROR)
        else:
            b["fantasma"].enabled = False

    def _construir_barra(self):
        d, b = self.juego, self._barra
        _caja(d, ANCHO_BARRA + 0.02, 0.09, estilo.TINTA, (0, 0.03), 8, -0.003)
        _caja(d, ANCHO_BARRA, 0.07, estilo.COLOR_BARRA_FONDO, (0, 0.03), 6, -0.004)
        b["zona"] = Entity(parent=d, model="quad", color=rgb(estilo.COLOR_BARRA_ALTO), scale=(0.1, 0.07))
        b["borde_i"] = Entity(parent=d, model="quad", color=rgb(estilo.PAPEL), scale=(0.008, 0.09))
        b["borde_d"] = Entity(parent=d, model="quad", color=rgb(estilo.PAPEL), scale=(0.008, 0.09))
        b["etiqueta"] = _texto(d, "ZONA", 18, estilo.COLOR_BARRA_ALTO, (0, 0.105), negrita=True)
        b["marca"] = Entity(parent=d)
        Entity(parent=b["marca"], model="quad", color=rgb(estilo.COLOR_ACENTO), scale=(0.014, 0.12))
        Entity(parent=b["marca"], model=_triangulo(), color=rgb(estilo.COLOR_ACENTO), scale=(0.04, 0.03),
               position=(0, 0.075, 0), rotation_z=180)
        b["fantasma"] = Entity(parent=d, model="quad", color=rgb(estilo.PAPEL), scale=(0.01, 0.1), enabled=False)
        _texto(d, "ZONA = donde hay que parar la marca amarilla", 14, estilo.COLOR_TEXTO_TENUE, (0, -0.045),
               z=-0.004)
        BotonPrimario("DETENER (Espacio)", al_clic=lambda: self.accion(None), ancho=0.5, alto=0.09,
                      tamano_fuente_px=24, parent=d, position=(0, -0.16, -0.004))
