# HUD del parkour (Ursina, camera.ui): tiempo, checkpoint, caídas, medalla provisional, avisos, ayuda de teclas,
# panel de pausa y panel de resultado. Solo muestra datos; las reglas viven en backend/logica/parkour_calculos.py.
# Todo se entiende con texto (no solo con color). Anclado con diseno_adaptable para que quepa en cualquier aspecto.

import os

from ursina import Entity, Text, camera, color

from backend.logica import parkour_calculos as pk
from frontend import diseno_adaptable, estilo, materiales as mat, minimapa_calculos as mm, parkour_minimapa, tipografia
from frontend import parkour_visual_calculos as pvc
from frontend import ui_botw_b
from frontend.componentes import boton_piel_primario, boton_piel_secundario, a_unidades, escala_fuente, panel_piel, rgb

DURACION_AVISO = 2.2
DURACION_AVISO_PURGA = 1.4
# Aviso («¡Checkpoint!», «¡Purga!…»): pegado bajo el panel del tiempo (que acaba en y = 0,3555) y más fino. Antes, en
# y = 0,325 con 0,062 de alto, tapaba la franja de arriba del cuadro, donde se ve la plataforma siguiente (S2).
Y_AVISO, ALTO_PASTILLA_AVISO, PX_AVISO = 0.333, 0.046, 21
Y_PURGA = 0.345              # cuenta atrás de la purga: arriba a la izquierda, bajo «Caídas»
AYUDA = "WASD mover   Espacio saltar (otra vez en el aire: doble salto)   R volver al checkpoint   Esc pausa"
MARGEN = 0.03
# ALCALDE_PARKOUR_SIN_RUTA (encendida): el panel de resultado ya no enseña la ruta óptima (Dijkstra) ni el bloque de
# pk.textos_ruta_dijkstra. Solo se quita la PRESENTACIÓN: parkour_calculos la sigue calculando y el loader la usa para
# validar niveles. ALCALDE_PARKOUR_SIN_RUTA=0 vuelve a mostrarla como antes.
PARKOUR_SIN_RUTA = True


def sin_ruta_activo():
    valor = os.environ.get("ALCALDE_PARKOUR_SIN_RUTA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PARKOUR_SIN_RUTA)


def _texto(padre, cadena, px, tono, pos, origen=(0, 0), negrita=False):
    opciones = {"font": tipografia.fuente_piel(titulo=True)} if negrita else {}
    return Text(cadena, parent=padre, origin=origen, position=(pos[0], pos[1], -0.01),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


# (nota de la pausa, rótulo del botón) según haya o no un destino de retorno distinto del mundo.
TEXTOS_SALIDA = {False: ("Tu avance se conserva: puedes salir al mundo y volver.", "Salir al mundo"),
                 True: ("Tu avance se conserva: puedes salir y volver.", "Volver")}

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
        self.caja = panel_piel(self, LADO_PLANO, LADO_PLANO, sombra=False, position=(x, 0.5 - MARGEN - LADO_PLANO / 2))
        # «Alturas» con su pastilla oscura: sin ella no se leía encima de las plataformas claras.
        Entity(parent=self.caja, model="quad", position=(0, -LADO_PLANO / 2 - 0.018, 0.005), scale=(0.1, 0.03),
               color=color.rgba(6 / 255, 8 / 255, 20 / 255, 0.7))
        self.titulo = _texto(self.caja, "Alturas", 13, estilo.COLOR_TEXTO, (0, -LADO_PLANO / 2 - 0.018))
        self.lienzo = Entity(parent=self.caja, scale=LADO_PLANO, z=-0.01)
        self.punto = Entity(parent=self.lienzo, model="circle", scale=0.05, z=-0.03, color=rgb(estilo.COLOR_ACENTO))
        self._quads, self._rotulos = {}, []
        self._alturas = None
        self._firma = None
        diseno_adaptable.anclar(self.caja, "derecha")

    def fijar(self, alturas):
        from frontend.componentes import destruir_arbol
        fondos = [r.fondo for r in self._rotulos if getattr(r, "fondo", None) is not None]
        for e in list(self._quads.values()) + self._rotulos + fondos:
            destruir_arbol(e)
        self._quads, self._rotulos, self._firma = {}, [], None
        self._alturas = alturas
        for p in alturas.get("plataformas", []):
            self._quads[p["id"]] = Entity(parent=self.lienzo, model="quad", z=-0.01, enabled=False)
        self._rotulos = [Text("", parent=self.lienzo, origin=(0, 0), z=-0.04, scale=escala_fuente(12) / LADO_PLANO,
                              color=rgb(estilo.COLOR_TEXTO)) for _ in range(ROTULOS_PLANO)]
        # Pastilla oscura tras cada rótulo: así no se confunde con los cuadros de las plataformas que tiene debajo.
        for rotulo in self._rotulos:
            rotulo.fondo = Entity(parent=self.lienzo, model="quad", z=-0.035, scale=(0.26, 0.09), enabled=False,
                                  color=color.rgba(6 / 255, 8 / 255, 20 / 255, 0.85))

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
        # Rótulos sin pisarse ni salirse del recuadro (parkour_minimapa.colocar_rotulos): encima de su plataforma.
        puestos = parkour_minimapa.colocar_rotulos(sorted(con_rotulo, key=lambda p: p["x"] ** 2 + p["y"] ** 2),
                                                   maximo=ROTULOS_PLANO)
        cercanas = [p for _, _, p in puestos]
        for rotulo, (rx, ry, _) in zip(self._rotulos, puestos):
            rotulo.x, rotulo.y = rx, ry
            rotulo.fondo.x, rotulo.fondo.y = rx, ry
        for i, rotulo in enumerate(self._rotulos):
            rotulo.fondo.enabled = i < len(puestos)
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

        self.aviso = _texto(self, "", PX_AVISO, estilo.COLOR_ACENTO, (0, Y_AVISO), negrita=True)
        self.ayuda = _texto(self, AYUDA, 14, estilo.COLOR_TEXTO_TENUE, (0, -0.46))

        self.plano = PlanoAlturas(self)
        self.pausa = self._panel_pausa()
        self.resultado = None
        self.visual = pvc.visual_activo()          # ALCALDE_PARKOUR_VISUAL=0: HUD de antes
        self._destello_estado = None               # (tono, alfa_max, duracion, edad)
        self._aviso_edad = 9.0
        self._tema_aplicado = None
        self._nivel_pistas = None
        # Purga (sesión E): cuenta atrás roja arriba a la izquierda, bajo «Caídas», con su pastilla oscura. Antes iba en
        # el centro (y = 0,255) y, con el aviso, tapaba la cabeza del personaje y la plataforma a la que salta (S2).
        self.purga_fondo = Entity(parent=self.izquierda, model="quad", position=(x0 + 0.13, Y_PURGA, 0.02),
                                  scale=(0.27, 0.05), color=color.rgba(40 / 255, 4 / 255, 12 / 255, 0.78), enabled=False)
        self.purga_txt = _texto(self.izquierda, "", 24, pvc.COLOR_PURGA, (x0 + 0.012, Y_PURGA), origen=(-0.5, 0),
                                negrita=True)
        self._purga_corria = False
        self.leyenda_extra = None
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
        self.pastilla_aviso = quad(self, 0, Y_AVISO, 0.66, ALTO_PASTILLA_AVISO, (6, 8, 20), 0.72, 0.02)
        # Fondos oscuros tras el texto de arriba a la izquierda y la línea de teclas: encima de las plataformas claras
        # (cian, verde, amarillo) no se leían.
        xi = -diseno_adaptable.aspecto() / 2 + MARGEN
        quad(self.izquierda, xi + 0.28, 0.426, 0.6, 0.11, (6, 8, 20), 0.6, 0.02)
        self.fondo_ayuda = quad(self, 0, -0.46, 1.12, 0.04, (6, 8, 20), 0.6, 0.02)
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
            _texto(self.leyenda, e["nombre"], 16, estilo.COLOR_TEXTO_TENUE, (x0 + 0.04, y), origen=(-0.5, 0))
        diseno_adaptable.anclar(self.leyenda, "izquierda")

    # Leyenda de los tipos de la sesión E presentes en el nivel (y de la purga), bajo la de siempre.
    def _leyenda_nueva(self, nivel):
        if self.leyenda_extra is not None:
            self.leyenda_extra.disable()
            self.leyenda_extra = None
        tipos = [c for c in pvc.CLAVES_NUEVAS if any(p.tipo == c for p in nivel.plataformas.values())]
        filas = [(pvc.ESTILOS[c]["borde"], pvc.ESTILOS[c]["acento"], pvc.ESTILOS[c]["nombre"]) for c in tipos]
        if nivel.purga:
            filas.append((pvc.COLOR_PURGA, (255, 200, 210), "Purga (se borra)"))
        if not filas:
            return
        self.leyenda_extra = Entity(parent=self)
        x0 = -diseno_adaptable.aspecto() / 2 + MARGEN
        y_base = -0.02 - 0.034 * len(pvc.CLAVES)
        alto = 0.034 * len(filas) + 0.02
        Entity(parent=self.leyenda_extra, model="quad", position=(x0 + 0.14, y_base - alto / 2 + 0.027, 0.02),
               scale=(0.31, alto), color=color.rgba(6 / 255, 8 / 255, 20 / 255, 0.5))
        for i, (borde, acento, nombre) in enumerate(filas):
            y = y_base - 0.034 * i
            Entity(parent=self.leyenda_extra, model="quad", position=(x0 + 0.012, y, 0.012), scale=(0.026, 0.02),
                   color=color.rgb32(*borde))
            Entity(parent=self.leyenda_extra, model="quad", position=(x0 + 0.012, y, 0.01), scale=(0.016, 0.011),
                   color=color.rgb32(*acento))
            _texto(self.leyenda_extra, nombre, 16, estilo.COLOR_TEXTO_TENUE, (x0 + 0.04, y), origen=(-0.5, 0))
        diseno_adaptable.anclar(self.leyenda_extra, "izquierda")

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
            acento = pvc.tema_base(nivel.tema)["acento"]
            self._leyenda_nueva(nivel)
            self.linea_tema.color = color.rgb32(*acento)
            ini, meta = nivel.plataformas[nivel.inicio], nivel.plataformas[nivel.meta]
            self._pistas = ((ini.x, ini.z), (meta.x, meta.z))
        p = pvc.progreso_hacia_meta(sim.x, sim.z, *self._pistas)
        if abs(p - self._progreso) > 0.004:
            self._progreso = p
            self.barra_relleno.scale_x = max(0.0001, 0.36 * p)

    # -- Paneles --

    def _panel_pausa(self):
        panel = panel_piel(self, 0.62, 0.52)
        panel.z = -0.5
        _texto(panel, "Pausa", 30, estilo.COLOR_TEXTO, (0, 0.18), negrita=True)
        self._nota_pausa = _texto(panel, TEXTOS_SALIDA[False][0], 15, estilo.COLOR_TEXTO_TENUE, (0, 0.11))
        boton_piel_primario("Continuar", al_clic=lambda: self.al_continuar and self.al_continuar(), parent=panel,
                            position=(0, 0.03, -0.01), ancho=a_unidades(260))
        boton_piel_secundario("Reiniciar el nivel", al_clic=lambda: self.al_reiniciar and self.al_reiniciar(), parent=panel,
                              position=(0, -0.08, -0.01), ancho=a_unidades(260))
        self._boton_salir = boton_piel_secundario(TEXTOS_SALIDA[False][1], al_clic=lambda: self.al_salir and self.al_salir(),
                                                  parent=panel, position=(0, -0.19, -0.01), ancho=a_unidades(260))
        panel.enabled = False
        diseno_adaptable.ajustar_escala(panel)
        return panel

    # `resultado` = dict de pk.resultado_del_nivel; `nueva_evidencia` True si se acaba de otorgar; `con_estado` False si
    # no hay GameState (el nivel se juega sin consecuencias).
    def mostrar_resultado(self, resultado, nueva_evidencia, con_estado, hay_recompensa):
        self.ocultar_resultado()
        panel = panel_piel(self, 0.9, 0.78)
        panel.z = -0.5
        titulo = _texto(panel, "¡Nivel completado!", 32, estilo.COLOR_ACENTO, (0, 0.32), negrita=True)
        # Piel BOTW (ALCALDE_UI_BOTW, frontend/ui_botw_b.py): título en cursiva negrita y entrada del panel.
        ui_botw_b.vestir(panel, titulos=(titulo,), piezas=(panel,))
        lineas = [
            f"Tiempo: {pk.formatear_tiempo(resultado['tiempo_s'])}      Caídas: {resultado['caidas']}",
            f"{pk.NOMBRE_CATEGORIA[resultado['categoria']]}      Eficiencia: {resultado['eficiencia']:.0f} %",
            f"Puntos: {resultado['puntos']}      Medalla: {pk.NOMBRE_MEDALLA[resultado['medalla']]}",
        ]
        for i, linea in enumerate(lineas):
            _texto(panel, linea, 20, estilo.COLOR_TEXTO, (0, 0.20 - 0.07 * i))
        y_mensaje = -0.10
        if sin_ruta_activo():
            pass
        elif pk.resultado_v2_activo():
            y_mensaje = self._bloque_ruta_v2(panel, resultado)
        else:
            optima = " > ".join(resultado["ruta_optima"])
            _texto(panel, f"Ruta óptima (Dijkstra): {optima}", 13, estilo.COLOR_TEXTO_TENUE, (0, -0.02))
        if nueva_evidencia:
            mensaje, tono = "Evidencia obtenida: queda en tu archivo de casos.", estilo.ESTADO_EXITO
        elif not hay_recompensa:
            mensaje, tono = "Este nivel no otorga evidencia.", estilo.COLOR_TEXTO_TENUE
        elif not con_estado and getattr(self, "_hay_retorno", False):   # desde la Fiscalía: la prueba la entrega el caso
            mensaje, tono = "La prueba se entrega al caso al volver al laboratorio.", estilo.COLOR_TEXTO
        elif not con_estado:
            mensaje, tono = "Sin partida activa: la evidencia no se guarda.", estilo.ESTADO_AVISO
        else:
            mensaje, tono = "Ya tenías la evidencia de este nivel, o aún no alcanzas la medalla pedida.", estilo.ESTADO_AVISO
        # el aviso más largo (74 letras) a 17 px se salía unos píxeles del panel (visto en ventana a 1280x720): con el
        # resultado v2 los largos van a 15 px
        _texto(panel, mensaje, 15 if pk.resultado_v2_activo() and len(mensaje) > 60 else 17, tono, (0, y_mensaje))
        # con destino de retorno propio (laboratorio de la Fiscalía) el botón no promete «el mundo»
        boton_piel_primario("Volver" if getattr(self, "_hay_retorno", False) else "Volver al mundo", al_clic=lambda: self.al_salir and self.al_salir(), parent=panel,
                            position=(-0.2, -0.27, -0.01), ancho=a_unidades(230))
        boton_piel_secundario("Reintentar", al_clic=lambda: self.al_reiniciar and self.al_reiniciar(), parent=panel,
                              position=(0.2, -0.27, -0.01), ancho=a_unidades(230))
        diseno_adaptable.ajustar_escala(panel)
        self.resultado = panel

    # Bloque de la ruta Dijkstra del resultado v2 (pk.textos_ruta_dijkstra): cabecera, la ruta partida en líneas que
    # caben en el panel y el coste de la ruta del jugador. Retorna la altura a la que va el mensaje de la evidencia.
    def _bloque_ruta_v2(self, panel, resultado):
        cabecera, lineas, pie = pk.textos_ruta_dijkstra(resultado)
        y = 0.0
        _texto(panel, cabecera, 14, estilo.COLOR_TEXTO, (0, y))
        for linea in lineas[:4]:
            y -= 0.032
            _texto(panel, linea, 13, estilo.COLOR_TEXTO_TENUE, (0, y))
        if pie:
            y -= 0.036
            _texto(panel, pie, 13, estilo.COLOR_TEXTO_TENUE, (0, y))
        return min(-0.10, y - 0.05)

    def ocultar_resultado(self):
        if self.resultado is not None:
            from frontend.componentes import destruir_arbol
            gestor = diseno_adaptable.obtener()
            if gestor is not None:
                gestor.olvidar(self.resultado)
            destruir_arbol(self.resultado)
            self.resultado = None

    # Con destino de retorno propio (p. ej. el laboratorio de la Fiscalía) la pausa no promete «el mundo».
    def fijar_retorno(self, hay_retorno):
        nota, boton = TEXTOS_SALIDA[bool(hay_retorno)]
        self._hay_retorno = bool(hay_retorno)
        try:
            self._nota_pausa.text = nota
            self._boton_salir.text = boton
        except Exception:                                # noqa: BLE001  solo es texto: nunca tumba la entrada
            pass

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
        self._actualizar_purga(sim, nivel)
        if self.visual:
            self._actualizar_visual(sim, nivel)
            self.avanzar(dt)
        if self._aviso_restante > 0:
            self._aviso_restante -= dt
            if self._aviso_restante <= 0:
                self.aviso.text = ""

    # Cuenta atrás de la purga (sesión E) y aviso al empezar. Sin purga en el nivel no muestra nada.
    def _actualizar_purga(self, sim, nivel):
        restante = sim.purga_restante() if getattr(nivel, "purga", None) else None
        corre = restante is not None
        if corre and not self._purga_corria:
            self.avisar("¡Purga! El suelo se borra detrás de ti", pvc.COLOR_PURGA)
            self._aviso_restante = DURACION_AVISO_PURGA          # más breve: el tramo de la purga es el más exigente
        self._purga_corria = corre
        self._poner(self.purga_txt, pvc.texto_purga(restante) if corre else "")
        self.purga_fondo.enabled = corre
