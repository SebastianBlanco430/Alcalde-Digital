# «Comparar dos versiones» visual (Ursina), estilo «cómic cívico»: el mismo minijuego (frontend/minijuegos/comparar.py,
# lógica comparar_calculos) sobre DOS HOJAS DE PAPEL:
#   - ORIGINAL: papel crema, sujeto con dos cintas y con el sello «ORIGINAL»;
#   - COPIA que circula: papel viejo, con arrugas, una esquina doblada y una mancha de café;
#   - cada línea es un renglón (microetiqueta del campo sobre el valor). Entre las hojas, una pasarela de puntos: el del
#     renglón con el foco se enciende; el renglón enfocado lleva banda cian y marcador amarillo;
#   - marcar es pasar un resaltador amarillo de izquierda a derecha (quieto con «reducir movimiento»);
#   - al cerrar: acierto = banda verde + círculo; falsa alarma = banda roja + tachón; la que faltó = aro rojo discontinuo.
#     Cada caso conserva además su etiqueta de texto (ENCONTRADA / ESTABA BIEN / TE LA PERDISTE): nada solo por color.
# Se conservan las tarjetas de la vista base (lógica, foco, clic y etiquetas); solo se recolocan sobre las hojas y se
# esconde su fondo. No cambia la partida ni el resultado. APAGADO: ALCALDE_COMPARAR_VISUAL=0. GUARDIÁN: un fallo deshace
# lo añadido y deja la vista de siempre.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Mesh, Text, color, destroy

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.comparar import MinijuegoComparar
from frontend.minijuegos_visual.capa import CapaVisual

try:
    from frontend.minijuegos_visual import piezas_papel as pp
except Exception:                       # noqa: BLE001
    pp = None
try:
    from frontend.minijuegos_visual import papel_calculos as pc
except Exception:                       # noqa: BLE001
    pc = None

COMPARAR_VISUAL = True
VARIABLE = "ALCALDE_COMPARAR_VISUAL"

TINTA = estilo.TINTA
PAPEL = estilo.PAPEL
PAPEL_VIEJO = getattr(pc, "PAPEL_VIEJO", (236, 224, 190))
AMARILLO = (255, 220, 60)
CIAN = (70, 220, 255)
ROJO = estilo.ESTADO_ERROR
VERDE = estilo.ESTADO_EXITO
TINTA_SUAVE = (70, 72, 86)
CAFE = (150, 106, 66)
AZUL_TINTA = (30, 90, 200)

X_ORIGINAL, X_COPIA, Y_HOJA = -0.42, 0.42, 0.02
ANCHO_HOJA, ALTO_HOJA = 0.76, 0.66
GIRO_ORIGINAL, GIRO_COPIA = -1.5, 1.2
Y0_RENGLON, PASO_RENGLON = 0.295, 0.097
ANCHO_FILA, ALTO_FILA = ANCHO_HOJA - 0.04, 0.088
Y_BOTONES, ANCHO_BOTON, ALTO_BOTON = -0.39, 0.40, 0.08       # alto >= 56 px lógicos (80 px a 720)
DUR_RESALTADOR = 0.18


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _quad(parent, pos, escala, tono, alfa=1.0, giro=0.0, origen=(0, 0)):
    return Entity(parent=parent, model="quad", position=pos, scale=escala, color=_rgba(tono, alfa), rotation_z=giro,
                  origin=origen)


def _elipse(parent, pos, rx, ry, tono, grosor=3):
    import math
    puntos = [(rx * math.cos(2 * math.pi * k / 40), ry * math.sin(2 * math.pi * k / 40), 0) for k in range(41)]
    return Entity(parent=parent, model=Mesh(vertices=puntos, mode="line", thickness=grosor), position=pos,
                  color=_rgba(tono))


# -- Piezas de papel: las compartidas si existen; si no, versiones mínimas locales --

def _hoja(parent, pos, tono, giro, doblez=False):
    if pp is not None:
        try:
            raiz = pp.hoja(parent, pos, (ANCHO_HOJA, ALTO_HOJA), color=tono, giro=giro, z=pos[2], doblez=doblez)
            for hijo in raiz.children:      # los polígonos de la esquina doblada pueden venir con la cara de espaldas
                hijo.double_sided = True
            return raiz
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=pos, rotation_z=giro)
    _quad(raiz, (0.004, -0.005, 0.002), (ANCHO_HOJA, ALTO_HOJA), TINTA, 160 / 255)
    _quad(raiz, (0, 0, 0.001), (ANCHO_HOJA + 0.008, ALTO_HOJA + 0.008), TINTA)
    _quad(raiz, (0, 0, 0), (ANCHO_HOJA, ALTO_HOJA), tono)
    return raiz


def _cinta(parent, pos, giro):
    if pp is not None:
        try:
            return pp.cinta(parent, pos, giro)
        except Exception:               # noqa: BLE001
            pass
    return _quad(parent, (pos[0], pos[1], -0.004), (0.08, 0.025), CIAN, 0.55, giro)


def _sello(parent, texto, pos, tono, giro):
    tono = estilo.tono_legible(tono, PAPEL_VIEJO)         # el texto del sello llega a contraste 4,5 sobre el papel
    if pp is not None:
        try:
            return pp.sello_goma(parent, texto, pos, tono, giro=giro, escala=(0.2, 0.06))
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.005), rotation_z=giro)
    _quad(raiz, (0, 0, 0.001), (0.2, 0.06), tono, 0.9)
    _quad(raiz, (0, 0, 0), (0.19, 0.05), PAPEL)
    ui.texto(raiz, texto, 15, None, tono, (0, 0.012), negrita=True, centrado=True)
    return raiz


class _ResaltadorLocal(Entity):

    def __init__(self, ancho, **opciones):
        super().__init__(**opciones)
        self._ancho, self._x0 = ancho, self.x - ancho / 2

    def set_progreso(self, p):
        p = max(0.0, min(1.0, float(p)))
        self.scale_x = max(1e-4, self._ancho * p)
        self.x = self._x0 + self.scale_x / 2


def _resaltador(parent, pos, escala):
    if pp is not None:
        try:
            return pp.resaltador(parent, pos, escala, color=AMARILLO, alfa=0.7)
        except Exception:               # noqa: BLE001
            pass
    return _ResaltadorLocal(escala[0], parent=parent, model="quad", position=(pos[0], pos[1], -0.002), scale=escala,
                            color=_rgba(AMARILLO, 0.7))


def _aro(parent, pos, rx, ry):
    if pp is not None:
        try:
            return pp.aro_discontinuo(parent, pos, rx, ry, color=ROJO)
        except Exception:               # noqa: BLE001
            pass
    return _elipse(parent, (pos[0], pos[1], -0.006), rx, ry, ROJO, 4)


def _txt_num(parent, cadena, pos):
    """Número del selector central (14 px, tinta)."""
    return Text(cadena, parent=parent, origin=(0, 0), position=(pos[0], pos[1], -0.004), scale=escala_fuente(14),
                font=tipografia.fuente_piel(titulo=True), color=_rgba(TINTA))


def _trazo(parent, puntos):
    if pp is not None:
        try:
            return pp.trazo_rotulador(parent, puntos, tono=AZUL_TINTA, grosor=4, z=-0.004)
        except Exception:               # noqa: BLE001
            pass
    return Entity(parent=parent)


def _progreso(t, reducir):
    if pc is not None:
        try:
            return pc.progreso_barrido(t, DUR_RESALTADOR, reducir)
        except Exception:               # noqa: BLE001
            pass
    return 1.0 if reducir else max(0.0, min(1.0, t / DUR_RESALTADOR))


class CompararVisual(CapaVisual, MinijuegoComparar):

    _papel_roto = False

    def construir(self):
        self._listo = False
        super().construir()
        try:
            self._montar_papel()
            self._listo = True
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("comparar_visual", error)
            self._deshacer_papel()

    def _activo(self):
        return getattr(self, "_listo", False) and not self._papel_roto

    # -- Montaje --

    def _montar_papel(self):
        self._respaldo = [(t, t.parent, t.position, t.ancho, t.alto) for t in self.izq + self.tarjetas]
        self._resaltadores, self._t_resaltador = {}, {}
        self.mesa = Entity(parent=self)
        # Fuera los encabezados largos de las columnas y el pie largo de teclas (las teclas van en los botones).
        for hijo in list(self.children):
            if isinstance(hijo, Text) and str(hijo.text).startswith(("ORIGINAL:", "COPIA QUE CIRCULA:")):
                hijo.enabled = False
        if getattr(self, "pie", None) is not None:
            self.pie.enabled = False

        self.hoja_original = _hoja(self.mesa, (X_ORIGINAL, Y_HOJA, 0.05), PAPEL, GIRO_ORIGINAL)
        self.hoja_copia = _hoja(self.mesa, (X_COPIA, Y_HOJA, 0.05), PAPEL_VIEJO, GIRO_COPIA, doblez=True)
        w, h = ANCHO_HOJA / 2, ALTO_HOJA / 2
        _cinta(self.hoja_original, (-w + 0.02, h - 0.02), 35)
        _cinta(self.hoja_original, (w - 0.02, h - 0.02), -35)
        _sello(self.hoja_original, "ORIGINAL", (w - 0.14, -h + 0.045), VERDE, -8)
        _sello(self.hoja_copia, "COPIA", (-w + 0.14, -h + 0.045), ROJO, 8)     # simétrico al sello ORIGINAL

        n = len(self.tarjetas)
        self._ys = [Y0_RENGLON - PASO_RENGLON * k - Y_HOJA for k in range(n)]
        for k, ly in enumerate(self._ys):
            linea = self.partida.lineas[k]
            self._colocar_fila(self.izq[k], self.hoja_original, ly, linea["etiqueta"], linea["original"])
            self._colocar_fila(self.tarjetas[k], self.hoja_copia, ly, linea["etiqueta"], linea["copia"])
            if k < n - 1:
                for hoja in (self.hoja_original, self.hoja_copia):
                    _quad(hoja, (0, ly - PASO_RENGLON / 2, -0.001), (ANCHO_HOJA - 0.06, 0.0018), TINTA, 0.16)

        # Pasarela de puntos entre las hojas y foco (banda cian en ambas hojas + marcador amarillo en la copia).
        self._puntos, self._aros = [], []
        for k in range(n):
            y = Y0_RENGLON - PASO_RENGLON * k
            aro = _quad(self.mesa, (0, y, -0.001), (0.04, 0.04), TINTA)
            aro.model = "circle"
            punto = _quad(self.mesa, (0, y, -0.002), (0.034, 0.034), PAPEL)
            punto.model = "circle"
            punto.numero = _txt_num(self.mesa, str(k + 1), (0, y))
            self._puntos.append(punto)
            self._aros.append(aro)
        # Línea activa: subrayado de rotulador (dos trazos) en ambas hojas, en lugar de un relleno de color.
        self._bandas = []
        for hoja in (self.hoja_original, self.hoja_copia):
            for puntos in (pc.subrayado_rotulador(ANCHO_FILA, semilla=3) if pc is not None else []):
                trazo = _trazo(hoja, puntos)
                trazo.dy = -ALTO_FILA / 2 + 0.024 + (puntos[0][1] if puntos else 0)
                self._bandas.append(trazo)
        self._marcador = Entity(parent=self.hoja_copia)
        _quad(self._marcador, (0, 0, 0.0005), (0.018, ALTO_FILA - 0.01), TINTA)
        _quad(self._marcador, (0, 0, 0), (0.011, ALTO_FILA - 0.017), AMARILLO)

        # Botones debajo de las hojas, lado a lado, con su tecla en la etiqueta.
        self._boton_confirmar_alto()
        self.boton_confirmar.position = (-ANCHO_BOTON / 2 - 0.03, Y_BOTONES)
        self._boton_igual_tinta()
        self.boton_igual.position = (ANCHO_BOTON / 2 + 0.03, Y_BOTONES)
        self.boton_confirmar.fijar_etiqueta("Confirmar (C)")
        self.boton_igual.fijar_etiqueta("No veo diferencias (N)")
        self._pintar_foco_papel()

    def _boton_confirmar_alto(self):
        """«Confirmar» a >= 56 px lógicos de alto (mismo atributo, misma acción y misma tecla; sigue siendo el botón amarillo)."""
        viejo = self.boton_confirmar
        nuevo = ui.Boton(viejo._etiqueta, viejo.al_clic, ANCHO_BOTON, ALTO_BOTON, 18, primario=True, parent=self,
                         position=viejo.position)
        self.focables = [nuevo if f is viejo else f for f in self.focables]
        self.boton_confirmar = nuevo
        destroy(viejo)
        nuevo.fijar_foco(False)

    def _boton_igual_tinta(self):
        """«No veo diferencias» pasa del azul pizarra al botón de papel y tinta (mismo atributo, misma acción y misma tecla)."""
        viejo = self.boton_igual
        nuevo = ui.BotonTinta(viejo._etiqueta, viejo.al_clic, ANCHO_BOTON, ALTO_BOTON, 18, parent=self,
                              position=viejo.position)
        self.focables = [nuevo if f is viejo else f for f in self.focables]
        self.boton_igual = nuevo
        destroy(viejo)
        nuevo.fijar_foco(False)

    def _colocar_fila(self, tarjeta, hoja, ly, etiqueta, valor):
        tarjeta.parent = hoja
        tarjeta.position = (0, ly, -0.01)
        tarjeta.ancho, tarjeta.alto = ANCHO_FILA, ALTO_FILA
        for parte in (tarjeta.borde, tarjeta.fondo, tarjeta.cuerpo, tarjeta.titulo):
            if parte is not None:
                parte.enabled = False
        tarjeta.golpe.scale = (ANCHO_FILA, ALTO_FILA)
        tarjeta.etiqueta.color = _rgba(TINTA)
        tarjeta.etiqueta.scale = escala_fuente(17)          # «SOSPECHOSA», «ESTABA BIEN», «TE LA PERDISTE»: >= 17 px
        tarjeta.etiqueta.position = (ANCHO_FILA / 2 - 0.02, ALTO_FILA / 2 - 0.006, -0.02)
        x0 = -ANCHO_FILA / 2 + 0.02
        tarjeta.papel_micro = ui.texto(tarjeta, str(etiqueta).upper(), 17, ANCHO_FILA - 0.3, TINTA_SUAVE,
                                       (x0, ALTO_FILA / 2 - 0.005), negrita=True)
        px = 17 if len(ui.lineas_de(valor, 17, ANCHO_FILA - 0.04)) == 1 else 15
        tarjeta.papel_valor = ui.texto(tarjeta, valor, px, ANCHO_FILA - 0.04, TINTA, (x0, ALTO_FILA / 2 - 0.036))

    def _deshacer_papel(self):
        self._papel_roto = True
        self._listo = False
        for t, padre, pos, ancho, alto in getattr(self, "_respaldo", ()):
            try:
                t.parent, t.position, t.ancho, t.alto = padre, pos, ancho, alto
                for parte in (t.borde, t.fondo, t.cuerpo, t.titulo):
                    if parte is not None:
                        parte.enabled = True
                t.golpe.scale = (ancho, alto)
                for nombre in ("papel_micro", "papel_valor"):
                    if getattr(t, nombre, None) is not None:
                        getattr(t, nombre).enabled = False
                t.etiqueta.color = _rgba(estilo.COLOR_TEXTO)
            except Exception:           # noqa: BLE001
                pass
        if getattr(self, "mesa", None) is not None:
            self.mesa.enabled = False

    # -- Foco --

    def _pintar_foco(self):
        super()._pintar_foco()
        if self._activo():
            self._vigilar_papel(self._pintar_foco_papel)

    def _vigilar_papel(self, funcion, *args):
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("comparar_visual", error)
            self._deshacer_papel()
            return None

    def _pintar_foco_papel(self):
        fila = self.foco if (not self.terminado and self.focables and self.foco < len(self.tarjetas)) else None
        for k, punto in enumerate(self._puntos):
            punto.color = _rgba(CIAN if k == fila else PAPEL)
            punto.scale = (0.036, 0.036) if k == fila else (0.032, 0.032)
            self._aros[k].scale = (0.046, 0.046) if k == fila else (0.04, 0.04)
        for banda in self._bandas + [self._marcador]:
            banda.enabled = fila is not None
            if fila is not None:
                banda.y = self._ys[fila] + getattr(banda, "dy", 0.0)
        if fila is not None:
            self._marcador.x = -ANCHO_HOJA / 2 + 0.012

    # -- Resaltador al marcar --

    def alternar(self, i):
        super().alternar(i)
        if self._activo():
            self._vigilar_papel(self._resaltar, i)

    def _resaltar(self, i):
        tarjeta = self.tarjetas[i]
        if i in self.partida.marcadas:
            barra = self._resaltadores.get(i)
            if barra is None:
                barra = _resaltador(tarjeta, (0, -0.012), (ANCHO_FILA - 0.02, 0.05))
                self._resaltadores[i] = barra
            barra.enabled = True
            if bv.reducir_movimiento() or self._fx is None:
                barra.set_progreso(1.0)
                self._t_resaltador.pop(i, None)
            else:
                barra.set_progreso(0.0)
                self._t_resaltador[i] = 0.0
        elif i in self._resaltadores:
            self._resaltadores[i].enabled = False
            self._t_resaltador.pop(i, None)

    # -- Cierre --

    def repasar_revision(self):
        if self._activo():
            self._vigilar_papel(self._marcas_de_cierre)
        return super().repasar_revision()

    def _marcas_de_cierre(self):
        for barra in self._resaltadores.values():
            barra.enabled = False
        self._t_resaltador.clear()
        for t in self.tarjetas:
            if t.estado == "encontrada":
                _quad(t, (0, 0, -0.002), (ANCHO_FILA, ALTO_FILA - 0.008), VERDE, 0.32)
                _elipse(t, (0, -0.004, -0.025), ANCHO_FILA / 2 - 0.005, ALTO_FILA / 2 + 0.004, VERDE, 4)
            elif t.estado == "falsa_alarma":
                _quad(t, (0, 0, -0.002), (ANCHO_FILA, ALTO_FILA - 0.008), ROJO, 0.28)
                ancho = min(ANCHO_FILA - 0.04, t.papel_valor.width * 1.02 if t.papel_valor.width else ANCHO_FILA - 0.04)
                _quad(t, (-ANCHO_FILA / 2 + 0.02, -0.003, -0.025), (ancho, 0.005), ROJO, 1.0, origen=(-0.5, 0))
            elif t.estado == "perdida":
                _aro(t, (-0.1, -0.012, -0.025), ANCHO_FILA / 2 - 0.12, ALTO_FILA / 2 - 0.014)   # solo rodea el valor: «TE LA PERDISTE» queda legible

    def posicion_estrellas(self):
        return (0.30, 0.46)               # arriba, a la izquierda del sello: ni sobre la copia ni sobre el sello

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not self._activo():
            return
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        for i in list(self._t_resaltador):
            self._t_resaltador[i] += dt
            p = _progreso(self._t_resaltador[i], reducir)
            self._resaltadores[i].set_progreso(p)
            if p >= 1.0:
                del self._t_resaltador[i]
