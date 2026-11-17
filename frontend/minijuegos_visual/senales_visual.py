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

import math
import re

from ursina import Entity, Mesh, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.senales import MinijuegoSenales
from frontend.minijuegos_visual.capa import CapaVisual

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
CAP_X, CAP_Y, CAP_ANCHO, CAP_ALTO = -0.38, -0.02, 0.92, 0.80
ALTO_BARRA = 0.085
ANCHO_BLOQUE = 0.80
# Ficha de pista
FICHA_ANCHO, FICHA_ALTO = 0.66, 0.46
FICHA_X, FICHA_Y = 0.52, 0.10
# Lupa
DIAMETRO_LUPA = 0.16
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


def _sello(parent, texto, pos, tono, giro=-6, escala=(0.16, 0.05)):
    if _pp is not None:
        try:
            return _pp.sello_goma(parent, texto, pos, tono, giro=giro, escala=escala, ovalado=True)
        except Exception:               # noqa: BLE001
            pass
    raiz = Entity(parent=parent, position=(pos[0], pos[1], -0.005), rotation_z=giro)
    Entity(parent=raiz, model="quad", scale=escala, color=_rgba(tono, 0.15))
    Text(texto, parent=raiz, origin=(0, 0), z=-0.001, scale=escala_fuente(16), font=tipografia.FUENTE_TITULO, color=_rgba(tono))
    return raiz


def _texto(parent, cadena, px, tono, pos, origen=(-0.5, 0.5), z=-0.004):
    return Text(cadena, parent=parent, origin=origen, position=(pos[0], pos[1], z), scale=escala_fuente(px),
                font=tipografia.FUENTE_TITULO, color=_rgba(tono))


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

    def _x_sello(self):
        return self.ancho / 2 - 0.1

    def _poner_sello(self, texto, tono):
        if self._sello is not None:
            self._sello.enabled = False
        dy = 0.012 if self.estado in self.ETIQUETAS_FIN else 0.0
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
                self._tachon = Entity(parent=self, model="quad", position=(self._x_sello(), 0.012, -0.03),
                                      scale=(0.19, 0.008), rotation_z=-14, color=_rgba(GRIS))
            self.etiqueta.text = self.ETIQUETAS_FIN[estado]
        elif self._sello is not None:
            self._sello.enabled = False
            self._sello = None
        self._sello_de = estado
        if estado in self.ETIQUETAS_FIN:
            self.etiqueta.y = -self.alto / 2 + a_unidades(20)     # la etiqueta baja: el sello ocupa la esquina


class SenalesVisual(CapaVisual, MinijuegoSenales):

    _lupa_rota = False

    def construir(self):
        """Misma partida y mismos objetos que MinijuegoSenales.construir, con la captura de móvil y la ficha de pista."""
        from frontend.minijuegos.senales_calculos import PartidaSenales
        self._listo = False
        self.partida = PartidaSenales(self.caso)
        p = self.partida
        self.x_tel = CAP_X
        self.x_lupa = FICHA_X
        self.etiquetas = [etiqueta_zona(z["lupa"], i) for i, z in enumerate(p.zonas)]
        self._montar_captura()
        # Bloques: reparten el cuerpo de la captura
        arriba = CAP_Y + CAP_ALTO / 2 - ALTO_BARRA - 0.03
        abajo = CAP_Y - CAP_ALTO / 2 + 0.025
        n = len(p.zonas)
        hueco = 0.014
        altos = [ui.Tarjeta.alto_necesario(z["texto"], ANCHO_BLOQUE, 17, margen_px=8, reserva=0.2) for z in p.zonas]
        sobra = (arriba - abajo) - sum(altos) - hueco * (n - 1)
        if sobra > 0:
            altos = [a + min(sobra / n, 0.03) for a in altos]
        y = arriba
        self.tarjetas = []
        for i, z in enumerate(p.zonas):
            dx = -0.02 if i % 2 == 0 else 0.02         # burbujas un pelín alternadas
            self.tarjetas.append(BloqueCaptura(ANCHO_BLOQUE, altos[i], z["texto"], "", 17, 14, parent=self,
                                               position=(CAP_X + dx, y - altos[i] / 2, -0.02),
                                               al_clic=lambda i=i: self.alternar(i), al_cursor=lambda i=i: self.poner_foco(i),
                                               margen_px=8, reserva=0.2))
            y -= altos[i] + hueco
        self._montar_ficha()
        bot_y = FICHA_Y - FICHA_ALTO / 2 - 0.07
        self.boton_confirmar = ui.Boton("Confirmar", self.confirmar, FICHA_ANCHO, 0.065, 18, primario=True, parent=self,
                                        position=(FICHA_X, bot_y))
        self.boton_nada = ui.Boton("No veo nada raro", self.sin_senales, FICHA_ANCHO, 0.065, 18, parent=self,
                                   position=(FICHA_X, bot_y - 0.09))
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
        Entity(parent=self.captura, model="quad", position=(0.006, -0.008, 0.003), scale=(CAP_ANCHO, CAP_ALTO),
               color=_rgba(TINTA, 0.63))
        Entity(parent=self.captura, model="quad", position=(0, 0, 0.002), scale=(CAP_ANCHO + 0.016, CAP_ALTO + 0.016),
               color=_rgba(TINTA))
        Entity(parent=self.captura, model="quad", position=(0, 0, 0.001), scale=(CAP_ANCHO, CAP_ALTO), color=_rgba(PAPEL))
        yb = CAP_ALTO / 2 - ALTO_BARRA / 2
        Entity(parent=self.captura, model="quad", position=(0, yb, 0), scale=(CAP_ANCHO, ALTO_BARRA), color=_rgba(AMARILLO))
        Entity(parent=self.captura, model="quad", position=(0, yb - ALTO_BARRA / 2, -0.001), scale=(CAP_ANCHO, 0.005),
               color=_rgba(TINTA))
        xa = -CAP_ANCHO / 2 + 0.05
        Entity(parent=self.captura, model="circle", position=(xa, yb, -0.001), scale=0.058, color=_rgba(TINTA))
        Entity(parent=self.captura, model="circle", position=(xa, yb, -0.002), scale=0.048, color=_rgba(PAPEL_VIEJO))
        textos = [z["texto"] for z in self.partida.zonas]
        cuenta = next((t for t in textos if t.startswith("@")), "") or "Mensaje reenviado"
        hora = next((m.group(0) for t in textos for m in [re.search(r"\b\d{1,2}:\d{2}\b", t)] if m), "") or "10:42"
        _texto(self.captura, cuenta[:28], 17, TINTA, (xa + 0.045, yb), origen=(-0.5, 0))
        _texto(self.captura, hora, 17, TINTA, (CAP_ANCHO / 2 - 0.03, yb), origen=(0.5, 0))

    # -- Ficha de pista --

    def _montar_ficha(self):
        izq = FICHA_X - FICHA_ANCHO / 2 + 0.03
        ancho_txt = FICHA_ANCHO - 0.06
        arriba = FICHA_Y + FICHA_ALTO / 2
        self.ficha = _hoja(self, (FICHA_X, FICHA_Y), (FICHA_ANCHO, FICHA_ALTO), PAPEL, z=0.03)
        pest = Entity(parent=self, position=(izq + 0.06, arriba + 0.022, 0.025))
        Entity(parent=pest, model="quad", scale=(0.13, 0.045), color=_rgba(TINTA))
        _texto(pest, "PISTA", 15, PAPEL, (0, 0), origen=(0, 0))
        self.ficha_etiqueta = _texto(self, "", 22, TINTA, (izq, arriba - 0.03))
        self.lupa_titulo = self.ficha_etiqueta              # el final de la vista base reescribe este título
        self.lupa = ui.texto(self, "", 17, ancho_txt, TINTA, (izq, arriba - 0.085))
        self.revision = ui.texto(self, "", 16, ancho_txt, TINTA, (izq, arriba - 0.085))
        yc = FICHA_Y - FICHA_ALTO / 2 + 0.05
        self.casillas = []
        for k in range(self.partida.max_marcas):
            raiz = Entity(parent=self, position=(izq + 0.03 + k * 0.065, yc, 0.02))
            Entity(parent=raiz, model="circle", scale=0.05, color=_rgba(TINTA), z=0.001)
            relleno = Entity(parent=raiz, model="circle", scale=0.038, color=_rgba(PAPEL))
            self.casillas.append(relleno)
        self.marcas_txt = _texto(self, "", 16, TINTA, (izq + 0.03 + self.partida.max_marcas * 0.065, yc), origen=(-0.5, 0))

    def _pintar_lupa(self):
        if self.terminado or not hasattr(self, "ficha_etiqueta"):
            return
        if self.foco < len(self.tarjetas):
            z = self.partida.zonas[self.foco]
            self.ficha_etiqueta.text = self.etiquetas[self.foco]
            self.lupa.text = "\n".join(ui.lineas_de(z["lupa"] + ". ¿Encaja con el resto?", 17, FICHA_ANCHO - 0.06))
        else:
            self.ficha_etiqueta.text = "Tu decisión"
            self.lupa.text = "\n".join(ui.lineas_de("Confirma tus marcas, o di que la captura no tiene nada raro.", 17,
                                                    FICHA_ANCHO - 0.06))
        self._pintar_contador()

    def _pintar_contador(self):
        n = len(self.partida.marcadas)
        for k, relleno in enumerate(getattr(self, "casillas", [])):
            relleno.color = _rgba(ROJO if k < n else PAPEL)
        self.marcas_txt.text = f"{n} de {self.partida.max_marcas} marcas"

    # -- Lupa que sigue al foco --

    def _montar_lupa(self):
        self.lente = Entity(parent=self, z=-0.15)
        Entity(parent=self.lente, model="circle", scale=DIAMETRO_LUPA, color=_rgba(CIAN, 0.10), z=0.002)
        _anillo(self.lente, DIAMETRO_LUPA + 0.012, AMARILLO, 0.85, grosor=7, z=0.001)
        _anillo(self.lente, DIAMETRO_LUPA, CIAN, 1.0, grosor=4)
        pest = Entity(parent=self.lente, position=(0, DIAMETRO_LUPA / 2 + 0.02, -0.001))
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
        self._destino_lupa = (tarjeta.x + tarjeta.ancho / 2 - 0.1, tarjeta.y)
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
        self._vigilar(self._cierre)

    def _cierre(self):
        if getattr(self, "lente", None) is not None:
            self.lente.enabled = False
        for b in (self.boton_confirmar, self.boton_nada):
            b.enabled = False
        self.marcas_txt.text = ""
        for relleno in self.casillas:
            relleno.parent.enabled = False
        self.ficha_etiqueta.text = "Lo que delataba"
        reales = self.partida.fallas()
        explicaciones = [self.partida.zonas[i]["explica"] for i in sorted(reales)] or ["No había nada raro: la captura era auténtica."]
        self.revision.text = "\n".join("- " + "\n  ".join(ui.lineas_de(e, 16, FICHA_ANCHO - 0.09)) for e in explicaciones)
        texto = "EDITADA" if reales else "AUTÉNTICA"
        _sello(self.captura, texto, (0.17, CAP_ALTO / 2 - ALTO_BARRA / 2), ROJO if reales else VERDE,
               giro=-8, escala=(0.26, 0.07)).z = -0.05

    def posicion_sello(self):
        return (FICHA_X + 0.12, 0.41)

    def posicion_estrellas(self):
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

