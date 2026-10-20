# Cálculos del HUD del mundo (Python puro: NO importa ursina, se prueba con pytest
# sin ventana). Reúne lo que TelefonoUI, Minimapa, AvisoInteraccion y la ruta del
# mundo necesitan decidir: qué mostrar en cada estado del teléfono, cuándo recalcular
# la ruta del GPS y cómo se dibuja el minimapa (escala, puntos, segmentos, flecha).
#
# Regla: el modelo manda (Telefono, FlujoPartida, MapaCiudad); aquí solo se traduce
# su estado a "qué dibujar". Las clases de frontend/hud.py lo ejecutan en Ursina.

import math
from dataclasses import dataclass

from backend.logica import navegacion
from backend.logica.misiones import EN_RADIO
from backend.logica.telefono import ABIERTO, NOTIFICANDO
from frontend import geometria_mundo

# -- Animación determinista ----------------------------------------------------


# Acerca `valor` a `objetivo` como máximo `paso` (lineal, sin sobrepasar). Es la base
# de las animaciones del HUD: dependen solo de la suma de los dt, así que se pueden
# avanzar a mano en un test.
def avanzar_hacia(valor, objetivo, paso):
    if valor < objetivo:
        return min(objetivo, valor + paso)
    return max(objetivo, valor - paso)


# Interpolación lineal.
def mezclar(a, b, t):
    return a + (b - a) * t


# -- Aviso de interacción ------------------------------------------------------


# "Presiona E para acceder" solo con la misión EN_RADIO y el teléfono sin abrir.
def aviso_visible(estado_mision, estado_telefono):
    return estado_mision == EN_RADIO and estado_telefono != ABIERTO


# -- Teléfono ------------------------------------------------------------------

ENCABEZADO_TELEFONO = "Civitas"
TEXTO_SIN_MISION = "Sin misión activa"
MODO_ICONO = "icono"
MODO_NOTIFICACION = "notificacion"
MODO_ABIERTO = "abierto"


@dataclass(frozen=True)
class FilaMensaje:
    remitente: str
    texto: str
    resaltado: bool          # mensaje que estaba sin leer al abrir el teléfono


@dataclass(frozen=True)
class VistaTelefono:
    modo: str                # MODO_ICONO / MODO_NOTIFICACION / MODO_ABIERTO
    contador: int            # no leídos (la insignia del ícono se oculta con 0)
    texto_notificacion: str  # último mensaje (lo que muestra el banner)
    encabezado: str
    linea_mision: str
    linea_destino: str       # "" si no hay misión
    filas: tuple             # FilaMensaje, los más recientes primero


_MODO_POR_ESTADO = {ABIERTO: MODO_ABIERTO, NOTIFICANDO: MODO_NOTIFICACION}


# Qué mostrar según el estado del teléfono. `mision`: Mision actual o None.
# `nuevos_al_abrir`: cuántos mensajes (los más recientes) estaban sin leer justo antes
# de abrir; abrir() los marca leídos de inmediato, así que la vista los recuerda para
# resaltarlos. Dos vistas iguales dibujan lo mismo (dataclass congelada).
def vista_telefono(telefono, mision, nuevos_al_abrir=0):
    mensajes = telefono.mensajes()
    filas = tuple(
        FilaMensaje(m.remitente, m.texto, resaltado=(indice < nuevos_al_abrir) or not m.leido)
        for indice, m in enumerate(reversed(mensajes))
    )
    if mision is None:
        linea_mision, linea_destino = TEXTO_SIN_MISION, ""
    else:
        linea_mision, linea_destino = f"Misión: {mision.titulo}", f"Destino: {mision.destino}"
    return VistaTelefono(
        modo=_MODO_POR_ESTADO.get(telefono.estado(), MODO_ICONO),
        contador=telefono.no_leidos(),
        texto_notificacion=mensajes[-1].texto if mensajes else "",
        encabezado=ENCABEZADO_TELEFONO,
        linea_mision=linea_mision,
        linea_destino=linea_destino,
        filas=filas,
    )


# -- Ruta del GPS (se comparte entre el minimapa y el mundo) --------------------


# Zona en la que está el punto, como clave hashable: ("plaza", L), ("calle", a, b,
# extremo_mas_cercano) o ("fuera", L). El extremo más cercano entra en la clave porque
# desempata la ruta a mitad de una calle (calcular_ruta_gps).
def clave_de_zona(mapa, x, z):
    lugar = mapa.lugar_en_plaza(x, z)
    if lugar is not None:
        return ("plaza", lugar)
    calle = mapa.calle_en(x, z)
    if calle is None:
        return ("fuera", mapa.lugar_mas_cercano(x, z))
    a, b = calle
    (xa, za), (xb, zb) = mapa.coordenada(a), mapa.coordenada(b)
    cercano = a if math.hypot(x - xa, z - za) <= math.hypot(x - xb, z - zb) else b
    return ("calle", a, b, cercano)


# Mantiene la ruta BFS del jugador al destino y SOLO la recalcula cuando cambia la
# zona (lugar/calle) o el destino: no en cada frame. Si el jugador se desvía a otra
# calle, la clave cambia y la ruta se rehace sola (como el GPS de GTA V).
class GuiaRuta:

    def __init__(self, mapa):
        self._mapa = mapa
        self._clave = None
        self.destino = None
        self.ruta = []           # lugares que faltan; ruta[0] = siguiente esquina
        self.recalculos = 0      # cuántas veces se calculó (lo usan los tests)

    # Devuelve True si la ruta cambió. destino None = sin misión: sin ruta.
    def actualizar(self, x, z, destino):
        if destino is None:
            cambio = self._clave is not None
            self._clave, self.destino, self.ruta = None, None, []
            return cambio
        clave = clave_de_zona(self._mapa, x, z) + (destino,)
        if clave == self._clave:
            return False
        self._clave, self.destino = clave, destino
        self.ruta = navegacion.calcular_ruta_gps(self._mapa, x, z, destino)
        self.recalculos += 1
        return True

    def siguiente_esquina(self):
        return self.ruta[0] if self.ruta else None


# -- Ruta en el mundo ----------------------------------------------------------


# Puntos (x, z) por los que pasa la ruta: el jugador y luego cada lugar de la ruta.
def puntos_de_ruta(mapa, x, z, ruta):
    if not ruta:
        return []
    return [(x, z)] + [mapa.coordenada(lugar) for lugar in ruta]


# (cx, cz, largo, rumbo) de un cubo plano que cubre el segmento p0-p1 en el mundo:
# misma convención que las calles (scale z = largo, rotation_y = rumbo).
def segmento_mundo(p0, p1):
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    return ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, math.hypot(dx, dz),
            geometria_mundo.rumbo_de(dx, dz))


# -- Minimapa ------------------------------------------------------------------

RELLENO_MINIMAPA = 0.012     # margen interno del minimapa (unidades de camera.ui)


# Caja (umin, umax, vmin, vmax), en unidades de MUNDO, que ocupa la zona transitable
# (todas las plazas con su radio; las calles quedan entre los centros, así que caben)
# después de girarla con el yaw de la cámara alrededor del centro de limites(), igual
# que a_minimapa. Es más ajustada que girar el rectángulo limites() entero (cuyas
# esquinas vacías sobresalen al rotar y achican el mapa), y nada transitable la excede.
def caja_rotada(mapa, yaw_grados):
    limites = mapa.limites()
    ancho, alto = limites[1] - limites[0], limites[3] - limites[2]
    puntos = [navegacion.a_minimapa(*mapa.coordenada(lugar), limites, (0, 0), (ancho, alto),
                                    yaw_grados) for lugar in mapa.lugares()]
    radio = mapa.radio_plaza
    return (min(u for u, _ in puntos) - radio, max(u for u, _ in puntos) + radio,
            min(v for _, v in puntos) - radio, max(v for _, v in puntos) + radio)


# Radio del círculo, centrado en el centro de limites(), que contiene todas las plazas (con su
# radio) y las esquinas de los edificios del mapa (si los tiene).
def _radio_envolvente(mapa, limites):
    cx, cz = (limites[0] + limites[1]) / 2, (limites[2] + limites[3]) / 2
    radio = max(math.hypot(x - cx, z - cz) + mapa.radio_plaza
                for x, z in (mapa.coordenada(lugar) for lugar in mapa.lugares()))
    edificios = getattr(mapa, "edificios", None)
    for edificio in (edificios() if callable(edificios) else []):
        xmin, xmax, zmin, zmax = edificio.caja()
        for x, z in ((xmin, zmin), (xmin, zmax), (xmax, zmin), (xmax, zmax)):
            radio = max(radio, math.hypot(x - cx, z - cz))
    return radio


# Todo lo que el minimapa dibuja, en coordenadas locales (u, v) con el origen en el
# CENTRO del minimapa (u a la derecha, v arriba). Rotado con el yaw de la cámara:
# arriba en el minimapa = arriba en la pantalla. Usa navegacion.a_minimapa con
# escala uniforme (no deforma): la mayor que deja caber caja_rotada() en `tamano`
# menos el relleno; la caja queda centrada.
#
# rotacion_libre (mundo 3D, el yaw cambia cada frame): la escala NO depende del yaw para que
# el mapa no "respire" al girar la cámara. Se usa el círculo que contiene toda la ciudad
# (plazas con su radio y las esquinas de los edificios, si el mapa los tiene) alrededor del
# centro de limites(), así que cabe con cualquier giro; `girar(yaw)` solo cambia el ángulo.
class GeometriaMinimapa:

    def __init__(self, mapa, tamano, yaw_grados, relleno=RELLENO_MINIMAPA, rotacion_libre=False):
        self._mapa = mapa
        self.tamano = tamano
        self.yaw = yaw_grados
        self.limites = mapa.limites()
        if rotacion_libre:
            radio = _radio_envolvente(mapa, self.limites)
            self.escala = (min(tamano) - 2 * relleno) / (2 * radio)
            umin = umax = vmin = vmax = 0.0       # caja centrada en el centro de limites()
        else:
            umin, umax, vmin, vmax = caja_rotada(mapa, yaw_grados)
            self.escala = min((tamano[0] - 2 * relleno) / (umax - umin),
                              (tamano[1] - 2 * relleno) / (vmax - vmin))
        xmin, xmax, zmin, zmax = self.limites
        # a_minimapa calcula min(w/ancho, h/alto): con este tamaño equivalente da `escala`.
        self._tamano_equivalente = ((xmax - xmin) * self.escala, (zmax - zmin) * self.escala)
        # Desplazamiento que centra la caja en el minimapa.
        self._centro = (-(umin + umax) / 2 * self.escala, -(vmin + vmax) / 2 * self.escala)

    # Cambia el yaw (solo útil con rotacion_libre: la escala y el centro no dependen de él).
    def girar(self, yaw_grados):
        self.yaw = yaw_grados

    def punto(self, x, z):
        return navegacion.a_minimapa(
            x, z, self.limites, self._centro, self._tamano_equivalente, self.yaw)

    def lugar(self, nombre):
        return self.punto(*self._mapa.coordenada(nombre))

    # Diámetro de la plaza y ancho de la calle ya escalados.
    def diametro_plaza(self):
        return 2 * self._mapa.radio_plaza * self.escala

    def ancho_calle(self):
        return self._mapa.ancho_calle * self.escala

    # [(p0, p1)] de cada calle del mapa.
    def calles(self):
        return [(self.lugar(a), self.lugar(b)) for a, b in self._mapa.segmentos()]

    # [(p0, p1)] de la ruta: del jugador a la siguiente esquina y de ahí al destino.
    def segmentos_ruta(self, x, z, ruta):
        puntos = [self.punto(*p) for p in puntos_de_ruta(self._mapa, x, z, ruta)]
        return list(zip(puntos, puntos[1:]))

    # (u, v, angulo) de la flecha del GPS: en el jugador, apuntando a la siguiente
    # esquina; angulo en grados desde "arriba" en sentido horario (angulo_hacia).
    # None si no hay ruta.
    def flecha(self, x, z, ruta):
        if not ruta:
            return None
        u0, v0 = self.punto(x, z)
        u1, v1 = self.lugar(ruta[0])
        return (u0, v0, navegacion.angulo_hacia(u0, v0, u1, v1))

    # True si el punto (u, v) está dentro del rectángulo del minimapa.
    def contiene(self, u, v, holgura=1e-9):
        return abs(u) <= self.tamano[0] / 2 + holgura and abs(v) <= self.tamano[1] / 2 + holgura

    # [(c0, c1, c2, c3)] con las esquinas (u, v) de cada casa (obstáculo de tipo "casa", caja
    # alineada a los ejes) rotadas con el yaw actual. Se descartan las casas con alguna esquina
    # fuera del minimapa: así el dibujo nunca se sale de su rectángulo. Orden de esquinas: el
    # contorno (sin diagonales), apto para dos triángulos (0,1,2) y (0,2,3).
    def cuadros_casas(self, obstaculos):
        cuadros = []
        for o in obstaculos:
            if o.tipo != "casa" or not o.es_caja:
                continue
            mx, mz = o.ancho / 2, o.fondo / 2
            esquinas = [self.punto(o.cx + dx, o.cz + dz)
                        for dx, dz in ((-mx, -mz), (mx, -mz), (mx, mz), (-mx, mz))]
            if all(self.contiene(u, v) for u, v in esquinas):
                cuadros.append(tuple(esquinas))
        return cuadros

    # [(p0, p1, ancho)] de cada escalera (extremos en (u, v) y ancho ya escalado); se descartan
    # las que tengan algún extremo fuera del minimapa.
    def segmentos_escaleras(self, escaleras):
        segmentos = []
        for e in escaleras:
            p0, p1 = self.punto(e.ax, e.az), self.punto(e.bx, e.bz)
            if self.contiene(*p0) and self.contiene(*p1):
                segmentos.append((p0, p1, e.ancho * self.escala))
        return segmentos


# Diferencia angular más corta entre dos yaw en grados, en [0, 180] (sin saltar al cruzar ±180).
def diferencia_yaw(a, b):
    return abs((a - b + 180) % 360 - 180)


# Esquinas (c0, c1, c2, c3) del rectángulo de grosor `ancho` centrado en el segmento p0-p1
# (mismo orden de contorno que cuadros_casas). Segmento de largo 0: rectángulo vacío en p0.
def segmento_a_rectangulo(p0, p1, ancho):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    largo = math.hypot(dx, dy)
    if largo == 0:
        return (p0, p0, p0, p0)
    nx, ny = -dy / largo * ancho / 2, dx / largo * ancho / 2
    return ((p0[0] - nx, p0[1] - ny), (p1[0] - nx, p1[1] - ny),
            (p1[0] + nx, p1[1] + ny), (p0[0] + nx, p0[1] + ny))


# (cu, cv, largo, rotacion_z) de un cuadro horizontal (largo en su eje x) que cubre el
# segmento p0-p1 del minimapa. rotation_z de Ursina gira en sentido HORARIO en
# pantalla (lo fija tests/test_hud_ventana.py); un cuadro horizontal apunta a 90 grados
# desde arriba, así que rotation_z = angulo_hacia - 90.
def segmento_a_cuadro(p0, p1):
    largo = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    angulo = navegacion.angulo_hacia(p0[0], p0[1], p1[0], p1[1])
    return ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, largo, angulo - 90)
