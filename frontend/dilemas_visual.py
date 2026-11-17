# DILEMAS visuales (Ursina). El panel de dilemas (tecla K; frontend/registro_dilemas.py y backend/logica/dilemas.py, que
# no cambian) se juega igual, pero:
#   - al abrirlo, el dilema se presenta como una ESCENA DE CÓMIC (frontend/cinematica_final.crear_vinetas, importado):
#     el barrio, tú con el teléfono y alguien que espera, con la situación en la cartela. Continuar lleva al panel;
#   - en el panel, las opciones son BURBUJAS DE PENSAMIENTO del personaje: tu retrato a la izquierda y una estela de
#     burbujas que sube hasta cada opción;
#   - al elegir, un panel «MAÑANA…» con la escena congelada (la viñeta en gris) y un gran signo de interrogación anticipa
#     que habrá una consecuencia;
#   - cuando llega (aviso del reloj al día siguiente), aparece junto al aviso la viñeta del día anterior en miniatura con
#     lo que elegiste.
# Entra envolviendo la vista del panel (conexion.dilemas_ui.vista), sin tocar registro_dilemas.py. El reloj de la vista
# lo da ControlDilemas.avanzar(), que llama a vista.chip() cada frame.
# APAGADO: ALCALDE_DILEMAS_VISUAL=0. GUARDIÁN: un fallo avisa una vez por stderr, esconde lo añadido y el panel sigue igual.

from ursina import Entity, Text, camera, color, time

from frontend import banderas_visuales as bv
from frontend import diseno_adaptable, estilo, tipografia
from frontend import dilemas_visual_calculos as calc
from frontend.componentes import escala_fuente, panel_tinta, rgb

DILEMAS_VISUAL = True
VARIABLE = "ALCALDE_DILEMAS_VISUAL"
SEGUNDOS_AYER = 8.0
CREMA = (252, 248, 232)


def activo():
    return bv.activa(DILEMAS_VISUAL, VARIABLE)


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class VistaDilemaVisual:

    def __init__(self, original, control, escena):
        self._original = original
        self._control = control
        self._escena = escena
        self.roto = False
        self._cinematica = None
        self._ultimo_comic = None
        self._recuerdos = []
        self._t_ayer = None
        panel = original.panel
        self.burbujas = Entity(parent=panel.marco, z=-0.005, enabled=False)
        self.retrato = Entity(parent=self.burbujas, model="quad", scale=0.17, position=(-0.75, -0.3, -0.01))
        Entity(parent=self.burbujas, model="circle", scale=0.2, color=_rgba(estilo.TINTA), position=(-0.75, -0.3, 0))
        self._nubes = []
        for boton in panel.botones:
            nube = Entity(parent=self.burbujas, position=(boton.x, boton.y, 0.004))
            nube.fondo = panel_tinta(nube, 1.22, 0.092, tono=CREMA, radio_px=40, sombra=False, borde_px=2)
            nube.puntitos = [Entity(parent=self.burbujas, model="circle", color=_rgba(CREMA), z=0.003) for _ in range(3)]
            self._nubes.append(nube)
        # «Mañana…»: la escena del cómic CONGELADA (en gris) + lo elegido + un gran «?».
        self.manana = Entity(parent=panel.marco, position=(0, -0.2, -0.03), enabled=False)
        panel_tinta(self.manana, 0.7, 0.3, tono=(70, 70, 76), radio_px=10)
        _mini_escena(self.manana, -0.2, 0.03, gris=True)
        self.manana_titulo = Text("", parent=self.manana, origin=(-0.5, 0.5), position=(-0.32, 0.135, -0.01),
                                  scale=escala_fuente(13), color=_rgba((200, 200, 205)))
        Text("?", parent=self.manana, origin=(0, 0), position=(0.25, 0.0, -0.01), scale=escala_fuente(80),
             font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_ACENTO))
        self.manana_texto = Text("", parent=self.manana, origin=(-0.5, 0.5), position=(-0.05, 0.06, -0.01),
                                 scale=escala_fuente(15), font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_TEXTO))
        # Al día siguiente: la misma escena en miniatura, ya a color, junto a lo que elegiste.
        self.ayer = Entity(parent=camera.ui, z=-0.4, enabled=False)
        panel_tinta(self.ayer, 0.66, 0.22, tono=(70, 70, 76), radio_px=10)
        _mini_escena(self.ayer, -0.21, 0.0, gris=False)
        self.ayer_texto = Text("", parent=self.ayer, origin=(-0.5, 0.5), position=(-0.08, 0.07, -0.01),
                               scale=escala_fuente(13), color=_rgba(estilo.COLOR_TEXTO))
        Text("!", parent=self.ayer, origin=(0, 0), position=(0.28, 0.0, -0.01), scale=escala_fuente(50),
             font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_ACENTO))

    def __getattr__(self, nombre):
        return getattr(self._original, nombre)

    # -- API de VistaDilema --

    def mostrar_dilema(self, contenido):
        self._original.mostrar_dilema(contenido)
        self._vigilar(self._mostrar_dilema, contenido)

    def mostrar_resultado(self, contenido):
        self._original.mostrar_resultado(contenido)
        self._vigilar(self._mostrar_resultado)

    def ocultar(self):
        self._original.ocultar()
        self._vigilar(self._ocultar)

    def chip(self, texto, visible):
        self._original.chip(texto, visible)
        self._vigilar(self._frame, time.dt)

    # -- Lo nuevo --

    def _rol(self):
        try:
            return self._escena.flujo.jugador_activo().rol
        except Exception:                # noqa: BLE001
            return "ciudadano"

    def _mostrar_dilema(self, contenido):
        self._contenido = contenido
        self.manana.enabled = False
        # Burbujas de pensamiento hacia cada opción, desde el retrato del jugador.
        from frontend import iconos
        try:
            self.retrato.texture = iconos.textura_retrato(self._rol())
        except Exception:                # noqa: BLE001
            self.retrato.texture = iconos.textura_retrato("ciudadano")
        desde = (self.retrato.x + 0.07, self.retrato.y + 0.06)
        for i, nube in enumerate(self._nubes):
            hay = i < len(contenido["opciones"])
            nube.enabled = hay
            for punto, (x, y), tam in zip(nube.puntitos, calc.posiciones_puntitos(desde, (nube.x - 0.6, nube.y - 0.03)),
                                         calc.tamanos_puntitos()):
                punto.enabled = hay
                punto.position = (x, y, 0.003)
                punto.scale = tam
        self.burbujas.enabled = True
        # La escena de cómic: una vez por dilema (reabrir el panel no la repite).
        if self._ultimo_comic != contenido.get("id"):
            self._ultimo_comic = contenido.get("id")
            from frontend.cinematica_final import crear_vinetas
            from backend.logica.roles import ROLES
            tono = ROLES[self._rol()].color if self._rol() in ROLES else (60, 70, 120)
            self._cinematica = crear_vinetas([calc.vineta_de_dilema(contenido, tono)], self._fin_comic, segundos=None,
                                             parent=camera.ui)

    def _fin_comic(self):
        cine, self._cinematica = self._cinematica, None
        if cine is not None:
            try:
                from frontend.componentes import destruir_arbol
                destruir_arbol(cine)
            except Exception:            # noqa: BLE001
                pass

    def _mostrar_resultado(self):
        self.burbujas.enabled = False
        resultado = self._control.ultimo_resultado or {}
        contenido = getattr(self, "_contenido", {}) or {}
        hora = None
        try:
            hora = self._escena.flujo.reloj.tiempo_absoluto()
        except Exception:                # noqa: BLE001
            pass
        clave = None
        try:
            from backend.datos import dilemas_loader
            if getattr(self, "_datos_dilemas", None) is None:
                self._datos_dilemas = dilemas_loader.cargar_dilemas()
            clave = calc.clave_retardada(self._datos_dilemas, resultado.get("dilema"), resultado.get("opcion"))
        except Exception:                # noqa: BLE001  sin clave exacta se compara por prefijo
            clave = None
        r = calc.recuerdo(contenido, resultado, hora, clave)
        self._recuerdos.append(r)
        self.manana_titulo.text = contenido.get("titulo", "")[:40]
        self.manana_texto.text = _partir(calc.texto_manana(r["eleccion"]), 20)
        self.manana.enabled = True
        self._original.panel.texto_resultado.y = 0.25         # deja sitio al panel «mañana…» debajo

    def _ocultar(self):
        self.burbujas.enabled = False
        self.manana.enabled = False
        try:
            self._original.panel.texto_resultado.y = 0.2
        except Exception:                # noqa: BLE001
            pass
        if self._cinematica is not None:
            self._fin_comic()

    def _frame(self, dt):
        if self._t_ayer is not None:
            self._t_ayer -= dt
            if self._t_ayer <= 0:
                self._t_ayer = None
                self.ayer.enabled = False

    # -- Al día siguiente --

    def al_aviso(self, aviso):
        if self.roto:
            return
        r = calc.recuerdo_de_aviso(aviso, self._recuerdos)
        if r is None:
            return
        self.ayer_texto.text = _partir(calc.texto_ayer(r), 22)
        media = diseno_adaptable.aspecto() / 2
        self.ayer.position = (media - 0.35, -0.05, -0.4)
        self.ayer.enabled = True
        self._t_ayer = SEGUNDOS_AYER

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self.roto:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("dilemas_visual", error)
            self.roto = True
            for e in (self.burbujas, self.manana, self.ayer):
                try:
                    e.enabled = False
                except Exception:        # noqa: BLE001
                    pass
            self._fin_comic()
            return None


def _mini_escena(padre, x, y, gris):
    """Miniatura de la viñeta del dilema (cielo, suelo, un edificio y dos personas): congelada en gris o a color."""
    def tono(c):
        if not gris:
            return c
        g = int(0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2])
        return (g, g, g)
    raiz = Entity(parent=padre, position=(x, y, -0.005))
    Entity(parent=raiz, model="quad", scale=(0.22, 0.15), color=_rgba(tono((120, 190, 235))))
    Entity(parent=raiz, model="quad", scale=(0.22, 0.04), y=-0.055, z=-0.001, color=_rgba(tono((96, 170, 110))))
    Entity(parent=raiz, model="quad", scale=(0.05, 0.07), position=(-0.07, -0.0, -0.002), color=_rgba(tono((196, 120, 90))))
    for px, c in ((-0.005, (60, 70, 120)), (0.05, (214, 80, 70))):
        Entity(parent=raiz, model="quad", scale=(0.018, 0.04), position=(px, -0.02, -0.003), color=_rgba(tono(c)))
        Entity(parent=raiz, model="circle", scale=0.018, position=(px, 0.009, -0.003), color=_rgba(tono(c)))
    return raiz


def _partir(texto, ancho):
    salida = []
    for parrafo in str(texto).split("\n"):
        palabras, actual = parrafo.split(), ""
        for palabra in palabras:
            if actual and len(actual) + 1 + len(palabra) > ancho:
                salida.append(actual)
                actual = palabra
            else:
                actual = f"{actual} {palabra}".strip()
        if actual:
            salida.append(actual)
    return "\n".join(salida[:5])


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    control = getattr(conexion, "dilemas_ui", None)
    if control is None:
        return None
    envoltorio = bv.envolver_vista(control, VistaDilemaVisual,
                                   lambda vista: VistaDilemaVisual(vista, control, escena_mundo))
    if envoltorio is None:
        return None
    from frontend import observador_avisos
    observador_avisos.instalar(escena_mundo)
    observador_avisos.suscribir(envoltorio.al_aviso)
    return envoltorio
