# Mapa grande a pantalla casi completa (solo en el mundo grande, ~900 x 650 m). Se abre y se cierra con la tecla «N»
# (frontend/mapa_grande_calculos.py: TECLA_MAPA; «M» es «Seguir misión» y «Tab» el teléfono) y también se cierra con
# Escape (EscenaMundo.alternar_pausa llama a HudMundo.cerrar_mapa_grande antes de abrir la pausa).
#
# Mientras está abierto los controles del mundo quedan congelados (EscenaMundo.controles_bloqueados lo consulta) y el
# ratón se suelta, igual que con el teléfono abierto; el minimapa, el panel de turno, el teléfono y los avisos se
# esconden (`visible`) para que nada choque con el mapa en 16:9 ni en 4:3, y se restauran al cerrar.
#
# Capas (frontend/minimapa_calculos.py, registro global): zonas, misiones, objetivos y NPC se dibujan encima del terreno
# y se rehacen solo si el registro cambia. Controles locales con el mapa abierto: + / - zoom (centrado en el jugador) y R
# alterna «norte arriba» / «gira con la cámara» (los rótulos se mantienen derechos). Solo existe con el mundo grande.
#
# Mallas ESTÁTICAS SIN CASAS: fondo de terreno suavizado por altura (colores por vértice con sombreado de ladera), calles,
# plazas de los 24 lugares con su color y su nombre corto, y encima los jugadores, el destino de la misión y la ruta del
# GPS (esto último es lo único que cambia por frame). Todo se compone al abrir y solo se rehace si cambia la proporción
# de la ventana. Lo que se decide con números está en frontend/mapa_grande_calculos.py (con pruebas sin ventana).

import time

from panda3d.core import LVecBase4, ScissorEffect
from ursina import Entity, Mesh, Text, camera, color

from backend.datos.nombres_visibles import nombre_visible
from backend.logica import ajustes as modelo_ajustes
from frontend import (
    diseno_adaptable, estilo, hud_calculos, mapa_grande_calculos as calc, minimapa_calculos as mm, tipografia)
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, rgb
from frontend.hud import COLOR_DESTINO, COLOR_RUTA, Minimapa, _fondo, _medidor, _seguro

COLOR_CALLE = (196, 200, 214)
COLOR_CALLE_BORDE = estilo.TINTA
COLOR_CHIP = color.rgba32(12, 14, 24, 205)
PX_ETIQUETA = 14
FLECHA = [(0, 0.5, 0), (-0.42, -0.5, 0), (0, -0.22, 0), (0.42, -0.5, 0)]      # punta arriba, centrada en el origen


class MapaGrandeVista(Entity):

    Z_PANEL = -2.0                     # delante de todo el HUD
    LARGO_FLECHA_JUGADOR = 0.05

    # mapa: MundoGrande. puede_abrir: callable() -> bool (partida en curso, sin pausa ni cinemática ni otro panel).
    # ocultar: entidades del HUD que se esconden mientras el mapa está abierto.
    def __init__(self, mapa, puede_abrir=None, ocultar=(), **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(**opciones)
        self._mapa = mapa
        self._puede_abrir = puede_abrir
        self._ocultar = list(ocultar)
        self._previos = []
        self.abierto = False
        terreno = getattr(mapa, "terreno", None)
        self._extension = tuple(terreno.extension) if terreno is not None and hasattr(terreno, "extension") else mapa.limites()
        self._rejilla = None                # (xs, zs, colores, triangulos): se calcula la primera vez que se abre
        self._aspecto = None
        self._encaje = None
        self.panel = Entity(parent=self, z=self.Z_PANEL, enabled=False)
        self.contenido = Entity(parent=self.panel)
        self.recomposiciones = 0            # cuántas veces se compuso el mapa (lo usan las pruebas)
        self.registro = mm.registro()
        self.zoom = 1.0                     # zoom local (calc.ZOOMS_MAPA); vuelve a 1 al abrir
        self.modo_rotacion = "norte"        # «norte» | «camara»; al abrir parte del ajuste del minimapa
        self.capa_mapa = None
        self.capa_extra = None
        self._firma_transf = None
        self._version_capas = None
        self._yaw = 0.0
        self._t_sondeo = 0.0
        self.reconstrucciones_capas = 0
        self._reiniciar_dinamicos()

    def _reiniciar_dinamicos(self):
        self.puntos = {}                    # nombre -> (aro, punto)
        self.flecha_jugador = None
        self.segmentos_ruta = []
        self._firma_ruta = None
        self._destino_dibujado = "?"
        self.etiquetas = {}                 # lugar -> Text
        self.texto_destino = None
        self.anillo_destino = None

    # -- Abrir y cerrar --

    def input(self, key):
        if key == calc.TECLA_MAPA:
            self.alternar()
        elif self.abierto and key in calc.TECLAS_ZOOM_MAS + calc.TECLAS_ZOOM_MENOS:
            self.cambiar_zoom(1 if key in calc.TECLAS_ZOOM_MAS else -1)
        elif self.abierto and key == calc.TECLA_GIRO:
            self.alternar_giro()

    def cambiar_zoom(self, direccion):
        nuevo = mm.siguiente_escalon(calc.ZOOMS_MAPA, self.zoom, direccion)
        if nuevo != self.zoom:
            self.zoom = nuevo
            self._version_capas = None          # los iconos se rehacen con el tamaño compensado
            self._aplicar_transformacion()

    def alternar_giro(self):
        self.modo_rotacion = "camara" if self.modo_rotacion == "norte" else "norte"
        self._aplicar_transformacion()

    def alternar(self):
        if self.abierto:
            self.cerrar()
            return True
        return self.abrir()

    def abrir(self):
        if self.abierto or (self._puede_abrir is not None and not self._puede_abrir()):
            return False
        self.abierto = True
        self.zoom = 1.0
        if modelo_ajustes.AJUSTES:
            self.modo_rotacion = modelo_ajustes.obtener().actual.minimapa_rotacion
        if self._rejilla is None or self._aspecto != diseno_adaptable.aspecto():
            self._componer()
        self._previos = [(e, e.visible) for e in self._ocultar]
        for e, _ in self._previos:
            e.visible = False               # `visible` y no `enabled`: TelefonoUI se reactiva sola cada frame
        self.panel.enabled = True
        self._version_capas = None
        self._aplicar_transformacion()
        return True

    # True si estaba abierto (Escape lo usa para no abrir la pausa además).
    def cerrar(self):
        if not self.abierto:
            return False
        self.abierto = False
        self.panel.enabled = False
        for e, previo in self._previos:
            e.visible = previo
        self._previos = []
        return True

    # -- Composición (solo al abrir y al cambiar la proporción de la ventana) --

    def _tabla_terreno(self):
        if self._rejilla is None:
            altura = getattr(self._mapa, "altura", None) or (lambda x, z: 0.0)
            xs, zs, alturas = calc.rejilla_alturas(altura, self._extension)
            colores = [color.rgba(*c) for c in calc.colores_de_rejilla(xs, zs, alturas)]
            self._rejilla = (xs, zs, colores, calc.triangulos_de_rejilla(len(xs), len(zs)))
        return self._rejilla

    def _componer(self):
        self.recomposiciones += 1
        destruir_arbol(self.contenido)
        self.contenido = Entity(parent=self.panel)
        self._reiniciar_dinamicos()
        raiz = self.contenido
        self.capa_mapa = mapa_raiz = Entity(parent=raiz)
        self._firma_transf = None
        self.capa_extra = None
        self._version_capas = None
        aspecto = diseno_adaptable.aspecto()
        self._aspecto = aspecto
        area = calc.area_del_mapa(aspecto)
        self._encaje = encaje = calc.encajar(self._extension, area)
        escala = encaje[0]
        mapa = self._mapa

        _fondo(raiz, aspecto - 0.04, 0.96, color.rgba32(12, 14, 24, 255), 14, z=0.01)
        xs, zs, colores, triangulos = self._tabla_terreno()
        vertices = [(*calc.a_pantalla(encaje, x, z), 0) for z in zs for x in xs]
        Entity(parent=mapa_raiz, model=Mesh(vertices=vertices, triangles=triangulos, colors=colores), z=0.0)

        # calles: borde oscuro + relleno claro (legibles sobre cualquier tono del terreno)
        ancho = max(mapa.ancho_calle * escala, 0.007)
        puntos = [(calc.a_pantalla(encaje, *mapa.coordenada(a)), calc.a_pantalla(encaje, *mapa.coordenada(b)))
                  for a, b in mapa.segmentos()]
        for grosor, tono, z in ((ancho + 0.004, COLOR_CALLE_BORDE, -0.001), (ancho, COLOR_CALLE, -0.0015)):
            Entity(parent=mapa_raiz, model=Minimapa._malla_de_cuadrilateros(
                [hud_calculos.segmento_a_rectangulo(p0, p1, grosor) for p0, p1 in puntos]), color=rgb(tono), z=z)

        # plazas con su color y contorno de tinta
        radio = max(mapa.radio_plaza * escala * 1.3, 0.0095)
        lugares = mapa.lugares()
        centros = [calc.a_pantalla(encaje, *mapa.coordenada(l)) for l in lugares]
        Entity(parent=mapa_raiz, z=-0.003, model=Minimapa._malla_de_poligonos(
            [(u, v, radio * 1.28, estilo.TINTA) for u, v in centros], 16))
        Entity(parent=mapa_raiz, z=-0.0035, model=Minimapa._malla_de_poligonos(
            [(u, v, radio, Minimapa.color_de_lugar(l)) for (u, v), l in zip(centros, lugares)], 16))
        self._centros = dict(zip(lugares, centros))
        self._radio_marca = radio

        # etiquetas con nombre corto, colocadas sin pisarse
        textos = {}
        for lugar in lugares:
            t = Text(_seguro(calc.nombre_corto_mapa(nombre_visible(lugar, corto=True))), parent=mapa_raiz, origin=(0, 0),
                     scale=escala_fuente(PX_ETIQUETA), color=rgb(estilo.COLOR_TEXTO))
            textos[lugar] = t
        medir = _medidor(next(iter(textos.values())))
        alto = a_unidades(PX_ETIQUETA) * 1.35
        tamanos = [(medir(textos[l].text) + 0.012, alto) for l in lugares]
        posiciones = calc.colocar_etiquetas([(u, v, radio * 1.28) for u, v in centros], tamanos, area)
        chips, guias = [], []
        self._guias_ent = None
        for lugar, (w, h), (pu, pv, anillo), (mu, mv) in zip(lugares, tamanos, posiciones, centros):
            textos[lugar].position = (pu, pv, -0.0058)
            chips.append(((pu - w / 2, pv - h / 2), (pu + w / 2, pv - h / 2), (pu + w / 2, pv + h / 2), (pu - w / 2, pv + h / 2)))
            if anillo > 0:        # etiqueta apartada de su marca: línea guía hasta el borde de la etiqueta
                fin = (min(max(mu, pu - w / 2), pu + w / 2), min(max(mv, pv - h / 2), pv + h / 2))
                guias.append(hud_calculos.segmento_a_rectangulo((mu, mv), fin, 0.0025))
        if guias:
            self._guias_ent = Entity(parent=mapa_raiz, z=-0.0045, color=rgb(estilo.COLOR_TEXTO_TENUE), model=Minimapa._malla_de_cuadrilateros(guias))
        self._chips_ent = Entity(parent=mapa_raiz, z=-0.005, color=COLOR_CHIP, model=Minimapa._malla_de_cuadrilateros(chips))
        self.etiquetas = textos

        # encabezado y leyenda
        Text("Mapa de Ciudad Nova", parent=raiz, origin=(-0.5, 0.5), scale=escala_fuente(22), font=tipografia.FUENTE_TITULO,
             color=rgb(estilo.COLOR_TEXTO), position=(-aspecto / 2 + 0.05, 0.5 - 0.045, -0.006))
        self.texto_destino = Text("", parent=raiz, origin=(0.5, 0.5), scale=escala_fuente(17), color=rgb(COLOR_DESTINO),
                                  position=(aspecto / 2 - 0.05, 0.5 - 0.05, -0.006))
        self._poner_leyenda(raiz, aspecto)
        self._aplicar_transformacion()

    def _poner_leyenda(self, raiz, aspecto):
        y = -0.5 + 0.06
        x = -aspecto / 2 + 0.06
        Entity(parent=raiz, z=-0.006, position=(x, y), scale=0.034, double_sided=True, color=rgb(estilo.COLOR_TEXTO),
               model=Mesh(vertices=FLECHA, triangles=[(0, 1, 2), (0, 2, 3)]))
        Text("Tú", parent=raiz, origin=(-0.5, 0), scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO),
             position=(x + 0.03, y, -0.006))
        x += 0.13
        Entity(parent=raiz, model="circle", z=-0.006, position=(x, y), scale=0.026, color=rgb(COLOR_DESTINO))
        Entity(parent=raiz, model="circle", z=-0.0065, position=(x, y), scale=0.015, color=rgb(estilo.COLOR_FONDO))
        Text("Destino de la misión", parent=raiz, origin=(-0.5, 0), scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO),
             position=(x + 0.026, y, -0.006))
        x += 0.36
        Entity(parent=raiz, model="quad", z=-0.006, position=(x + 0.02, y), scale=(0.05, 0.009), color=rgb(COLOR_RUTA))
        Text("Ruta del GPS", parent=raiz, origin=(-0.5, 0), scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO),
             position=(x + 0.058, y, -0.006))
        Text("N o Esc: cerrar  ·  + / -: zoom  ·  R: giro", parent=raiz, origin=(0.5, 0), scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE),
             position=(aspecto / 2 - 0.06, y, -0.006))

    # -- Frame (solo con el mapa abierto) --

    # posiciones: [(nombre, rgb_rol, x, z)] de todos los jugadores; activo: nombre del jugador del turno; yaw: yaw de la
    # cámara (el jugador mira hacia allí); destino: lugar o None; ruta: lugares que faltan (GuiaRuta).
    def actualizar(self, posiciones, activo, yaw, destino, ruta):
        if not self.abierto:
            return
        if self._aspecto != diseno_adaptable.aspecto():
            self._componer()
        encaje = self._encaje
        self._yaw = yaw
        presentes = {n for n, _, _, _ in posiciones}
        for nombre, (aro, punto) in self.puntos.items():
            if nombre not in presentes:
                aro.enabled = punto.enabled = False
        pos_activo = None
        for nombre, rgb_rol, x, z in posiciones:
            u, v = calc.a_pantalla(encaje, x, z)
            if nombre == activo:
                pos_activo = (x, z)
                self._poner_jugador(u, v, yaw, rgb_rol)
                continue
            if nombre not in self.puntos:
                aro = Entity(parent=self.capa_mapa, model="circle", z=-0.0072, color=color.white, scale=0.026)
                punto = Entity(parent=self.capa_mapa, model="circle", z=-0.0074, scale=0.018)
                self.puntos[nombre] = (aro, punto)
            aro, punto = self.puntos[nombre]
            aro.position = punto.position = (u, v, aro.z)
            punto.z = -0.0074
            punto.color = rgb(rgb_rol)
            aro.enabled = punto.enabled = True
        self._marcar_destino(destino, pos_activo)
        if pos_activo is not None:
            self._dibujar_ruta(pos_activo, ruta)
        self._actualizar_capas()
        self._pos_activo = pos_activo
        self._aplicar_transformacion()

    # -- Capas del registro (zonas, misiones, objetivos, NPC) --

    ICONO = 0.012                       # radio en pantalla de un marcador (se compensa con el zoom)
    BORDE_ZONA = 0.003

    def _actualizar_capas(self):
        ahora = time.perf_counter()
        if ahora - self._t_sondeo >= 1 / 15:
            self._t_sondeo = ahora
            self.registro.sondear()
        if self._version_capas == (self.registro.version, self.zoom):
            return
        self._version_capas = (self.registro.version, self.zoom)
        self.reconstrucciones_capas += 1
        if self.capa_extra is not None:
            destruir_arbol(self.capa_extra)
        self.capa_extra = extra = Entity(parent=self.capa_mapa, z=-0.0068)

        def proyectar(x, z):
            return calc.a_pantalla(self._encaje, x, z)
        for tono, grupo in mm.plan_zonas(self.registro.zonas(), proyectar, self.BORDE_ZONA / self.zoom).items():
            vertices, triangulos = grupo["relleno"]
            if triangulos:
                Entity(parent=extra, z=0.001, model=Mesh(vertices=vertices, triangles=triangulos),
                       color=color.rgba32(*tono, int(255 * mm.ALFA_RELLENO_ZONA)))
            Entity(parent=extra, z=0.0005, model=Minimapa._malla_de_cuadrilateros(grupo["borde"]),
                   color=color.rgba32(*tono, int(255 * mm.ALFA_BORDE_ZONA)))
        marcadores = self.registro.marcadores()
        if marcadores:
            vertices, triangulos, colores = mm.plan_marcadores(marcadores, proyectar, self.ICONO / self.zoom)
            Entity(parent=extra, model=Mesh(vertices=vertices, triangles=triangulos,
                                            colors=[color.rgba(*c) for c in colores]))

    # Zoom centrado en el jugador y giro opcional: se mueve, escala y gira UNA capa (y los rótulos se contra-giran).
    def _aplicar_transformacion(self):
        capa = self.capa_mapa
        if capa is None or self._encaje is None:
            return
        giro = -self._yaw if self.modo_rotacion == "camara" else 0.0
        area = calc.area_del_mapa(self._aspecto)
        centro = (area[0], area[1])
        pos = getattr(self, "_pos_activo", None)
        if self.zoom == 1.0 and giro == 0.0:
            q = centro
        elif pos is not None:
            q = calc.a_pantalla(self._encaje, *pos)
        else:
            q = centro
        firma = (self.zoom, round(giro, 1), round(q[0], 4), round(q[1], 4), self._aspecto)
        if firma == self._firma_transf:
            return
        self._firma_transf = firma
        capa.scale = self.zoom
        capa.rotation_z = giro
        capa.x, capa.y = calc.posicion_de_capa(self.zoom, giro, q, centro)
        recorte = self.zoom != 1.0 or giro != 0.0
        if recorte:
            izq, der, aba, arr = calc.fracciones_de_area(area, self._aspecto)
            capa.set_effect(ScissorEffect.make_screen(LVecBase4(izq, der, aba, arr)))
        else:
            capa.clear_effect(ScissorEffect.get_class_type())
        for texto in self.etiquetas.values():
            texto.rotation_z = -giro
            texto.scale = escala_fuente(PX_ETIQUETA) / self.zoom
        for malla in (getattr(self, "_chips_ent", None), getattr(self, "_guias_ent", None)):
            if malla is not None:
                malla.enabled = not recorte      # los fondos de las etiquetas son rectángulos del mapa: con giro o zoom se ocultan

    def _poner_jugador(self, u, v, yaw, rgb_rol):
        if self.flecha_jugador is None:
            lado = self.LARGO_FLECHA_JUGADOR
            malla = Mesh(vertices=FLECHA, triangles=[(0, 1, 2), (0, 2, 3)])
            borde = Entity(parent=self.capa_mapa, z=-0.0076, scale=lado * 1.3, double_sided=True, color=color.white, model=malla)
            cuerpo = Entity(parent=self.capa_mapa, z=-0.0078, scale=lado * 0.95, double_sided=True, model=malla)
            self.flecha_jugador = (borde, cuerpo)
        borde, cuerpo = self.flecha_jugador
        cuerpo.color = rgb(rgb_rol)
        for parte in self.flecha_jugador:
            parte.x, parte.y = u, v
            parte.rotation_z = yaw      # horario desde arriba (norte = +z): igual que el yaw de la cámara

    def _marcar_destino(self, destino, pos_activo):
        if destino != self._destino_dibujado:
            self._destino_dibujado = destino
            for lugar, texto in self.etiquetas.items():
                texto.color = rgb(COLOR_DESTINO if lugar == destino else estilo.COLOR_TEXTO)
            if self.anillo_destino is None:
                self.anillo_destino = Entity(parent=self.capa_mapa, model="circle", color=rgb(COLOR_DESTINO), z=-0.0025)
            self.anillo_destino.enabled = destino is not None
            if destino is not None:
                self.anillo_destino.position = (*self._centros[destino], -0.0025)
                self.anillo_destino.scale = self._radio_marca * 2 * 1.9
        if self.texto_destino is None:
            return
        if destino is None:
            texto = "Sin destino: «M» sigue la misión"
        else:
            texto = f"Destino: {nombre_visible(destino, corto=True)}"
            if pos_activo is not None:
                cx, cz = self._mapa.coordenada(destino)
                metros = ((cx - pos_activo[0]) ** 2 + (cz - pos_activo[1]) ** 2) ** 0.5
                texto += f" · {calc.metros_redondeados(metros)} m"
        texto = _seguro(texto)
        if texto != self.texto_destino.text:
            self.texto_destino.text = texto

    def _dibujar_ruta(self, pos_activo, ruta):
        puntos_mundo = calc.puntos_de_ruta(self._mapa, pos_activo[0], pos_activo[1], ruta)
        firma = (tuple(ruta), round(pos_activo[0], 1), round(pos_activo[1], 1))
        if firma == self._firma_ruta:
            return
        self._firma_ruta = firma
        puntos = [calc.a_pantalla(self._encaje, x, z) for x, z in puntos_mundo]
        pares = list(zip(puntos, puntos[1:]))
        while len(self.segmentos_ruta) < len(pares):
            self.segmentos_ruta.append(Entity(parent=self.capa_mapa, model="quad", z=-0.002, color=rgb(COLOR_RUTA)))
        for cuadro, (p0, p1) in zip(self.segmentos_ruta, pares):
            cu, cv, largo, giro = hud_calculos.segmento_a_cuadro(p0, p1)
            cuadro.position = (cu, cv, -0.002)
            cuadro.scale = (largo, 0.0085)
            cuadro.rotation_z = giro
            cuadro.enabled = True
        for cuadro in self.segmentos_ruta[len(pares):]:
            cuadro.enabled = False
