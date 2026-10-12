# HUD 2D del mundo (Ursina, en camera.ui): teléfono, minimapa, aviso de interacción
# y panel de turno, más la ruta resaltada sobre las calles del mundo (en `scene`).
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
from ursina import Entity, Mesh, Text, camera, color, destroy, window

from backend.logica.roles import ROLES
from frontend import estilo, geometria_mundo, hud_calculos
from frontend.componentes import BotonAccion, a_unidades, escala_fuente, modelo_redondeado, rgb
from frontend.objetos_mundo import pieza
from frontend.texto import envolver_texto

MARGEN = 0.02                       # separación de los bordes de la pantalla
COLOR_FONDO_HUD = color.rgba32(12, 14, 24, 240)
COLOR_RUTA = (70, 220, 255)         # cian brillante: la ruta (minimapa y mundo)
COLOR_DESTINO = (255, 220, 60)      # amarillo: el destino (igual que la baliza del mundo)
COLOR_ALERTA = (214, 62, 62)        # insignia de no leídos
COLOR_RESALTADO = (62, 78, 138)     # mensaje sin leer en el teléfono


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
    ANCHO_PANEL, ALTO_PANEL = 0.42, 0.52

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
        # "burbuja" de mensaje dentro de la pantalla (la fuente no tiene íconos)
        _fondo(self, ancho_pantalla - 0.026, 0.026, rgb(estilo.COLOR_TEXTO), 5,
               position=(centro_x, centro_y + 0.012, -0.002))
        _fondo(self, ancho_pantalla - 0.026, 0.016, rgb(estilo.COLOR_TEXTO_TENUE), 4,
               position=(centro_x, centro_y - 0.016, -0.002))
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
        self.texto_contador.text = str(min(vista.contador, 9)) + ("+" if vista.contador > 9 else "")
        self._dibujar_banner(vista)
        self._dibujar_panel(vista)

    def _dibujar_banner(self, vista):
        if vista.texto_notificacion != self._firma_banner:
            self._firma_banner = vista.texto_notificacion
            self._armar_banner(vista.texto_notificacion)
        visible = vista.modo == hud_calculos.MODO_NOTIFICACION or self.nivel_banner > 0
        self.banner.enabled = visible and bool(vista.texto_notificacion)
        y_visible = self.y_inferior + self._alto_banner / 2
        y_oculto = -0.5 - self._alto_banner / 2 - MARGEN
        self.banner.position = (self.x_derecho - self.ANCHO_ICONO - 0.012 - self.ANCHO_BANNER / 2,
                                hud_calculos.mezclar(y_oculto, y_visible, self.nivel_banner))

    def _armar_banner(self, texto):
        for hijo in list(self.banner.children):
            destroy(hijo)
        relleno = 0.012
        titulo = Text(hud_calculos.ENCABEZADO_TELEFONO, parent=self.banner, origin=(-0.5, 0.5),
                      scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
        cuerpo, alto_texto = _texto_envuelto(
            self.banner, texto, self.ANCHO_BANNER - 2 * relleno, 18, estilo.COLOR_TEXTO, (0, 0))
        self._alto_banner = a_unidades(15) * 1.3 + alto_texto + 2 * relleno
        _fondo(self.banner, self.ANCHO_BANNER, self._alto_banner, rgb(estilo.COLOR_PANEL), 10,
               z=0.002)
        izquierda, arriba = -self.ANCHO_BANNER / 2 + relleno, self._alto_banner / 2 - relleno
        titulo.position = (izquierda, arriba, -0.001)
        cuerpo.position = (izquierda, arriba - a_unidades(15) * 1.3, -0.001)

    _alto_banner = 0.12

    def _dibujar_panel(self, vista):
        abierto = vista.modo == hud_calculos.MODO_ABIERTO
        self.panel.enabled = abierto
        if not abierto or vista == self._firma_panel:
            return
        self._firma_panel = vista
        for hijo in list(self.panel.children):
            destroy(hijo)
        ancho, alto = self.ANCHO_PANEL, self.ALTO_PANEL
        relleno = 0.016
        izquierda, ancho_texto = -ancho / 2 + relleno, ancho - 2 * relleno
        centro_x = self.x_derecho - ancho / 2
        centro_y = self.y_inferior + self.ALTO_ICONO + 0.012 + alto / 2
        self.panel.position = (centro_x, centro_y)
        _fondo(self.panel, ancho, alto, rgb(estilo.COLOR_PANEL), 12, z=0.002)

        y = alto / 2 - relleno
        Text(vista.encabezado, parent=self.panel, origin=(-0.5, 0.5), position=(izquierda, y, -0.001),
             scale=escala_fuente(26), color=rgb(estilo.COLOR_TEXTO))
        y -= a_unidades(26) * 1.3
        Entity(parent=self.panel, model="quad", scale=(ancho_texto, 0.002), position=(0, y, -0.001),
               color=rgb(estilo.COLOR_BARRA_FONDO))
        y -= 0.012
        mision, alto_mision = _texto_envuelto(
            self.panel, vista.linea_mision, ancho_texto, 19, estilo.COLOR_TEXTO, (izquierda, y, -0.001))
        y -= alto_mision
        if vista.linea_destino:
            _texto_envuelto(self.panel, vista.linea_destino, ancho_texto, 17,
                            estilo.COLOR_TEXTO_TENUE, (izquierda, y, -0.001))
            y -= a_unidades(17) * 1.25
        y -= 0.014
        Text("Mensajes", parent=self.panel, origin=(-0.5, 0.5), position=(izquierda, y, -0.001),
             scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
        y -= a_unidades(15) * 1.5
        Text("Tab para cerrar", parent=self.panel, origin=(0.5, -0.5),
             position=(ancho / 2 - relleno, -alto / 2 + 0.008, -0.001),
             scale=escala_fuente(14), color=rgb(estilo.COLOR_TEXTO_TENUE))

        limite_inferior = -alto / 2 + 0.034      # deja sitio a la ayuda de la base
        for fila in vista.filas:                 # los más recientes primero
            cuerpo, alto_texto = _texto_envuelto(
                self.panel, fila.texto, ancho_texto - 0.016, 16, estilo.COLOR_TEXTO,
                (izquierda + 0.008, y - 0.007, -0.002))
            alto_fila = alto_texto + 0.014
            if y - alto_fila < limite_inferior:   # no cabe: se omiten los más antiguos
                destroy(cuerpo)
                break
            tono = COLOR_RESALTADO if fila.resaltado else estilo.COLOR_TARJETA
            _fondo(self.panel, ancho_texto, alto_fila, rgb(tono), 6,
                   position=(0, y - alto_fila / 2, -0.001))
            y -= alto_fila + 0.008


# -- Minimapa ------------------------------------------------------------------


class Minimapa(Entity):

    ANCHO = 280 / 720                # ~280 x 200 px de la ventana de 1280 x 720
    ALTO = 200 / 720
    LARGO_FLECHA = 0.05

    def __init__(self, mapa, yaw_grados=None, **opciones):
        super().__init__(**opciones)
        self._mapa = mapa
        yaw = geometria_mundo.yaw_de_camara() if yaw_grados is None else yaw_grados
        self.geometria = hud_calculos.GeometriaMinimapa(mapa, (self.ANCHO, self.ALTO), yaw)
        self.position = (window.aspect_ratio / 2 - MARGEN - self.ANCHO / 2,
                         0.5 - MARGEN - self.ALTO / 2)

        # Capas con z cada vez más negativo = más cerca de la cámara de camera.ui.
        self.fondo = _fondo(self, self.ANCHO, self.ALTO, COLOR_FONDO_HUD, 10)
        self.capa_calles = Entity(parent=self, z=-0.001)
        self.capa_ruta = Entity(parent=self, z=-0.002)
        self.capa_lugares = Entity(parent=self, z=-0.003)
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
        self._firma_ruta = None
        self._construir_mapa()
        self.marcador_destino = Entity(parent=self.capa_lugares, model="circle", z=0.0005,
                                       color=rgb(COLOR_DESTINO), enabled=False)

    def _construir_mapa(self):
        g = self.geometria
        for p0, p1 in g.calles():
            self._poner_segmento(Entity(parent=self.capa_calles, model="quad"), p0, p1,
                                 g.ancho_calle(), rgb((112, 116, 132)))
        for lugar in self._mapa.lugares():
            u, v = g.lugar(lugar)
            self.lugares[lugar] = Entity(parent=self.capa_lugares, model="circle", position=(u, v),
                                         scale=g.diametro_plaza(), color=rgb((150, 152, 164)))

    # Coloca un cuadro como línea gruesa de p0 a p1 (rotation_z en sentido horario).
    def _poner_segmento(self, cuadro, p0, p1, grosor, tono):
        cu, cv, largo, rotacion = hud_calculos.segmento_a_cuadro(p0, p1)
        cuadro.position = (cu, cv)
        cuadro.scale = (largo, grosor)
        cuadro.rotation_z = rotacion
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
            u, v = g.punto(x, z)
            aro.position = punto.position = (u, v)
            aro.enabled = es_activo
            punto.enabled = True                 # reaparece si el nombre vuelve a estar
            aro.scale = 0.026
            punto.scale = 0.018 if es_activo else 0.012
            punto.color = rgb(rgb_rol) if es_activo else color.rgba32(*rgb_rol, 130)
            punto.z = -0.0005 if es_activo else 0.001     # los demás, detrás del activo

        if destino is None:
            self.marcador_destino.enabled = False
        else:
            self.marcador_destino.enabled = True
            self.marcador_destino.position = g.lugar(destino)
            self.marcador_destino.scale = g.diametro_plaza() * 1.35

        for nombre, rgb_rol, x, z in posiciones:
            if nombre == activo:
                self._dibujar_ruta(x, z, ruta)
                return
        self._dibujar_ruta(0, 0, [])

    def _dibujar_ruta(self, x, z, ruta):
        firma = (tuple(ruta), round(x, 3), round(z, 3))
        if firma == self._firma_ruta:
            return
        self._firma_ruta = firma
        g = self.geometria
        segmentos = g.segmentos_ruta(x, z, ruta)
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
            self.flecha.position = (flecha[0], flecha[1])
            self.flecha.rotation_z = flecha[2]       # horario desde arriba = rotation_z de Ursina

    def entidades_dibujadas(self):
        # Entidades visibles con su posición local (u, v): para comprobar el recorte.
        todas = [self.capa_calles, self.capa_ruta, self.capa_lugares, self.capa_jugadores]
        resultado = []
        for capa in todas:
            resultado += [e for e in capa.children if e.enabled]
        if self.flecha.enabled:
            resultado.append(self.flecha)
        return resultado


# -- Aviso de interacción --------------------------------------------------------


class AvisoInteraccion(Entity):

    TEXTO = "Presiona E para acceder"

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.position = (0, -0.5 + MARGEN + 0.04)
        ancho, alto = 0.44, 0.07
        _fondo(self, ancho, alto, COLOR_FONDO_HUD, 12, z=0.001)
        self.texto = Text(self.TEXTO, parent=self, origin=(0, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(22), color=rgb(estilo.COLOR_TEXTO))
        self.enabled = False

    def actualizar(self, estado_mision, estado_telefono):
        self.enabled = hud_calculos.aviso_visible(estado_mision, estado_telefono)


# -- Panel de turno ----------------------------------------------------------------


class PanelTurno(Entity):

    RELLENO = 0.014

    def __init__(self, **opciones):
        super().__init__(**opciones)
        self.fondo = _fondo(self, 0.1, 0.1, COLOR_FONDO_HUD, 8, z=0.001)
        self.texto_turno = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(22),
                                color=rgb(estilo.COLOR_TEXTO))
        self.texto_mision = Text("", parent=self, origin=(-0.5, 0.5), scale=escala_fuente(17),
                                 color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.position = (-window.aspect_ratio / 2 + MARGEN, 0.5 - MARGEN)

    # Fija los textos y ajusta el fondo al más ancho.
    def fijar(self, turno, mision):
        self.texto_turno.text = _seguro(turno)
        self.texto_mision.text = _seguro(mision)
        ancho = max(_medidor(self.texto_turno)(self.texto_turno.text),
                    _medidor(self.texto_mision)(self.texto_mision.text))
        alto_turno, alto_mision = a_unidades(22) * 1.2, a_unidades(17) * 1.2
        r = self.RELLENO
        self.fondo.model = modelo_redondeado(ancho + 2 * r, alto_turno + alto_mision + 2 * r, 8)
        self.fondo.scale = (ancho + 2 * r, alto_turno + alto_mision + 2 * r)
        self.fondo.position = ((ancho + 2 * r) / 2, -(alto_turno + alto_mision + 2 * r) / 2)
        self.texto_turno.position = (r, -r, -0.001)
        self.texto_mision.position = (r, -r - alto_turno, -0.001)


# -- Fin de la partida ---------------------------------------------------------------


# Panel centrado "Partida terminada": indicadores finales de la ciudad y un botón para
# volver al menú. Lo muestra EscenaMundo cuando FlujoPartida.partida_terminada().
class PanelFinPartida(Entity):

    TITULO = "Partida terminada"
    ANCHO, ALTO = 0.62, 0.56

    def __init__(self, al_menu, **opciones):
        super().__init__(**opciones)
        _fondo(self, self.ANCHO, self.ALTO, COLOR_FONDO_HUD, 14, z=0.002)
        Text(self.TITULO, parent=self, origin=(0, 0), position=(0, self.ALTO / 2 - 0.07, -0.001),
             scale=escala_fuente(32), color=rgb(estilo.COLOR_TEXTO))
        Text("Indicadores finales de Ciudad Nova", parent=self, origin=(0, 0),
             position=(0, self.ALTO / 2 - 0.13, -0.001), scale=escala_fuente(17),
             color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.textos = {}
        for i, nombre in enumerate(("convivencia", "confianza", "desinformacion")):
            self.textos[nombre] = Text(
                "", parent=self, origin=(0, 0), position=(0, 0.06 - i * 0.075, -0.001),
                scale=escala_fuente(24), color=rgb(estilo.COLOR_TEXTO))
        self.boton_menu = BotonAccion(
            "Volver al menú", al_clic=al_menu, ancho=0.36, alto=a_unidades(56),
            parent=self, position=(0, -self.ALTO / 2 + 0.09, -0.001))
        self.enabled = False

    # Muestra el panel con los valores de `indicadores` (dict nombre -> 0..100).
    def mostrar(self, indicadores):
        for nombre, texto in self.textos.items():
            texto.text = f"{estilo.ETIQUETAS_INDICADORES[nombre]}: {indicadores[nombre]}"
        self.enabled = True

    def ocultar(self):
        self.enabled = False


# -- HUD completo -------------------------------------------------------------------


class HudMundo(Entity):

    # mapa: MapaCiudad. El HUD arranca desactivado (EscenaMundo lo activa al entrar).
    # al_menu: callback del botón "Volver al menú" del panel de fin de partida.
    def __init__(self, mapa, obtener_flujo, al_menu=None, **opciones):
        opciones.setdefault("parent", camera.ui)
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self._obtener_flujo = obtener_flujo
        self.panel_turno = PanelTurno(parent=self)
        self.minimapa = Minimapa(mapa, parent=self)
        self.telefono_ui = TelefonoUI(self._telefono_activo, self._mision_actual, parent=self)
        self.aviso = AvisoInteraccion(parent=self)
        self.panel_fin = PanelFinPartida(
            lambda: al_menu() if al_menu is not None else None, parent=self)
        self.guia = hud_calculos.GuiaRuta(mapa)

    def _telefono_activo(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.jugador_activo().telefono

    def _mision_actual(self):
        flujo = self._obtener_flujo()
        return None if flujo is None else flujo.mision_actual()

    # Un paso del HUD (dt segundos): ruta, minimapa, teléfono y aviso con el estado del
    # modelo. Devuelve True si la ruta cambió (EscenaMundo redibuja la del mundo).
    def actualizar(self, dt, sesion):
        flujo = self._obtener_flujo()
        if flujo is None or sesion is None:
            return False
        activo = flujo.jugador_activo()
        mision = flujo.mision_actual()
        destino = mision.destino if mision is not None else None
        cambio = self.guia.actualizar(activo.x, activo.z, destino)

        self.minimapa.actualizar(
            [(j.nombre, ROLES[j.rol].color, j.x, j.z) for j in sesion.jugadores()],
            activo.nombre, destino, self.guia.ruta)
        self.telefono_ui.avanzar(dt)
        self.aviso.actualizar(flujo.estado_mision(), activo.telefono.estado())
        return cambio


# -- Ruta en el mundo ----------------------------------------------------------------


# Ruta BFS resaltada sobre las calles del mundo: cubos planos brillantes y discos en
# las esquinas, ligeramente sobre las calles (tapa de las calles y=0.04, plazas 0.07,
# disco del edificio 0.09, aro del avatar 0.12). Sin sombreado (siempre brillantes).
class RutaMundo(Entity):

    Y_SEGMENTO = 0.095       # cubo de 0.02: tapa en y = 0.105
    Y_JUNTA = 0.110
    ANCHO = 0.7

    def __init__(self, mapa, **opciones):
        super().__init__(**opciones)
        self._mapa = mapa
        self.segmentos = []
        self.juntas = []
        self._firma = None

    def actualizar(self, x, z, ruta):
        firma = (tuple(ruta), round(x, 2), round(z, 2))
        if firma == self._firma:
            return
        self._firma = firma
        puntos = hud_calculos.puntos_de_ruta(self._mapa, x, z, ruta)
        pares = list(zip(puntos, puntos[1:]))
        tono = rgb(COLOR_RUTA)
        while len(self.segmentos) < len(pares):
            self.segmentos.append(pieza(parent=self, model="cube", color=tono, shader=None))
        while len(self.juntas) < len(puntos):
            self.juntas.append(pieza(parent=self, model="circle", rotation_x=90, color=tono,
                                     shader=None, scale=self.ANCHO))
        for cubo, (p0, p1) in zip(self.segmentos, pares):
            cx, cz, largo, rumbo = hud_calculos.segmento_mundo(p0, p1)
            cubo.position = (cx, self.Y_SEGMENTO, cz)
            cubo.scale = (self.ANCHO, 0.02, largo)
            cubo.rotation_y = rumbo
            cubo.enabled = True
        for cubo in self.segmentos[len(pares):]:
            cubo.enabled = False
        for disco, (px, pz) in zip(self.juntas, puntos):
            disco.position = (px, self.Y_JUNTA, pz)
            disco.enabled = True
        for disco in self.juntas[len(puntos):]:
            disco.enabled = False

    def segmentos_visibles(self):
        return [s for s in self.segmentos if s.enabled]
