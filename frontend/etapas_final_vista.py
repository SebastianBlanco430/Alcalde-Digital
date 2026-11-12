# Finales por etapas, lo que se VE y se OYE (docs/PLAN_FINALES_HISTORIA.md). La lógica es backend/logica/etapas_final.py
# (pura); lo instala frontend/registro_etapas_final.py y no toca ninguna clase existente.
#
# Un controlador (Entity hija del HUD del mundo: solo corre con el mundo activo) lee cada 0,5 s el índice de la partida
# (el real o el forzado), saca la etapa con histéresis y, cuando cambia:
#   - ambiente_vivo.fijar_etapa(e)       -> ciudad_viva reparte fuego / rodadores / fiesta
#   - tinte de cámara (quad en camera.ui detrás del HUD, fundido de 2 s) y viñeta oscura en -3
#   - NPC de etapa (piscina de hasta 8 cuerpos de la fábrica de siempre, con prop y globo de texto)
#   - perfil de audio del mundo (frontend/audio_enganches.fijar_perfil_mundo_etapa)
#   - aviso corto por la cola de avisos del reloj
# y pinta el medidor «Confianza de Ciudad Nova» arriba al centro (barra + número + nombre de la etapa con flecha).
# Debajo del medidor va la barra pequeña de DESINFORMACIÓN (docs/PLAN_CLARIDAD_JUEGO.md §2.2): ícono + «Desinformación
# 34 · más baja = mejor», con los colores invertidos. Se oculta con el medidor. ALCALDE_BARRA_DESINFO=0 la quita.
#
# Depuración: ALCALDE_INDICE_FORZADO=<0-100> fija el índice; con ALCALDE_DEBUG=1, F8 baja una etapa y F9 sube una.

import math
import os
import random
import sys

from backend.logica import etapas_final
from frontend import ambiente_vivo

PERIODO_LECTURA = 0.5            # s entre dos lecturas del índice
SEGUNDOS_TINTE = 2.0             # fundido del tinte al cambiar de etapa
MAX_NPC = 8                      # cuerpos como mucho (uno por tipo)
ANILLO_NPC = (15.0, 45.0)        # m alrededor del jugador donde se recolocan
ANILLO_NPC_CRISIS = (9.0, 28.0)  # en -2 y -3 los malos salen «más seguidos»: anillo más corto
RADIO_LOD_NPC = 60.0             # m: más lejos se recolocan en el anillo
RADIO_GLOBO = 4.0                # m: más cerca, el NPC dice su frase
VELOCIDAD_NPC = 1.1              # m/s
SEMILLA_NPC = 5417
GROSOR_TINTA_PROP = 0.018        # m por lado del casco de tinta de los props (contorno_calculos.GROSOR_CUERPO)

ANCHO_MEDIDOR, ALTO_MEDIDOR = 0.60, 0.088
ANCHO_BARRA, ALTO_BARRA = 0.54, 0.012
Y_MEDIDOR = 0.5 - 0.02 - ALTO_MEDIDOR / 2
MARCAS = (10, 25, 40, 60, 75, 90)

BARRA_DESINFO = True             # bandera de la barra de desinformación (ALCALDE_BARRA_DESINFO=0 la quita)
ALTO_DESINFO = ALTO_MEDIDOR / 2  # mismo ancho que el medidor, mitad de alto
SEPARACION_DESINFO = 0.012       # hueco entre el medidor y la barra
LADO_ICONO_DESINFO = 0.028
ALTO_BARRA_DESINFO = 0.008
SUFIJO_DESINFO = "más baja = mejor"


def barra_desinfo_activa():
    """¿Se pinta la barra de desinformación? ALCALDE_BARRA_DESINFO=1/0 manda sobre la constante."""
    valor = os.environ.get("ALCALDE_BARRA_DESINFO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(BARRA_DESINFO)


def texto_desinfo(valor):
    """«Desinformación 34 · más baja = mejor» (puro)."""
    return f"Desinformación {int(round(max(0.0, min(100.0, float(valor)))))} · {SUFIJO_DESINFO}"


def _aviso(texto):
    print(f"[etapas_final] {texto}", file=sys.stderr)


def textura_vineta(lado=128):
    """Imagen RGBA negra con alfa radial (0 en el centro, 1 en las esquinas) para la viñeta oscura de la etapa -3."""
    from PIL import Image
    imagen = Image.new("RGBA", (lado, lado))
    pixeles = []
    medio = (lado - 1) / 2.0
    for y in range(lado):
        for x in range(lado):
            r = math.hypot((x - medio) / medio, (y - medio) / medio) / math.sqrt(2.0)
            alfa = max(0.0, min(1.0, (r - 0.45) / 0.5)) ** 1.6
            pixeles.append((0, 0, 0, int(255 * alfa)))
    imagen.putdata(pixeles)
    return imagen


def crear_controlador(escena, conexion):
    from panda3d.core import CullFaceAttrib
    from ursina import Circle, Entity, Text, Texture, color, time
    from ursina.shaders import unlit_shader

    from frontend import diseno_adaptable, estilo, reloj_calculos as rc, tipografia
    from frontend.componentes import escala_fuente, panel_tinta, rgb
    from frontend.contorno_calculos import inflar_escala, realzar_color

    textos = etapas_final.cargar_textos()

    # -- Medidor ----------------------------------------------------------------------------------------------------

    class Medidor(Entity):
        """Barra fina «Confianza de Ciudad Nova»: número, marcas de etapa y nombre de la etapa con flecha (no solo color)."""

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.position = (0, Y_MEDIDOR)
            self.fondo = panel_tinta(self, ANCHO_MEDIDOR, ALTO_MEDIDOR, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                     borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            izquierda = -ANCHO_BARRA / 2
            self.titulo = Text(textos["medidor"]["titulo"], parent=self, origin=(-0.5, 0), position=(izquierda, 0.026, -0.01),
                               scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO_TENUE))
            self.numero = Text("50", parent=self, origin=(0.5, 0), position=(ANCHO_BARRA / 2, 0.026, -0.01),
                               scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
            self.borde = Entity(parent=self, model="quad", scale=(ANCHO_BARRA + 0.006, ALTO_BARRA + 0.006),
                                position=(0, 0.003, -0.008), color=rgb(estilo.TINTA))
            self.barra_fondo = Entity(parent=self, model="quad", scale=(ANCHO_BARRA, ALTO_BARRA), position=(0, 0.003, -0.009),
                                      color=rgb(estilo.COLOR_BARRA_FONDO))
            self.barra = Entity(parent=self, model="quad", origin=(-0.5, 0), scale=(0.0001, ALTO_BARRA),
                                position=(izquierda, 0.003, -0.01), color=rgb(estilo.ESTADO_AVISO))
            for marca in MARCAS:
                Entity(parent=self, model="quad", scale=(0.003, ALTO_BARRA + 0.008),
                       position=(izquierda + ANCHO_BARRA * marca / 100.0, 0.003, -0.011), color=rgb(estilo.PAPEL))
            self.flecha = Entity(parent=self, model=Circle(3), scale=0.016, position=(0, -0.026, -0.01), color=rgb(estilo.PAPEL))
            self.guion = Entity(parent=self, model="quad", scale=(0.016, 0.004), position=(0, -0.026, -0.01),
                                color=rgb(estilo.PAPEL))
            self.etiqueta = Text("", parent=self, origin=(0, 0), position=(0.012, -0.026, -0.01), scale=escala_fuente(14),
                                 color=rgb(estilo.COLOR_TEXTO), font=tipografia.FUENTE_TITULO)
            self._pintado = None
            self.enabled = False
            diseno_adaptable.ajustar_escala(self)

        def pintar(self, indice, etapa):
            clave = (int(round(indice)), etapa)
            if clave == self._pintado:
                return
            self._pintado = clave
            tono = estilo.ESTADO_EXITO if etapa > 0 else estilo.ESTADO_ERROR if etapa < 0 else estilo.ESTADO_AVISO
            self.numero.text = str(clave[0])
            self.barra.scale_x = max(0.0001, ANCHO_BARRA * max(0.0, min(100.0, indice)) / 100.0)
            self.barra.color = rgb(tono)
            nombre = etapas_final.nombre_de_etapa(etapa)
            if self.etiqueta.text != nombre:
                self.etiqueta.text = nombre
            self.etiqueta.color = rgb(tono)
            ancho = self.etiqueta.width
            self.flecha.enabled, self.guion.enabled = etapa != 0, etapa == 0
            self.flecha.x = self.guion.x = self.etiqueta.x - ancho / 2 - 0.018
            self.flecha.rotation_z = 0 if etapa > 0 else 180       # Circle(3) nace apuntando arriba
            self.flecha.color = self.guion.color = rgb(tono)

    class BarraDesinfo(Entity):
        """Barra pequeña de desinformación, colgada bajo el medidor (hija suya: se oculta y se escala con él). Ícono
        (megáfono) + texto con el número + barra de color invertido: más baja = mejor."""

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.position = (0, -ALTO_MEDIDOR / 2 - SEPARACION_DESINFO - ALTO_DESINFO / 2)
            self.fondo = panel_tinta(self, ANCHO_MEDIDOR, ALTO_DESINFO, tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                     borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            izquierda = -ANCHO_BARRA / 2
            try:
                from backend.logica import manillas as mdl
                from frontend import registro_manillas
                Entity(parent=self, model="quad", scale=(LADO_ICONO_DESINFO, LADO_ICONO_DESINFO),
                       position=(izquierda + LADO_ICONO_DESINFO / 2, 0, -0.01),
                       texture=registro_manillas.texturas()[1](mdl.SIMBOLOS["desinformacion"]))
            except Exception as error:
                _aviso(f"ícono de desinformación no pintado ({type(error).__name__}: {error})")
            self.x_barra = izquierda + LADO_ICONO_DESINFO + 0.012
            self.ancho_barra = ANCHO_BARRA / 2 - self.x_barra
            self.texto = Text("", parent=self, origin=(-0.5, 0), position=(self.x_barra, 0.009, -0.01),
                              scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO))
            centro = self.x_barra + self.ancho_barra / 2
            Entity(parent=self, model="quad", scale=(self.ancho_barra + 0.005, ALTO_BARRA_DESINFO + 0.005),
                   position=(centro, -0.011, -0.008), color=rgb(estilo.TINTA))
            Entity(parent=self, model="quad", scale=(self.ancho_barra, ALTO_BARRA_DESINFO), position=(centro, -0.011, -0.009),
                   color=rgb(estilo.COLOR_BARRA_FONDO))
            self.barra = Entity(parent=self, model="quad", origin=(-0.5, 0), scale=(0.0001, ALTO_BARRA_DESINFO),
                                position=(self.x_barra, -0.011, -0.01), color=rgb(estilo.ESTADO_AVISO))
            self._pintado = None

        def pintar(self, valor):
            valor = int(round(max(0.0, min(100.0, float(valor)))))
            if valor == self._pintado:
                return
            self._pintado = valor
            self.texto.text = texto_desinfo(valor)
            self.barra.scale_x = max(0.0001, self.ancho_barra * valor / 100.0)
            self.barra.color = rgb(estilo.rgb_por_valor(100 - valor))       # invertido: mucha desinformación = rojo

    # -- NPC de etapa -----------------------------------------------------------------------------------------------

    def pieza(padre, modelo, posicion, escala, tono, giro=(0, 0, 0)):
        """Una primitiva de color plano con su casco de tinta (caras delanteras ocultas), como el resto del juego."""
        relleno = Entity(parent=padre, model=modelo, position=posicion, scale=escala, rotation=giro, shader=unlit_shader,
                         unlit=True, color=rgb(realzar_color(tono)))
        casco = Entity(parent=padre, model=modelo, position=posicion, scale=inflar_escala(escala, GROSOR_TINTA_PROP),
                       rotation=giro, shader=unlit_shader, unlit=True, color=rgb(estilo.TINTA))
        casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        relleno.ignore = casco.ignore = True
        return relleno

    def poner_prop(cuerpo, prop, tono, y_cabeza=1.75):
        """`y_cabeza`: altura de la coronilla de ese modelo (npc_postura.y_ancla_cabeza), para capucha y gorro."""
        if prop == "capucha":
            pieza(cuerpo, "sphere", (0, y_cabeza - 0.13, -0.05), (0.38, 0.36, 0.38), tono)
            pieza(cuerpo, "cube", (0, y_cabeza - 0.33, -0.11), (0.42, 0.14, 0.20), tono)
        elif prop == "canasta":
            pieza(cuerpo, "cube", (0.34, 0.88, 0.14), (0.34, 0.20, 0.26), (150, 104, 62))
            for k, flor in enumerate(((222, 64, 64), (248, 206, 56), tono)):
                pieza(cuerpo, "sphere", (0.24 + 0.10 * k, 1.03, 0.14), (0.13, 0.13, 0.13), flor)
        elif prop == "bandeja":
            pieza(cuerpo, "cube", (0, 1.06, 0.36), (0.52, 0.04, 0.30), (120, 124, 136))
            for k in range(3):
                pieza(cuerpo, "sphere", (-0.15 + 0.15 * k, 1.12, 0.36), (0.13, 0.10, 0.20), (214, 160, 90))
            pieza(cuerpo, "cube", (0, y_cabeza + 0.05, 0), (0.24, 0.14, 0.24), tono)         # gorro
        elif prop == "escoba":
            pieza(cuerpo, "cube", (0.36, 0.85, 0.12), (0.045, 1.5, 0.045), (150, 104, 62))
            pieza(cuerpo, "cube", (0.36, 0.14, 0.12), (0.32, 0.24, 0.09), (236, 200, 70))
            pieza(cuerpo, "cube", (0, 1.24, 0.02), (0.46, 0.20, 0.30), tono)                 # chaleco
        elif prop == "guitarra":
            pieza(cuerpo, "sphere", (0.06, 1.0, 0.26), (0.34, 0.42, 0.12), (170, 104, 56))
            pieza(cuerpo, "cube", (-0.24, 1.2, 0.26), (0.06, 0.52, 0.04), (90, 60, 40), (0, 0, 55))
            pieza(cuerpo, "sphere", (0.06, 1.0, 0.33), (0.12, 0.12, 0.02), (40, 30, 26))
        elif prop == "banda":
            pieza(cuerpo, "cube", (0, 1.22, 0.0), (0.56, 0.09, 0.32), tono, (0, 0, 38))
            pieza(cuerpo, "sphere", (0.16, 1.36, 0.16), (0.10, 0.10, 0.04), estilo.ACENTO_PRIMARIO)

    class CuerpoEtapa:
        """Un NPC de etapa: cuerpo de la fábrica de siempre + prop + nombre + globo con una frase."""

        def __init__(self, tipo, datos, orden):
            from frontend.globos_npc import AJUSTE_LINEA, ALTURA, COLOR_FONDO, COLOR_TEXTO, ESCALA_TEXTO, RELLENO
            from frontend.npc_modelo import crear_npc
            from frontend.peatones import ROPA
            from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
            from frontend.componentes import destruir_arbol
            from frontend.piezas import etiqueta, silenciar
            self.tipo, self.datos = tipo, datos
            self.nombre = datos["nombre"]
            self.frases = list(datos["frases"])
            self._frase = orden
            self.azar = random.Random(SEMILLA_NPC + orden * 97)
            self.rumbo = self.azar.uniform(0, 360)
            self.t_giro = self.azar.uniform(3, 8)
            self.x = self.z = 0.0
            self.hablando = False
            i = int(datos.get("modelo", orden))
            tono = tuple(datos.get("color", ROPA[i % len(ROPA)]))
            npc = crear_npc(i, SEMILLA_NPC, aspecto_peaton(i, SEMILLA_NPC), rasgos_peaton(i, SEMILLA_NPC), tono, parent=escena)
            npc.aro.enabled = False
            npc.nombre = self.nombre
            y = npc.etiqueta.y
            destruir_arbol(npc.etiqueta)
            npc.etiqueta = silenciar(etiqueta(self.nombre, parent=npc, y=y, scale=8))
            npc.suelo = escena._mundo.altura
            from frontend import npc_postura
            ancla = npc_postura.ancla_cabeza(npc)             # la misma ancla de la que cuelgan los globos de los NPC
            try:
                # Soporte en metros reales: algunos modelos traen el cuerpo escalado y los props saldrían desplazados.
                soporte = Entity(parent=getattr(npc, "cuerpo", npc))
                soporte.world_scale = 1
                soporte.ignore = True
                poner_prop(soporte, datos.get("prop"), tono, float(ancla.y) - 0.06)
            except Exception as error:
                _aviso(f"{tipo}: sin prop ({type(error).__name__}: {error})")
            self._ajuste = AJUSTE_LINEA
            self.globo = etiqueta("…", parent=ancla, scale=ESCALA_TEXTO, color=color.rgb32(*COLOR_TEXTO), wordwrap=AJUSTE_LINEA,
                                  y=ALTURA)
            self.globo.background_entity.color = color.rgba32(*COLOR_FONDO)
            self._relleno = RELLENO
            self.globo.enabled = False
            silenciar(self.globo)
            self.npc = npc
            self.activo = True
            npc.enabled = False

        def mostrar(self, visible):
            self.npc.enabled = bool(visible)
            if not visible and self.hablando:
                self.callar()

        def colocar(self, x, z):
            self.x, self.z = x, z
            self.npc.colocar(x, z)

        def hablar(self):
            self.hablando = True
            frase = self.frases[self._frase % len(self.frases)]
            self._frase += 1
            self.globo.text = frase
            self.globo.wordwrap = self._ajuste
            fondo = self.globo.background_entity
            if fondo is not None:
                fondo.scale = (self.globo.width + self._relleno[0], self.globo.height + self._relleno[1])
            self.globo.enabled = True
            self.npc.etiqueta.enabled = False

        def callar(self):
            self.hablando = False
            self.globo.enabled = False
            self.npc.etiqueta.enabled = True

    # -- Controlador ------------------------------------------------------------------------------------------------

    class ControladorEtapas(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self.etapa = 0
            self.indice = None
            self._t = 0.0
            self._sesion = None
            self._azar = random.Random(SEMILLA_NPC)
            # Tinte: detrás del HUD (z mayor = más lejos en camera.ui) para no tapar textos.
            self.tinte = Entity(parent=self, model="quad", scale=(4.0, 2.0), z=2.0, color=color.rgba(0, 0, 0, 0), enabled=False)
            self.vineta = Entity(parent=self, model="quad", scale=(diseno_adaptable.aspecto() * 1.02, 1.02), z=1.9,
                                 texture=Texture(textura_vineta()), color=color.rgba(1, 1, 1, 0), enabled=False)
            self._tinte_actual = [0.0, 0.0, 0.0, 0.0]
            self._tinte_objetivo = (0.0, 0.0, 0.0, 0.0)
            self._vineta_actual, self._vineta_objetivo = 0.0, 0.0
            self.medidor = Medidor(parent=self)
            self.barra_desinfo = None
            if barra_desinfo_activa():
                try:
                    self.barra_desinfo = BarraDesinfo(parent=self.medidor)
                except Exception as error:
                    _aviso(f"barra de desinformación no instalada ({type(error).__name__}: {error})")
            self.cuerpos = {}                # tipo -> CuerpoEtapa (se crean la primera vez que hacen falta)
            self._visibles = []
            self.cambios = 0                 # cambios de etapa (pruebas)

        # -- Lectura --

        def _flujo(self):
            return getattr(escena, "flujo", None)

        def _terminada(self, flujo):
            try:
                return bool(flujo.partida_terminada())
            except Exception:
                return False

        def _leer(self):
            flujo = self._flujo()
            sesion = getattr(escena, "_sesion", None)
            if sesion is not self._sesion:                    # otra partida: se parte de la ciudad de siempre, sin aviso
                self._sesion = sesion
                self._cambiar(0, avisar=False)
            if flujo is None or self._terminada(flujo):
                return
            try:
                self.indice = etapas_final.indice_de_flujo(flujo)
            except Exception as error:
                self.indice = None
                _aviso(f"no se pudo leer el índice ({type(error).__name__}: {error})")
            if self.indice is None:                           # en línea: no hay etapas
                self._cambiar(0, avisar=False)
                return
            self._cambiar(etapas_final.etapa_de_indice(self.indice, self.etapa))

        def _cambiar(self, etapa, avisar=True):
            ambiente_vivo.fijar_etapa(etapa)
            if etapa == self.etapa:
                return
            self.etapa = etapa
            self.cambios += 1
            t = etapas_final.tinte(etapa)
            self._tinte_objetivo, self._vineta_objetivo = t["color"], t["vineta"]
            self._repartir_npc()
            try:
                from frontend import audio_enganches
                audio_enganches.fijar_perfil_mundo_etapa(etapa)
            except Exception as error:
                _aviso(f"audio de etapa no aplicado ({type(error).__name__}: {error})")
            if avisar:
                self._avisar(etapas_final.aviso_de_etapa(etapa))

        def _avisar(self, texto):
            if not texto:
                return
            try:
                conexion.vigia_reloj.control.cola.agregar(texto)
            except Exception:
                try:
                    escena.hud.mostrar_aviso(texto)
                except Exception:
                    pass

        def forzar_etapa(self, etapa):
            """Depuración y pruebas: fuerza el índice al centro de esa etapa y la aplica ya."""
            etapa = max(etapas_final.ETAPA_MIN, min(etapas_final.ETAPA_MAX, int(etapa)))
            etapas_final.fijar_indice_forzado(etapas_final.centro_de_etapa(etapa))
            self.indice = etapas_final.indice_forzado()
            self._cambiar(etapa)
            self._t = PERIODO_LECTURA

        def input(self, key):
            if key in ("f8", "f9") and etapas_final.depuracion():
                self.forzar_etapa(self.etapa + (1 if key == "f9" else -1))

        # -- Tinte --

        def _avanzar_tinte(self, dt):
            paso = min(1.0, dt / SEGUNDOS_TINTE)
            cambio = False
            for k in range(4):
                falta = self._tinte_objetivo[k] - self._tinte_actual[k]
                if abs(falta) > 1e-4:
                    # el color salta al del objetivo cuando el quad aún es invisible; el alfa siempre se funde
                    if k < 3 and self._tinte_actual[3] < 0.004:
                        self._tinte_actual[k] = self._tinte_objetivo[k]
                    else:
                        self._tinte_actual[k] += math.copysign(min(abs(falta), paso * max(0.25, abs(falta) * 4)), falta)
                    cambio = True
            falta = self._vineta_objetivo - self._vineta_actual
            if abs(falta) > 1e-4:
                self._vineta_actual += math.copysign(min(abs(falta), paso * 0.6), falta)
                cambio = True
            if cambio:
                r, g, b, a = self._tinte_actual
                self.tinte.color = color.rgba(r, g, b, a)
                self.tinte.enabled = a > 0.002
                self.vineta.color = color.rgba(1, 1, 1, self._vineta_actual)
                self.vineta.enabled = self._vineta_actual > 0.002

        # -- NPC --

        def _cuerpo(self, tipo):
            if tipo in self.cuerpos:
                return self.cuerpos[tipo]
            datos = textos.get("npc", {}).get(tipo)
            cuerpo = None
            if datos is not None and len(self.cuerpos) < MAX_NPC:
                try:
                    cuerpo = CuerpoEtapa(tipo, datos, len(self.cuerpos))
                except Exception as error:
                    _aviso(f"NPC «{tipo}» no creado ({type(error).__name__}: {error})")
            self.cuerpos[tipo] = cuerpo
            return cuerpo

        def _jugador(self):
            try:
                activo = self._flujo().jugador_activo()
                return float(activo.x), float(activo.z)
            except Exception:
                from ursina import camera
                return camera.world_x, camera.world_z

        def _punto_en_anillo(self, jx, jz):
            cerca, lejos = ANILLO_NPC_CRISIS if self.etapa <= -2 else ANILLO_NPC
            mundo = escena._mundo
            x = z = None
            for _ in range(14):
                a = self._azar.uniform(0, 2 * math.pi)
                r = self._azar.uniform(cerca, lejos)
                x, z = jx + r * math.cos(a), jz + r * math.sin(a)
                try:
                    if mundo.es_transitable(x, z):
                        return x, z
                except Exception:
                    return x, z
            return x, z                                       # sin punto libre a mano: se acepta el último

        def _repartir_npc(self):
            quieren = etapas_final.npc_de_etapa(self.etapa)
            visibles = []
            jx, jz = self._jugador()
            for tipo in quieren:
                cuerpo = self._cuerpo(tipo)
                if cuerpo is None:
                    continue
                if not cuerpo.npc.enabled:
                    cuerpo.colocar(*self._punto_en_anillo(jx, jz))
                    cuerpo.mostrar(True)
                visibles.append(cuerpo)
            for tipo, cuerpo in self.cuerpos.items():
                if cuerpo is not None and cuerpo not in visibles:
                    cuerpo.mostrar(False)
            self._visibles = visibles

        def _avanzar_npc(self, dt):
            if not self._visibles:
                return
            jx, jz = self._jugador()
            mundo = escena._mundo
            for cuerpo in self._visibles:
                d = math.hypot(cuerpo.x - jx, cuerpo.z - jz)
                if d > RADIO_LOD_NPC:
                    cuerpo.colocar(*self._punto_en_anillo(jx, jz))
                    continue
                npc = cuerpo.npc
                cerca = d <= RADIO_GLOBO
                if cerca != cuerpo.hablando:
                    cuerpo.hablar() if cerca else cuerpo.callar()
                if cerca:                                     # se para y mira al jugador mientras habla
                    npc.fijar_velocidad(0.0)
                    npc.mirar_hacia(math.degrees(math.atan2(jx - cuerpo.x, jz - cuerpo.z)))
                    continue
                cuerpo.t_giro -= dt
                if cuerpo.t_giro <= 0:
                    cuerpo.t_giro = cuerpo.azar.uniform(4, 9)
                    cuerpo.rumbo = (cuerpo.rumbo + cuerpo.azar.uniform(-110, 110)) % 360
                r = math.radians(cuerpo.rumbo)
                x, z = cuerpo.x + math.sin(r) * VELOCIDAD_NPC * dt, cuerpo.z + math.cos(r) * VELOCIDAD_NPC * dt
                libre = True
                try:
                    libre = bool(mundo.es_transitable(x + math.sin(r) * 0.6, z + math.cos(r) * 0.6))
                except Exception:
                    pass
                if not libre:
                    cuerpo.rumbo = (cuerpo.rumbo + 150 + cuerpo.azar.uniform(0, 60)) % 360
                    npc.fijar_velocidad(0.0)
                else:
                    cuerpo.colocar(x, z)
                    npc.fijar_velocidad(VELOCIDAD_NPC)
                npc.mirar_hacia(cuerpo.rumbo)

        # -- Medidor --

        def _medidor_visible(self):
            flujo = self._flujo()
            if flujo is None or self.indice is None or self._terminada(flujo):
                return False
            if getattr(escena, "_cinematica", False) or getattr(escena, "en_pausa", False):
                return False
            vigia = getattr(conexion, "vigia_reloj", None)
            motivo = getattr(getattr(vigia, "control", None), "motivo", None)
            if motivo == rc.PANEL:
                from frontend import registro_tutorial      # el tutorial señala el medidor: se queda a la vista
                return registro_tutorial.senalando_hud()
            return motivo not in (rc.PAUSA, rc.MAPA, rc.TERMINADA)

        def _pintar_desinfo(self):
            if self.barra_desinfo is None:
                return
            try:
                valor = escena._sesion.estado_partida.indicadores()["desinformacion"]
            except Exception:
                valor = None
            self.barra_desinfo.enabled = valor is not None
            if valor is not None:
                self.barra_desinfo.pintar(valor)

        # -- Frame --

        def update(self):
            self.avanzar(min(time.dt, 0.1))

        def avanzar(self, dt):
            self._t -= dt
            if self._t <= 0:
                self._t = PERIODO_LECTURA
                self._leer()
            self._avanzar_tinte(dt)
            self._avanzar_npc(dt)
            visible = self._medidor_visible()
            if visible:
                self.medidor.pintar(self.indice, self.etapa)
                self._pintar_desinfo()
            if self.medidor.enabled != visible:
                self.medidor.enabled = visible

        def estadisticas(self):
            return {"etapa": self.etapa, "indice": self.indice, "cambios": self.cambios,
                    "npc": [c.tipo for c in self._visibles], "tinte": tuple(round(v, 3) for v in self._tinte_actual),
                    "vineta": round(self._vineta_actual, 3), "medidor": self.medidor.enabled}

    return ControladorEtapas(parent=escena.hud)
