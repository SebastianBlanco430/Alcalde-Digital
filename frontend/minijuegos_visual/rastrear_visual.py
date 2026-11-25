# «Rastrear la fuente» visual (Ursina): el mismo minijuego (frontend/minijuegos/rastrear.py, lógica rastrear_calculos) como
# un TABLERO DE CORCHO de detective, estilo «cómic cívico»:
#   - franja de arriba: la CADENA, que crece de derecha a izquierda. La polaroid «TÚ» está fija a la derecha y cada salto
#     acertado clava una nota más a su izquierda, unida por un hilo rojo que llega flojo y se tensa;
#   - franja de abajo: las 3 notas candidatas (cabecera amarilla con quién y hora, el mensaje y, si es un reenvío, un chip
#     «>>» y la esquina doblada). Foco: la nota sube y se enmarca en amarillo. Error: tiembla, se apaga y queda DESCARTADA;
#   - en medio, una tira de papel con la pregunta del salto, los puntos del progreso y los 2 ovillos de los rodeos, que se
#     apagan al errar;
#   - al llegar al origen, la última nota de la cadena se ilumina con un sello «FUENTE».
# No cambia la partida ni el resultado (hereda y llama a super(); la capa común va delante en el MRO).
# APAGADO: ALCALDE_RASTREAR_VISUAL=0. GUARDIÁN: un fallo al montar esconde el tablero y vuelve a la vista de siempre.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

import random

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import destruir_arbol, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.rastrear import MinijuegoRastrear
from frontend.minijuegos.rastrear_calculos import MAX_ERRORES
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual
from frontend.minijuegos_visual.trazos import Linea

try:
    from frontend.minijuegos_visual import piezas_papel as pp
except Exception:                       # noqa: BLE001
    pp = None
try:
    from frontend.minijuegos_visual import papel_calculos as pc
except Exception:                       # noqa: BLE001
    pc = None

RASTREAR_VISUAL = True
VARIABLE = "ALCALDE_RASTREAR_VISUAL"

TINTA = getattr(estilo, "TINTA", (18, 20, 32))
PAPEL = getattr(estilo, "PAPEL", (250, 244, 228))
ROJO = getattr(estilo, "ESTADO_ERROR", (214, 62, 62))
VERDE = getattr(estilo, "ESTADO_EXITO", (80, 190, 110))
AMARILLO = (255, 220, 60)
CIAN = (70, 220, 255)
CORCHO = getattr(pc, "CORCHO", (150, 106, 66))
CORCHO_OSC = getattr(pc, "CORCHO_OSC", (118, 80, 48))
GRIS_PIN = (150, 150, 165)

BORDE = 0.004
SOMBRA = (0.004, -0.005)
ANCHO_CORCHO, ALTO_CORCHO, Y_CORCHO = 1.70, 0.80, -0.03
Y_CADENA = 0.22
X_TU, PASO_CADENA = 0.70, 0.25
NOTA_CADENA = (0.21, 0.13)
Y_TIRA = 0.06
NOTA = (0.50, 0.34)
Y_NOTAS = -0.195
XS_NOTAS = (-0.55, 0.0, 0.55)
GIROS = (-1.2, 0.6, -0.4)
DUR_TENSAR = 0.2
DUR_TEMBLOR = 0.2


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _txt(parent, cadena, px, tono=TINTA, pos=(0, 0), origen=(0, 0), negrita=True, z=-0.004):
    return Text(str(cadena), parent=parent, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px),
                font=tipografia.fuente_piel(titulo=True) if negrita else tipografia.FUENTE_TEXTO, color=_rgba(tono))


# -- Piezas de papel (de piezas_papel si está; si no, mínimas locales) --

def _hoja(parent, pos, escala, tono=PAPEL, giro=0, z=0, doblez=False):
    if pp is not None:
        try:
            raiz = pp.hoja(parent, pos, escala, color=tono, giro=giro, z=z, doblez=doblez)
            for hijo in raiz.children:          # los polígonos de la esquina doblada no deben perderse por su cara
                hijo.double_sided = True
            return raiz
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], z), rotation_z=giro)
    Entity(parent=raiz, model="quad", position=(SOMBRA[0], SOMBRA[1], 0.002), scale=escala, color=_rgba(TINTA, 0.6))
    Entity(parent=raiz, model="quad", position=(0, 0, 0.001), scale=(escala[0] + 2 * BORDE, escala[1] + 2 * BORDE),
           color=_rgba(TINTA))
    Entity(parent=raiz, model="quad", scale=escala, color=_rgba(tono))
    return raiz


def _chincheta(parent, pos, tono):
    if pp is not None:
        try:
            return pp.chincheta(parent, pos, color=tono)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.004))
    Entity(parent=raiz, model="circle", z=0.001, scale=0.026, color=_rgba(TINTA))
    Entity(parent=raiz, model="circle", scale=0.018, color=_rgba(tono))
    return raiz


def _chip(parent, texto, pos, tono=CIAN):
    if pp is not None:
        try:
            return pp.chip(parent, texto, pos, color=tono)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.003))
    Entity(parent=raiz, model="quad", z=0.001, scale=(0.068, 0.044), color=_rgba(TINTA))
    Entity(parent=raiz, model="quad", scale=(0.06, 0.036), color=_rgba(tono))
    _txt(raiz, texto, 14, pos=(0, 0))
    return raiz


def _ovillo(parent, pos, encendido=True):
    if pp is not None:
        try:
            return pp.ovillo(parent, pos, encendido)
        except Exception:               # noqa: BLE001
            pass

    class _Local(Entity):
        def __init__(self, **o):
            super().__init__(**o)
            Entity(parent=self, model="circle", z=0.001, scale=0.03, color=_rgba(TINTA))
            self._bola = Entity(parent=self, model="circle", scale=0.022)

        def encender(self, valor=True):
            self.encendido = bool(valor)
            self._bola.color = _rgba(ROJO if valor else (214, 200, 168))

    o = _Local(parent=parent, position=(pos[0], pos[1], -0.003))
    o.encender(encendido)
    return o


def _sello(parent, texto, pos, tono, giro=-8, escala=(0.17, 0.06)):
    tono = estilo.tono_legible(tono, PAPEL)               # el texto del sello llega a contraste 4,5 sobre el papel
    if pp is not None:
        try:
            return pp.sello_goma(parent, texto, pos, tono, giro=giro, escala=escala)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.005), rotation_z=giro)
    Entity(parent=raiz, model="quad", z=0.001, scale=escala, color=_rgba(tono))
    Entity(parent=raiz, model="quad", scale=(escala[0] - 0.01, escala[1] - 0.01), color=_rgba(PAPEL))
    _txt(raiz, texto, 16, tono)
    return raiz


PX_TITULO = 14                          # cabecera amarilla de la nota candidata
MARGEN_TITULO = 0.016


def titulo_nota(numero, opcion, ancho):
    """«número   quién  ·  hora» en UNA línea de `ancho` unidades, medida con la fuente y el tamaño con que se dibuja
    (ui.medir, negrita, PX_TITULO px). Si no cabe, se recorta el nombre con «…»; la hora nunca. (Antes el nombre se
    recortaba a 26 caracteres sin medir ni contar la hora y la cabecera se salía de la nota.)"""
    from frontend.minijuegos_3d import corcho_calculos
    return corcho_calculos.cabecera_nota(numero, opcion.get("de", ""), opcion.get("hora") or "",
                                         lambda c: ui.medir(c, PX_TITULO, True) <= ancho)


def _es_reenvio(opcion):
    return "reenviado" in str(opcion.get("texto", "")).lower()


class NotaCandidata(Entity):
    """Nota de papel clavada en el corcho. Misma interfaz que ui.Tarjeta para el minijuego base: ancho, alto, estado,
    habilitada, al_clic, al_cursor, fijar_estado(), fijar_foco()."""

    def __init__(self, opcion, numero, giro=0.0, al_clic=None, al_cursor=None, **opciones):
        super().__init__(**opciones)
        reenvio = _es_reenvio(opcion)
        lineas = ui.lineas_de(str(opcion.get("texto", "")), 16, NOTA[0] - 0.05)
        n_lineas = min(3, len(lineas))
        w = NOTA[0]
        h = pc.alto_nota(n_lineas, reenvio) if pc is not None else NOTA[1]
        self.ancho, self.alto = w, h
        self.al_clic, self.al_cursor = al_clic, al_cursor
        self.habilitada = True
        self.estado = "normal"
        self._foco = False
        self.sello_reenvio = None
        self.y = self.y + NOTA[1] / 2 - h / 2          # borde superior fijo: las notas cuelgan de la misma línea
        self._y0 = self.y
        self.rotation_z = giro
        self.marco = Entity(parent=self, model="quad", scale=(w + 0.03, h + 0.03), z=0.01, color=_rgba(AMARILLO),
                            enabled=False)
        _hoja(self, (0, 0), (w, h), PAPEL, z=0, doblez=reenvio)
        # Cabecera amarilla: número de tecla, quién y hora.
        alto_cab = 0.05
        y_cab = h / 2 - alto_cab / 2
        Entity(parent=self, model="quad", position=(0, y_cab, -0.001), scale=(w, alto_cab), color=_rgba(AMARILLO))
        Entity(parent=self, model="quad", position=(0, y_cab - alto_cab / 2, -0.0015), scale=(w, BORDE),
               color=_rgba(TINTA))
        self.titulo = _txt(self, titulo_nota(numero, opcion, w - 2 * MARGEN_TITULO), PX_TITULO,
                           pos=(-w / 2 + MARGEN_TITULO, y_cab), origen=(-0.5, 0))
        # Cuerpo: 16 px, máximo 3 líneas.
        if len(lineas) > 3:
            lineas = lineas[:3]
            lineas[-1] = lineas[-1].rstrip(" .,") + "…"
        self.cuerpo = _txt(self, "\n".join(lineas), 16, pos=(-w / 2 + 0.02, y_cab - alto_cab / 2 - 0.022),
                           origen=(-0.5, 0.5), negrita=False)
        self.cuerpo.line_height = 1.15
        if reenvio:
            self.sello_reenvio = _sello(self, "REENVIADO", (w / 2 - 0.15, -h / 2 + 0.04), ROJO, giro=-6, escala=(0.19, 0.048))
        _chincheta(self, (0, h / 2 + 0.002), GRIS_PIN)
        # Descartada: velo de corcho (la nota queda a ~35 %) y sello.
        self.velo = Entity(parent=self, model="quad", scale=(w + 0.012, h + 0.012), z=-0.006,
                           color=_rgba(CORCHO, 0.65), enabled=False)
        self.sello = _sello(self, "DESCARTADA", (0, -0.01), ROJO, giro=-8, escala=(0.26, 0.07))
        self.sello.z = -0.02
        self.sello.enabled = False
        self.golpe = Entity(parent=self, model="quad", scale=(w, h), collider="box", color=_rgba((0, 0, 0), 0),
                            z=-0.03)
        self.golpe.on_click = self._clic
        self.golpe.on_mouse_enter = self._entra
        self._pintar()

    def fijar_estado(self, estado, etiqueta=None):
        self.estado = estado
        self._pintar()

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        self._pintar()

    def _pintar(self):
        if self.is_empty():
            return
        descartada = self.estado in ("descartada", "incorrecta")
        self.velo.enabled = descartada
        self.sello.enabled = descartada
        if self.sello_reenvio is not None:
            self.sello_reenvio.enabled = not descartada      # el sello DESCARTADA manda
        enfocada = self._foco and not descartada
        self.marco.enabled = enfocada
        self.y = self._y0 + (0.02 if enfocada else 0.0)
        self.z = -0.02 if enfocada else 0.0

    def _clic(self):
        if self.habilitada and self.al_clic is not None:
            self.al_clic()

    def _entra(self):
        if self.al_cursor is not None:
            self.al_cursor()


class RastrearVisual(CapaVisual, MinijuegoRastrear):

    AYUDA = "1, 2, 3 o clic: elegir   Flechas: cambiar de nota"
    _tablero_roto = False

    def construir(self):
        self._listo = False
        antes = set(id(h) for h in self.children)
        super().construir()
        try:
            self._montar_corcho(antes)
            self._listo = True
            self._pintar_ronda()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("rastrear_visual", error)
            self._quitar_tablero()
            MinijuegoRastrear._pintar_ronda(self)

    def _montar_corcho(self, antes):
        # Fuera la intro, la regla escrita y el rastro en texto: lo cuenta el tablero.
        self._ocultos = [h for h in self.children if id(h) not in antes and isinstance(h, Text)]
        for h in self._ocultos:
            h.enabled = False
        self.y_ronda = Y_NOTAS + NOTA[1] / 2 - 0.02          # el origen (tarjeta de siempre) sale en la franja baja
        self.tablero = Entity(parent=self, z=0.1)
        _hoja(self.tablero, (0, Y_CORCHO), (ANCHO_CORCHO, ALTO_CORCHO), CORCHO, z=0.05)
        self._grano_y_esquinas()
        # Tira del medio: pregunta del salto + puntos del progreso; a la derecha, los ovillos de los rodeos.
        self.tira = _hoja(self.tablero, (-0.13, Y_TIRA), (1.36, 0.062), PAPEL, z=0.0)
        self.puntos = Entity(parent=self.tira, z=-0.004)
        self.pregunta = _txt(self.tira, "", 15, pos=(-0.60, 0), origen=(-0.5, 0), negrita=False)
        self.ovillos = [_ovillo(self.tablero, (0.66 + 0.05 * k, Y_TIRA, -0.01)) for k in range(max(1, MAX_ERRORES - 1))]
        n_ov = len(self.ovillos)
        x_ov = 0.66 + 0.05 * (n_ov - 1) / 2
        etiqueta = _hoja(self.tablero, (x_ov, Y_TIRA - 0.054), (0.25, 0.044), PAPEL, z=-0.005)
        # Con cifra («INTENTOS: 2 de 2»): las vidas no dependen solo del color del ovillo.
        self.rotulo_intentos = _txt(etiqueta, f"INTENTOS: {n_ov} de {n_ov}", 17, pos=(0, 0))
        # Cadena: polaroid «TÚ» + notas clavadas + hilos.
        self.cadena = Entity(parent=self.tablero, z=-0.01)
        if pp is not None:
            try:
                self.polaroid = pp.polaroid_retrato(self.cadena, "TÚ", (X_TU, Y_CADENA), giro=2)
            except Exception:           # noqa: BLE001
                self.polaroid = None
        else:
            self.polaroid = None
        if self.polaroid is None:
            self.polaroid = _hoja(self.cadena, (X_TU, Y_CADENA), (0.19, 0.24), PAPEL, giro=2)
            _txt(self.polaroid, "TÚ", 20, pos=(0, -0.085))
        _chincheta(self.cadena, (X_TU, Y_CADENA + 0.12), VERDE)
        self.notas_cadena, self.hilos = [], []
        self.elegidos = [("TÚ", None)]
        self._t_hilo = None
        self._t_fuente = None
        self._pendiente = None
        self.fuente = None

    def _grano_y_esquinas(self):
        """Corcho: grano fino (muchas motas pequeñas, algunas claras) y las cuatro esquinas más oscuras."""
        if pc is None:
            return
        for x, y, r, oscuro, alfa in pc.grano_corcho(170, ANCHO_CORCHO, ALTO_CORCHO, Y_CORCHO):
            Entity(parent=self.tablero, model="circle", z=0.04, scale=r * 2,
                   color=_rgba(CORCHO_OSC if oscuro else (176, 134, 92), alfa), position=(x, y))
        for cx, cy, w, h, alfa in pc.esquinas_oscuras(ANCHO_CORCHO, ALTO_CORCHO, Y_CORCHO, capas=12, lado=0.26, alfa=0.02):
            Entity(parent=self.tablero, model="quad", z=0.03, scale=(w, h), position=(cx, cy), color=_rgba((60, 38, 22), alfa))

    def _quitar_tablero(self):
        self._tablero_roto = True
        self._listo = False
        tablero = getattr(self, "tablero", None)
        if tablero is not None:
            tablero.enabled = False
        for h in getattr(self, "_ocultos", ()):
            h.enabled = True

    # -- Ronda: notas candidatas --

    def _pintar_ronda(self):
        if not getattr(self, "_listo", False) or self._tablero_roto:
            return super()._pintar_ronda()
        try:
            self._pintar_ronda_corcho()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("rastrear_visual", error)
            self._quitar_tablero()
            super()._pintar_ronda()

    def _pintar_ronda_corcho(self):
        if self.ronda is not None:
            destruir_arbol(self.ronda)
        self.ronda = Entity(parent=self)
        self.focables = []
        salto = self.partida.salto_actual()
        self._pintar_tira(salto)
        if salto is None:
            self._pintar_origen(self.y_ronda)
            return
        reducir = bv.reducir_movimiento()
        for i, o in enumerate(salto["opciones"][:3]):
            nota = NotaCandidata(o, i + 1, giro=0.0 if reducir else GIROS[i % 3], parent=self.ronda,
                                 position=(XS_NOTAS[i % 3], Y_NOTAS, 0), al_clic=lambda i=i: self.elegir(i),
                                 al_cursor=lambda i=i: self.poner_foco(i))
            if i in salto["descartadas"]:
                nota.fijar_estado("descartada")
                nota.habilitada = False
            self.focables.append(nota)
        self.foco = next((i for i, f in enumerate(self.focables) if f.habilitada), 0)
        self._pintar_foco()

    def _pintar_tira(self, salto):
        for hijo in list(self.puntos.children):
            destruir_arbol(hijo)
        total = len(self.partida.saltos)
        for k in range(total):
            x = -0.655 + 0.026 * k
            hecho, actual = k < self.partida.indice, k == self.partida.indice and salto is not None
            Entity(parent=self.puntos, model="circle", position=(x, 0, 0.001), scale=0.022 if actual else 0.018,
                   color=_rgba(TINTA))
            if not hecho:
                Entity(parent=self.puntos, model="circle", position=(x, 0, 0), scale=0.014 if actual else 0.011,
                       color=_rgba(AMARILLO if actual else PAPEL))
        x0 = -0.655 + 0.026 * total + 0.005
        self.pregunta.x = x0
        texto = salto["pregunta"] if salto is not None else "Llegaste al origen."
        lineas = ui.lineas_de(texto, 15, 0.60 - x0 + 0.65)
        self.pregunta.text = lineas[0] + ("…" if len(lineas) > 1 else "")
        restantes = max(0, MAX_ERRORES - 1 - self.partida.errores)
        for k, ovillo in enumerate(self.ovillos):
            ovillo.encender(k < restantes)
            self._aspa_perdido(ovillo, k >= restantes)
        if getattr(self, "rotulo_intentos", None) is not None:
            self.rotulo_intentos.text = f"INTENTOS: {restantes} de {len(self.ovillos)}"

    @staticmethod
    def _aspa_perdido(ovillo, perdido):
        """Forma además del color: un ovillo gastado lleva un aspa de tinta encima."""
        aspa = getattr(ovillo, "_aspa_e", None)
        if aspa is None:
            aspa = Entity(parent=ovillo, z=-0.02)
            for giro in (45, -45):
                Entity(parent=aspa, model="quad", scale=(0.034, 0.006), rotation_z=giro, color=_rgba(TINTA))
            ovillo._aspa_e = aspa
        aspa.enabled = bool(perdido)

    # -- Hilo guía: del último eslabón de la cadena a la nota enfocada (el hilo «recorre» la cadena) --

    def _pintar_foco(self):
        super()._pintar_foco()
        if getattr(self, "_listo", False) and not self._tablero_roto:
            try:
                self._pintar_guia()
            except Exception as error:      # noqa: BLE001
                bv.avisar_una_vez("rastrear_visual", error)

    def _pintar_guia(self):
        if getattr(self, "guia", None) is None:
            self.guia = Linea(ROJO, 2, alfa=0.55, parent=self.cadena, z=-0.006)
        activa = (not self.terminado and self.focables and 0 <= self.foco < len(self.focables)
                  and self.focables[self.foco].habilitada and not self.partida.llegado)
        if not activa:
            self.guia.fijar([])
            return
        # Cabo suelto: sale del último eslabón hacia el hueco donde irá la siguiente nota.
        origen = self._pin(len(self.notas_cadena))
        self.guia.fijar(calc.catenaria(origen, (origen[0] - 0.13, origen[1] - 0.045), 0.03))

    # -- Elegir: hilo que se tensa o nota que tiembla --

    def elegir(self, i):
        salto = self.partida.salto_actual()
        opcion = salto["opciones"][i] if salto is not None and 0 <= i < len(salto["opciones"]) else None
        n_antes, errores_antes = len(self.rastro), self.partida.errores
        self._pendiente = opcion
        super().elegir(i)
        self._pendiente = None
        if not self._listo or self._tablero_roto:
            return
        self._vigilar(self._tras_elegir, i, opcion, n_antes, errores_antes)

    def _tras_elegir(self, i, opcion, n_antes, errores_antes):
        if len(self.rastro) > n_antes and opcion is not None:
            self.elegidos.append((opcion["de"], opcion.get("hora")))
            self._t_hilo = 0.0
            nota = self._pintar_cadena()
            if self._fx is not None and nota is not None:
                self._fx.destello(nota, VERDE)
                self._fx.acierto(None)
            if self.partida.llegado:
                self._iluminar_fuente()
        elif self.partida.errores > errores_antes:
            nota = self.focables[i] if 0 <= i < len(self.focables) else None
            if self._fx is not None:
                self._fx.error(nota)
        self._pintar_tira(self.partida.salto_actual())
        self._pintar_guia()

    def _pintar_cadena(self):
        xs = calc.posiciones_rastro(len(self.elegidos), X_TU, PASO_CADENA, -0.78)
        nueva = None
        while len(self.notas_cadena) < len(self.elegidos) - 1:
            k = len(self.notas_cadena) + 1
            nombre, hora = self.elegidos[k]
            giro = 0.0 if bv.reducir_movimiento() else (pc.giro_por_id(nombre, 1.5) if pc is not None else 0.0)
            nota = _hoja(self.cadena, (xs[k], Y_CADENA), NOTA_CADENA, PAPEL, giro=giro)
            nota.ancho, nota.alto = NOTA_CADENA
            partes = ui.lineas_de(str(nombre), 13, NOTA_CADENA[0] - 0.02)[:2]
            _txt(nota, "\n".join(partes), 13, pos=(0, 0.02 if len(partes) > 1 else 0.012))
            if hora:
                _txt(nota, hora, 12, pos=(0, -0.04 if len(partes) > 1 else -0.026), negrita=False)
            _chincheta(nota, (0, NOTA_CADENA[1] / 2 - 0.004), VERDE)
            self.notas_cadena.append(nota)
            self.hilos.append(Linea(ROJO, 3, parent=self.cadena, z=-0.008))
            nueva = nota
        self._pintar_hilos()
        return nueva

    def _pin(self, k):
        if k == 0:
            return (X_TU, Y_CADENA + 0.12)
        nota = self.notas_cadena[k - 1]
        return (nota.x, Y_CADENA + NOTA_CADENA[1] / 2 - 0.004)

    def _pintar_hilos(self):
        reducir = bv.reducir_movimiento()
        for k, hilo in enumerate(self.hilos):
            nuevo = k == len(self.hilos) - 1 and self._t_hilo is not None and not reducir
            caida = calc.caida_hilo(self._t_hilo, dur=DUR_TENSAR, reducir=reducir) if nuevo else 0.012
            hilo.fijar(calc.catenaria(self._pin(k), self._pin(k + 1), caida))

    # -- Momento estrella: la fuente --

    def _pintar_origen(self, y):
        super()._pintar_origen(y)

    def _iluminar_fuente(self):
        if not self.notas_cadena:
            return
        nota = self.notas_cadena[-1]
        self.fuente = Entity(parent=self.cadena, position=(nota.x, nota.y, 0.003))
        Entity(parent=self.fuente, model="quad", scale=(NOTA_CADENA[0] + 0.05, NOTA_CADENA[1] + 0.05),
               color=_rgba(AMARILLO))
        self.sello_fuente = _sello(self.cadena, "FUENTE", (nota.x, nota.y - NOTA_CADENA[1] / 2 - 0.022), TINTA,
                                   giro=-6, escala=(0.15, 0.05))
        self.sello_fuente.z = -0.02
        self._t_fuente = 0.0
        self._pintar_sello_fuente()

    def _pintar_sello_fuente(self):
        reducir = bv.reducir_movimiento()
        escala, _, _ = fx_calc.caida_sello(self._t_fuente, dur=0.2, reducir=reducir)
        self.sello_fuente.scale = escala

    def posicion_sello(self):
        return (-0.48, 0.25)              # el hueco libre de la cadena (izquierda), no encima de las notas

    def posicion_estrellas(self):
        return (-0.2, 0.15)               # a la derecha del sello: la medalla (a la izquierda de las estrellas) cabe en pantalla

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not self._listo or self._tablero_roto:
            return
        if self._t_hilo is not None:
            self._t_hilo += dt
            self._pintar_hilos()
            if self._t_hilo > DUR_TENSAR:
                self._t_hilo = None
                self._pintar_hilos()
        if self._t_fuente is not None and self.fuente is not None and not self.fuente.is_empty():
            self._t_fuente += dt
            self._pintar_sello_fuente()
            if self._t_fuente > 0.3:
                self._t_fuente = None
