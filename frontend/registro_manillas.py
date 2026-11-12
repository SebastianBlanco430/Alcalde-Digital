# Manillas de Bonfim (punto 6 del plan final). frontend/extensiones.py llama a registrar(); no se edita main.py. Tres piezas:
#
#   1. BRAZALETE del HUD (ControlManillas + VistaBrazalete): una cinta por indicador (convivencia, confianza, desinformación,
#      bienestar digital y conflictos) colgadas de una cuerda en el borde izquierdo. Cada cinta cambia de color, tejido
#      (lisa -> rayada -> punteada -> deshilachada), nudos (3-2-1-0) y desgaste según el nivel; el cambio se FUNDE (no
#      salta). Cada una lleva su dije (símbolo) y el ratón encima enseña la frase y el valor. Se esconde con la pausa, la
#      cinemática, el mapa grande, los paneles modales y el fin de partida, como el resto del HUD.
#   2. LEYENDA (tecla B): qué es cada manilla (ciudad, vecinos y cómo leer nivel/tejido/nudos), con la frase actual de cada
#      indicador. No bloquea el juego; B o Escape-pausa la cierran.
#   3. CINTAS EN LOS NPC (ControlCintasNPC): una cinta algo exagerada de tamaño en la muñeca izquierda de los NPC cercanos
#      (nivel A de la multitud, peatones del mundo chico y NPC clave), con el color/tejido de su estado emocional
#      (npc_postura.estado_de). PISCINA FIJA de CAPACIDAD_NPC cintas que se reparten entre los NPC cercanos
#      (manillas_calculos.elegir_cintas_npc): no se crea ni se destruye nada tras el arranque.
#
# Los datos salen de frontend/ambiente_vivo.py (el Ambiente suavizado; alimentado por registro_ambiente_npc) y del modelo
# backend/logica/manillas.py; la parte pura está en frontend/manillas_calculos.py y el dibujo con Pillow en
# frontend/manillas_dibujo.py. No toca los archivos de multitud, peatones ni NPC: usa la API pública npc.ancla_muneca("i").
#
# Banderas: ALCALDE_MANILLAS=0 lo apaga todo; ALCALDE_MANILLAS_HUD=0 solo el brazalete y la leyenda;
# ALCALDE_MANILLAS_NPC=0 solo las cintas de los NPC.

import math
import os
import sys

from frontend import ambiente_vivo
from frontend import manillas_calculos as mcal

MANILLAS = True
MANILLAS_HUD = True
MANILLAS_NPC = True

ANCHO_CHIP, ALTO_CHIP = 0.355, 0.2
MARGEN = 0.02
Y_CENTRO = -0.07                      # centro vertical del brazalete (entre el panel de turno y los chips de abajo)
ANCHO_CINTA, ALTO_CINTA = 0.034, 0.085
PASO_COLUMNA = 0.066
LADO_DIJE = 0.026

# Cinta de la muñeca (medidas del esqueleto, en m; algo exagerada para leerse a unos 10 m).
RADIO_ARO, ALTO_ARO = 0.062, 0.085
ANCHO_COLA, LARGO_COLA = 0.10, 0.25
GIRO_COLA = 20.0                      # grados que se abre la cola hacia fuera de la muñeca


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_MANILLAS", MANILLAS)


def hud_activo():
    return activo() and _bandera("ALCALDE_MANILLAS_HUD", MANILLAS_HUD)


def npc_activo():
    return activo() and _bandera("ALCALDE_MANILLAS_NPC", MANILLAS_NPC)


def _aviso(texto):
    print(f"[manillas] {texto}", file=sys.stderr)


# ---------------------------------------------------------------- lógica del brazalete (sin ursina; se prueba con escenas falsas)

class ControlManillas:
    """Lee el Ambiente vivo, decide el aspecto de cada manilla (con histéresis) y se lo da a la vista.
    `escena`: lo que usa de EscenaMundo (flujo, _sesion, en_pausa, _cinematica, hud, economia, _bloqueado_por_paneles()).
    `vista`: pintar(aspectos|None, visible, dt), alternar_leyenda(aspectos|None), cerrar_leyenda(), leyenda_abierta(),
    cursor(punto_o_None)."""

    def __init__(self, escena, vista):
        self.escena, self.vista = escena, vista
        self.niveles = {}
        self.aspectos = None
        self.oculto = True

    def _panel_abierto(self):
        escena = self.escena
        economia = getattr(escena, "economia", None)
        try:
            return bool(escena._bloqueado_por_paneles() or (economia is not None and economia.bloquea_controles()))
        except Exception:
            return False

    def _mapa_abierto(self):
        try:
            return bool(self.escena.hud.mapa_grande_abierto())
        except Exception:
            return False

    def esta_oculto(self):
        flujo = getattr(self.escena, "flujo", None)
        sin_partida = flujo is None or getattr(self.escena, "_sesion", None) is None
        terminada = bool(not sin_partida and flujo.partida_terminada())
        return mcal.oculto_hud(
            en_pausa=bool(getattr(self.escena, "en_pausa", False)), cinematica=bool(getattr(self.escena, "_cinematica", False)),
            mapa_abierto=self._mapa_abierto(), panel_abierto=self._panel_abierto(), terminada=terminada, sin_partida=sin_partida)

    def calcular(self):
        """{indicador: aspecto} con el Ambiente vivo, o None si aún no hay partida."""
        valores = mcal.valores_ciudad(ambiente_vivo.obtener(), ambiente_vivo.suave().valores()["indicadores"])
        if valores is None:
            return None
        aspectos = {}
        for indicador in mcal.INDICADORES_HUD:
            aspecto = mcal.aspecto_ciudad(indicador, valores[indicador], self.niveles.get(indicador))
            self.niveles[indicador] = aspecto["nivel"]
            aspectos[indicador] = aspecto
        return aspectos

    def avanzar(self, dt):
        self.oculto = self.esta_oculto()
        self.aspectos = None if self.oculto else self.calcular()
        if self.oculto and self.vista.leyenda_abierta():
            self.vista.cerrar_leyenda()
        self.vista.pintar(self.aspectos, not self.oculto and self.aspectos is not None, dt)
        return self.aspectos

    def input(self, key):
        """Tecla B: abre / cierra la leyenda (solo con el brazalete visible: no encima de la pausa ni de un panel)."""
        if key != mcal.TECLA:
            return False
        if self.vista.leyenda_abierta():
            self.vista.cerrar_leyenda()
            return True
        if self.oculto:
            return False
        self.vista.alternar_leyenda(self.aspectos)
        return True


# ---------------------------------------------------------------- vista Ursina

def _cache_texturas():
    from ursina import Texture
    from frontend import manillas_dibujo as dib
    cache = {}

    def textura(clave, ancho=64, alto=160):
        k = (clave, ancho, alto)
        if k not in cache:
            color, patron, nudos, desgaste = clave
            t = Texture(dib.dibujar_cinta(color, patron, nudos, desgaste, ancho, alto))
            t.filtering = "bilinear"
            cache[k] = t
        return cache[k]

    dijes = {}

    def dije(simbolo):
        if simbolo not in dijes:
            t = Texture(dib.dibujar_dije(simbolo, 48))
            t.filtering = "bilinear"
            dijes[simbolo] = t
        return dijes[simbolo]

    return textura, dije


_TEXTURAS = None


def texturas():
    global _TEXTURAS
    if _TEXTURAS is None:
        _TEXTURAS = _cache_texturas()
    return _TEXTURAS


def _crear_vista(escena_mundo):
    from ursina import Entity, Text, camera, color, mouse

    from backend.logica import manillas as mdl
    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import escala_fuente, panel_tinta, rgb

    textura, dije = texturas()

    def texto(padre, cadena, px, posicion, origen=(-0.5, 0), titulo=False, tono=None):
        extra = {"font": tipografia.FUENTE_TITULO} if titulo else {}
        return Text(cadena, parent=padre, origin=origen, position=posicion, scale=escala_fuente(px),
                    color=rgb(tono or estilo.COLOR_TEXTO), **extra)

    class Columna:
        """Una cinta del brazalete: dos capas para fundir la nueva sobre la anterior, y su dije."""

        def __init__(self, padre, indicador, x):
            self.indicador, self.clave = indicador, None
            y = ALTO_CHIP / 2 - 0.058 - ALTO_CINTA / 2
            self.actual = Entity(parent=padre, model="quad", scale=(ANCHO_CINTA, ALTO_CINTA), position=(x, y, -0.01))
            self.nueva = Entity(parent=padre, model="quad", scale=(ANCHO_CINTA, ALTO_CINTA), position=(x, y, -0.012),
                                color=color.rgba(1, 1, 1, 0), enabled=False)
            self.dije = Entity(parent=padre, model="quad", scale=(LADO_DIJE, LADO_DIJE),
                               position=(x, y - ALTO_CINTA / 2 - LADO_DIJE / 2 - 0.004, -0.01),
                               texture=dije(mdl.SIMBOLOS[indicador]))
            self.centro_ui = (x, y - 0.012)
            self.t = None

        def poner(self, clave, inmediato):
            if clave == self.clave:
                return
            primera = self.clave is None
            self.clave = clave
            if primera or inmediato:
                self.actual.texture = textura(clave)
                self.nueva.enabled = False
                self.t = None
                return
            self.nueva.texture = textura(clave)
            self.nueva.color = color.rgba(1, 1, 1, 0)
            self.nueva.enabled = True
            self.t = 0.0

        def avanzar(self, dt):
            if self.t is None:
                return
            self.t += dt
            p = mcal.progreso_fundido(self.t)
            self.nueva.color = color.rgba(1, 1, 1, p)
            if self.t >= mcal.DURACION_FUNDIDO:
                self.actual.texture = self.nueva.texture
                self.nueva.enabled = False
                self.t = None

    class VistaBrazalete:

        def __init__(self, escena):
            self.chip = Entity(parent=escena.hud, enabled=False)
            self.chip.fondo = panel_tinta(self.chip, ANCHO_CHIP, ALTO_CHIP, tono=estilo.COLOR_FONDO,
                                          radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            texto(self.chip, "Manillas", 13, (-ANCHO_CHIP / 2 + 0.014, ALTO_CHIP / 2 - 0.022, -0.01), titulo=True)
            tecla = texto(self.chip, mcal.TECLA.upper(), 13, (ANCHO_CHIP / 2 - 0.014, ALTO_CHIP / 2 - 0.022, -0.01),
                          origen=(0.5, 0), titulo=True, tono=estilo.ACENTO_SECUNDARIO)
            tecla.nombre = "tecla"
            cuerda_y = ALTO_CHIP / 2 - 0.044
            Entity(parent=self.chip, model="quad", scale=(ANCHO_CHIP - 0.03, 0.007), position=(0, cuerda_y, -0.009),
                   color=rgb(estilo.TINTA))
            Entity(parent=self.chip, model="quad", scale=(ANCHO_CHIP - 0.034, 0.0035), position=(0, cuerda_y, -0.0095),
                   color=rgb((250, 246, 232)))
            x0 = -PASO_COLUMNA * (len(mcal.INDICADORES_HUD) - 1) / 2
            self.columnas = [Columna(self.chip, ind, x0 + k * PASO_COLUMNA) for k, ind in enumerate(mcal.INDICADORES_HUD)]
            self.chip.position = (-diseno_adaptable.aspecto() / 2 + MARGEN + ANCHO_CHIP / 2, Y_CENTRO)
            diseno_adaptable.anclar(self.chip, "izquierda")
            self.aspectos = None
            self._visible = False
            self.tooltip = self._crear_tooltip(escena.hud)
            self._escena = escena
            self._hover = None
            self.leyenda = self._crear_leyenda(escena.hud)          # se crea ya (escondida): pulsar B no tiene tirón
            self._por_calentar = self._claves_a_calentar()

        @staticmethod
        def _claves_a_calentar():
            """Todas las cintas que puede pintar el brazalete (4 niveles x sus grados de desgaste): se dibujan de a una por
            frame al arrancar, para que ningún cambio de nivel dibuje una en pleno juego."""
            claves = []
            for nivel, (color_n, patron_n, nudos_n) in mdl.ESTILO_NIVEL.items():
                i = mdl.NIVELES.index(nivel)
                techo = 1.0 if i == len(mdl.NIVELES) - 1 else 1.0 - mdl.UMBRALES_NIVEL[i] / 100.0
                piso = 0.0 if i == 0 else 1.0 - (mdl.UMBRALES_NIVEL[i - 1] / 100.0 if i else 1.0)
                for g in range(mcal.PASOS_DESGASTE + 1):
                    d = g / mcal.PASOS_DESGASTE
                    if piso - 0.05 <= d <= techo + 0.05:
                        claves.append((tuple(color_n), patron_n, nudos_n, d))
            return claves

        # -- Tooltip (solo con el ratón libre; con él bloqueado se usa la leyenda con B) --

        def _crear_tooltip(self, padre):
            t = Entity(parent=padre, enabled=False)
            t.fondo = panel_tinta(t, 0.44, 0.075, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                  borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            t.linea1 = texto(t, "", 14, (-0.205, 0.016, -0.01), titulo=True)
            t.linea2 = texto(t, "", 12, (-0.205, -0.016, -0.01))
            return t

        def cursor(self, punto):
            indice = mcal.cinta_bajo_cursor(punto, [c.centro_ui for c in self.columnas], ANCHO_CINTA * 0.9, (ALTO_CINTA + LADO_DIJE) / 2)
            if indice == self._hover:
                return indice
            self._hover = indice
            if indice is None or self.aspectos is None:
                self.tooltip.enabled = False
                return indice
            a = self.aspectos[mcal.INDICADORES_HUD[indice]]
            l1, l2 = mcal.texto_tooltip(a)
            self.tooltip.linea1.text, self.tooltip.linea2.text = l1, l2
            cx, cy = self.columnas[indice].centro_ui
            self.tooltip.position = (self.chip.x + ANCHO_CHIP / 2 + 0.23, cy)
            self.tooltip.enabled = True
            return indice

        # -- Brazalete --

        def pintar(self, aspectos, visible, dt):
            self.aspectos = aspectos
            if visible != self._visible:
                self._visible = visible
                self.chip.enabled = visible
                if not visible:
                    self.tooltip.enabled = False
                    self._hover = None
            if self._por_calentar:
                textura(self._por_calentar.pop())
            if not visible:
                return
            for col in self.columnas:
                a = aspectos[col.indicador]
                col.poner(mcal.clave_textura(a), inmediato=False)
                col.avanzar(dt)
                col.centro_ui = tuple(col.actual.get_position(camera.ui))[:2]
            if self.leyenda.enabled:
                self._refrescar_leyenda()
            if not mouse.locked and mouse.position is not None:
                self.cursor((mouse.x, mouse.y))
            else:
                self.cursor(None)

        # -- Leyenda --

        def leyenda_abierta(self):
            return bool(self.leyenda.enabled)

        def cerrar_leyenda(self):
            self.leyenda.enabled = False

        def alternar_leyenda(self, aspectos):
            if self.leyenda.enabled:
                self.leyenda.enabled = False
                return
            self.aspectos = aspectos if aspectos is not None else self.aspectos
            self.leyenda.enabled = True
            self._refrescar_leyenda()

        def _crear_leyenda(self, padre):
            info = mcal.lineas_leyenda()
            ANCHO, ALTO = 0.94, 0.88
            L = Entity(parent=padre, enabled=False, z=-0.02)
            L.fondo = panel_tinta(L, ANCHO, ALTO, tono=estilo.COLOR_FONDO)
            texto(L, info["titulo"], 22, (-ANCHO / 2 + 0.03, ALTO / 2 - 0.045, -0.01), titulo=True)
            texto(L, f"{mcal.TECLA.upper()} para cerrar", 13, (ANCHO / 2 - 0.03, ALTO / 2 - 0.045, -0.01), origen=(0.5, 0),
                  tono=estilo.ACENTO_SECUNDARIO)
            texto(L, "La ciudad (ahora)", 15, (-ANCHO / 2 + 0.03, 0.315, -0.01), titulo=True, tono=estilo.ACENTO_SECUNDARIO)
            texto(L, "Los vecinos", 15, (0.03, 0.315, -0.01), titulo=True, tono=estilo.ACENTO_SECUNDARIO)
            L.filas_ciudad = []
            for k, (indicador, _nombre, simbolo) in enumerate(info["ciudad"]):
                y = 0.235 - k * 0.075
                cinta = Entity(parent=L, model="quad", scale=(0.03, 0.07), position=(-ANCHO / 2 + 0.05, y, -0.01))
                Entity(parent=L, model="quad", scale=(0.03, 0.03), position=(-ANCHO / 2 + 0.1, y, -0.01), texture=dije(simbolo))
                linea = texto(L, "", 13, (-ANCHO / 2 + 0.13, y + 0.012, -0.01), titulo=True)
                detalle = texto(L, "", 12, (-ANCHO / 2 + 0.13, y - 0.016, -0.01))
                L.filas_ciudad.append((indicador, cinta, linea, detalle))
            for k, (estado, patron, nudos, frase) in enumerate(info["vecinos"]):
                y = 0.235 - k * 0.075
                m = mdl.manilla_de_npc(estado)
                nd = mdl.detalle_manilla_npc(estado)
                cinta = Entity(parent=L, model="quad", scale=(0.03, 0.07), position=(0.05, y, -0.01),
                               texture=textura((tuple(m.color), m.patron, nd["nudos"], mcal.cuantizar_desgaste(m.desgaste))))
                titulo_, _, descr = frase.partition(": ")
                texto(L, titulo_, 13, (0.09, y + 0.012, -0.01), titulo=True)
                texto(L, f"{descr} · {patron}, {mcal._nudos_texto(nudos)}", 12, (0.09, y - 0.016, -0.01))
            texto(L, "Cómo leer la ciudad", 15, (-ANCHO / 2 + 0.03, -0.14, -0.01), titulo=True, tono=estilo.ACENTO_SECUNDARIO)
            for k, (nivel, patron, nudos, frase) in enumerate(info["niveles"]):
                x = -ANCHO / 2 + 0.03 + k * 0.225
                color_n, patron_n, nudos_n = mdl.ESTILO_NIVEL[nivel]
                des = (0.0, 0.25, 0.6, 1.0)[k]
                Entity(parent=L, model="quad", scale=(0.022, 0.054), position=(x + 0.011, -0.205, -0.01),
                       texture=textura((tuple(color_n), patron_n, nudos_n, des)))
                nombre, _, descr = frase.partition(": ")
                texto(L, nombre, 13, (x + 0.034, -0.19, -0.01), titulo=True)
                texto(L, f"{patron}, {mcal._nudos_texto(nudos)}", 12, (x + 0.034, -0.218, -0.01))
            for k, nota in enumerate(info["notas"]):
                partes = _partir(nota, 96)
                for j, linea in enumerate(partes):
                    texto(L, linea, 12, (-ANCHO / 2 + 0.03, -0.30 - (k * 2 + j) * 0.027 - k * 0.012, -0.01),
                          tono=estilo.COLOR_TEXTO)
            L.position = (0, 0)
            diseno_adaptable.ajustar_escala(L)
            return L

        def _refrescar_leyenda(self):
            if self.aspectos is None:
                return
            for indicador, cinta, linea, detalle in self.leyenda.filas_ciudad:
                a = self.aspectos[indicador]
                clave = mcal.clave_textura(a)
                if cinta.texture is None or getattr(cinta, "_clave", None) != clave:
                    cinta.texture, cinta._clave = textura(clave), clave
                nombre, _, frase = a["descripcion"].partition(": ")
                if linea.text != nombre:
                    linea.text = nombre
                nuevo = f"{frase} · {a['patron']}, {mcal._nudos_texto(a['nudos'])}"
                if detalle.text != nuevo:
                    detalle.text = nuevo

    return VistaBrazalete(escena_mundo)


def _partir(texto, ancho):
    """Parte `texto` en líneas de hasta `ancho` caracteres, por palabras (puro)."""
    lineas, actual = [], ""
    for palabra in texto.split():
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return lineas


# ---------------------------------------------------------------- cintas en las muñecas de los NPC

class AsignadorCintasNPC:
    """Estado de la piscina de cintas, sin ursina: quién lleva cuál (id -> ranura) y con qué estado. `poner(ranura, cuerpo,
    estado)` y `quitar(ranura)` los pone quien lo use (la vista Ursina, o un registro en las pruebas)."""

    def __init__(self, poner, quitar, capacidad=mcal.CAPACIDAD_NPC):
        self.poner, self.quitar, self.capacidad = poner, quitar, capacidad
        self.asignados = {}                    # id del cuerpo -> ranura
        self.estados = {}                      # ranura -> estado con el que se pintó
        self.cuerpos = {}                      # ranura -> cuerpo
        self.reasignaciones = 0

    def repartir(self, candidatos):
        """`candidatos`: [(id, distancia, estado, cuerpo)]. Devuelve la lista de ids que llevan cinta."""
        nuevo = mcal.elegir_cintas_npc([(i, d) for i, d, _e, _c in candidatos], self.asignados, self.capacidad)
        por_id = {i: (e, c) for i, _d, e, c in candidatos}
        for ranura in list(self.cuerpos):
            if ranura not in nuevo.values():
                self.quitar(ranura)
                del self.cuerpos[ranura], self.estados[ranura]
        for i, ranura in nuevo.items():
            estado, cuerpo = por_id[i]
            if self.cuerpos.get(ranura) is not cuerpo:
                self.poner(ranura, cuerpo, estado)
                self.cuerpos[ranura], self.estados[ranura] = cuerpo, estado
                self.reasignaciones += 1
            elif self.estados[ranura] != estado:
                self.poner(ranura, cuerpo, estado)
                self.estados[ranura] = estado
        self.asignados = nuevo
        return list(nuevo)


def _crear_cintas_npc(escena):
    from ursina import Entity, Mesh, camera, color, time

    from backend.logica import manillas as mdl
    from frontend import npc_postura
    from frontend.componentes import rgb

    textura, _dije = texturas()
    reserva = Entity(parent=escena, enabled=True)

    class CintaNPC:

        def __init__(self):
            self.raiz = Entity(parent=reserva, enabled=False)
            v, uv, tr = mcal.geometria_anillo(RADIO_ARO, ALTO_ARO, 10)
            self.aro = Entity(parent=self.raiz, model=Mesh(vertices=v, uvs=uv, triangles=tr, mode="triangle"),
                              double_sided=True)
            # La cola cuelga hacia los dedos (+Y de la muñeca) y un poco hacia fuera del cuerpo (-X de la muñeca en los
            # nueve modelos; medido con ancla.getRelativeVector). Dos cintas cruzadas: se ve desde cualquier lado.
            self.cola_raiz = Entity(parent=self.raiz, position=(-RADIO_ARO * 0.95, ALTO_ARO * 0.35, 0),
                                    rotation_z=GIRO_COLA)
            self.colas = []
            for giro in (0.0, 90.0):
                brazo = Entity(parent=self.cola_raiz, rotation_y=giro)
                cola = Entity(parent=brazo, model="quad", double_sided=True, scale=(ANCHO_COLA, LARGO_COLA),
                              y=LARGO_COLA / 2, rotation_z=180)
                self.colas.append(cola)
            for e in [self.aro] + self.colas:
                e.unlit = True
            self.estado = None

        def poner(self, ancla, estado):
            m = mdl.manilla_de_npc(estado)
            d = mdl.detalle_manilla_npc(estado)
            self.raiz.parent = ancla
            self.raiz.enabled = True
            self.raiz.position = (0, 0, 0)
            self.aro.color = rgb(m.color)
            tex = textura((tuple(m.color), m.patron, d["nudos"], mcal.cuantizar_desgaste(m.desgaste)))
            for cola in self.colas:
                cola.texture = tex
            self.estado = estado

        def quitar(self):
            self.raiz.enabled = False
            self.raiz.parent = reserva
            self.estado = None

    pool = [CintaNPC() for _ in range(mcal.CAPACIDAD_NPC)]
    for estado in mdl.ESTADOS_NPC:                      # las 5 texturas, ya (ninguna se dibuja en pleno juego)
        m, d = mdl.manilla_de_npc(estado), mdl.detalle_manilla_npc(estado)
        textura((tuple(m.color), m.patron, d["nudos"], mcal.cuantizar_desgaste(m.desgaste)))

    def _poner(ranura, cuerpo, estado):
        ancla = npc_postura.ancla_muneca(cuerpo, "i")
        if ancla is None:
            pool[ranura].quitar()
            return
        pool[ranura].poner(ancla, estado)

    class ControlCintasNPC(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.asignador = AsignadorCintasNPC(_poner, lambda r: pool[r].quitar())
            self._frame = 0
            self.pool = pool

        def _candidatos(self):
            cx, cz = camera.world_x, camera.world_z
            yaw = math.radians(camera.world_rotation_y)
            fx, fz = math.sin(yaw), math.cos(yaw)
            cuerpos = []
            m = getattr(escena, "multitud", None)
            if m is not None:
                cuerpos += [a for a in m._actores if a.enabled]
            p = getattr(escena, "peatones", None)
            if p is not None:
                cuerpos += [a for a in p.personajes if a.enabled]
            economia = getattr(escena, "economia", None)
            for it in getattr(economia, "interacciones", ()):
                cuerpo = getattr(it, "npc", None)
                if cuerpo is not None and getattr(cuerpo, "enabled", False):
                    cuerpos.append(cuerpo)
            salida = []
            for c in cuerpos:
                if getattr(c, "_postura", None) is None:             # sin estado emocional no hay cinta que contar
                    continue
                dx, dz = c.world_x - cx, c.world_z - cz
                d = math.hypot(dx, dz)
                if d > mcal.RADIO_SALIDA_NPC:
                    continue
                if d > 1.5 and (dx * fx + dz * fz) / d < 0.2:            # de espaldas a la cámara: no vale la ranura
                    continue
                salida.append((id(c), d, npc_postura.estado_de(c), c))
            return salida

        def update(self):
            self.avanzar()

        def avanzar(self):
            self._frame += 1
            if self._frame % mcal.PERIODO_ASIGNACION:
                return
            self.asignador.repartir(self._candidatos())

        def estadisticas(self):
            return {"con_cinta": len(self.asignador.asignados), "reasignaciones": self.asignador.reasignaciones,
                    "capacidad": len(pool)}

    return ControlCintasNPC(parent=escena)


# ---------------------------------------------------------------- registro

def _crear_vigia(escena_mundo):
    from ursina import Entity, time

    vista = _crear_vista(escena_mundo)
    control = ControlManillas(escena_mundo, vista)

    class VigiaManillas(Entity):

        def update(self):
            control.avanzar(min(time.dt, 0.1))

        def input(self, key):
            control.input(key)

    vigia = VigiaManillas(parent=escena_mundo.hud)
    vigia.vista, vigia.control = vista, control
    return vigia


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    if hud_activo():
        try:
            conexion.vigia_manillas = _crear_vigia(escena_mundo)
        except Exception as error:
            _aviso(f"brazalete no instalado ({type(error).__name__}: {error})")
    if npc_activo():
        try:
            conexion.cintas_npc = _crear_cintas_npc(escena_mundo)
        except Exception as error:
            _aviso(f"cintas de NPC no instaladas ({type(error).__name__}: {error})")
    return getattr(conexion, "vigia_manillas", None)
