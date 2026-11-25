# «Señales de edición» visual (Ursina), estilo «cómic cívico». El mismo minijuego (frontend/minijuegos/senales.py, lógica
# senales_calculos) con otra cara:
#   - la captura es una captura de móvil dibujada (barra amarilla con avatar, cuenta y hora; cuerpo con burbujas de papel
#     viejo). Cada zona del caso es un bloque/burbuja de esa captura (BloqueCaptura imita a ui.Tarjeta);
#   - una LUPA (aro cian transparente con halo amarillo y pestaña de tinta con la etiqueta de la zona) sigue al foco con
#     suavizado de 150 ms; no copia ni tapa el texto;
#   - marcar pone un sello rojo ovalado «RARO»; el contador son 3 casillas que se rellenan;
#   - a la derecha, una ficha «PISTA» con la etiqueta de la zona y una pregunta corta; debajo Confirmar / No veo nada raro;
#   - al cerrar: las señales reales llevan sello «TRUCO» verde, las marcas falsas quedan tachadas en gris.
# No cambia la partida ni el resultado. APAGADO: ALCALDE_SENALES_VISUAL=0. GUARDIÁN: un fallo de lo añadido avisa y lo apaga.
# REDUCIR MOVIMIENTO: la lupa salta sin deslizarse.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

import math
import re

from ursina import Entity, Mesh, Text, color, destroy

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.senales import MinijuegoSenales
from frontend.minijuegos_visual.capa import CapaVisual
from frontend.minijuegos_visual import senales_piezas_calculos as sc

try:
    from frontend.minijuegos_visual import piezas_papel as _pp
except Exception:                       # noqa: BLE001  sin piezas de papel: helpers locales
    _pp = None
try:
    from frontend.minijuegos_visual.papel_calculos import PAPEL_VIEJO
except Exception:                       # noqa: BLE001
    PAPEL_VIEJO = (236, 224, 190)

SENALES_VISUAL = True
VARIABLE = "ALCALDE_SENALES_VISUAL"

TINTA = estilo.TINTA
PAPEL = estilo.PAPEL
AMARILLO = (255, 220, 60)
CIAN = (70, 220, 255)
ROJO = getattr(estilo, "ESTADO_ERROR", (214, 62, 62))
VERDE = getattr(estilo, "ESTADO_EXITO", (80, 190, 110))
GRIS = (130, 132, 140)

# Captura de móvil
CAP_X, CAP_Y, CAP_ANCHO, CAP_ALTO = -0.38, 0.02, 0.92, 0.56
ALTO_BARRA = 0.085
ANCHO_BLOQUE = 0.80
MARCO_TEL = 0.022                    # grosor del marco del teléfono (tinta)
RESERVA_SELLO = 0.26                 # sitio libre a la derecha de cada burbuja para el sello y la lupa
# Ficha de pista (alto compacto: ~130 px; en el cierre crece para las explicaciones)
FICHA_ANCHO, FICHA_ALTO_FIN = 0.62, 0.38
FICHA_X = 0.52
PX_PISTA = 18
ALTO_BOTON = 0.08                 # >= 56 px lógicos (57,6 a 720)
# Lupa
DIAMETRO_LUPA = 0.125
SUAVIZADO = 0.05                     # constante de tiempo: ~150 ms hasta llegar
AYUDA_CORTA = "Flechas: zona   Enter: marcar   C: confirmar   N: nada raro"

ETIQUETAS = (("foto", "Foto"), ("cuenta", "Cuenta"), ("hora", "Hora"), ("fecha", "Fecha"), ("pide", "Promesa"),
             ("premio", "Premio"), ("titular", "Titular"), ("monto", "Monto"), ("comercio", "Comercio"),
             ("tipograf", "Letra"), ("firma", "Firma"), ("escritura", "Escribiendo"), ("código", "Código"),
             ("condicion", "Condiciones"), ("placa", "Placa"), ("origen", "Ruta"), ("gente", "Encuesta"),
             ("lugar", "Lugar"))


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def etiqueta_zona(lupa, i):
    """Etiqueta corta de la zona a partir de su texto de lupa («Nombre de la cuenta...» -> «Cuenta»)."""
    bajo = str(lupa or "").lower()
    for clave, nombre in ETIQUETAS:
        if clave in bajo:
            return nombre
    return f"Zona {i + 1}"


def _anillo(parent, diametro, tono, alfa=1.0, grosor=3, z=0.0):
    r = diametro / 2
    puntos = [(r * math.cos(2 * math.pi * k / 48), r * math.sin(2 * math.pi * k / 48), 0) for k in range(49)]
    return Entity(parent=parent, model=Mesh(vertices=puntos, mode="line", thickness=grosor), color=_rgba(tono, alfa), z=z)


def _linea(parent, puntos, tono, grosor=3, alfa=1.0, z=0.0):
    return Entity(parent=parent, model=Mesh(vertices=[(x, y, 0) for x, y in puntos], mode="line", thickness=grosor),
                  color=_rgba(tono, alfa), z=z)


def _lupita(parent, pos, relleno, z=0.0):
    """Lupa pequeña del contador: aro de tinta con mango; el cristal se rellena (rojo) al marcar. Devuelve el cristal."""
    raiz = Entity(parent=parent, position=(pos[0], pos[1], z))
    ini, fin = sc.mango_lupa(0.022, -45, 0.024)
    _linea(raiz, [ini, fin], TINTA, grosor=6, z=0.002)
    Entity(parent=raiz, model="circle", scale=0.050, color=_rgba(TINTA), z=0.001)
    cristal = Entity(parent=raiz, model="circle", scale=0.036, color=_rgba(relleno))
    return cristal


def _hoja(parent, pos, escala, tono, z=0.0):
    if _pp is not None:
        try:
            return _pp.hoja(parent, pos, escala, color=tono, giro=0, z=z)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], z))
    Entity(parent=raiz, model="quad", position=(0.004, -0.005, 0.002), scale=escala, color=_rgba(TINTA, 0.63))
    Entity(parent=raiz, model="quad", position=(0, 0, 0.001), scale=(escala[0] + 0.008, escala[1] + 0.008), color=_rgba(TINTA))
    Entity(parent=raiz, model="quad", scale=escala, color=_rgba(tono))
    return raiz


def _sello(parent, texto, pos, tono, giro=-6, escala=(0.18, 0.058)):
    tono = estilo.tono_legible(tono, PAPEL_VIEJO)         # el texto del sello llega a contraste 4,5 sobre el papel
    if _pp is not None:
        try:
            return _pp.sello_goma(parent, texto, pos, tono, giro=giro, escala=escala, ovalado=True)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.005), rotation_z=giro)
    Entity(parent=raiz, model="quad", scale=escala, color=_rgba(tono, 0.15))
    Text(texto, parent=raiz, origin=(0, 0), z=-0.001, scale=escala_fuente(16), font=tipografia.fuente_piel(titulo=True), color=_rgba(tono))
    return raiz


def _texto(parent, cadena, px, tono, pos, origen=(-0.5, 0.5), z=-0.004):
    return Text(cadena, parent=parent, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px),
                font=tipografia.fuente_piel(titulo=True), color=_rgba(tono))


class BloqueCaptura(ui.Tarjeta):
    """Una zona de la captura dibujada como burbuja de papel viejo. Mismos estados que ui.Tarjeta (la capa los lee), pero
    se pintan con sellos: «RARO» al marcar; al cerrar «TRUCO» en las señales reales y la marca falsa tachada en gris."""

    ETIQUETAS_FIN = {"encontrada": "LA VISTE", "perdida": "SE TE PASÓ", "falsa_alarma": "ESTABA BIEN"}

    _sello = None
    _tachon = None
    _sello_de = None

    def __init__(self, *args, **opciones):
        super().__init__(*args, tono=PAPEL_VIEJO, **opciones)
        self.cuerpo.color = _rgba(TINTA)
        self.etiqueta.color = _rgba(TINTA)
        # doble check de «mensaje leído», pequeño, en la esquina de abajo a la derecha de la burbuja
        self._checks = []
        for pts in sc.puntos_doble_check(0.016):
            self._checks.append(_linea(self, [(self.ancho / 2 - 0.035 + x, -self.alto / 2 + 0.02 + y) for x, y in pts], (60, 130, 190),
                   grosor=3, z=-0.012))

    def _x_sello(self):
        return self.ancho / 2 - 0.14

    def _poner_sello(self, texto, tono):
        if self._sello is not None:
            destroy(self._sello)
        dy = 0.02 if self.estado in self.ETIQUETAS_FIN else 0.0      # sube: no pisa la etiqueta final de 17 px
        self._sello = _sello(self, texto, (self._x_sello(), dy), tono)
        self._sello.z = -0.02

    def _pintar(self):
        if self.is_empty() or self.borde.is_empty():
            return
        estado = self.estado
        foco = self._foco
        grosor = 6 if foco else (5 if estado in ("encontrada", "perdida", "falsa_alarma") else 3)
        borde = AMARILLO if foco else TINTA
        extra = a_unidades(grosor)
        if getattr(self, "_grosor_pintado", None) != grosor:
            self._grosor_pintado = grosor
            self.borde.model = ui.modelo_redondeado(self.ancho + 2 * extra, self.alto + 2 * extra, 9 + grosor)
            self.borde.scale = (self.ancho + 2 * extra, self.alto + 2 * extra)
        self.borde.color = _rgba(borde)
        self.fondo.color = _rgba(PAPEL_VIEJO)
        self.etiqueta.text = ""
        if estado == "marcada":
            if getattr(self, "_sello_de", None) != "marcada":
                self._poner_sello("RARO", ROJO)
        elif estado in ("encontrada", "perdida"):
            if getattr(self, "_sello_de", None) != estado:
                self._poner_sello("TRUCO", VERDE)
            self.etiqueta.text = self.ETIQUETAS_FIN[estado]
        elif estado == "falsa_alarma":
            if getattr(self, "_sello_de", None) != estado:
                self._poner_sello("RARO", GRIS)
                self._tachon = Entity(parent=self, model="quad", position=(self._x_sello(), 0.02, -0.03),
                                      scale=(0.19, 0.008), rotation_z=-14, color=_rgba(GRIS))
            self.etiqueta.text = self.ETIQUETAS_FIN[estado]
        elif self._sello is not None:
            destroy(self._sello)
            self._sello = None
        self._sello_de = estado
        for marca in getattr(self, "_checks", []):
            marca.enabled = estado not in self.ETIQUETAS_FIN       # la etiqueta final ocupa esa esquina
        if estado in self.ETIQUETAS_FIN:
            self.etiqueta.y = -self.alto / 2 + 0.031              # la etiqueta baja: el sello ocupa la esquina


class SenalesVisual(CapaVisual, MinijuegoSenales):

    _lupa_rota = False
    _vista_base = False               # True si la captura falló al montarse y quedó la vista de siempre

    def construir(self):
        """Captura de móvil; si su montaje falla, se borra lo creado y queda la vista de siempre (guardián)."""
        antes = set(id(h) for h in self.children)
        try:
            self._construir_captura()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("senales_visual", error)
            for hijo in list(self.children):
                if id(hijo) not in antes:
                    destroy(hijo)
            self._lupa_rota = True
            self._listo = False
            self.lente = None
            self._vista_base = True
            self.casillas = []
            MinijuegoSenales.construir(self)

    def _construir_captura(self):
        """Misma partida y mismos objetos que MinijuegoSenales.construir, con la captura de móvil y la ficha de pista."""
        from frontend.minijuegos.senales_calculos import PartidaSenales
        self._listo = False
        self.partida = PartidaSenales(self.caso)
        p = self.partida
        self.x_tel = CAP_X
        self.x_lupa = FICHA_X
        self.etiquetas = [etiqueta_zona(z["lupa"], i) for i, z in enumerate(p.zonas)]
        self._montar_captura()
        # Bloques: reparten el cuerpo de la captura; cada burbuja mide según su texto y se pega a la izquierda (recibido)
        arriba = CAP_Y + CAP_ALTO / 2 - ALTO_BARRA - 0.03
        abajo = CAP_Y - CAP_ALTO / 2 + 0.03
        anchos = [sc.ancho_burbuja(max(ui.medir(l, 17) for l in z["texto"].split("\n")), ANCHO_BLOQUE, reserva=RESERVA_SELLO)
                  for z in p.zonas]
        altos = [ui.Tarjeta.alto_necesario(z["texto"], anchos[i], 17, margen_px=8, reserva=RESERVA_SELLO)
                 for i, z in enumerate(p.zonas)]
        altos, centros = sc.repartir(altos, arriba, abajo)
        self.tarjetas = []
        for i, z in enumerate(p.zonas):
            x = sc.x_burbuja(anchos[i], ANCHO_BLOQUE, CAP_X, sc.lado_de(i, z["texto"]))
            self.tarjetas.append(BloqueCaptura(anchos[i], altos[i], z["texto"], "", 17, 17, parent=self,
                                               position=(x, centros[i], -0.02),
                                               al_clic=lambda i=i: self.alternar(i), al_cursor=lambda i=i: self.poner_foco(i),
                                               margen_px=8, reserva=RESERVA_SELLO))
        lineas = max(len(ui.lineas_de(z["lupa"] + ". ¿Encaja con el resto?", PX_PISTA, FICHA_ANCHO - 0.06)) for z in p.zonas)
        self.ficha_alto = sc.alto_ficha(lineas)
        col = sc.columna_derecha(self.ficha_alto, 0.06, ALTO_BOTON, CAP_Y - 0.01)
        self.col = col
        self._montar_ficha(col)
        self.boton_confirmar = ui.Boton("Confirmar", self.confirmar, FICHA_ANCHO, ALTO_BOTON, 18, primario=True, parent=self,
                                        position=(FICHA_X, col["confirmar_y"]))
        self.boton_nada = ui.BotonTinta("No veo nada raro", self.sin_senales, FICHA_ANCHO, ALTO_BOTON, 18, parent=self,
                                        position=(FICHA_X, col["nada_y"]))
        self.focables = self.tarjetas + [self.boton_confirmar, self.boton_nada]
        try:
            self.pie.text = AYUDA_CORTA
        except Exception:               # noqa: BLE001
            pass
        try:
            self._montar_lupa()
            self._listo = True
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("senales_visual", error)
            self._quitar_lupa()
        self._pintar_lupa()

    # -- Captura de móvil --

    def _montar_captura(self):
        self.captura = Entity(parent=self, position=(CAP_X, CAP_Y, 0.05))
        m = MARCO_TEL
        # teléfono: sombra dura, marco de tinta con esquinas redondeadas, pantalla de papel
        Entity(parent=self.captura, model=ui.modelo_redondeado(CAP_ANCHO + 2 * m, CAP_ALTO + 2 * m, 18), position=(0.008, -0.010, 0.004),
               scale=(CAP_ANCHO + 2 * m, CAP_ALTO + 2 * m), color=_rgba(TINTA, 0.55))
        Entity(parent=self.captura, model=ui.modelo_redondeado(CAP_ANCHO + 2 * m, CAP_ALTO + 2 * m, 18), position=(0, 0, 0.003),
               scale=(CAP_ANCHO + 2 * m, CAP_ALTO + 2 * m), color=_rgba(TINTA))
        Entity(parent=self.captura, model="quad", position=(0, 0, 0.001), scale=(CAP_ANCHO, CAP_ALTO), color=_rgba(PAPEL))
        # altavoz y cámara en el marco de arriba; barra de inicio abajo
        Entity(parent=self.captura, model="quad", position=(0, CAP_ALTO / 2 + m / 2, 0.0), scale=(0.10, 0.007),
               color=_rgba((90, 90, 105)))
        Entity(parent=self.captura, model="circle", position=(0.09, CAP_ALTO / 2 + m / 2, 0.0), scale=0.010,
               color=_rgba((90, 90, 105)))
        Entity(parent=self.captura, model="quad", position=(0, -CAP_ALTO / 2 - m / 2, 0.0), scale=(0.14, 0.006),
               color=_rgba((90, 90, 105)))
        yb = CAP_ALTO / 2 - ALTO_BARRA / 2
        Entity(parent=self.captura, model="quad", position=(0, yb, 0), scale=(CAP_ANCHO, ALTO_BARRA), color=_rgba(AMARILLO))
        Entity(parent=self.captura, model="quad", position=(0, yb - ALTO_BARRA / 2, -0.001), scale=(CAP_ANCHO, 0.005),
               color=_rgba(TINTA))
        # avatar con cara de cómic
        xa = -CAP_ANCHO / 2 + 0.05
        Entity(parent=self.captura, model="circle", position=(xa, yb, -0.001), scale=0.062, color=_rgba(TINTA))
        Entity(parent=self.captura, model="circle", position=(xa, yb, -0.002), scale=0.052, color=_rgba((245, 200, 160)))
        ojo_i, ojo_d, r_ojo, sonrisa = sc.cara_avatar(0.026)
        for ox, oy in (ojo_i, ojo_d):
            Entity(parent=self.captura, model="circle", position=(xa + ox, yb + oy, -0.003), scale=r_ojo * 2, color=_rgba(TINTA))
        _linea(self.captura, [(xa + x, yb + y) for x, y in sonrisa], TINTA, grosor=3, z=-0.003)
        textos = [z["texto"] for z in self.partida.zonas]
        cuenta = next((t for t in textos if t.startswith("@")), "") or "Mensaje reenviado"
        hora = next((m.group(0) for t in textos for m in [re.search(r"\b\d{1,2}:\d{2}\b", t)] if m), "") or "10:42"
        _texto(self.captura, cuenta[:28], 17, TINTA, (xa + 0.045, yb + 0.014), origen=(-0.5, 0))
        _texto(self.captura, "reenviado", 17, (90, 70, 50), (xa + 0.045, yb - 0.02), origen=(-0.5, 0))
        _texto(self.captura, hora, 17, TINTA, (CAP_ANCHO / 2 - 0.075, yb), origen=(0.5, 0))
        for pts in sc.puntos_doble_check(0.022):
            _linea(self.captura, [(CAP_ANCHO / 2 - 0.045 + x, yb + y) for x, y in pts], (60, 130, 190), grosor=4, z=-0.003)

    # -- Ficha de pista --

    def _montar_ficha(self, col):
        izq = FICHA_X - FICHA_ANCHO / 2 + 0.03
        ancho_txt = FICHA_ANCHO - 0.06
        self._ficha_izq, self._ficha_arriba = izq, col["arriba"]
        arriba = col["arriba"]
        self._hoja_ficha(self.ficha_alto, arriba)
        self.ficha_etiqueta = _texto(self, "", 22, TINTA, (izq, arriba - 0.026))
        self.lupa_titulo = self.ficha_etiqueta              # el final de la vista base reescribe este título
        self.lupa = ui.texto(self, "", PX_PISTA, ancho_txt, TINTA, (izq, arriba - 0.075))
        self.revision = ui.texto(self, "", 16, ancho_txt, TINTA, (izq, arriba - 0.075))
        # contador: lupitas que se rellenan de rojo al marcar, más el texto «n de 3 marcas»
        yc = col["contador_y"]
        self.casillas, self._raices_casillas = [], []
        ancho_tira = FICHA_ANCHO * 0.9
        self._tira_contador = _hoja(self, (FICHA_X, yc), (ancho_tira, 0.062), PAPEL, z=0.03)
        for k in range(self.partida.max_marcas):
            x = sc.x_contador(izq + 0.075, k, 0.062)
            self.casillas.append(_lupita(self, (x, yc), PAPEL, z=0.02))
            self._raices_casillas.append(self.casillas[-1].parent)
        self.marcas_txt = _texto(self, "", 17, TINTA, (izq + 0.075 + self.partida.max_marcas * 0.062 + 0.005, yc), origen=(-0.5, 0))

    def _hoja_ficha(self, alto, arriba):
        """Ficha de papel con pestaña «PISTA»; se rehace (más alta) al cerrar para las explicaciones."""
        for viejo in getattr(self, "_piezas_ficha", []):
            destroy(viejo)
        izq = self._ficha_izq
        ficha = _hoja(self, (FICHA_X, arriba - alto / 2), (FICHA_ANCHO, alto), PAPEL, z=0.03)
        pest = Entity(parent=self, position=(izq + 0.06, arriba + 0.022, 0.025))
        Entity(parent=pest, model="quad", scale=(0.13, 0.045), color=_rgba(TINTA))
        _texto(pest, "PISTA", 15, PAPEL, (0, 0), origen=(0, 0))
        self.ficha = ficha
        self._piezas_ficha = [ficha, pest]

    def _pintar_lupa(self):
        if self._vista_base:
            return MinijuegoSenales._pintar_lupa(self)
        if self.terminado or not hasattr(self, "ficha_etiqueta"):
            return
        if self.foco < len(self.tarjetas):
            z = self.partida.zonas[self.foco]
            self.ficha_etiqueta.text = self.etiquetas[self.foco]
            self.lupa.text = "\n".join(ui.lineas_de(z["lupa"] + ". ¿Encaja con el resto?", PX_PISTA, FICHA_ANCHO - 0.06))
        else:
            self.ficha_etiqueta.text = "Tu decisión"
            self.lupa.text = "\n".join(ui.lineas_de("Confirma tus marcas, o di que la captura no tiene nada raro.", PX_PISTA,
                                                    FICHA_ANCHO - 0.06))
        self._pintar_contador()

    def _pintar_contador(self):
        n = len(self.partida.marcadas)
        for k, cristal in enumerate(getattr(self, "casillas", [])):
            cristal.color = _rgba(ROJO if k < n else PAPEL)
        self.marcas_txt.text = sc.texto_marcas(n, self.partida.max_marcas)

    # -- Lupa que sigue al foco --

    def _montar_lupa(self):
        self.lente = Entity(parent=self, z=-0.15)
        r = DIAMETRO_LUPA / 2
        ini, fin = sc.mango_lupa(r, -45, r * 0.95)
        _linea(self.lente, [ini, fin], TINTA, grosor=13, z=0.004)
        _linea(self.lente, [ini, fin], AMARILLO, grosor=7, z=0.003)
        Entity(parent=self.lente, model="circle", scale=DIAMETRO_LUPA, color=_rgba(CIAN, 0.10), z=0.002)
        _anillo(self.lente, DIAMETRO_LUPA + 0.020, TINTA, 1.0, grosor=7, z=0.001)
        _anillo(self.lente, DIAMETRO_LUPA + 0.008, AMARILLO, 1.0, grosor=6, z=0.0005)
        _anillo(self.lente, DIAMETRO_LUPA - 0.004, CIAN, 1.0, grosor=4)
        _linea(self.lente, sc.arco_brillo(r), (255, 255, 255), grosor=5, alfa=0.9, z=-0.001)
        pest = Entity(parent=self.lente, position=(0, DIAMETRO_LUPA / 2 + 0.03, -0.001))
        self.pestana_fondo = Entity(parent=pest, model="quad", scale=(0.13, 0.036), color=_rgba(TINTA))
        self.pestana_txt = _texto(pest, "", 14, PAPEL, (0, 0), origen=(0, 0), z=-0.001)
        self._destino_lupa = None
        self._colocar_lupa(inmediato=True)

    def _quitar_lupa(self):
        self._lupa_rota = True
        self._listo = False
        lente = getattr(self, "lente", None)
        if lente is not None:
            lente.enabled = False

    def _pintar_foco(self):
        super()._pintar_foco()
        if getattr(self, "_listo", False) and not self._lupa_rota:
            self._vigilar(self._colocar_lupa)

    def _colocar_lupa(self, inmediato=False):
        if self.terminado or self.foco >= len(self.tarjetas):
            self.lente.enabled = False
            return
        tarjeta = self.tarjetas[self.foco]
        self.lente.enabled = True
        self._destino_lupa = (tarjeta.x + tarjeta.ancho / 2 - 0.06, tarjeta.y)
        if inmediato or bv.reducir_movimiento():
            self.lente.x, self.lente.y = self._destino_lupa
        nombre = self.etiquetas[self.foco]
        self.pestana_txt.text = nombre
        self.pestana_fondo.scale_x = max(0.1, ui.medir(nombre, 14, True) + 0.03)

    # -- Marcar --

    def alternar(self, i):
        super().alternar(i)
        if getattr(self, "casillas", None):
            self._pintar_contador()

    # -- Cierre --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if not self._vista_base:
            self._vigilar(self._cierre)

    def _cierre(self):
        if getattr(self, "lente", None) is not None:
            self.lente.enabled = False
        for b in (self.boton_confirmar, self.boton_nada):
            b.enabled = False
        self.marcas_txt.text = ""
        for raiz in self._raices_casillas:
            raiz.enabled = False
        self._tira_contador.enabled = False
        self._hoja_ficha(FICHA_ALTO_FIN, self._ficha_arriba)
        self.ficha_etiqueta.text = "Lo que delataba"
        reales = self.partida.fallas()
        explicaciones = [self.partida.zonas[i]["explica"] for i in sorted(reales)] or ["No había nada raro: la captura era auténtica."]
        self.revision.text = "\n".join("- " + "\n  ".join(ui.lineas_de(e, 16, FICHA_ANCHO - 0.09)) for e in explicaciones)
        self.revision.y = self._ficha_arriba - 0.075
        texto = "EDITADA" if reales else "AUTÉNTICA"
        _sello(self.captura, texto, (0.17, CAP_ALTO / 2 - ALTO_BARRA / 2), ROJO if reales else VERDE,
               giro=-8, escala=(0.26, 0.07)).z = -0.05

    def posicion_sello(self):
        if self._vista_base:
            return super().posicion_sello()
        return (FICHA_X + 0.12, 0.41)

    def posicion_estrellas(self):
        if self._vista_base:
            return super().posicion_estrellas()
        return (FICHA_X + 0.2, 0.35)

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not getattr(self, "_listo", False) or self._lupa_rota or self._destino_lupa is None:
            return
        if self.lente.enabled and not bv.reducir_movimiento():
            dx, dy = self._destino_lupa
            self.lente.x = fx_calc.acercar(self.lente.x, dx, dt, SUAVIZADO)
            self.lente.y = fx_calc.acercar(self.lente.y, dy, dt, SUAVIZADO)

