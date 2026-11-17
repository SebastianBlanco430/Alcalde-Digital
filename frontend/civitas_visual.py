# Bandeja de CIVITAS visual (tecla L; frontend/registro_habitos.py y backend/logica/habitos_digitales.py no cambian).
# Junto al panel aparece un teléfono que enseña lo que el panel describe:
#   - ESTAFAS: el mensaje como una notificación real (pantalla de bloqueo con la hora). Marcar una pista dibuja un círculo
#     rojo de rotulador alrededor de su fila (los mismos trazos que «Señales»). Si caes en la estafa, los reales SALEN DE LA
#     BILLETERA del HUD uno por uno; al día siguiente, tu avatar aparece mandando la estafa a tus vecinos;
#   - PUBLICAR FOTO: la foto es una ilustración tuya en el barrio con cada dato en su sitio; tapar un dato es poner una
#     PEGATINA encima. Si publicas con datos a la vista, un PERFIL DESCONOCIDO hace zoom con su lupa sobre lo expuesto;
#   - TIEMPO DE PANTALLA: un feed que se DESLIZA SOLO; la batería y la luz del día BAJAN y la pantalla se va oscureciendo.
# Entra envolviendo la vista de la bandeja (conexion.habitos_ui.vista, por encima de la de rectificar), sin tocar
# registro_habitos.py. El reloj de la vista lo da ControlHabitos.avanzar() (vista.chip() cada frame).
# APAGADO: ALCALDE_CIVITAS_VISUAL=0. REDUCIR MOVIMIENTO: el feed no se desliza; trazos y monedas sin animación.
# GUARDIÁN: un fallo avisa una vez por stderr, esconde lo añadido, devuelve el panel a su sitio y la bandeja sigue igual.

import datetime

from ursina import Entity, Text, camera, color, time

from frontend import banderas_visuales as bv
from frontend import civitas_visual_calculos as calc
from frontend import diseno_adaptable, estilo, tipografia
from frontend import rectificar_visual_calculos as rcalc
from frontend.componentes import escala_fuente, panel_tinta, rgb

CIVITAS_VISUAL = True
VARIABLE = "ALCALDE_CIVITAS_VISUAL"

ANCHO_TEL, ALTO_TEL = 0.40, 0.80
ROJO = (225, 45, 45)
DORADO = (255, 205, 64)
AMARILLO_PEGATINA = (255, 214, 60)
SEGUNDOS_ROBADA = 8.0


def activo():
    return bv.activa(CIVITAS_VISUAL, VARIABLE)


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _partir(cadena, px, ancho, max_lineas, negrita=False):
    from frontend.minijuegos import ui
    lineas = ui.lineas_de(cadena, px, ancho, negrita)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1].rstrip(" .,") + "…"
    return "\n".join(lineas)


class TelefonoCivitas(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        from frontend.telefono_marco import MarcoTelefono
        self.z = -0.075
        self.marco = MarcoTelefono(ANCHO_TEL, ALTO_TEL, (0, 0), parent=self)
        self.pantalla = panel_tinta(self, ANCHO_TEL, ALTO_TEL, tono=(26, 29, 40), radio_px=12, sombra=False, borde_px=0,
                                    position=(0, 0, 0.004))
        self.modo = None
        self._construir_notificacion()
        self._construir_foto()
        self._construir_feed()
        self.velo = Entity(parent=self, model="quad", scale=(ANCHO_TEL, ALTO_TEL), z=-0.05, color=_rgba((0, 0, 0), 0))

    # -- Notificación (estafas) --

    def _construir_notificacion(self):
        self.notificacion = Entity(parent=self, enabled=False)
        self.reloj = Text("", parent=self.notificacion, origin=(0, 0), position=(0, 0.25, -0.01), scale=escala_fuente(46),
                          font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_TEXTO))
        self.fecha = Text("", parent=self.notificacion, origin=(0, 0), position=(0, 0.19, -0.01), scale=escala_fuente(13),
                          color=_rgba(estilo.COLOR_TEXTO_TENUE))
        tarjeta = panel_tinta(self.notificacion, ANCHO_TEL - 0.04, 0.3, tono=(236, 238, 244), radio_px=10, sombra=False,
                              borde_px=0, position=(0, -0.02, -0.005))
        x0 = -ANCHO_TEL / 2 + 0.035
        self.app = Text("CIVITAS · Mensaje · ahora", parent=self.notificacion, origin=(-0.5, 0.5), position=(x0, 0.115, -0.01),
                        scale=escala_fuente(11), font=tipografia.FUENTE_TITULO, color=_rgba((90, 90, 110)))
        self.remitente = Text("", parent=self.notificacion, origin=(-0.5, 0.5), position=(x0, 0.09, -0.01),
                              scale=escala_fuente(12), font=tipografia.FUENTE_TITULO, color=_rgba((25, 25, 35)))
        self.mensaje = Text("", parent=self.notificacion, origin=(-0.5, 0.5), position=(x0, 0.055, -0.01),
                            scale=escala_fuente(12), color=_rgba((30, 30, 40)))
        self.tarjeta_notif = tarjeta

    def notificar(self, evento):
        self._modo("notificacion")
        ahora = datetime.datetime.now()
        self.reloj.text = f"{ahora.hour:02d}:{ahora.minute:02d}"
        self.fecha.text = "Mensaje nuevo"
        self.remitente.text = _partir(evento.get("remitente", ""), 12, ANCHO_TEL - 0.08, 1, True)
        self.mensaje.text = _partir(evento.get("texto", ""), 12, ANCHO_TEL - 0.08, 6)

    # -- Foto (publicar) --

    def _construir_foto(self):
        self.foto = Entity(parent=self, enabled=False)
        Text("Tu foto para Civitas", parent=self.foto, origin=(0, 0), position=(0, 0.3, -0.01), scale=escala_fuente(14),
             font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_ACENTO))
        lienzo = Entity(parent=self.foto, position=(0, 0.08, -0.004))
        Entity(parent=lienzo, model="quad", scale=(0.34, 0.34), color=_rgba((130, 196, 236)))
        Entity(parent=lienzo, model="quad", scale=(0.34, 0.11), y=-0.115, z=-0.001, color=_rgba((110, 168, 110)))
        Entity(parent=lienzo, model="quad", scale=(0.12, 0.16), position=(0.09, 0.0, -0.002), color=_rgba((196, 120, 90)))
        Entity(parent=lienzo, model="quad", scale=(0.05, 0.08), position=(-0.05, -0.04, -0.003), color=_rgba((60, 90, 160)))
        Entity(parent=lienzo, model="circle", scale=0.05, position=(-0.05, 0.02, -0.003), color=_rgba((236, 190, 152)))
        self.lienzo = lienzo
        self.zonas = []
        for _ in range(len(calc.ZONAS_FOTO)):
            zona = Entity(parent=lienzo, z=-0.01, enabled=False)
            zona.fondo = panel_tinta(zona, 0.15, 0.045, tono=(30, 30, 40), radio_px=6, sombra=False, borde_px=0)
            zona.texto = Text("", parent=zona, origin=(0, 0), z=-0.002, scale=escala_fuente(9), color=_rgba((250, 250, 250)))
            zona.pegatina = Entity(parent=zona, z=-0.004, enabled=False)
            Entity(parent=zona.pegatina, model="quad", scale=(0.165, 0.058), rotation_z=-4, color=_rgba(AMARILLO_PEGATINA))
            Text("TAPADO", parent=zona.pegatina, origin=(0, 0), z=-0.001, scale=escala_fuente(9),
                 font=tipografia.FUENTE_TITULO, color=_rgba((40, 30, 10)))
            self.zonas.append(zona)
        self.lupa = Entity(parent=lienzo, z=-0.02, enabled=False)
        Entity(parent=self.lupa, model="circle", scale=0.11, color=_rgba((70, 50, 30)))
        Entity(parent=self.lupa, model="circle", scale=0.095, color=_rgba((235, 238, 245), 0.55), z=-0.001)
        Entity(parent=self.lupa, model="quad", scale=(0.014, 0.06), rotation_z=-40, position=(0.045, -0.05, 0.001),
               color=_rgba((70, 50, 30)))
        self.espia = Text("", parent=self.foto, origin=(0, 0.5), position=(0, -0.12, -0.01), scale=escala_fuente(12),
                          color=_rgba(ROJO))

    def mostrar_foto(self, evento, marcas):
        self._modo("foto")
        elementos = evento.get("elementos", [])
        for i, (zona, (x, y)) in enumerate(zip(self.zonas, calc.zonas_foto(len(self.zonas)))):
            hay = i < len(elementos)
            zona.enabled = hay
            if hay:
                zona.position = (x, y, -0.01)
                zona.texto.text = calc.recortar(elementos[i]["texto"], 17)
                zona.pegatina.enabled = elementos[i]["id"] in marcas
        self.lupa.enabled = False
        self.espia.text = ""

    # -- Feed (tiempo de pantalla) --

    def _construir_feed(self):
        self.feed = Entity(parent=self, enabled=False)
        self.feed_tarjetas = []
        for i in range(3):
            t = Entity(parent=self.feed, z=-0.004)
            panel_tinta(t, ANCHO_TEL - 0.04, 0.2, tono=(40, 44, 58), radio_px=8, sombra=False, borde_px=0)
            t.texto = Text("", parent=t, origin=(-0.5, 0.5), position=(-ANCHO_TEL / 2 + 0.04, 0.08, -0.01),
                           scale=escala_fuente(12), color=_rgba(estilo.COLOR_TEXTO))
            self.feed_tarjetas.append(t)
        self._feed_textos = ["", "", ""]
        self._t_feed = 0.0

    def mostrar_feed(self, texto, minutos):
        self._modo("feed")
        if texto:
            self._feed_textos = [texto] + self._feed_textos[:2]
        for t, cadena in zip(self.feed_tarjetas, self._feed_textos):
            t.texto.text = _partir(cadena or "…", 12, ANCHO_TEL - 0.08, 5)
        self.marco.bateria(calc.bateria(minutos))
        self.velo.color = _rgba((0, 0, 0), calc.oscuridad(minutos, bv.reducir_movimiento()))

    def _modo(self, modo):
        self.modo = modo
        self.notificacion.enabled = modo == "notificacion"
        self.foto.enabled = modo == "foto"
        self.feed.enabled = modo == "feed"
        if modo != "feed":
            self.velo.color = _rgba((0, 0, 0), 0)
            self.marco.bateria(1.0)
        self.enabled = True

    def sincronizar(self, dt):
        if self.enabled and self.modo == "feed":
            self._t_feed += dt
            desplazado = calc.desplazamiento_feed(self._t_feed, 0.22, reducir=bv.reducir_movimiento())
            for i, t in enumerate(self.feed_tarjetas):
                t.y = 0.2 - i * 0.22 + desplazado


class VistaCivitas:

    def __init__(self, original, control, escena):
        self._original = original
        self._control = control
        self._escena = escena
        self.roto = False
        self.telefono = TelefonoCivitas()
        self._x_panel = None
        self._circulos = {}           # índice de fila -> Linea
        self._t_circulos = {}
        self._monedas = []
        self._t_monedas = None
        self._t_lupa = None
        self._exp = []
        self.robada = None
        self._t_robada = None

    def __getattr__(self, nombre):
        return getattr(self._original, nombre)

    # -- API de la vista de la bandeja --

    def mostrar(self, contenido):
        self._original.mostrar(contenido)
        self._vigilar(self._mostrar, contenido)

    def ocultar(self):
        self._original.ocultar()
        self._vigilar(self._ocultar)

    def chip(self, texto, visible):
        self._original.chip(texto, visible)
        self._vigilar(self._frame, time.dt)

    # -- Lo nuevo --

    def _tipo(self):
        c = self._control
        if c.fase in ("marcar", "decidir"):
            return (c._evento or {}).get("tipo")
        if c.fase == "revision":
            return (c.ultimo_resultado or {}).get("tipo")
        if c.fase == "feed":
            return "feed"
        return None

    def _mostrar(self, contenido):
        tipo = self._tipo()
        if tipo not in ("estafa", "publicar", "feed"):
            self._ocultar()
            return
        sitio = rcalc.lado_a_lado(diseno_adaptable.aspecto())
        if sitio is None:                     # ventana estrecha: la bandeja de siempre
            self.telefono.enabled = False
            return
        panel = self._original.panel
        if self._x_panel is None:
            self._x_panel = 0.0
        panel.x = sitio[0]
        self.telefono.position = (sitio[1], 0, -0.075)
        c = self._control
        if tipo == "feed":
            minutos = 0
            try:
                minutos = c._flujo().tiempo_pantalla_hoy()
            except Exception:            # noqa: BLE001
                pass
            # Una publicación trae la hora tras «·» en su contador; la pantalla de entrada al feed no.
            texto = contenido.get("texto") if "·" in contenido.get("contador", "") else ""
            self.telefono.mostrar_feed(texto, minutos)
            self._limpiar_circulos()
            return
        if c.fase in ("marcar", "decidir"):
            evento = c._evento
            if tipo == "estafa":
                self.telefono.notificar(evento)
            else:
                self.telefono.mostrar_foto(evento, c.marcas)
            self._pintar_circulos(evento, c.marcas if c.fase == "marcar" else set())
        elif c.fase == "revision":
            self._limpiar_circulos()
            resultado = c.ultimo_resultado or {}
            if tipo == "estafa" and resultado.get("perdida"):
                self._soltar_monedas(resultado["perdida"])
            elif tipo == "publicar":
                self._exp = calc.expuestos(resultado)
                if self._exp:
                    self._t_lupa = 0.0

    # Círculos de rotulador alrededor de las filas marcadas del panel.
    def _pintar_circulos(self, evento, marcas):
        from frontend.minijuegos_visual import pistas_visuales_calculos as pcalc
        from frontend.minijuegos_visual.trazos import Linea
        filas = self._original.panel.filas
        ids = [e["id"] for e in evento.get("elementos", [])]
        for i, boton in enumerate(filas):
            marcada = i < len(ids) and ids[i] in marcas and boton.enabled
            if marcada and i not in self._circulos:
                linea = Linea(ROJO, 4, parent=boton.parent, z=-0.06)
                linea.position = (boton.x, boton.y, -0.06)
                self._circulos[i] = linea
                self._t_circulos[i] = 0.0
                ancho = boton.scale_x if boton.scale_x > 0.3 else 1.18
                linea.forma = pcalc.circulo_rotulador(ancho / 2 + 0.01, 0.04, semilla=i)
                linea.fijar(pcalc.parcial(linea.forma, 0.02))
            elif not marcada and i in self._circulos:
                self._circulos.pop(i).enabled = False
                self._t_circulos.pop(i, None)

    def _limpiar_circulos(self):
        for linea in self._circulos.values():
            linea.enabled = False
        self._circulos, self._t_circulos = {}, {}

    # Monedas que salen de la billetera del HUD.
    def _soltar_monedas(self, perdida):
        n = calc.monedas(perdida)
        for e in self._monedas:
            e.enabled = False
        while len(self._monedas) < n:
            moneda = Entity(parent=camera.ui, z=-0.3)
            Entity(parent=moneda, model="circle", scale=0.04, color=_rgba((150, 110, 20)))
            Entity(parent=moneda, model="circle", scale=0.033, color=_rgba(DORADO), z=-0.001)
            Text("R$", parent=moneda, origin=(0, 0), z=-0.002, scale=escala_fuente(9), font=tipografia.FUENTE_TITULO,
                 color=_rgba((90, 60, 10)))
            self._monedas.append(moneda)
        self._n_monedas = n
        from frontend.registro_reloj import ALTO_CHIP, MARGEN
        media = diseno_adaptable.aspecto() / 2
        self._origen_monedas = (-media + MARGEN + 0.1, -0.5 + MARGEN + ALTO_CHIP / 2)
        self._t_monedas = 0.0 if not bv.reducir_movimiento() else calc.duracion_monedas(n)

    def _ocultar(self):
        self.telefono.enabled = False
        self._limpiar_circulos()
        if self._x_panel is not None:
            try:
                self._original.panel.x = self._x_panel
            except Exception:            # noqa: BLE001
                pass
            self._x_panel = None
        self._t_lupa = None

    def _frame(self, dt):
        self.telefono.sincronizar(dt)
        reducir = bv.reducir_movimiento()
        from frontend.minijuegos_visual import pistas_visuales_calculos as pcalc
        for i in list(self._t_circulos):
            self._t_circulos[i] += dt
            linea = self._circulos[i]
            linea.fijar(pcalc.parcial(linea.forma, pcalc.avance_trazo(self._t_circulos[i], reducir=reducir)))
            if self._t_circulos[i] > 0.4:
                del self._t_circulos[i]
        if self._t_monedas is not None:
            self._t_monedas += dt
            for i, moneda in enumerate(self._monedas[:self._n_monedas]):
                x, y, alfa = calc.trayectoria_moneda(self._t_monedas, i, self._origen_monedas)
                moneda.enabled = alfa > 0
                moneda.position = (x, y, -0.3)
            if self._t_monedas > calc.duracion_monedas(self._n_monedas):
                self._t_monedas = None
                for moneda in self._monedas:
                    moneda.enabled = False
        if self._t_lupa is not None and self._exp:
            self._t_lupa += dt
            k = int(self._t_lupa / 1.2) % len(self._exp)
            zona = self.telefono.zonas[self._exp[k]]
            lupa = self.telefono.lupa
            lupa.enabled = True
            objetivo = (zona.x, zona.y)
            if reducir:
                lupa.position = (*objetivo, -0.02)
            else:
                from frontend import efectos_ui_calculos as fx
                lupa.x = fx.acercar(lupa.x, objetivo[0], dt, 0.12)
                lupa.y = fx.acercar(lupa.y, objetivo[1], dt, 0.12)
            lupa.scale = 1.0 + (0.0 if reducir else 0.15 * abs(((self._t_lupa * 1.5) % 2) - 1))
            self.telefono.espia.text = _partir(f"@perfil_desconocido hizo zoom en: {zona.texto.text}", 12, ANCHO_TEL - 0.06, 3)
        if self._t_robada is not None:
            self._t_robada -= dt
            if self._t_robada <= 0:
                self._t_robada = None
                self.robada.enabled = False

    # -- Al día siguiente: tu cuenta mandando la estafa a tus vecinos --

    def al_aviso(self, aviso):
        if self.roto or not calc.es_cuenta_robada(aviso):
            return
        self._vigilar(self._cuenta_robada)

    def _cuenta_robada(self):
        if self.robada is None:
            from frontend import iconos
            self.robada = Entity(parent=camera.ui, z=-0.4)
            panel_tinta(self.robada, 0.6, 0.32, tono=(60, 30, 36), radio_px=10)
            yo = Entity(parent=self.robada, model="quad", scale=0.1, position=(-0.2, -0.03, -0.01))
            try:
                rol = self._escena.flujo.jugador_activo().rol
            except Exception:            # noqa: BLE001
                rol = "ciudadano"
            yo.texture = iconos.textura_retrato(rol)
            for k, y in enumerate((0.04, -0.03, -0.1)):
                Entity(parent=self.robada, model="quad", scale=(0.16, 0.006), position=(-0.06, -0.03 + (y + 0.03) * 0.6, -0.01),
                       rotation_z=-(y + 0.03) * 220, color=_rgba(ROJO))
                Entity(parent=self.robada, model="circle", scale=0.05, position=(0.06, y, -0.01),
                       color=_rgba((120 + 30 * k, 170, 220 - 40 * k)))
            Text("Tu cuenta, en manos del estafador,\nmandó el engaño a tus vecinos.", parent=self.robada, origin=(0, 0.5),
                 position=(0.0, 0.145, -0.01), scale=escala_fuente(11), color=_rgba(estilo.COLOR_TEXTO))
        media = diseno_adaptable.aspecto() / 2
        self.robada.position = (media - 0.33, -0.05, -0.4)
        self.robada.enabled = True
        self._t_robada = SEGUNDOS_ROBADA

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self.roto:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("civitas_visual", error)
            self.roto = True
            try:
                self._ocultar()
                for moneda in self._monedas:
                    moneda.enabled = False
                if self.robada is not None:
                    self.robada.enabled = False
            except Exception:            # noqa: BLE001
                pass
            return None


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    control = getattr(conexion, "habitos_ui", None)
    if control is None:
        return None
    envoltorio = bv.envolver_vista(control, VistaCivitas, lambda vista: VistaCivitas(vista, control, escena_mundo))
    if envoltorio is None:
        return None
    from frontend import observador_avisos
    observador_avisos.instalar(escena_mundo)
    observador_avisos.suscribir(envoltorio.al_aviso)
    return envoltorio
