# HUD 2D del mundo (Ursina, en camera.ui): teléfono, minimapa, aviso de interacción
# y panel de turno (la ruta en el piso la dibuja frontend/marcadores_mundo.py).
# Todo se decide en frontend/hud_calculos.py (Python puro, con tests sin ventana);
# aquí solo se dibuja lo que el modelo dice. Coordenadas de camera.ui: y en
# [-0.5, 0.5] (0.5 = arriba), x en [-aspecto/2, aspecto/2].
#
# Nada de aquí usa update(): EscenaMundo llama a HudMundo.actualizar(dt) en su
# update(), así la escena desactivada no gasta nada y los tests avanzan las
# animaciones a mano con dt fijos (sin depender del reloj real).
#
# Fuente por defecto: no tiene flechas ni ✓ ★ ▲ (por eso la flecha del GPS es una
# malla propia) y Text interpreta "<...>" como etiquetas (por eso _seguro()).

from panda3d.core import TextNode
from ursina import Entity, Mesh, Text, camera, color, window

from backend.datos.nombres_visibles import nombre_visible
from backend.logica.roles import ROLES
from frontend import diseno_adaptable, diseno_adaptable_calculos, estilo, hud_calculos, iconos
from frontend.componentes import (
    BarraIndicador, BotonAccion, BotonPrimario, a_unidades, destruir_arbol, escala_fuente,
    modelo_redondeado, panel_tinta, rgb)
from frontend.texto import envolver_texto

MARGEN = 0.02                       # separación de los bordes de la pantalla
COLOR_FONDO_HUD = color.rgba32(12, 14, 24, 240)
COLOR_RUTA = estilo.COLOR_RUTA          # cian: la ruta (minimapa y mundo); fuente única en estilo.py
COLOR_DESTINO = estilo.COLOR_DESTINO    # amarillo: el destino (igual que la baliza del mundo)
COLOR_ALERTA = (214, 62, 62)        # insignia de no leídos
COLOR_RESALTADO = (62, 78, 138)     # mensaje sin leer en el teléfono


# Curva de salida cuadrática (rápida al inicio, suave al final) para t en [0, 1].
def _ease_out_quad(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


# Icono cuadrado del HUD (textura de frontend/iconos.py) de `lado` unidades de camera.ui.
def _icono(padre, nombre, lado, posicion, **opciones):
    return Entity(parent=padre, model="quad", texture=iconos.textura_icono(nombre),
                  scale=(lado, lado), position=posicion, **opciones)


# Separa «Misión: X» en ("Misión:", "X"); otro texto (p. ej. «Sin misión activa») -> ("", texto).
PREFIJO_MISION = "Misión:"


def _separar_mision(cadena):
    if cadena.startswith(PREFIJO_MISION):
        return PREFIJO_MISION, cadena[len(PREFIJO_MISION):].lstrip()
    return "", cadena


# Text interpreta "<...>" como etiquetas: se cambian por paréntesis.
def _seguro(cadena):
    return cadena.replace("<", "(").replace(">", ")")


# Función cadena -> ancho (camera.ui) con la fuente y la escala de un Text ya creado.
def _medidor(texto):
    nodo = TextNode("medida")
    nodo.setFont(texto.font)
    factor = texto.size * texto.scale_x
    return lambda cadena: nodo.calcWidth(cadena) * factor


# Text de varias líneas con origen arriba-izquierda, envuelto a `ancho`. Devuelve
# (texto, alto) con el alto estimado en unidades de camera.ui.
def _texto_envuelto(padre, cadena, ancho, px, rgb_texto, posicion):
    texto = Text("", parent=padre, origin=(-0.5, 0.5), position=posicion,
                 scale=escala_fuente(px), color=rgb(rgb_texto))
    texto.line_height = 1.25
    lineas = envolver_texto(_seguro(cadena), _medidor(texto), ancho) or [""]
    texto.text = "\n".join(lineas)
    return texto, len(lineas) * a_unidades(px) * texto.line_height


def _fondo(padre, ancho, alto, tono, radio_px=8, **opciones):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio_px),
                  scale=(ancho, alto), color=tono, **opciones)


# -- Teléfono ------------------------------------------------------------------


class TelefonoUI(Entity):

    DURACION_NOTIFICACION = 4.0     # segundos con el banner visible
    VELOCIDAD_DESLIZ = 5.0          # niveles por segundo (el banner sube en 0.2 s)

    ANCHO_ICONO, ALTO_ICONO = 0.075, 0.12
    ANCHO_BANNER = 0.44
    ANCHO_PANEL, ALTO_PANEL = 0.42, 0.52      # más alto tapa el chip del destino del minimapa; la casilla
                                              # «Seguir misión» le quita sitio a los mensajes (se recortan solos)
    ALTO_CASILLA = a_unidades(34)

    # obtener_telefono(): Telefono del jugador ACTIVO. obtener_mision(): Mision actual
    # o None. Son callables para no atar la vista a la sesión (se prueban con falsos).
    def __init__(self, obtener_telefono, obtener_mision, **opciones):
        super().__init__(**opciones)
        self._obtener_telefono = obtener_telefono
        self._obtener_mision = obtener_mision
        self._telefono = None
        self._nuevos_al_abrir = 0        # no leídos justo antes de abrir (para resaltar)
        self.tiempo_notificacion = 0.0
        self.nivel_banner = 0.0          # 0 = oculto bajo la pantalla, 1 = a la vista
        self.vista = None
        self._firma_banner = None
        self._firma_panel = None

        self.x_derecho = window.aspect_ratio / 2 - MARGEN
        self.y_inferior = -0.5 + MARGEN
        self._construir_icono()
        self.banner = Entity(parent=self)
        self.panel = Entity(parent=self, enabled=False)

    # -- Construcción --

    def _construir_icono(self):
        centro_x = self.x_derecho - self.ANCHO_ICONO / 2
        centro_y = self.y_inferior + self.ALTO_ICONO / 2
        self.icono = BotonAccion("", al_clic=self.alternar, ancho=self.ANCHO_ICONO,
                                 alto=self.ALTO_ICONO, parent=self, position=(centro_x, centro_y))
        self.icono.color = rgb((26, 29, 44))
        self.icono.highlight_color = rgb((44, 50, 78))
        self.icono.pressed_color = rgb((44, 50, 78))
        ancho_pantalla, alto_pantalla = self.ANCHO_ICONO - 0.014, self.ALTO_ICONO - 0.026
        _fondo(self, ancho_pantalla, alto_pantalla, rgb(estilo.COLOR_BOTON), 5,
               position=(centro_x, centro_y + 0.004, -0.001))
        # icono del teléfono (frontend/iconos.py) dentro de la pantalla
        _icono(self, "telefono", ancho_pantalla, (centro_x, centro_y + 0.004, -0.002))
        # insignia roja con el contador de no leídos
        self.insignia = Entity(parent=self, position=(centro_x - 0.03, centro_y + 0.052, -0.004),
                               enabled=False)
        Entity(parent=self.insignia, model="circle", scale=0.04, color=rgb(COLOR_ALERTA))
        self.texto_contador = Text("0", parent=self.insignia, origin=(0, 0), position=(0, 0, -0.001),
                                   scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO))

    # -- Estado --

    def telefono(self):
        return self._telefono

    def alternar(self):
        if self._telefono is not None:
            self._telefono.alternar()

    # Casilla «Seguir misión» (clic en el panel; la tecla M la maneja el controlador del jugador).
    def alternar_seguir(self):
        if self._telefono is not None:
            self._telefono.alternar_seguir_mision()

    # Un paso de `dt` segundos: sincroniza con el teléfono del jugador activo, corre el
    # reloj de la notificación (4 s y luego terminar_notificacion), desliza el banner y
    # dibuja. Con dt = 0 solo sincroniza y dibuja. Determinista: depende de los dt.
    def avanzar(self, dt):
        telefono = self._obtener_telefono()
        if telefono is not self._telefono:        # cambió el turno: otro teléfono
            if self._telefono is not None:
                # El saliente ya no se ve: su banner no debe quedar "notificando" para siempre
                # (los mensajes siguen sin leer; no se marcan como leídos).
                self._telefono.terminar_notificacion()
            self._telefono = telefono
            self.tiempo_notificacion = 0.0
            self.nivel_banner = 0.0
            self._nuevos_al_abrir = 0
        if telefono is None:
            self.enabled = False
            return
        self.enabled = True

        if telefono.estado() == hud_calculos.ABIERTO:
            pass                                   # conserva cuántos eran nuevos
        else:
            self._nuevos_al_abrir = telefono.no_leidos()
        if telefono.estado() == hud_calculos.NOTIFICANDO:
            self.tiempo_notificacion += dt
            if self.tiempo_notificacion >= self.DURACION_NOTIFICACION:
                telefono.terminar_notificacion()
        else:
            self.tiempo_notificacion = 0.0

        objetivo = 1.0 if telefono.estado() == hud_calculos.NOTIFICANDO else 0.0
        self.nivel_banner = hud_calculos.avanzar_hacia(
            self.nivel_banner, objetivo, dt * self.VELOCIDAD_DESLIZ)
        self.vista = hud_calculos.vista_telefono(
            telefono, self._obtener_mision(), self._nuevos_al_abrir)
        self._dibujar()

    # Lo que se ve ahora (para los tests y el HUD).
    def banner_visible(self):
        return self.banner.enabled and self.nivel_banner > 0

    def panel_visible(self):
        return self.panel.enabled

    def contador_visible(self):
        return self.insignia.enabled

    # -- Dibujo --

    def _dibujar(self):
        vista = self.vista
        self.insignia.enabled = vista.contador > 0
        contador = str(min(vista.contador, 9)) + ("+" if vista.contador > 9 else "")
        if self.texto_contador.text != contador:     # .text rehace la malla aunque sea el mismo texto
            self.texto_contador.text = contador
        self._dibujar_banner(vista)
        self._dibujar_panel(vista)

    def _dibujar_banner(self, vista):
        if vista.texto_notificacion != self._firma_banner:
            self._firma_banner = vista.texto_notificacion
            self._armar_banner(vista.texto_notificacion)
        visible = vista.modo == hud_calculos.MODO_NOTIFICACION or self.nivel_banner > 0
        self.banner.enabled = (visible and bool(vista.texto_notificacion)
                               and vista.modo != hud_calculos.MODO_ABIERTO)
        y_visible = self.y_inferior + self._alto_banner / 2
        y_oculto = -0.5 - self._alto_banner / 2 - MARGEN
        self.banner.position = (self.x_derecho - self.ANCHO_ICONO - 0.012 - self.ANCHO_BANNER / 2,
                                hud_calculos.mezclar(y_oculto, y_visible,
                                                     _ease_out_quad(self.nivel_banner)))

    def _armar_banner(self, texto):
        for hijo in list(self.banner.children):
            destruir_arbol(hijo)
        relleno = 0.012
        titulo = Text(hud_calculos.ENCABEZADO_TELEFONO, parent=self.banner, origin=(-0.5, 0.5),
                      scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))
        lado_icono = a_unidades(24)
        cuerpo, alto_texto = _texto_envuelto(
            self.banner, texto, self.ANCHO_BANNER - 2 * relleno, 18, estilo.COLOR_TEXTO, (0, 0))
        self._alto_banner = a_unidades(15) * 1.3 + alto_texto + 2 * relleno
        _fondo(self.banner, self.ANCHO_BANNER, self._alto_banner, rgb(estilo.COLOR_PANEL), 10,
               z=0.002)
        izquierda, arriba = -self.ANCHO_BANNER / 2 + relleno, self._alto_banner / 2 - relleno
        _icono(self.banner, "telefono", lado_icono,
               (izquierda + lado_icono / 2, arriba - a_unidades(8), -0.001))
        titulo.position = (izquierda + lado_icono + 0.006, arriba, -0.001)
        cuerpo.position = (izquierda, arriba - a_unidades(15) * 1.3, -0.001)

    _alto_banner = 0.12

    def _dibujar_panel(self, vista):
        abierto = vista.modo == hud_calculos.MODO_ABIERTO
        self.panel.enabled = abierto
        if not abierto or vista == self._firma_panel:
            return
        self._firma_panel = vista
        for hijo in list(self.panel.children):
            destruir_arbol(hijo)
        ancho, alto = self.ANCHO_PANEL, self.ALTO_PANEL
        relleno = 0.016
        izquierda, ancho_texto = -ancho / 2 + relleno, ancho - 2 * relleno
        centro_x = self.x_derecho - ancho / 2
        centro_y = self.y_inferior + self.ALTO_ICONO + 0.012 + alto / 2
        self.panel.position = (centro_x, centro_y)
        _fondo(self.panel, ancho, alto, rgb(estilo.COLOR_PANEL), 12, z=0.002)

        y = alto / 2 - relleno
        lado_icono = a_unidades(30)
        _icono(self.panel, "telefono", lado_icono, (izquierda + lado_icono / 2, y - a_unidades(15), -0.001))
        Text(vista.encabezado, parent=self.panel, origin=(-0.5, 0.5),
             position=(izquierda + lado_icono + 0.008, y, -0.001),
             scale=escala_fuente(26), color=rgb(estilo.COLOR_TEXTO))
        y -= a_unidades(26) * 1.3
        Entity(parent=self.panel, model="quad", scale=(ancho_texto, 0.002), position=(0, y, -0.001),
               color=rgb(estilo.COLOR_BARRA_FONDO))
        y -= 0.012
        prefijo, titulo_mision = _separar_mision(vista.linea_mision)
        if prefijo:                      # «Misión:» en el color del destino, con su icono
            lado_mision = a_unidades(20)
            _icono(self.panel, "mision", lado_mision, (izquierda + lado_mision / 2, y - a_unidades(10), -0.001))
            Text(prefijo, parent=self.panel, origin=(-0.5, 0.5),
                 position=(izquierda + lado_mision + 0.006, y, -0.001),
                 scale=escala_fuente(17), color=rgb(COLOR_DESTINO))
            y -= a_unidades(17) * 1.35
        mision, alto_mision = _texto_envuelto(
            self.panel, titulo_mision, ancho_texto, 19, estilo.COLOR_TEXTO, (izquierda, y, -0.001))
        y -= alto_mision
        if vista.linea_destino:
            _texto_envuelto(self.panel, vista.linea_destino, ancho_texto, 17,
                            estilo.COLOR_TEXTO_TENUE, (izquierda, y, -0.001))
            y -= a_unidades(17) * 1.25
        if vista.texto_seguir:
            y = self._dibujar_casilla(vista, izquierda, ancho_texto, y - 0.008)
        y -= 0.014
        Text("Mensajes", parent=self.panel, origin=(-0.5, 0.5), position=(izquierda, y, -0.001),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO_TENUE))
        y -= a_unidades(17) * 1.5
        Text("Tab para cerrar", parent=self.panel, origin=(0.5, -0.5),
             position=(ancho / 2 - relleno, -alto / 2 + 0.008, -0.001),
             scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO_TENUE))

        limite_inferior = -alto / 2 + 0.034      # deja sitio a la ayuda de la base
        for fila in vista.filas:                 # los más recientes primero
            cuerpo, alto_texto = _texto_envuelto(
                self.panel, fila.texto, ancho_texto - 0.016, 16, estilo.COLOR_TEXTO,
                (izquierda + 0.008, y - 0.007, -0.002))
            alto_fila = alto_texto + 0.014
            if y - alto_fila < limite_inferior:   # no cabe: se omiten los más antiguos
                destruir_arbol(cuerpo)
                break
            tono = COLOR_RESALTADO if fila.resaltado else estilo.COLOR_TARJETA
            _fondo(self.panel, ancho_texto, alto_fila, rgb(tono), 6,
                   position=(0, y - alto_fila / 2, -0.001))
            y -= alto_fila + 0.008

    # Casilla «Seguir misión» (docs/DISENO.md): toda la fila es un botón; caja con borde de tinta, amarilla y con
    # visto si está marcada, vacía si no, y el estado ESCRITO («Sí» / «No»), no solo dibujado. Devuelve la y de abajo.
    def _dibujar_casilla(self, vista, izquierda, ancho_texto, y):
        alto = self.ALTO_CASILLA
        centro_y = y - alto / 2
        fila = BotonAccion("", al_clic=self.alternar_seguir, ancho=ancho_texto, alto=alto, parent=self.panel,
                           position=(0, centro_y, -0.001))
        fila.color = rgb(estilo.COLOR_TARJETA)
        fila.highlight_color = rgb(estilo.COLOR_SUPERFICIE_ALTA)
        fila.pressed_color = rgb(estilo.COLOR_SUPERFICIE_ALTA)
        lado = a_unidades(20)
        cx = izquierda + 0.012 + lado / 2
        borde = a_unidades(3)
        _fondo(self.panel, lado + 2 * borde, lado + 2 * borde, rgb(estilo.TINTA), 4, position=(cx, centro_y, -0.002))
        _fondo(self.panel, lado, lado, rgb(COLOR_DESTINO if vista.sigue_mision else estilo.COLOR_FONDO), 3,
               position=(cx, centro_y, -0.003))
        if vista.sigue_mision:              # visto de tinta: un trazo corto y uno largo
            Entity(parent=self.panel, model="quad", color=rgb(estilo.TINTA), rotation_z=45,
                   position=(cx - lado * 0.2, centro_y - lado * 0.06, -0.004), scale=(lado * 0.42, lado * 0.16))
            Entity(parent=self.panel, model="quad", color=rgb(estilo.TINTA), rotation_z=-55,
                   position=(cx + lado * 0.1, centro_y + lado * 0.06, -0.004), scale=(lado * 0.7, lado * 0.16))
        Text(vista.texto_seguir, parent=self.panel, origin=(-0.5, 0), position=(cx + lado / 2 + 0.012, centro_y, -0.004),
             scale=escala_fuente(17), color=rgb(estilo.COLOR_TEXTO))
        return y - alto


# -- Minimapa ------------------------------------------------------------------


class Minimapa(Entity):

    ANCHO = 280 / 720                # ~280 x 200 px de la ventana de 1280 x 720
    ALTO = 200 / 720
    LARGO_FLECHA = 0.05
    YAW_MIN_CASAS = 1.5              # grados de giro a partir de los cuales se rehacen casas y escaleras
    COLOR_CASAS = color.rgba32(88, 92, 108, 200)    # casas: algo transparentes
    COLOR_ESCALERAS = color.rgba32(200, 190, 160, 255)
    ANCHO_MIN_ESCALERA = 0.003       # grosor mínimo de una escalera en camera.ui (unidades)
    COLOR_CALLES = (140, 146, 164)   # antes (112, 116, 132): más contraste sobre el fondo oscuro
    COLOR_LUGAR_SIN_IDENTIDAD = (150, 152, 164)   # lugar que no está en estilo.COLORES_LUGAR

    # rotacion_libre (mundo 3D): el yaw se cambia cada frame con fijar_yaw() y la escala no depende de él.
    def __init__(self, mapa, yaw_grados=None, rotacion_libre=False, **opciones):
        super().__init__(**opciones)
        self._mapa = mapa
        yaw = 0 if yaw_grados is None else yaw_grados
        self.geometria = hud_calculos.GeometriaMinimapa(
            mapa, (self.ANCHO, self.ALTO), yaw, rotacion_libre=rotacion_libre)
        self.position = (window.aspect_ratio / 2 - MARGEN - self.ANCHO / 2,
                         0.5 - MARGEN - self.ALTO / 2)

        # Capas con z cada vez más negativo = más cerca de la cámara de camera.ui.
        self.fondo = _fondo(self, self.ANCHO, self.ALTO, COLOR_FONDO_HUD, 10)
        self.capa_calles = Entity(parent=self, z=-0.001)
        self.capa_casas = Entity(parent=self, z=-0.0015)      # casas y escaleras (una malla cada una)
        self.capa_ruta = Entity(parent=self, z=-0.002)
        self.capa_lugares = Entity(parent=self, z=-0.003)
        self.capa_plazas = Entity(parent=self.capa_lugares)   # plazas y marcas de puerta: se gira entera
        self.capa_jugadores = Entity(parent=self, z=-0.004)
        self.flecha = Entity(
            parent=self, z=-0.006, scale=self.LARGO_FLECHA, double_sided=True,
            color=color.white, enabled=False,
            model=Mesh(vertices=[(0, 1, 0), (-0.42, 0, 0), (0, 0.28, 0), (0.42, 0, 0)],
                       triangles=[(0, 1, 2), (0, 2, 3)]))
        # La punta de la flecha (en el espacio local del modelo): los tests miden con ella.
        self.punta_flecha = Entity(parent=self.flecha, position=(0, 1, 0))

        self.segmentos_ruta = []      # cuadros reutilizados para dibujar la ruta
        self.puntos = {}              # nombre -> (aro, punto) de cada jugador
        self.lugares = {}             # lugar -> círculo de la plaza
        self.contornos_lugar = {}     # lugar -> círculo de tinta detrás de la plaza
        self.calles = []              # [(cuadro, a, b)] para recolocarlas al girar
        self.marcas_edificios = {}    # lugar -> cuadrito en la puerta (solo mundo con edificios)
        self._firma_ruta = None
        self._destino_etiqueta = None
        self.malla_casas = Entity(parent=self.capa_casas, enabled=False, color=self.COLOR_CASAS)
        self.malla_escaleras = Entity(parent=self.capa_casas, z=-0.0003, enabled=False,
                                      color=self.COLOR_ESCALERAS)
        self.reconstrucciones_casas = 0   # cuántas veces se rehicieron las mallas (lo usan los tests)
        self._yaw_casas = None            # yaw con el que se construyeron las mallas
        self._yaw_mapa = None             # yaw con el que se colocaron calles y plazas
        self._construir_mapa()
        self._reconstruir_casas()
        self.marcador_destino = Entity(parent=self.capa_lugares, model="circle", z=0.0005,
                                       color=rgb(COLOR_DESTINO), enabled=False)
        # Etiqueta corta del destino, bajo el minimapa (chip oscuro con el nombre en amarillo).
        self.etiqueta_destino = Text("", parent=self, origin=(0.5, 0.5), scale=escala_fuente(16),
                                     position=(self.ANCHO / 2 - 0.008, -self.ALTO / 2 - 0.012, -0.007),
                                     color=rgb(COLOR_DESTINO), enabled=False)
        self.fondo_etiqueta = _fondo(self, 0.1, 0.03, COLOR_FONDO_HUD, 6, z=-0.0065, enabled=False)

    def _construir_mapa(self):
        g = self.geometria
        for a, b in self._mapa.segmentos():
            cuadro = Entity(parent=self.capa_calles, model="quad", color=rgb(self.COLOR_CALLES))
            self.calles.append((cuadro, a, b))
        for lugar in self._mapa.lugares():
            # contorno de tinta: separa el color del lugar del aro amarillo del destino
            self.contornos_lugar[lugar] = Entity(parent=self.capa_plazas, model="circle", z=0.0002,
                                                 scale=g.diametro_plaza() * 1.22, color=rgb(estilo.TINTA))
            self.lugares[lugar] = Entity(parent=self.capa_plazas, model="circle",
                                         scale=g.diametro_plaza(),
                                         color=rgb(self.color_de_lugar(lugar)))
        for lugar in self._mapa.lugares():
            try:
                self._mapa.edificio_de(lugar)
            except (AttributeError, ValueError):
                continue
            self.marcas_edificios[lugar] = Entity(
                parent=self.capa_plazas, model="quad", z=-0.0005, scale=0.011,
                color=rgb((60, 64, 84)))
        self._colocar_mapa()

    # Color de identidad del lugar (estilo.COLORES_LUGAR). Los nombres del mapa son más largos
    # («Universidade de Ciudad Nova», «Parque do Povo»): se busca el nombre exacto y, si no,
    # la clave con la que empieza. Lugar desconocido: gris neutro.
    @classmethod
    def color_de_lugar(cls, lugar):
        if lugar in estilo.COLORES_LUGAR:
            return estilo.COLORES_LUGAR[lugar]
        for clave, tono in estilo.COLORES_LUGAR.items():
            if lugar.startswith(clave):
                return tono
        return cls.COLOR_LUGAR_SIN_IDENTIDAD

    # Posiciona calles, plazas y marcas según el yaw actual de la geometría.
    def _colocar_mapa(self):
        g = self.geometria
        for cuadro, a, b in self.calles:
            self._poner_segmento(cuadro, g.lugar(a), g.lugar(b), g.ancho_calle())    # color fijo: al crearla
        for lugar, circulo in self.lugares.items():
            circulo.position = g.lugar(lugar)
            self.contornos_lugar[lugar].position = (*g.lugar(lugar)[:2], 0.0002)
        for lugar, marca in self.marcas_edificios.items():
            marca.position = g.punto(*self._mapa.edificio_de(lugar).puerta())
        self._yaw_mapa = g.yaw
        self.capa_calles.rotation_z = self.capa_plazas.rotation_z = 0

    # Gira el minimapa con la cámara. La escala no cambia; las mallas de casas y escaleras se rehacen solo si el
    # yaw cambió más de YAW_MIN_CASAS, y calles y plazas solo se recolocan una a una cada YAW_MIN_MAPA_SUAVE grados.
    def fijar_yaw(self, yaw_grados):
        if abs(yaw_grados - self.geometria.yaw) < 0.05:
            return
        self.geometria.girar(yaw_grados)
        if (self.GIRO_SUAVE_MAPA and self._yaw_mapa is not None
                and hud_calculos.diferencia_yaw(yaw_grados, self._yaw_mapa) <= self.YAW_MIN_MAPA_SUAVE):
            self._girar_capas_mapa()
        else:
            self._colocar_mapa()
        self._firma_ruta = None            # la ruta y la flecha se redibujan con el nuevo yaw
        if (self._yaw_casas is not None
                and hud_calculos.diferencia_yaw(yaw_grados, self._yaw_casas) > self._umbral_casas()):
            self._reconstruir_casas()
        self._girar_capa_casas()

    # Rendimiento (GIRO_SUAVE_CASAS): rehacer las mallas costaba varios ms y, al girar la cámara, pasaba casi
    # cada frame. Entre reconstrucciones se gira la capa entera lo que falta (exacto: el giro del minimapa es
    # alrededor de su centro) y solo se rehace cada YAW_MIN_CASAS_SUAVE grados. False = lo de siempre.
    GIRO_SUAVE_CASAS = True
    YAW_MIN_CASAS_SUAVE = 6.0

    def _umbral_casas(self):
        return self.YAW_MIN_CASAS_SUAVE if self.GIRO_SUAVE_CASAS else self.YAW_MIN_CASAS

    # Rendimiento (GIRO_SUAVE_MAPA): recolocar calles, plazas y marcas costaba ~0,3 ms por frame al girar la cámara.
    # Como con las casas, entre recolocaciones se giran las capas enteras (exacto: el giro es alrededor del centro
    # del minimapa) y solo se recoloca cada YAW_MIN_MAPA_SUAVE grados. False = lo de siempre.
    GIRO_SUAVE_MAPA = True
    YAW_MIN_MAPA_SUAVE = 6.0

    def _girar_capas_mapa(self):
        delta = (self.geometria.yaw - self._yaw_mapa + 180) % 360 - 180
        self.capa_calles.rotation_z = self.capa_plazas.rotation_z = -delta

    def _girar_capa_casas(self):
        if not self.GIRO_SUAVE_CASAS or self._yaw_casas is None:
            return
        delta = (self.geometria.yaw - self._yaw_casas + 180) % 360 - 180
        self.capa_casas.rotation_z = -delta     # rotation_z gira en sentido horario; el yaw, antihorario

    # Rehace las dos mallas (casas y escaleras) con el yaw actual. Mundo sin obstaculos() o
    # escaleras() (mapa 2D): no hay nada que dibujar y las mallas quedan apagadas.
    def _reconstruir_casas(self):
        g = self.geometria
        obstaculos = getattr(self._mapa, "obstaculos", None)
        escaleras = getattr(self._mapa, "escaleras", None)
        cuadros = g.cuadros_casas(obstaculos()) if callable(obstaculos) else []
        rectangulos = [hud_calculos.segmento_a_rectangulo(p0, p1, max(ancho, self.ANCHO_MIN_ESCALERA))
                       for p0, p1, ancho in (g.segmentos_escaleras(escaleras())
                                             if callable(escaleras) else [])]
        self._yaw_casas = g.yaw
        self.reconstrucciones_casas += 1
        for entidad, cuadrilateros in ((self.malla_casas, cuadros),
                                       (self.malla_escaleras, rectangulos)):
            entidad.enabled = bool(cuadrilateros)
            entidad.model = self._malla_de_cuadrilateros(cuadrilateros) if cuadrilateros else None

    # Una sola Mesh con todos los cuadriláteros [(c0, c1, c2, c3)] de (u, v): dos triángulos cada uno.
    @staticmethod
    def _malla_de_cuadrilateros(cuadrilateros):
        vertices, triangulos = [], []
        for i, esquinas in enumerate(cuadrilateros):
            base = 4 * i
            vertices += [(u, v, 0) for u, v in esquinas]
            triangulos += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        return Mesh(vertices=vertices, triangles=triangulos)

    # Coloca un cuadro como línea gruesa de p0 a p1 (rotation_z en sentido horario). Sin `tono` conserva su color
    # (las calles: se recolocan en cada giro de la cámara y su color no cambia).
    def _poner_segmento(self, cuadro, p0, p1, grosor, tono=None):
        cu, cv, largo, rotacion = hud_calculos.segmento_a_cuadro(p0, p1)
        cuadro.position = (cu, cv)
        cuadro.scale = (largo, grosor)
        cuadro.rotation_z = rotacion
        if tono is not None:
            cuadro.color = tono

    # posiciones: [(nombre, rgb_rol, x, z)] de todos los jugadores; activo: nombre del
    # jugador del turno; destino: lugar o None; ruta: lugares que faltan (GuiaRuta).
    def actualizar(self, posiciones, activo, destino, ruta):
        g = self.geometria
        presentes = {nombre for nombre, _, _, _ in posiciones}
        for nombre, (aro, punto) in self.puntos.items():
            if nombre not in presentes:          # jugador de una partida anterior: se oculta
                aro.enabled = punto.enabled = False
        for nombre, rgb_rol, x, z in posiciones:
            if nombre not in self.puntos:
                aro = Entity(parent=self.capa_jugadores, model="circle", color=color.white)
                punto = Entity(parent=self.capa_jugadores, model="circle", z=-0.0005)
                self.puntos[nombre] = (aro, punto)
            aro, punto = self.puntos[nombre]
            es_activo = nombre == activo
            u, v = g.acotar(*g.punto(x, z), margen=0.014)    # fuera del mapa: pegado al borde
            aro.position = punto.position = (u, v)
            aro.enabled = es_activo
            punto.enabled = True                 # reaparece si el nombre vuelve a estar
            aro.scale = 0.026
            punto.scale = 0.018 if es_activo else 0.012
            punto.color = rgb(rgb_rol) if es_activo else color.rgba32(*rgb_rol, 130)
            punto.z = -0.0005 if es_activo else 0.001     # los demás, detrás del activo

        self._poner_etiqueta_destino(destino)
        if destino is None:
            self.marcador_destino.enabled = False
        else:
            self.marcador_destino.enabled = True
            self.marcador_destino.position = g.acotar(*g.lugar(destino), margen=0.014)
            self.marcador_destino.scale = g.diametro_plaza() * 1.6

        for nombre, rgb_rol, x, z in posiciones:
            if nombre == activo:
                self._dibujar_ruta(x, z, ruta)
                return
        self._dibujar_ruta(0, 0, [])

    # Chip «Destino: <lugar>» bajo el minimapa, alineado a su borde derecho. Sin destino se oculta.
    def _poner_etiqueta_destino(self, destino):
        if destino == self._destino_etiqueta:
            return
        self._destino_etiqueta = destino
        self.etiqueta_destino.enabled = self.fondo_etiqueta.enabled = destino is not None
        if destino is None:
            return
        # Con la traducción corta: el chip no debe pasar del ancho del minimapa.
        self.etiqueta_destino.text = _seguro(nombre_visible(destino, corto=True))
        ancho = _medidor(self.etiqueta_destino)(self.etiqueta_destino.text)
        relleno, alto = 0.012, a_unidades(16) * 1.5
        self.fondo_etiqueta.model = modelo_redondeado(ancho + 2 * relleno, alto, 6)
        self.fondo_etiqueta.scale = (ancho + 2 * relleno, alto)
        derecha = self.ANCHO / 2
        self.fondo_etiqueta.position = (derecha - (ancho + 2 * relleno) / 2, -self.ALTO / 2 - 0.012 - alto / 2 + 0.002, -0.0065)
        self.etiqueta_destino.position = (derecha - relleno, -self.ALTO / 2 - 0.012 + 0.002 - (alto - a_unidades(16)) / 2, -0.007)

    def _dibujar_ruta(self, x, z, ruta):
        firma = (tuple(ruta), round(x, 3), round(z, 3))
        if firma == self._firma_ruta:
            return
        self._firma_ruta = firma
        g = self.geometria
        segmentos = [r for r in (g.recortar_segmento(p0, p1) for p0, p1 in g.segmentos_ruta(x, z, ruta))
                     if r is not None]        # lo que queda fuera del recuadro no se dibuja
        while len(self.segmentos_ruta) < len(segmentos):
            self.segmentos_ruta.append(Entity(parent=self.capa_ruta, model="quad"))
        for cuadro, (p0, p1) in zip(self.segmentos_ruta, segmentos):
            self._poner_segmento(cuadro, p0, p1, max(g.ancho_calle() * 0.55, 0.006), rgb(COLOR_RUTA))
            cuadro.enabled = True
        for cuadro in self.segmentos_ruta[len(segmentos):]:
            cuadro.enabled = False

        flecha = g.flecha(x, z, ruta)
        self.flecha.enabled = flecha is not None
        if flecha is not None:
            self.flecha.position = g.acotar(flecha[0], flecha[1], margen=self.LARGO_FLECHA)
            self.flecha.rotation_z = flecha[2]       # horario desde arriba = rotation_z de Ursina

    def entidades_dibujadas(self):
        # Entidades visibles con su posición local (u, v): para comprobar el recorte.
        todas = [self.capa_calles, self.capa_ruta, self.capa_lugares, self.capa_plazas, self.capa_jugadores]
        resultado = []
        for capa in todas:
            resultado += [e for e in capa.children if e.enabled and e is not self.capa_plazas]
        if self.flecha.enabled:
            resultado.append(self.flecha)
        return resultado


# -- Aviso de interacción --------------------------------------------------------


class AvisoInteraccion(Entity):

    TEXTO = "Presiona E para acceder"
    ANCHO_MIN, ANCHO_MAX, ALTO = 0.44, 0.66, 0.07    # el máximo deja libre el banner del teléfono
    RELLENO = 0.05
    LADO_TECLA = 0.05                 # la tecla E dibujada (icono 'interactuar')
    SEPARACION_TECLA = 0.012
    DURACION_APARICION = 0.12         # segundos: alfa 0 -> 1 y sube 6 px (ease_out_quad)
    SUBIDA_PX = 6

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.y_base = -0.5 + MARGEN + 0.04
        self.position = (0, self.y_base)
        self.fondo = _fondo(self, self.ANCHO_MIN, self.ALTO, COLOR_FONDO_HUD, 12, z=0.001)
        self.tecla = _icono(self, "interactuar", self.LADO_TECLA, (0, 0, -0.001))
        self.texto = Text(self.TEXTO, parent=self, origin=(-0.5, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO))
        self._ancho = self.ANCHO_MIN
        self._ancho_texto = 0.0
        self.aparicion = 0.0          # segundos desde que apareció (0 .. DURACION_APARICION)
        self.nivel = 0.0              # avance eased 0..1 de la aparición (1 = ya a la vista)
        self.enabled = False
        self._colocar()

    # Tecla + texto como un grupo centrado dentro del fondo.
    def _colocar(self):
        grupo = self.LADO_TECLA + self.SEPARACION_TECLA + self._ancho_texto
        izquierda = -grupo / 2
        self.tecla.x = izquierda + self.LADO_TECLA / 2
        self.texto.x = izquierda + self.LADO_TECLA + self.SEPARACION_TECLA

    # `texto`: otro mensaje (p. ej. "Presiona E para entrar a la Prefeitura"); None = el de siempre.
    # El fondo se ajusta al ancho de tecla + texto (entre ANCHO_MIN y ANCHO_MAX; si aun así no
    # cabe, el texto se achica).
    def actualizar(self, estado_mision, estado_telefono, texto=None):
        cadena = _seguro(texto if texto is not None else self.TEXTO)
        if cadena != self.texto.text:
            self.texto.text = cadena
            self.texto.scale = escala_fuente(22)
            ancho_texto = _medidor(self.texto)(cadena)
            # El máximo nunca pasa del ancho real de la ventana (en 16:9 sigue siendo ANCHO_MAX).
            ancho_max = min(self.ANCHO_MAX, diseno_adaptable.aspecto() - 4 * MARGEN)
            maximo = ancho_max - self.RELLENO - self.LADO_TECLA - self.SEPARACION_TECLA
            if ancho_texto > maximo:
                self.texto.scale = escala_fuente(22) * maximo / ancho_texto
                ancho_texto = maximo
            self._ancho_texto = ancho_texto
            self._ancho = max(self.ANCHO_MIN,
                              ancho_texto + self.LADO_TECLA + self.SEPARACION_TECLA + self.RELLENO)
            self.fondo.model = modelo_redondeado(self._ancho, self.ALTO, 12)
            self.fondo.scale = (self._ancho, self.ALTO)
            self._colocar()
        visible = hud_calculos.aviso_visible(estado_mision, estado_telefono)
        if visible and not self.enabled:      # acaba de aparecer: la animación empieza de cero
            self.aparicion = 0.0
            self._aplicar_aparicion()
        self.enabled = visible

    # Avanza `dt` segundos la aparición (llamado desde HudMundo.actualizar; determinista).
    def avanzar(self, dt):
        if not self.enabled:
            return
        self.aparicion = min(self.DURACION_APARICION, self.aparicion + dt)
        self._aplicar_aparicion()

    def _aplicar_aparicion(self):
        self.nivel = _ease_out_quad(self.aparicion / self.DURACION_APARICION)
        self.y = self.y_base - a_unidades(self.SUBIDA_PX) * (1 - self.nivel)
        alfa = int(round(255 * self.nivel))
        self.fondo.color = color.rgba32(12, 14, 24, int(round(240 * self.nivel)))
        self.tecla.color = color.rgba32(255, 255, 255, alfa)
        self.texto.color = color.rgba32(*estilo.COLOR_TEXTO, alfa)


# -- Aviso genérico adaptable --------------------------------------------------------


# Chip de texto en la parte baja de la pantalla para avisos sueltos («E: montar bici», «Espacio:
# saltar»...). A diferencia de AvisoInteraccion no lleva la tecla E dibujada ni depende del estado
# de la misión: lo controla quien llama con mostrar()/ocultar(). El ancho se adapta a la ventana:
# el texto se encoge hasta el 75 %, luego se parte en hasta dos líneas y solo si ni así cabe
# se recorta con elipsis. Si el aviso de «E» está visible, se apila encima de él.
class AvisoGenerico(Entity):

    ANCHO_MIN, ALTO = 0.30, 0.07
    ANCHO_MAX = 0.66                  # como AvisoInteraccion: deja libre el banner del teléfono; en ventanas estrechas manda el ancho de la ventana
    RELLENO = 0.05
    PX = 22
    ESCALA_MIN = 0.75
    MAX_LINEAS = 2
    LINEA = 1.25                      # interlineado
    DURACION_APARICION = 0.12
    SUBIDA_PX = 6

    def __init__(self, referencia=None, **opciones):
        super().__init__(**opciones)
        self._referencia = referencia          # AvisoInteraccion sobre el que se apila (opcional)
        self.y_base = -0.5 + MARGEN + 0.04
        self.position = (0, self.y_base)
        self.fondo = _fondo(self, self.ANCHO_MIN, self.ALTO, COLOR_FONDO_HUD, 12, z=0.001)
        self.texto = Text("", parent=self, origin=(0, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(self.PX), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = self.LINEA
        self.cadena = ""              # texto pedido (sin partir)
        self.lineas = []              # líneas que se dibujan
        self.plan = None              # último plan de ajuste (escala, lineas, recortado)
        self.aparicion = 0.0
        self.nivel = 0.0
        self.deseado = False          # True entre mostrar() y ocultar()
        self.enabled = False
        diseno_adaptable.suscribir(lambda aspecto, factor: self._componer())

    # Ancho máximo del chip para la ventana actual.
    def ancho_maximo(self):
        return min(self.ANCHO_MAX, diseno_adaptable.aspecto() - 4 * MARGEN)

    # Muestra `texto`. Si ya se muestra el mismo no reinicia la animación.
    def mostrar(self, texto):
        cadena = _seguro(str(texto))
        if not cadena.strip():
            self.ocultar()
            return
        cambio = cadena != self.cadena
        self.cadena = cadena
        if cambio:
            self._componer()
        if not self.deseado:
            self.deseado = True
            self.aparicion = 0.0
            self.enabled = True
            self._aplicar_aparicion()

    def ocultar(self):
        self.deseado = False
        self.enabled = False
        self.aparicion = 0.0

    # Reparte el texto en líneas dentro del ancho de la ventana y ajusta el fondo.
    def _componer(self):
        if not self.cadena:
            return
        self.texto.scale = escala_fuente(self.PX)
        medir = _medidor(self.texto)
        maximo = self.ancho_maximo() - self.RELLENO
        plan = diseno_adaptable_calculos.plan_texto_en_ancho(
            self.cadena, medir, maximo, self.ESCALA_MIN, self.MAX_LINEAS)
        self.plan = plan
        self.lineas = plan["lineas"]
        self.texto.text = "\n".join(self.lineas)
        self.texto.scale = escala_fuente(self.PX) * plan["escala"]
        ancho_texto = max((medir(linea) for linea in self.lineas), default=0.0) * plan["escala"]
        self._ancho = max(self.ANCHO_MIN, ancho_texto + self.RELLENO)
        self._alto = max(self.ALTO, len(self.lineas) * a_unidades(self.PX) * self.LINEA * plan["escala"]
                         + 0.03)
        self.fondo.model = modelo_redondeado(self._ancho, self._alto, 12)
        self.fondo.scale = (self._ancho, self._alto)

    _ancho = ANCHO_MIN
    _alto = ALTO

    # Avanza `dt` segundos la aparición (llamado desde HudMundo.actualizar; determinista).
    def avanzar(self, dt):
        if not self.enabled:
            return
        self.aparicion = min(self.DURACION_APARICION, self.aparicion + dt)
        self._aplicar_aparicion()

    def _aplicar_aparicion(self):
        self.nivel = _ease_out_quad(self.aparicion / self.DURACION_APARICION)
        # Sube sobre el aviso de «E» si éste está a la vista (su alto + un hueco).
        apilado = 0.0
        ref = self._referencia
        if ref is not None and ref.enabled:
            apilado = ref.ALTO / 2 + self._alto / 2 + 0.012
        self.y = self.y_base + (self._alto - self.ALTO) / 2 + apilado - a_unidades(self.SUBIDA_PX) * (1 - self.nivel)
        alfa = int(round(255 * self.nivel))
        self.fondo.color = color.rgba32(12, 14, 24, int(round(240 * self.nivel)))
        self.texto.color = color.rgba32(*estilo.COLOR_TEXTO, alfa)


# -- Panel de turno ----------------------------------------------------------------


class PanelTurno(Entity):

    RELLENO = 0.014

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.fondo = _fondo(self, 0.1, 0.1, COLOR_FONDO_HUD, 8, z=0.001)
        self.texto_turno = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(22),
                                color=rgb(estilo.COLOR_TEXTO))
        # «Misión:» va aparte, en el color del destino; texto_mision lleva el título.
        self.texto_prefijo = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(17),
                                  color=rgb(COLOR_DESTINO))
        self.texto_mision = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(17),
                                 color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.position = (-window.aspect_ratio / 2 + MARGEN, 0.5 - MARGEN)

    # Fija los textos y ajusta el fondo al más ancho.
    def fijar(self, turno, mision):
        prefijo, titulo = _separar_mision(mision)
        self.texto_turno.text = _seguro(turno)
        self.texto_prefijo.text = prefijo
        self.texto_prefijo.enabled = bool(prefijo)
        self.texto_mision.text = _seguro(titulo)
        # El título arranca tras «Misión: » (el espacio se mide con el mismo TextNode).
        avance = _medidor(self.texto_prefijo)(prefijo + " ") if prefijo else 0.0
        ancho = max(_medidor(self.texto_turno)(self.texto_turno.text),
                    avance + _medidor(self.texto_mision)(self.texto_mision.text))
        alto_turno, alto_mision = a_unidades(22) * 1.2, a_unidades(17) * 1.2
        r = self.RELLENO
        self.fondo.model = modelo_redondeado(ancho + 2 * r, alto_turno + alto_mision + 2 * r, 8)
        self.fondo.scale = (ancho + 2 * r, alto_turno + alto_mision + 2 * r)
        self.fondo.position = ((ancho + 2 * r) / 2, -(alto_turno + alto_mision + 2 * r) / 2)
        self.texto_turno.position = (r, -r, -0.001)
        self.texto_prefijo.position = (r, -r - alto_turno, -0.001)
        self.texto_mision.position = (r + avance, -r - alto_turno, -0.001)
        self._ancho_total = ancho + 2 * r
        self.ajustar_ancho()

    _ancho_total = 0.0

    # Ancho máximo del panel de turno: lo que queda entre el borde izquierdo y el minimapa. Si el
    # panel no cabe (ventana estrecha) se escala entero, anclado a su esquina superior izquierda.
    # En 16:9 el máximo es de sobra y la escala se queda en 1 (comportamiento de siempre).
    def ajustar_ancho(self, aspecto=None, factor=None):
        if aspecto is None:
            aspecto = diseno_adaptable.aspecto()
        maximo = aspecto - 2 * MARGEN - Minimapa.ANCHO - 0.03
        escala = diseno_adaptable_calculos.factor_para_ancho(self._ancho_total, maximo, minimo=0.4)
        self.scale = escala


# -- Fin de la partida ---------------------------------------------------------------


# Panel centrado "Partida terminada": indicadores finales de la ciudad y un botón para
# volver al menú. Lo muestra EscenaMundo cuando FlujoPartida.partida_terminada().
class PanelFinPartida(Entity):

    TITULO = "Partida terminada"
    ANCHO, ALTO = 0.62, 0.70
    ANCHO_BARRA = 0.44
    LADO_ICONO = 0.07
    SEPARACION_FILA = 0.12
    DURACION_BARRAS = 0.8             # segundos que tardan las barras en crecer de 0 al valor
    INDICADORES = ("convivencia", "confianza", "desinformacion")

    def __init__(self, al_menu, **opciones):
        super().__init__(**opciones)
        self.panel = panel_tinta(self, self.ANCHO, self.ALTO, tono=estilo.COLOR_FONDO)
        Text(self.TITULO, parent=self, origin=(0, 0), position=(0, self.ALTO / 2 - 0.07, -0.001),
             scale=escala_fuente(32), color=rgb(estilo.COLOR_TEXTO))
        Text("Indicadores finales de Ciudad Nova", parent=self, origin=(0, 0),
             position=(0, self.ALTO / 2 - 0.13, -0.001), scale=escala_fuente(17),
             color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.barras = {}
        self.textos = {}                  # nombre -> Text «Etiqueta: valor» de cada barra
        self.valores = {}
        izquierda = -self.ANCHO / 2 + 0.05
        for i, nombre in enumerate(self.INDICADORES):
            arriba = 0.16 - i * self.SEPARACION_FILA
            _icono(self, nombre, self.LADO_ICONO,
                   (izquierda + self.LADO_ICONO / 2, arriba - 0.05, -0.001))
            barra = BarraIndicador(estilo.ETIQUETAS_INDICADORES[nombre], self.ANCHO_BARRA, 0,
                                   parent=self, position=(izquierda + self.LADO_ICONO + 0.02, arriba, -0.001))
            self.barras[nombre] = barra
            self.textos[nombre] = barra.texto_etiqueta
        self.boton_menu = BotonPrimario(
            "Volver al menú", al_clic=al_menu, ancho=0.36, alto=a_unidades(56),
            parent=self, position=(0, -self.ALTO / 2 + 0.09, -0.001))
        self.tiempo = self.DURACION_BARRAS          # animación terminada
        self.enabled = False

    # Muestra el panel con los valores de `indicadores` (dict nombre -> 0..100). Las
    # etiquetas muestran ya el valor final; las barras crecen en DURACION_BARRAS (avanzar).
    # Llamarlo otra vez con el panel ya visible no reinicia la animación.
    def mostrar(self, indicadores):
        ya_visible = self.enabled
        for nombre, barra in self.barras.items():
            self.valores[nombre] = indicadores[nombre]
            barra.actualizar(indicadores[nombre])
        if not ya_visible:
            self.tiempo = 0.0
            self._dibujar_barras()
        self.enabled = True

    def ocultar(self):
        self.enabled = False

    # Un paso de `dt` segundos de la animación de las barras (lo llama HudMundo.actualizar).
    def avanzar(self, dt):
        if not self.enabled or self.tiempo >= self.DURACION_BARRAS:
            return
        self.tiempo = min(self.DURACION_BARRAS, self.tiempo + dt)
        self._dibujar_barras()

    # Proporción del valor final alcanzada (0..1, ease_out_quad).
    def avance(self):
        return _ease_out_quad(self.tiempo / self.DURACION_BARRAS)

    def _dibujar_barras(self):
        for nombre, barra in self.barras.items():
            ancho = barra.ancho_barra * max(0.0, min(1.0, self.valores[nombre] / 100)) * self.avance()
            if ancho <= 0:
                barra.relleno.enabled = False
                continue
            barra.relleno.enabled = True
            barra.relleno.scale_x = ancho
            barra.relleno.x = ancho / 2
            barra.relleno.model = modelo_redondeado(ancho, barra.alto_barra, 4)
            barra.relleno.color = rgb(self._color_de(nombre))

    # Color por tercio del valor final; en «desinformacion» un valor alto es MALO (se invierte).
    def _color_de(self, nombre):
        valor = self.valores[nombre]
        return estilo.rgb_por_valor(100 - valor if nombre == "desinformacion" else valor)


# -- HUD completo -------------------------------------------------------------------


class HudMundo(Entity):

    # mapa: MapaCiudad. El HUD arranca desactivado (EscenaMundo lo activa al entrar).
    # al_menu: callback del botón "Volver al menú" del panel de fin de partida.
    # rotacion_libre: mundo 3D (el minimapa gira con la cámara; ver actualizar(yaw_grados)).
    def __init__(self, mapa, obtener_flujo, al_menu=None, rotacion_libre=False, **opciones):
        opciones.setdefault("parent", camera.ui)
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self._mapa = mapa
        self._obtener_flujo = obtener_flujo
        self.panel_turno = PanelTurno(parent=self)
        self.minimapa = Minimapa(mapa, rotacion_libre=rotacion_libre, parent=self)
        self.telefono_ui = TelefonoUI(self._telefono_activo, self._mision_actual, parent=self)
        self.aviso = AvisoInteraccion(parent=self)
        self.panel_fin = PanelFinPartida(
            lambda: al_menu() if al_menu is not None else None, parent=self)
        self.guia = hud_calculos.GuiaRuta(mapa)
        # Aviso genérico (API pública: mostrar_aviso / ocultar_aviso), apilado sobre el de «E».
        self.aviso_generico = AvisoGenerico(parent=self, referencia=self.aviso)
        # Diseño adaptable: lo anclado a un borde sigue al borde cuando cambia la ventana (no-op
        # si el gestor no está instalado o UI_ADAPTABLE es False).
        diseno_adaptable.anclar(self.panel_turno, "izquierda")
        diseno_adaptable.anclar(self.minimapa, "derecha")
        diseno_adaptable.anclar(self.telefono_ui, "derecha")
        diseno_adaptable.suscribir(self.panel_turno.ajustar_ancho)

    # Aviso adaptable en la parte baja de la pantalla, sobre «Presiona E...» si éste está visible.
    # `texto` se encoge o se parte en dos líneas para caber en la ventana (elipsis solo si ni así).
    # Lo usa EscenaMundo para avisos como «E: montar bici» o «Espacio: saltar».
    def mostrar_aviso(self, texto):
        self.aviso_generico.mostrar(texto)

    # Oculta el aviso genérico (con fundido corto).
    def ocultar_aviso(self):
        self.aviso_generico.ocultar()

    def _telefono_activo(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.jugador_activo().telefono

    def _mision_actual(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.mision_actual()

    # Un paso del HUD (dt segundos): ruta, minimapa, teléfono y aviso con el estado del
    # modelo. Devuelve True si la ruta cambió (EscenaMundo redibuja la del mundo).
    # yaw_grados (mundo 3D): yaw de la cámara; el minimapa gira con él (arriba = adelante).
    def actualizar(self, dt, sesion, yaw_grados=None):
        self.aviso_generico.avanzar(dt)
        flujo = self._obtener_flujo()
        if flujo is None or sesion is None:
            return False
        if yaw_grados is not None:
            self.minimapa.fijar_yaw(yaw_grados)
        activo = flujo.jugador_activo()
        mision = flujo.mision_actual()
        destino = mision.destino if mision is not None else None
        # «Seguir misión» desmarcada: ni ruta ni destino en el minimapa (el aviso de la E sí usa el destino real).
        seguido = hud_calculos.destino_visible(destino, hud_calculos.sigue_mision(activo.telefono))
        cambio = self.guia.actualizar(activo.x, activo.z, seguido)

        self.minimapa.actualizar(
            [(j.nombre, ROLES[j.rol].color, j.x, j.z) for j in sesion.jugadores()],
            activo.nombre, seguido, self.guia.ruta)
        self.telefono_ui.avanzar(dt)
        self.panel_fin.avanzar(dt)
        self.aviso.actualizar(flujo.estado_mision(), activo.telefono.estado(),
                              self._texto_aviso(destino))
        self.aviso.avanzar(dt)
        return cambio

    # "Presiona E para entrar a <edificio>" si el mapa tiene edificios (mundo 3D); None = el de siempre.
    def _texto_aviso(self, destino):
        edificio_de = getattr(self._mapa, "edificio_de", None)
        if destino is None or edificio_de is None:
            return None
        try:
            return f"Presiona E para entrar a {nombre_visible(edificio_de(destino).titulo)}"
        except ValueError:
            return None
