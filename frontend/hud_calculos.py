# Cálculos del HUD del mundo (Python puro: NO importa ursina, se prueba con pytest
# sin ventana). Reúne lo que TelefonoUI, Minimapa, AvisoInteraccion y la ruta del
# mundo necesitan decidir: qué mostrar en cada estado del teléfono, cuándo recalcular
# la ruta del GPS y cómo se dibuja el minimapa (escala, puntos, segmentos, flecha).
#
# Regla: el modelo manda (Telefono, FlujoPartida, MapaCiudad); aquí solo se traduce
# su estado a "qué dibujar". Las clases de frontend/hud.py lo ejecutan en Ursina.

import math
from dataclasses import dataclass

from backend.datos.nombres_visibles import glosar_texto, nombre_visible
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
# Casilla «Seguir misión» del panel (ver backend/logica/telefono.py): el estado se dice con texto, no solo
# con la marca, para quien no distingue colores.
TEXTO_SEGUIR = "Seguir misión"
TECLA_SEGUIR = "M"


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
    sigue_mision: bool = True    # casilla «Seguir misión» marcada (ayudas hacia el destino visibles)
    texto_seguir: str = ""       # «Seguir misión: Sí (M)»; "" si no hay misión (la casilla no se muestra)


_MODO_POR_ESTADO = {ABIERTO: MODO_ABIERTO, NOTIFICANDO: MODO_NOTIFICACION}


# Qué mostrar según el estado del teléfono. `mision`: Mision actual o None.
# `nuevos_al_abrir`: cuántos mensajes (los más recientes) estaban sin leer justo antes
# de abrir; abrir() los marca leídos de inmediato, así que la vista los recuerda para
# resaltarlos. Dos vistas iguales dibujan lo mismo (dataclass congelada).
# Los nombres brasileños se traducen solo aquí (nombres_visibles): los mensajes guardados siguen con el texto
# original (flujo_partida compara MENSAJE_SIN_MISIONES).
def vista_telefono(telefono, mision, nuevos_al_abrir=0):
    mensajes = telefono.mensajes()
    filas = tuple(
        FilaMensaje(m.remitente, glosar_texto(m.texto), resaltado=(indice < nuevos_al_abrir) or not m.leido)
        for indice, m in enumerate(reversed(mensajes))
    )
    sigue = sigue_mision(telefono)
    if mision is None:
        linea_mision, linea_destino, texto_seguir = TEXTO_SIN_MISION, "", ""
    else:
        linea_mision = f"Misión: {glosar_texto(mision.titulo)}"
        linea_destino = f"Destino: {nombre_visible(mision.destino)}"
        texto_seguir = texto_casilla_seguir(sigue)
    return VistaTelefono(
        modo=_MODO_POR_ESTADO.get(telefono.estado(), MODO_ICONO),
        contador=telefono.no_leidos(),
        texto_notificacion=glosar_texto(mensajes[-1].texto) if mensajes else "",
        encabezado=ENCABEZADO_TELEFONO,
        linea_mision=linea_mision,
        linea_destino=linea_destino,
        filas=filas,
        sigue_mision=sigue,
        texto_seguir=texto_seguir,
    )


# ¿El jugador sigue su misión? (casilla «Seguir misión»). Un teléfono sin la casilla (falsos de las pruebas) la sigue.
def sigue_mision(telefono):
    consulta = getattr(telefono, "sigue_mision", None)
    return bool(consulta()) if callable(consulta) else True


def texto_casilla_seguir(sigue):
    return f"{TEXTO_SEGUIR}: {'Sí' if sigue else 'No'} ({TECLA_SEGUIR})"


# El destino que el mundo dibuja (baliza, ruta, minimapa, bandera): el de la misión solo si el jugador la sigue.
def destino_visible(destino, sigue_mision):
    return destino if sigue_mision else None


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

    # Acota (u, v) al recuadro del minimapa dejando `margen` libre en el borde: así el punto del
    # jugador, el destino y la flecha nunca se salen aunque el jugador recorra fuera de limites().
    # Un punto que ya está dentro queda idéntico.
    def acotar(self, u, v, margen=0.0):
        mu = max(0.0, self.tamano[0] / 2 - margen)
        mv = max(0.0, self.tamano[1] / 2 - margen)
        return (max(-mu, min(mu, u)), max(-mv, min(mv, v)))

    # Recorta el segmento p0-p1 (u, v) al recuadro del minimapa (Liang-Barsky). Devuelve (q0, q1) o
    # None si queda por completo fuera. Un segmento ya dentro vuelve idéntico. Lo usa la ruta del GPS:
    # al recorrer fuera de limites() su primer tramo parte del jugador, que puede estar fuera.
    def recortar_segmento(self, p0, p1):
        hx, hy = self.tamano[0] / 2, self.tamano[1] / 2
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, p0[0] + hx), (dx, hx - p0[0]), (-dy, p0[1] + hy), (dy, hy - p0[1])):
            if p == 0:
                if q < 0:
                    return None
                continue
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return None
        if t0 == 0.0 and t1 == 1.0:
            return (p0, p1)
        return ((p0[0] + t0 * dx, p0[1] + t0 * dy), (p0[0] + t1 * dx, p0[1] + t1 * dy))

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


# -- Minimapa LOCAL (mundo grande) -------------------------------------------------------------------------------
#
# En el mundo grande (900 x 650 m, ~4.600 casas) ajustar toda la ciudad a 280 x 200 px da un rombo ilegible. El minimapa
# local enseña solo lo que rodea al jugador: una ventana de ±RADIO_VENTANA_MINIMAPA m (a lo ancho del recuadro; a lo alto
# caben menos metros), centrada en él y girada con la cámara como siempre (arriba = adelante). El jugador queda SIEMPRE
# en el centro (u, v) = (0, 0).
#
# Idea de rendimiento: lo que no se mueve (calles, plazas, casas) vive en una capa en coordenadas absolutas ESCALADAS
# (u = escala * x, v = escala * z, sin girar) y se coloca con UNA sola transformación por frame
# (transformacion_capa: posición + rotation_z). Girar la cámara o caminar no rehace ninguna malla; solo se rehacen las
# mallas de casas al cambiar el chunk del jugador (ver CacheCasasMinimapa). El mundo chico no pasa por aquí.

RADIO_VENTANA_MINIMAPA = 150.0    # m del centro al borde izquierdo/derecho del recuadro
MARGEN_FLECHA_BORDE = 0.016       # unidades de camera.ui que la flecha del destino deja libres hasta el borde
LADO_CHUNK_VENTANA = 64.0         # el de MundoGrande (backend/logica/mundo_grande.py)


class GeometriaMinimapaLocal(GeometriaMinimapa):

    def __init__(self, mapa, tamano, yaw_grados, centro=(0.0, 0.0), radio_ventana=RADIO_VENTANA_MINIMAPA,
                 relleno=RELLENO_MINIMAPA):
        self._mapa = mapa
        self.tamano = tamano
        self.limites = mapa.limites()
        self.radio_ventana = radio_ventana
        self.escala = (tamano[0] / 2 - relleno) / radio_ventana          # unidades de camera.ui por metro
        self.centro_mundo = (float(centro[0]), float(centro[1]))
        self.girar(yaw_grados)

    # El yaw cambia cada frame: se guardan seno y coseno.
    def girar(self, yaw_grados):
        self.yaw = yaw_grados
        theta = math.radians(yaw_grados)
        self._cos, self._sin = math.cos(theta), math.sin(theta)

    def centrar(self, x, z):
        self.centro_mundo = (float(x), float(z))

    # Misma rotación que navegacion.a_minimapa, pero con el centro en el jugador y la escala fija.
    def punto(self, x, z):
        dx, dz = x - self.centro_mundo[0], z - self.centro_mundo[1]
        return (self.escala * (dx * self._cos - dz * self._sin), self.escala * (dx * self._sin + dz * self._cos))

    # Coordenadas absolutas escaladas (la capa estática no gira ni se centra).
    def absoluto(self, x, z):
        return (self.escala * x, self.escala * z)

    # (px, py, rotation_z) de la capa estática para que sus puntos absolutos caigan donde dice punto(): rotación
    # alrededor del origen de la capa y traslación por el centro girado. rotation_z de Ursina es horario: -yaw.
    def transformacion_capa(self):
        u, v = self.punto(0.0, 0.0)
        return (u, v, -self.yaw)

    # Radio (m) del círculo alrededor del jugador que contiene el recuadro con cualquier giro.
    def radio_cobertura(self):
        return math.hypot(self.tamano[0] / 2, self.tamano[1] / 2) / self.escala

    # Lugares cuya plaza puede asomar en el recuadro.
    def lugares_en_ventana(self):
        limite = self.radio_cobertura() + self._mapa.radio_plaza
        cx, cz = self.centro_mundo
        return [n for n in self._mapa.lugares()
                if math.hypot(self._mapa.coordenada(n)[0] - cx, self._mapa.coordenada(n)[1] - cz) <= limite]

    # Chunks que hay que tener dibujados mientras el jugador esté en SU chunk actual: los que quedan a menos de
    # radio_cobertura() del rectángulo de ese chunk (así no se rehace nada hasta cambiar de chunk). [(ci, cj)].
    def chunks_de_ventana(self, mundo):
        return chunks_alrededor(mundo, mundo.chunk_de(*self.centro_mundo), self.radio_cobertura())

    # Flecha de borde hacia un punto del mundo fuera del recuadro: (u, v, angulo, metros) con (u, v) en el borde (con
    # `margen` libre) sobre el rayo centro -> punto, y angulo horario desde arriba (como GeometriaMinimapa.flecha).
    # None si el punto cae dentro del recuadro (entonces se dibuja su marca normal).
    def flecha_de_borde(self, x, z, margen=MARGEN_FLECHA_BORDE):
        u, v = self.punto(x, z)
        mu, mv = self.tamano[0] / 2 - margen, self.tamano[1] / 2 - margen
        if abs(u) <= mu and abs(v) <= mv:
            return None
        t = min(mu / abs(u) if u else math.inf, mv / abs(v) if v else math.inf)
        metros = math.hypot(x - self.centro_mundo[0], z - self.centro_mundo[1])
        return (u * t, v * t, navegacion.angulo_hacia(0.0, 0.0, u, v), metros)


# Chunks (ci, cj) de `mundo` a menos de `radio` m del rectángulo del chunk `centro`, ordenados.
def chunks_alrededor(mundo, centro, radio):
    ci0, cj0 = centro
    x0, x1, z0, z1 = mundo.limites_de_chunk(ci0, cj0)
    n = int(math.ceil(radio / LADO_CHUNK_VENTANA)) + 1
    resultado = []
    for ci in range(max(0, ci0 - n), min(mundo.chunks_x, ci0 + n + 1)):
        for cj in range(max(0, cj0 - n), min(mundo.chunks_z, cj0 + n + 1)):
            a0, a1, b0, b1 = mundo.limites_de_chunk(ci, cj)
            dx, dz = max(0.0, a0 - x1, x0 - a1), max(0.0, b0 - z1, z0 - b1)
            if math.hypot(dx, dz) <= radio:
                resultado.append((ci, cj))
    return resultado


# Casas (obstáculos tipo "casa", de caja) y escaleras que PERTENECEN a un chunk: cada una se asigna al chunk de su
# centro (el contenido de un chunk incluye lo que lo toca, y una casa en el borde saldría dos veces).
def casas_y_escaleras_de_chunk(mundo, ci, cj):
    contenido = mundo.contenido_de_chunk(ci, cj, 0.0)
    casas = [o for o in contenido["obstaculos"]
             if o.tipo == "casa" and o.es_caja and mundo.chunk_de(o.cx, o.cz) == (ci, cj)]
    escaleras = [e for e in contenido["escaleras"]
                 if mundo.chunk_de((e.ax + e.bx) / 2, (e.az + e.bz) / 2) == (ci, cj)]
    return casas, escaleras


_TRIANGULOS_CUADROS = []


# Triángulos (a, b, c) de `n` cuadriláteros de 4 vértices seguidos (mismo patrón que Minimapa._malla_de_cuadrilateros).
def triangulos_de_cuadros(n):
    while len(_TRIANGULOS_CUADROS) < 2 * n:
        base = 2 * len(_TRIANGULOS_CUADROS)
        _TRIANGULOS_CUADROS.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
    return _TRIANGULOS_CUADROS[:2 * n]


# Casas y escaleras ya convertidas a vértices absolutos escalados, por chunk, con un tope (LRU simple): el
# minimapa pide los de su ventana y solo calcula los que faltan. Python puro: se prueba con un mundo falso.
class CacheCasasMinimapa:

    def __init__(self, mundo, escala, ancho_min_escalera=0.003, maximo=160):
        self._mundo = mundo
        self._escala = escala
        self._ancho_min = ancho_min_escalera
        self._maximo = maximo
        self._chunks = {}                  # (ci, cj) -> (vertices de casas, vertices de escaleras)
        self.calculados = 0                # chunks calculados desde cero (lo usan las pruebas)

    def _calcular(self, ci, cj):
        k = self._escala
        casas, escaleras = casas_y_escaleras_de_chunk(self._mundo, ci, cj)
        vc = []
        for o in casas:
            mx, mz = o.ancho / 2, o.fondo / 2
            vc += [(k * (o.cx + dx), k * (o.cz + dz), 0.0) for dx, dz in ((-mx, -mz), (mx, -mz), (mx, mz), (-mx, mz))]
        ve = []
        for e in escaleras:
            rect = segmento_a_rectangulo((k * e.ax, k * e.az), (k * e.bx, k * e.bz), max(e.ancho * k, self._ancho_min))
            ve += [(u, v, 0.0) for u, v in rect]
        self.calculados += 1
        return vc, ve

    # (vertices_casas, vertices_escaleras) de los chunks pedidos, concatenados.
    def vertices(self, chunks):
        casas, escaleras = [], []
        for clave in chunks:
            if clave not in self._chunks:
                self._chunks[clave] = self._calcular(*clave)
            else:                                          # reciente: pasa al final del orden de inserción
                self._chunks[clave] = self._chunks.pop(clave)
            vc, ve = self._chunks[clave]
            casas += vc
            escaleras += ve
        sobran = len(self._chunks) - self._maximo
        if sobran > 0:
            for clave in [k for k in self._chunks if k not in set(chunks)][:sobran]:
                del self._chunks[clave]
        return casas, escaleras
