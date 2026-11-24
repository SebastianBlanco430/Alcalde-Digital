# Minimapa de FOTO AÉREA para el mundo chico (estilo GTA): el recuadro enseña lo que rodea al jugador, AMPLIADO, con la foto de la
# ciudad (frontend/mapa_satelite.py) de fondo, centrado en él y girando con la cámara (o con el norte arriba, según el ajuste).
#
# POR QUÉ. Con la ciudad entera en 280 x 200 px la foto salía de ~1 px por metro: un rombo diminuto ilegible. Aquí la ventana es
# de ±RADIO_VENTANA m (≈ 90 x 64 m), unos 4 px por metro: se distinguen techos, plazas, la cancha y los árboles.
#
# QUÉ DIBUJA (todo recortado al recuadro con un scissor):
#   - la foto (una malla con la textura) y encima, en el MISMO sistema de coordenadas del mundo: una marca pequeña por lugar con su
#     color, y las zonas y marcadores del registro (misiones, objetivos, NPC; frontend/minimapa_calculos.py);
#   - la ruta del GPS (cian) y el destino: un anillo amarillo si cae dentro de la ventana o una flecha en el borde hacia él si no;
#   - los demás jugadores (puntos) y el jugador activo, SIEMPRE en el centro (flecha con el color de su rol).
# El mundo no se rehace al andar: la capa estática se mueve y gira UNA vez por frame (la misma técnica del minimapa local del
# mundo grande: hud_calculos.GeometriaMinimapaLocal).
#
# LO CREA Minimapa.poner_satelite (hud.py) como hijo suyo y lo llama desde Minimapa.actualizar / fijar_yaw; si algo falla, el
# minimapa vuelve al vectorial de siempre (el guardián está en Minimapa.poner_satelite).

import math

from panda3d.core import LVecBase4, ScissorEffect
from ursina import Entity, Mesh, camera, color

from backend.logica import navegacion
from frontend import diseno_adaptable, estilo, hud_calculos, minimapa_calculos as mm
from frontend.componentes import destruir_arbol, rgb

RADIO_VENTANA = 44.0          # m del centro al borde izquierdo/derecho del recuadro
RADIO_LUGAR = 0.0105          # radio en pantalla de la marca de un lugar
ANCHO_RUTA = 0.0065
LARGO_FLECHA = 0.05
FORMA_FLECHA = Mesh(vertices=[(0, 0.5, 0), (-0.42, -0.5, 0), (0, -0.22, 0), (0.42, -0.5, 0)], triangles=[(0, 1, 2), (0, 2, 3)])
TINTE_FOTO = color.rgba(0.94, 0.94, 0.97, 1.0)


class MinimapaFoto(Entity):

    # minimapa: el Minimapa que lo contiene (da ANCHO, ALTO, su posición y escala para el recorte). mapa: MundoCiudad.
    # satelite: mapa_satelite.Satelite. yaw: yaw efectivo inicial.
    def __init__(self, minimapa, mapa, satelite, yaw=0.0, **opciones):
        super().__init__(parent=minimapa, z=-0.0006, **opciones)
        self._minimapa = minimapa
        self._mapa = mapa
        self._sat = satelite
        self.g = hud_calculos.GeometriaMinimapaLocal(
            mapa, (minimapa.ANCHO, minimapa.ALTO), yaw, radio_ventana=RADIO_VENTANA)
        self._yaw_camara = yaw
        self._firma_recorte = None
        self._version_capas = None
        self._t_sondeo = 0.0
        self.recorte = Entity(parent=self)                  # todo lo que se recorta al recuadro
        self.capa_mundo = Entity(parent=self.recorte)       # coordenadas absolutas escaladas: se mueve y gira entera
        self.capa_extra = None
        self._construir_estatico()
        self.capa_ruta = Entity(parent=self.recorte, z=-0.002)
        self.segmentos_ruta = []
        self.capa_jugadores = Entity(parent=self.recorte, z=-0.004)
        self.puntos = {}
        self.marca_destino = Entity(parent=self.recorte, z=-0.0025, model="circle", color=rgb(estilo.COLOR_DESTINO), enabled=False)
        self.centro_destino = Entity(parent=self.marca_destino, model="circle", z=-0.001, scale=0.62, color=rgb(estilo.TINTA))
        self.flecha_destino = Entity(parent=self.recorte, z=-0.0065, model=FORMA_FLECHA, double_sided=True, scale=LARGO_FLECHA * 0.8,
                                     color=rgb(estilo.COLOR_DESTINO), enabled=False)
        self.borde_jugador = Entity(parent=self.recorte, z=-0.0068, model=FORMA_FLECHA, double_sided=True, color=color.white,
                                    scale=LARGO_FLECHA * 1.32)
        self.cuerpo_jugador = Entity(parent=self.recorte, z=-0.007, model=FORMA_FLECHA, double_sided=True,
                                     scale=LARGO_FLECHA * 0.95)
        self.hay_activo = False

    # -- Capa estática (una vez) --

    def _construir_estatico(self):
        g, mapa = self.g, self._mapa
        xmin, xmax, zmin, zmax = (float(v) for v in mapa.limites())
        esquinas = [(xmin, zmin), (xmax, zmin), (xmax, zmax), (xmin, zmax)]
        foto = Entity(parent=self.capa_mundo, z=0.0005, color=TINTE_FOTO,
                      model=Mesh(vertices=[(*g.absoluto(x, z), 0) for x, z in esquinas],
                                 uvs=[self._sat.uv_de(x, z) for x, z in esquinas], triangles=[(0, 1, 2), (0, 2, 3)]))
        foto.set_texture(self._sat.textura, 1)
        lugares = list(mapa.lugares())
        centros = [g.absoluto(*mapa.coordenada(lugar)) for lugar in lugares]
        from frontend.hud import Minimapa
        Entity(parent=self.capa_mundo, z=-0.003, model=Minimapa._malla_de_poligonos(
            [(u, v, RADIO_LUGAR * 1.28, estilo.TINTA) for u, v in centros], 16))
        Entity(parent=self.capa_mundo, z=-0.0035, model=Minimapa._malla_de_poligonos(
            [(u, v, RADIO_LUGAR, Minimapa.color_de_lugar(lugar)) for (u, v), lugar in zip(centros, lugares)], 16))

    # -- Giro y recorte --

    def fijar_yaw(self, yaw_efectivo, yaw_camara):
        self.g.girar(yaw_efectivo)
        self._yaw_camara = yaw_camara

    # El scissor recorta lo que asoma del recuadro (3 px menos: respeta las esquinas redondeadas del fondo). Se rehace solo si el
    # recuadro cambió de sitio, de tamaño o de proporción de ventana.
    def _ajustar_recorte(self):
        m = self._minimapa
        aspecto = diseno_adaptable.aspecto()
        pos, escala = m.get_pos(camera.ui), m.get_scale(camera.ui)
        firma = (round(pos.x, 5), round(pos.y, 5), round(escala.x, 5), round(escala.y, 5), round(aspecto, 4))
        if firma == self._firma_recorte:
            return
        self._firma_recorte = firma
        mitad_x, mitad_y = (m.ANCHO / 2 - 0.003) * escala.x, (m.ALTO / 2 - 0.003) * escala.y
        izq, der = (pos.x - mitad_x) / aspecto + 0.5, (pos.x + mitad_x) / aspecto + 0.5
        aba, arr = pos.y - mitad_y + 0.5, pos.y + mitad_y + 0.5
        self.recorte.set_effect(ScissorEffect.make_screen(LVecBase4(izq, der, aba, arr)))

    # -- Frame --

    # posiciones: [(nombre, rgb_rol, x, z)]; activo: nombre del jugador del turno; destino: lugar o None; ruta: lugares que faltan.
    def actualizar(self, posiciones, activo, destino, ruta):
        g = self.g
        self._yaw_camara = self._minimapa._yaw_camara        # lo mantiene Minimapa.fijar_yaw aunque el mapa no gire (norte arriba)
        pos = next(((x, z) for nombre, _, x, z in posiciones if nombre == activo), None)
        self.hay_activo = pos is not None
        self.cuerpo_jugador.enabled = self.borde_jugador.enabled = self.hay_activo      # sin jugador activo no hay flecha
        if pos is not None:
            g.centrar(*pos)
        u, v, giro = g.transformacion_capa()
        self.capa_mundo.position = (u, v)
        self.capa_mundo.rotation_z = giro
        self._ajustar_recorte()
        self._capas_del_registro()
        self._jugadores(posiciones, activo)
        self._destino(destino)
        self._ruta(pos, ruta)

    def _capas_del_registro(self):
        import time
        ahora = time.perf_counter()
        reg = self._minimapa.registro
        if ahora - self._t_sondeo >= 1 / 15:
            self._t_sondeo = ahora
            reg.sondear()
        if self._version_capas == reg.version:
            return
        self._version_capas = reg.version
        if self.capa_extra is not None:
            destruir_arbol(self.capa_extra)
        self.capa_extra = extra = Entity(parent=self.capa_mundo, z=-0.0038)
        g = self.g
        from frontend.hud import Minimapa
        for tono, grupo in mm.plan_zonas(reg.zonas(), g.absoluto, 0.003).items():
            vertices, triangulos = grupo["relleno"]
            if triangulos:
                Entity(parent=extra, z=0.001, model=Mesh(vertices=vertices, triangles=triangulos),
                       color=color.rgba32(*tono, int(255 * mm.ALFA_RELLENO_ZONA)))
            Entity(parent=extra, z=0.0005, model=Minimapa._malla_de_cuadrilateros(grupo["borde"]),
                   color=color.rgba32(*tono, int(255 * mm.ALFA_BORDE_ZONA)))
        marcadores = reg.marcadores()
        if marcadores:
            vertices, triangulos, colores = mm.plan_marcadores(marcadores, g.absoluto, 0.012)
            Entity(parent=extra, model=Mesh(vertices=vertices, triangles=triangulos, colors=[color.rgba(*c) for c in colores]))

    def _jugadores(self, posiciones, activo):
        g = self.g
        presentes = {nombre for nombre, _, _, _ in posiciones}
        for nombre, (aro, punto) in self.puntos.items():
            if nombre not in presentes:
                aro.enabled = punto.enabled = False
        giro_flecha = self._yaw_camara - g.yaw              # con la cámara arriba apunta arriba; con el norte arriba, hacia donde mira
        for nombre, rgb_rol, x, z in posiciones:
            if nombre == activo:
                if nombre in self.puntos:                   # hot-seat: antes era un punto; ahora es la flecha del centro
                    self.puntos[nombre][0].enabled = self.puntos[nombre][1].enabled = False
                self.cuerpo_jugador.color = rgb(rgb_rol)
                self.borde_jugador.rotation_z = self.cuerpo_jugador.rotation_z = giro_flecha
                continue
            if nombre not in self.puntos:
                self.puntos[nombre] = (Entity(parent=self.capa_jugadores, model="circle", color=color.white, scale=0.022),
                                       Entity(parent=self.capa_jugadores, model="circle", z=-0.0005, scale=0.015))
            aro, punto = self.puntos[nombre]
            aro.position = punto.position = (*g.acotar(*g.punto(x, z), margen=0.012), aro.z)
            punto.z = -0.0005
            punto.color = rgb(rgb_rol)
            aro.enabled = punto.enabled = True

    def _destino(self, destino):
        g = self.g
        if destino is None:
            self.marca_destino.enabled = self.flecha_destino.enabled = False
            return
        # punto exacto de la misión (puerta de la Fiscalía), el mismo en que termina la ruta del suelo; si no, el lugar
        x, z = navegacion.destino_en_minimapa(self._mapa, destino, getattr(self._minimapa, "punto_destino", None))
        flecha = g.flecha_de_borde(x, z, margen=LARGO_FLECHA * 0.9)
        self.marca_destino.enabled = flecha is None
        self.flecha_destino.enabled = flecha is not None
        if flecha is None:
            self.marca_destino.position = (*g.punto(x, z), -0.0025)
            self.marca_destino.scale = RADIO_LUGAR * 2 * 2.1
        else:
            self.flecha_destino.position = (flecha[0], flecha[1], -0.0065)
            self.flecha_destino.rotation_z = flecha[2]

    def _ruta(self, pos, ruta):
        g = self.g
        exacta = getattr(self._minimapa, "ruta_puntos", None)       # la polilínea del suelo (misión con punto exacto)
        if pos is not None and exacta and len(exacta) > 1:
            puntos = [g.punto(*p) for p in [pos] + list(exacta[1:])]
        else:
            puntos = [] if pos is None or not ruta else [g.punto(*p) for p in hud_calculos.puntos_de_ruta(self._mapa, pos[0], pos[1], ruta)]
        pares = list(zip(puntos, puntos[1:]))
        while len(self.segmentos_ruta) < len(pares):
            self.segmentos_ruta.append(Entity(parent=self.capa_ruta, model="quad", color=rgb(estilo.COLOR_RUTA)))
        for cuadro, (p0, p1) in zip(self.segmentos_ruta, pares):
            cu, cv, largo, giro = hud_calculos.segmento_a_cuadro(p0, p1)
            cuadro.position = (cu, cv, 0)
            cuadro.scale = (largo, ANCHO_RUTA)
            cuadro.rotation_z = giro
            cuadro.enabled = True
        for cuadro in self.segmentos_ruta[len(pares):]:
            cuadro.enabled = False
