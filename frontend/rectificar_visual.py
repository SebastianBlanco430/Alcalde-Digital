# «Rectificar» visual (Ursina). La tarjeta de rectificar de la bandeja de Civitas (tecla L; backend/logica/rectificar.py,
# que no cambia) se juega igual, pero a su lado aparece un teléfono con la publicación vieja que SIGUE VIVA:
#   - mientras se lee la tarjeta, los contadores (reacciones, comentarios, compartidos) suben y llegan comentarios
#     enfadados;
#   - RECTIFICAR: la corrección se escribe letra a letra, los contadores bajan y los comentarios pasan a «gracias por aclarar»;
#   - BORRAR: la publicación se desvanece... y a los 2 s reaparece como CAPTURA con borde rojo, en manos de otro usuario;
#   - DEFENDER: los comentarios se multiplican y la publicación se replica en copias por la pantalla.
#   - Al día siguiente, cuando llega la consecuencia (aviso del reloj), aparece la MISMA tarjeta en pequeño junto al aviso.
#   - En el mundo, algunos vecinos cercanos se enojan (defender) o se muestran sociables (rectificar) durante un rato.
#
# Cómo entra sin tocar registro_habitos.py: envuelve la vista del panel (conexion.habitos_ui.vista) con VistaRectificar,
# que llama SIEMPRE a la vista de siempre y solo añade el teléfono cuando la tarjeta es de rectificar. El reloj de la
# vista lo da ControlHabitos.avanzar(), que llama a vista.chip() cada frame (un solo sincronizar por frame, sin update).
# La matemática va en frontend/rectificar_visual_calculos.py (puro, con tests).
#
# APAGADO: ALCALDE_RECTIFICAR_VISUAL=0 (o RECTIFICAR_VISUAL = False). GUARDIÁN: si algo falla, avisa una vez por stderr,
# esconde el teléfono, devuelve el panel a su sitio y la bandeja sigue como siempre.
# REDUCIR MOVIMIENTO: la corrección aparece entera, sin giros en las copias.

from ursina import Entity, Text, color, camera, time

from frontend import banderas_visuales as bv
from frontend import diseno_adaptable, estilo, tipografia
from frontend import rectificar_visual_calculos as calc
from frontend.componentes import escala_fuente, panel_tinta, rgb

RECTIFICAR_VISUAL = True
VARIABLE = "ALCALDE_RECTIFICAR_VISUAL"

ANCHO_TEL, ALTO_TEL = 0.40, 0.80
ANCHO_TEXTO = ANCHO_TEL - 0.05
N_COMENTARIOS = 4
SEGUNDOS_DIA_SIGUIENTE = 8.0
ESCALA_MINI = 0.62
ROJO = (235, 87, 87)
VERDE = (88, 214, 141)


def activo():
    return bv.activa(RECTIFICAR_VISUAL, VARIABLE)


def _partir(cadena, px, ancho, max_lineas, negrita=False):
    from frontend.minijuegos import ui
    lineas = ui.lineas_de(cadena, px, ancho, negrita)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1].rstrip(" .,") + "…"
    return "\n".join(lineas)


def _alfa(entidad, alfa):
    """Opacidad de una entidad y de todos sus hijos con modelo (panel_tinta es un contenedor sin modelo)."""
    pila = [entidad]
    while pila:
        e = pila.pop()
        if getattr(e, "model", None) is not None or isinstance(e, Text):
            e.alpha = alfa
        pila.extend(e.children)


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class PublicacionViva(Entity):
    """El teléfono con la publicación. Se crea una vez y se reutiliza (también para la tarjeta del día siguiente)."""

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        from frontend.telefono_marco import MarcoTelefono
        self.z = -0.075
        self.telefono = MarcoTelefono(ANCHO_TEL, ALTO_TEL, (0, 0), parent=self)
        self.fondo = panel_tinta(self, ANCHO_TEL, ALTO_TEL, tono=(26, 29, 40), radio_px=12, sombra=False, borde_px=0,
                                 position=(0, 0, 0.004))
        x0 = -ANCHO_TEL / 2 + 0.025
        self.rotulo = Text("", parent=self, origin=(-0.5, 0.5), position=(x0, ALTO_TEL / 2 - 0.045, -0.01),
                           scale=escala_fuente(13), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
        # Tarjeta de la publicación (y su versión «captura» con borde rojo).
        self.tarjeta = Entity(parent=self, y=0.235)
        self.borde_captura = panel_tinta(self.tarjeta, ANCHO_TEL - 0.02, 0.18, tono=ROJO, radio_px=8, sombra=False,
                                         borde_px=0, position=(0, 0, 0.002))
        self.cuerpo_tarjeta = panel_tinta(self.tarjeta, ANCHO_TEL - 0.03, 0.17, tono=estilo.COLOR_TARJETA, radio_px=8,
                                          sombra=False, borde_px=0, position=(0, 0, 0.001))
        self.autor = Text("", parent=self.tarjeta, origin=(-0.5, 0.5), position=(x0, 0.075, -0.01),
                          scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO_TENUE), font=tipografia.FUENTE_TITULO)
        self.texto = Text("", parent=self.tarjeta, origin=(-0.5, 0.5), position=(x0, 0.048, -0.01),
                          scale=escala_fuente(14), color=rgb(estilo.COLOR_TEXTO))
        self.contadores = Text("", parent=self, origin=(-0.5, 0.5), position=(x0, 0.13, -0.01),
                               scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.correccion = Text("", parent=self, origin=(-0.5, 0.5), position=(x0, 0.075, -0.01),
                               scale=escala_fuente(13), color=rgb(VERDE), font=tipografia.FUENTE_TITULO)
        self.comentarios = []
        for i in range(N_COMENTARIOS):
            caja = Entity(parent=self, position=(0, -0.06 - i * 0.075, 0))
            panel_tinta(caja, ANCHO_TEL - 0.04, 0.066, tono=(40, 44, 58), radio_px=6, sombra=False, borde_px=0,
                        position=(0, 0, 0.002))
            caja.nombre = Text("", parent=caja, origin=(-0.5, 0.5), position=(x0 + 0.01, 0.026, -0.01),
                               scale=escala_fuente(11), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
            caja.texto = Text("", parent=caja, origin=(-0.5, 0.5), position=(x0 + 0.01, 0.005, -0.01),
                              scale=escala_fuente(11), color=rgb(estilo.COLOR_TEXTO))
            self.comentarios.append(caja)
        self.copias = []          # copias de la publicación (defender): se crean al primer uso, en el padre
        self.estado = calc.VIVA
        self.t = 0.0
        self.t_decision = None
        self._texto_post = ""
        self._comentarios_vistos = None

    # -- Estado --

    def abrir(self, texto_post, rotulo="Civitas · tu publicación de ayer"):
        self._texto_post = texto_post
        self.estado, self.t, self.t_decision = calc.VIVA, 0.0, None
        self.rotulo.text = rotulo
        self.autor.text = "Tú · hace 1 día"
        self.texto.text = _partir(texto_post, 14, ANCHO_TEXTO, 4)
        self.correccion.text = ""
        self.borde_captura.enabled = False
        self.tarjeta.enabled = True
        self._comentarios_vistos = None
        self._alfa_pintada = -1
        self._esconder_copias()
        self.scale = 1.0
        self.enabled = True
        self._pintar()

    def decidir(self, decision):
        if decision in calc.DECISIONES and self.t_decision is None:
            self.estado, self.t_decision = decision, self.t

    def estado_final(self, decision, rotulo):
        """La misma tarjeta, ya en su estado tras decidir (para el día siguiente)."""
        self.abrir(self._texto_post, rotulo)
        self.estado, self.t, self.t_decision = decision, 10.0, 0.0
        self._pintar()

    def cerrar(self):
        self.enabled = False
        self._esconder_copias()

    def _esconder_copias(self):
        for copia in self.copias:
            copia.enabled = False

    # -- Frame --

    def sincronizar(self, dt):
        if not self.enabled:
            return
        self.t += dt
        self._pintar()

    def _pintar(self):
        reducir = bv.reducir_movimiento()
        tras = 0.0 if self.t_decision is None else self.t - self.t_decision
        estado = self.estado
        c = calc.contadores(estado, self.t, self.t_decision)
        self.contadores.text = calc.texto_contadores(c)
        # Publicación original / captura.
        alfa = calc.opacidad_publicacion(estado, tras)
        captura = calc.captura_visible(estado, tras)
        if captura:
            alfa = 1.0
            self.autor.text = "@anonimo_77 · captura de tu publicación"
            self.borde_captura.enabled = True
        self.tarjeta.enabled = alfa > 0.01
        if abs(alfa - getattr(self, "_alfa_pintada", -1)) > 0.01:
            self._alfa_pintada = alfa
            for parte in (self.cuerpo_tarjeta, self.autor, self.texto):
                _alfa(parte, alfa)
        # Corrección letra a letra.
        if estado == calc.RECTIFICAR:
            n = calc.letras(calc.CORRECCION, tras, reducir)
            self.correccion.text = _partir("Corrección: " + calc.CORRECCION[:n], 13, ANCHO_TEXTO, 4, negrita=True) if n else ""
        # Comentarios (solo se reescriben cuando cambian).
        estado_comentarios = estado if self.t_decision is not None else calc.VIVA
        if estado == calc.BORRAR and not captura:
            visibles = []
        else:
            visibles = calc.comentarios_visibles(estado_comentarios, tras if self.t_decision is not None else self.t,
                                                 N_COMENTARIOS)
        if visibles != self._comentarios_vistos:
            self._comentarios_vistos = visibles
            amable = estado_comentarios == calc.RECTIFICAR
            for i, caja in enumerate(self.comentarios):
                caja.enabled = i < len(visibles) and not (estado == calc.RECTIFICAR and i >= 2 and self.correccion.text)
                if i < len(visibles):
                    caja.nombre.text = visibles[i][0]
                    caja.nombre.color = rgb(VERDE if amable else ROJO)
                    caja.texto.text = _partir(visibles[i][1], 11, ANCHO_TEXTO - 0.02, 2)
        # Copias por la pantalla (defender).
        n_copias = calc.copias_visibles(estado, tras, reducir)
        if n_copias:
            self._pintar_copias(n_copias, reducir)

    def _pintar_copias(self, n, reducir):
        if not self.copias:
            for _ in range(calc.COPIAS_MAX):
                # Delante del panel de la bandeja (z -0.06), en zonas sin texto (ver calc.posiciones_copias).
                copia = Entity(parent=self.parent, z=-0.085, enabled=False)
                panel_tinta(copia, 0.30, 0.12, tono=estilo.COLOR_TARJETA, radio_px=8)
                copia.texto = Text("", parent=copia, origin=(-0.5, 0.5), position=(-0.13, 0.045, -0.002),
                                   scale=escala_fuente(11), color=rgb(estilo.COLOR_TEXTO))
                self.copias.append(copia)
        aspecto = diseno_adaptable.aspecto()
        for i, (copia, (x, y, giro)) in enumerate(zip(self.copias, calc.posiciones_copias(7, aspecto=aspecto))):
            if i < n and not copia.enabled:
                copia.position = (x, y, -0.085 - 0.006 * i)
                copia.rotation_z = 0 if reducir else giro
                copia.texto.text = _partir("Compartido: " + self._texto_post, 11, 0.26, 3)
                copia.enabled = True


class VistaRectificar:
    """Envuelve la vista de la bandeja (VistaHabitos): la de siempre pinta; esta añade el teléfono en las tarjetas de
    rectificar. Todo lo demás (panel, chip...) pasa directo a la vista de siempre."""

    def __init__(self, original, control, escena_mundo):
        self._original = original
        self._control = control
        self._escena = escena_mundo
        self.publicacion = PublicacionViva()
        self.roto = False
        self._x_panel = None
        self._t_dia_siguiente = None
        self._recuerdo = {}           # id de caso -> texto de la publicación (para la tarjeta del día siguiente)
        self._vecinos = []            # (personaje, expira_en)
        self._t = 0.0

    def __getattr__(self, nombre):
        return getattr(self._original, nombre)

    # -- API de VistaHabitos --

    def mostrar(self, contenido):
        self._original.mostrar(contenido)
        self._vigilar(self._mostrar_visual, contenido)

    def ocultar(self):
        self._original.ocultar()
        self._vigilar(self._ocultar_visual)

    def chip(self, texto, visible):
        self._original.chip(texto, visible)
        self._vigilar(self._frame, time.dt)

    # -- Lo nuevo --

    def _es_rectificar(self):
        control = self._control
        if control.fase in ("marcar", "decidir"):
            return (control._evento or {}).get("tipo") == "rectificar"
        if control.fase == "revision":
            return (control.ultimo_resultado or {}).get("tipo") == "rectificar"
        return False

    def _mostrar_visual(self, contenido):
        if not self._es_rectificar():
            self._ocultar_visual()
            return
        sitio = calc.lado_a_lado(diseno_adaptable.aspecto())
        panel = self._original.panel
        if sitio is None:                     # ventana estrecha: no cabe al lado; la bandeja queda como siempre
            self.publicacion.cerrar()
            return
        x_panel, x_telefono = sitio
        if self._x_panel is None:
            self._x_panel = panel.x
        panel.x = x_panel
        self.publicacion.x, self.publicacion.y = x_telefono, 0.0
        self._t_dia_siguiente = None
        control = self._control
        if control.fase in ("marcar", "decidir"):
            evento = control._evento
            texto = calc.texto_publicacion(evento.get("texto"))
            self._recuerdo[evento.get("id")] = texto
            if not self.publicacion.enabled or self.publicacion.t_decision is not None \
                    or self.publicacion._texto_post != texto:
                self.publicacion.abrir(texto)
        elif control.fase == "revision":
            resultado = control.ultimo_resultado
            if not self.publicacion.enabled:
                self.publicacion.abrir(self._recuerdo.get(resultado.get("id"), ""))
            self.publicacion.decidir(resultado.get("decision"))
            self._reaccion_vecinos(resultado.get("decision"))

    def _ocultar_visual(self):
        if self._t_dia_siguiente is None:
            self.publicacion.cerrar()
        if self._x_panel is not None:
            self._original.panel.x = self._x_panel
            self._x_panel = None

    def _frame(self, dt):
        self._t += dt
        self.publicacion.sincronizar(dt)
        if self._t_dia_siguiente is not None:
            self._t_dia_siguiente -= dt
            if self._t_dia_siguiente <= 0:
                self._t_dia_siguiente = None
                self.publicacion.cerrar()
        if self._vecinos:
            vivos = []
            for personaje, expira in self._vecinos:
                if expira > self._t:
                    vivos.append((personaje, expira))
                else:
                    try:
                        personaje._postura_forzada = None
                    except Exception:            # noqa: BLE001
                        pass
            self._vecinos = vivos

    # -- Al día siguiente: la misma tarjeta junto al aviso --

    def al_aviso(self, aviso):
        if self.roto:
            return
        datos = calc.decision_de_clave(aviso.get("clave"))
        if datos is None:
            return
        caso_id, decision = datos
        texto = self._recuerdo.get(caso_id)
        if not texto:
            return
        self.publicacion._texto_post = texto
        self.publicacion.estado_final(decision, calc.TITULO_DIA_SIGUIENTE.get(decision, "Ayer en Civitas"))
        self.publicacion.scale = ESCALA_MINI
        media = diseno_adaptable.aspecto() / 2
        self.publicacion.x = media - ANCHO_TEL * ESCALA_MINI / 2 - 0.03
        self.publicacion.y = 0.18
        self._t_dia_siguiente = SEGUNDOS_DIA_SIGUIENTE

    # -- Vecinos cercanos --

    def _reaccion_vecinos(self, decision):
        estado = calc.postura_vecinos(decision)
        if estado is None or self._vecinos:
            return
        candidatos = list(_personajes_del_mundo(self._escena))
        if not candidatos:
            return
        try:
            centro = (camera.world_x, camera.world_z)
            jugador = self._escena.flujo.jugador_activo()
            cuerpo = getattr(jugador, "personaje", None) or getattr(jugador, "cuerpo", None)
            if cuerpo is not None:
                centro = (cuerpo.world_x, cuerpo.world_z)
        except Exception:                        # noqa: BLE001
            pass
        posiciones = [(p.world_x, p.world_z) if p.enabled else None for p in candidatos]
        for i in calc.mas_cercanos(posiciones, centro):
            candidatos[i]._postura_forzada = estado
            self._vecinos.append((candidatos[i], self._t + calc.SEGUNDOS_VECINOS))

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self.roto:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("rectificar_visual", error)
            self.roto = True
            try:
                self.publicacion.cerrar()
                if self._x_panel is not None:
                    self._original.panel.x = self._x_panel
                for personaje, _ in self._vecinos:
                    personaje._postura_forzada = None
                self._vecinos = []
            except Exception:            # noqa: BLE001
                pass
            return None


def _personajes_del_mundo(escena):
    """Cuerpos de NPC del mundo que admiten postura: los peatones."""
    peatones = getattr(escena, "peatones", None)
    for personaje in getattr(peatones, "personajes", None) or ():
        if hasattr(personaje, "aplicar_postura"):
            yield personaje


def registrar(gestor, conexion, escena_mundo):
    """Envuelve la vista de la bandeja de Civitas (si existe) y se suscribe a los avisos del día siguiente."""
    if not activo():
        return None
    control = getattr(conexion, "habitos_ui", None)
    if control is None:
        return None
    envoltorio = bv.envolver_vista(control, VistaRectificar, lambda vista: VistaRectificar(vista, control, escena_mundo))
    if envoltorio is None:
        return None
    from frontend import observador_avisos
    observador_avisos.instalar(escena_mundo)
    observador_avisos.suscribir(envoltorio.al_aviso)
    return envoltorio
