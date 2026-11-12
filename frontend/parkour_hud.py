# HUD del parkour (Ursina, camera.ui): tiempo, checkpoint, caídas, medalla provisional, avisos, ayuda de teclas,
# panel de pausa y panel de resultado. Solo muestra datos; las reglas viven en backend/logica/parkour_calculos.py.
# Todo se entiende con texto (no solo con color). Anclado con diseno_adaptable para que quepa en cualquier aspecto.

from ursina import Entity, Text, camera, color

from backend.logica import parkour_calculos as pk
from frontend import diseno_adaptable, estilo, materiales as mat, minimapa_calculos as mm, parkour_minimapa, tipografia
from frontend import parkour_visual_calculos as pvc
from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb

DURACION_AVISO = 2.2
AYUDA = "WASD mover   Espacio saltar (otra vez en el aire: doble salto)   R volver al checkpoint   Esc pausa"
MARGEN = 0.03


def _texto(padre, cadena, px, tono, pos, origen=(0, 0), negrita=False):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena, parent=padre, origin=origen, position=(pos[0], pos[1], -0.01),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


LADO_PLANO = 0.24            # lado del plano de alturas (unidades de camera.ui)
RADIO_PLANO_M = 14.0         # el plano muestra ±este radio (m) alrededor del jugador
ROTULOS_PLANO = 3            # plataformas más cercanas (a otra altura) que llevan rótulo «+3 m»
COLOR_META = (120, 230, 140)


class PlanoAlturas(Entity):
    """Minimapa del nivel (arriba a la derecha): cada plataforma vista desde arriba, coloreada según quede más alta, más
    baja o al nivel del jugador, y con rótulo «+3 m» / «-2 m» en las más cercanas (no depende solo del color). Los
    cálculos son de parkour_minimapa.plano_de_alturas; aquí solo se dibuja, y solo se repinta cuando algo cambia."""

    def __init__(self, padre):
        super().__init__(parent=padre)
        x = diseno_adaptable.aspecto() / 2 - MARGEN - LADO_PLANO / 2
        self.caja = panel_tinta(self, LADO_PLANO, LADO_PLANO, sombra=False, position=(x, 0.5 - MARGEN - LADO_PLANO / 2))
        self.titulo = _texto(self.caja, "Alturas", 13, estilo.COLOR_TEXTO_TENUE, (0, -LADO_PLANO / 2 - 0.018))
        self.lienzo = Entity(parent=self.caja, scale=LADO_PLANO, z=-0.01)
        self.punto = Entity(parent=self.lienzo, model="circle", scale=0.05, z=-0.03, color=rgb(estilo.COLOR_ACENTO))
        self._quads, self._rotulos = {}, []
        self._alturas = None
        self._firma = None
        diseno_adaptable.anclar(self.caja, "derecha")

    def fijar(self, alturas):
        from frontend.componentes import destruir_arbol
        for e in list(self._quads.values()) + self._rotulos:
            destruir_arbol(e)
        self._quads, self._rotulos, self._firma = {}, [], None
        self._alturas = alturas
        for p in alturas.get("plataformas", []):
            self._quads[p["id"]] = Entity(parent=self.lienzo, model="quad", z=-0.01, enabled=False)
        self._rotulos = [Text("", parent=self.lienzo, origin=(0, 0), z=-0.04, scale=escala_fuente(12) / LADO_PLANO,
                              color=rgb(estilo.COLOR_TEXTO)) for _ in range(ROTULOS_PLANO)]

    def actualizar(self, x, z, y):
        if self._alturas is None:
            return
        plano = parkour_minimapa.plano_de_alturas(self._alturas, x, z, y, radio_m=RADIO_PLANO_M)
        visibles = [p for p in plano["plataformas"] if p["visible"]]
        for p in plano["plataformas"]:
            quad = self._quads[p["id"]]
            quad.enabled = p["visible"]
            if p["visible"]:
                quad.x, quad.y = p["x"], p["y"]
                quad.scale_x, quad.scale_y = p["ancho"], p["alto"]
        # Rótulo solo en las plataformas a otra altura (y en la meta): son las que hay que decidir si se alcanzan.
        con_rotulo = [p for p in visibles if p["nivel"] != "igual" or p["meta"]]
        cercanas = sorted(con_rotulo, key=lambda p: p["x"] ** 2 + p["y"] ** 2)[:ROTULOS_PLANO]
        for rotulo, p in zip(self._rotulos, cercanas):
            rotulo.x, rotulo.y = p["x"], p["y"]
        firma = (tuple(p["nivel"] for p in plano["plataformas"]), tuple((p["id"], p["texto"]) for p in cercanas))
        if firma == self._firma:
            return
        self._firma = firma
        for p in plano["plataformas"]:
            self._quads[p["id"]].color = rgb(COLOR_META if p["meta"] else mm.COLORES_NIVEL[p["nivel"]])
        for rotulo, p in zip(self._rotulos, cercanas):
            rotulo.text = "Meta" if p["meta"] else p["texto"]
        for rotulo in self._rotulos[len(cercanas):]:
            rotulo.text = ""


class HudParkour(Entity):

    def __init__(self, al_continuar=None, al_reiniciar=None, al_salir=None):
        super().__init__(parent=camera.ui, enabled=False)
        self._aviso_restante = 0.0
        self.al_continuar, self.al_reiniciar, self.al_salir = al_continuar, al_reiniciar, al_salir

        # Arriba, centro: tiempo y medalla alcanzable.
        self.tiempo = _texto(self, "00:00.0", 34, estilo.COLOR_TEXTO, (0, 0.44), negrita=True)
        self.medalla = _texto(self, "", 17, estilo.COLOR_ACENTO, (0, 0.395))

        # Arriba, izquierda: nivel, checkpoint y caídas.
        self.izquierda = Entity(parent=self)
        x0 = -diseno_adaptable.aspecto() / 2 + MARGEN
        self.nivel_txt = _texto(self.izquierda, "", 17, estilo.COLOR_TEXTO, (x0, 0.46), origen=(-0.5, 0), negrita=True)
        self.checkpoint = _texto(self.izquierda, "", 16, estilo.COLOR_TEXTO_TENUE, (x0, 0.425), origen=(-0.5, 0))
        self.caidas = _texto(self.izquierda, "", 16, estilo.COLOR_TEXTO_TENUE, (x0, 0.392), origen=(-0.5, 0))
        diseno_adaptable.anclar(self.izquierda, "izquierda")

        self.aviso = _texto(self, "", 24, estilo.COLOR_ACENTO, (0, 0.325), negrita=True)
        self.ayuda = _texto(self, AYUDA, 14, estilo.COLOR_TEXTO_TENUE, (0, -0.46))

        self.plano = PlanoAlturas(self)
        self.pausa = self._panel_pausa()
        self.resultado = None
        self.visual = pvc.visual_activo()          # ALCALDE_PARKOUR_VISUAL=0: HUD de antes
        self._destello_estado = None               # (tono, alfa_max, duracion, edad)
        self._aviso_edad = 9.0
        self._tema_aplicado = None
        self._nivel_pistas = None
        if self.visual:
            self._decorar()

    # -- Aspecto nuevo (aditivo): paneles tras el tiempo y el aviso, barra de progreso, leyenda de tipos y destello --

    def _decorar(self):
        def quad(padre, x, y, sx, sy, tono, alfa, z):
            return Entity(parent=padre, model="quad", position=(x, y, z), scale=(sx, sy),
                          color=color.rgba(tono[0] / 255, tono[1] / 255, tono[2] / 255, alfa))

        self.fondo_tiempo = quad(self, 0, 0.418, 0.40, 0.125, (6, 8, 20), 0.62, 0.02)
        self.linea_tema = quad(self, 0, 0.358, 0.40, 0.006, mat.NEON_CIAN, 1.0, 0.015)
        self.barra_fondo = quad(self, 0, 0.372, 0.36, 0.011, (30, 36, 60), 0.9, 0.015)
        self.barra_relleno = quad(self, -0.18, 0.372, 0.0001, 0.011, estilo.COLOR_ACENTO, 1.0, 0.012)
        self.barra_relleno.origin = (-0.5, 0)
        self.pastilla_aviso = quad(self, 0, 0.325, 0.74, 0.062, (6, 8, 20), 0.72, 0.02)
        self.pastilla_aviso.enabled = False
        self._aviso_escala = tuple(self.aviso.scale)
        self._progreso = -1.0
        self.destello_cuadro = quad(self, 0, 0, 3.2, 1.2, (255, 255, 255), 0.0, 0.9)
        self.destello_cuadro.enabled = False
        # Leyenda de tipos: cada tipo tiene color Y patrón en el mundo; aquí además su nombre.
        self.leyenda = Entity(parent=self)
        x0 = -diseno_adaptable.aspecto() / 2 + MARGEN
        quad(self.leyenda, x0 + 0.14, -0.092, 0.31, 0.034 * 6 + 0.03, (6, 8, 20), 0.5, 0.02)
        for i, clave in enumerate(pvc.CLAVES):
            e = pvc.ESTILOS[clave]
            y = -0.02 - 0.034 * i
            quad(self.leyenda, x0 + 0.012, y - 0.0, 0.026, 0.02, e["borde"], 1.0, 0.012)
            quad(self.leyenda, x0 + 0.012, y - 0.0, 0.016, 0.011, e["acento"] if clave != "fija" else e["panel"], 1.0, 0.01)
            _texto(self.leyenda, e["nombre"], 13, estilo.COLOR_TEXTO_TENUE, (x0 + 0.04, y), origen=(-0.5, 0))
        diseno_adaptable.anclar(self.leyenda, "izquierda")

    def destello(self, tono, alfa=0.38, duracion=0.45):
        if self.visual:
            self._destello_estado = [tono, alfa, duracion, 0.0]

    # Avanza destello y asentado del aviso (también con el nivel terminado, para que no queden congelados).
    def avanzar(self, dt):
        if not self.visual:
            return
        if self._destello_estado is not None:
            tono, alfa, dur, edad = self._destello_estado
            edad += dt
            a = pvc.alfa_destello(edad, dur, alfa)
            self._destello_estado[3] = edad
            self.destello_cuadro.enabled = a > 0
            if a > 0:
                self.destello_cuadro.color = color.rgba(tono[0] / 255, tono[1] / 255, tono[2] / 255, a)
            else:
                self._destello_estado = None
        self._aviso_edad += dt
        k = pvc.escala_aviso(self._aviso_edad)
        self.aviso.scale = tuple(v * k for v in self._aviso_escala)
        self.pastilla_aviso.enabled = bool(self.aviso.text)

    def _actualizar_visual(self, sim, nivel):
        if self._tema_aplicado != nivel.id:
            self._tema_aplicado = nivel.id
            acento = mat.tema(nivel.tema)["acento"]
            self.linea_tema.color = color.rgb32(*acento)
            ini, meta = nivel.plataformas[nivel.inicio], nivel.plataformas[nivel.meta]
            self._pistas = ((ini.x, ini.z), (meta.x, meta.z))
        p = pvc.progreso_hacia_meta(sim.x, sim.z, *self._pistas)
        if abs(p - self._progreso) > 0.004:
            self._progreso = p
            self.barra_relleno.scale_x = max(0.0001, 0.36 * p)

    # -- Paneles --

    def _panel_pausa(self):
        panel = panel_tinta(self, 0.62, 0.52)
        panel.z = -0.5
        _texto(panel, "Pausa", 30, estilo.COLOR_TEXTO, (0, 0.18), negrita=True)
        _texto(panel, "Tu avance se conserva: puedes salir al mundo y volver.", 15, estilo.COLOR_TEXTO_TENUE, (0, 0.11))
        BotonPrimario("Continuar", al_clic=lambda: self.al_continuar and self.al_continuar(), parent=panel,
                      position=(0, 0.03, -0.01), ancho=a_unidades(260))
        BotonSecundario("Reiniciar el nivel", al_clic=lambda: self.al_reiniciar and self.al_reiniciar(), parent=panel,
                        position=(0, -0.08, -0.01), ancho=a_unidades(260))
        BotonSecundario("Salir al mundo", al_clic=lambda: self.al_salir and self.al_salir(), parent=panel,
                        position=(0, -0.19, -0.01), ancho=a_unidades(260))
        panel.enabled = False
        diseno_adaptable.ajustar_escala(panel)
        return panel

    # `resultado` = dict de pk.resultado_del_nivel; `nueva_evidencia` True si se acaba de otorgar; `con_estado` False si
    # no hay GameState (el nivel se juega sin consecuencias).
    def mostrar_resultado(self, resultado, nueva_evidencia, con_estado, hay_recompensa):
        self.ocultar_resultado()
        panel = panel_tinta(self, 0.9, 0.78)
        panel.z = -0.5
        _texto(panel, "¡Nivel completado!", 32, estilo.COLOR_ACENTO, (0, 0.32), negrita=True)
        lineas = [
            f"Tiempo: {pk.formatear_tiempo(resultado['tiempo_s'])}      Caídas: {resultado['caidas']}",
            f"{pk.NOMBRE_CATEGORIA[resultado['categoria']]}      Eficiencia: {resultado['eficiencia']:.0f} %",
            f"Puntos: {resultado['puntos']}      Medalla: {pk.NOMBRE_MEDALLA[resultado['medalla']]}",
        ]
        for i, linea in enumerate(lineas):
            _texto(panel, linea, 20, estilo.COLOR_TEXTO, (0, 0.20 - 0.07 * i))
        optima = " > ".join(resultado["ruta_optima"])
        _texto(panel, f"Ruta óptima (Dijkstra): {optima}", 13, estilo.COLOR_TEXTO_TENUE, (0, -0.02))
        if nueva_evidencia:
            mensaje, tono = "Evidencia obtenida: queda en tu archivo de casos.", estilo.ESTADO_EXITO
        elif not hay_recompensa:
            mensaje, tono = "Este nivel no otorga evidencia.", estilo.COLOR_TEXTO_TENUE
        elif not con_estado:
            mensaje, tono = "Sin partida activa: la evidencia no se guarda.", estilo.ESTADO_AVISO
        else:
            mensaje, tono = "Ya tenías la evidencia de este nivel, o aún no alcanzas la medalla pedida.", estilo.ESTADO_AVISO
        _texto(panel, mensaje, 17, tono, (0, -0.10))
        BotonPrimario("Volver al mundo", al_clic=lambda: self.al_salir and self.al_salir(), parent=panel,
                      position=(-0.2, -0.27, -0.01), ancho=a_unidades(230))
        BotonSecundario("Reintentar", al_clic=lambda: self.al_reiniciar and self.al_reiniciar(), parent=panel,
                        position=(0.2, -0.27, -0.01), ancho=a_unidades(230))
        diseno_adaptable.ajustar_escala(panel)
        self.resultado = panel

    def ocultar_resultado(self):
        if self.resultado is not None:
            from frontend.componentes import destruir_arbol
            gestor = diseno_adaptable.obtener()
            if gestor is not None:
                gestor.olvidar(self.resultado)
            destruir_arbol(self.resultado)
            self.resultado = None

    def mostrar_pausa(self, visible):
        self.pausa.enabled = bool(visible)

    # -- Frame --

    def avisar(self, texto, tono=None):
        self.aviso.text = texto
        self._aviso_restante = DURACION_AVISO
        if self.visual:
            self.aviso.color = rgb(tono or estilo.COLOR_ACENTO)
            self._aviso_edad = 0.0

    @staticmethod
    def _poner(texto, cadena):
        if getattr(texto, "_cadena_puesta", None) != cadena:
            texto._cadena_puesta = cadena
            texto.text = cadena

    def actualizar(self, sim, nivel, dt):
        # Asignar .text reconstruye la malla del texto: solo se hace cuando la cadena cambia de verdad.
        self._poner(self.tiempo, pk.formatear_tiempo(sim.t))
        self._poner(self.medalla,
                    f"Medalla alcanzable: {pk.NOMBRE_MEDALLA[pk.medalla_alcanzable(nivel, sim.t, sim.caidas)]}")
        self._poner(self.checkpoint, f"Checkpoint: {sim.checkpoint}")
        self._poner(self.caidas, f"Caídas: {sim.caidas}")
        self._poner(self.nivel_txt, nivel.nombre)
        self.plano.actualizar(sim.x, sim.z, sim.y)
        if self.visual:
            self._actualizar_visual(sim, nivel)
            self.avanzar(dt)
        if self._aviso_restante > 0:
            self._aviso_restante -= dt
            if self._aviso_restante <= 0:
                self.aviso.text = ""
