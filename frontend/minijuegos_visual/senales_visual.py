# «Señales de edición» visual (Ursina): el mismo minijuego (frontend/minijuegos/senales.py, lógica senales_calculos) con
#   - una LUPA de detective que flota sobre la zona con el foco y AMPLÍA de verdad su texto (letra mucho mayor, centrada en
#     el detalle con números si lo hay: horas, cifras...). La lupa de texto de la derecha sigue igual;
#   - marcar es dibujar un CÍRCULO ROJO de rotulador alrededor de la zona, con animación de trazo;
#   - momento estrella: al confirmar, la captura se «despega» como una pegatina (se levanta, gira y se va) y deja ver
#     debajo lo que había de verdad (la revisión de cada zona), con un golpe de glitch (mundo_digital_glitch).
# No cambia la partida ni el resultado. APAGADO: ALCALDE_SENALES_VISUAL=0. GUARDIÁN: un fallo quita lo añadido.
# REDUCIR MOVIMIENTO: el círculo aparece entero, la pegatina se desvanece sin girar y no hay glitch.

import re

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.senales import ANCHO_TEL, MARCO_TEL, MinijuegoSenales
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual
from frontend.minijuegos_visual.trazos import Linea

SENALES_VISUAL = True
VARIABLE = "ALCALDE_SENALES_VISUAL"

ROJO = (225, 45, 45)
DIAMETRO_LUPA = 0.2
PX_LUPA = 24
DUR_PEGATINA = 0.9


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def fragmento_lupa(texto):
    """Trozo del texto que enseña la lupa: desde la palabra anterior al primer detalle con números (hora, cifra) o desde
    el principio. Se parte por palabras al ancho de la lente en la vista."""
    palabras = str(texto or "").split()
    indice = next((i for i, p in enumerate(palabras) if re.search(r"\d", p)), 0)
    return " ".join(palabras[max(0, indice - 1):])


class SenalesVisual(CapaVisual, MinijuegoSenales):

    _lupa_rota = False

    def construir(self):
        self._listo = False
        super().construir()
        try:
            self._montar_lupa()
            self._listo = True
            self._colocar_lupa(inmediato=True)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("senales_visual", error)
            self._quitar_lupa()

    def _montar_lupa(self):
        self.lente = Entity(parent=self, z=-0.12)
        Entity(parent=self.lente, model="circle", scale=DIAMETRO_LUPA + 0.014, color=_rgba((70, 50, 30)), z=0.002)
        Entity(parent=self.lente, model="circle", scale=DIAMETRO_LUPA, color=_rgba((235, 238, 245), 0.96), z=0.001)
        self.mango = Entity(parent=self.lente, model="quad", scale=(0.022, 0.11), rotation_z=-40, color=_rgba((70, 50, 30)),
                            position=(DIAMETRO_LUPA * 0.42, -DIAMETRO_LUPA * 0.5, 0.003))
        self.lente_txt = Text("", parent=self.lente, origin=(0, 0), z=-0.001, scale=escala_fuente(PX_LUPA),
                              font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA))
        self.circulos = {}            # i -> Linea
        self._t_circulo = {}
        self._t_pegatina = None
        self._glitch = None

    def _quitar_lupa(self):
        self._lupa_rota = True
        self._listo = False
        for nombre in ("lente", "pegatina"):
            e = getattr(self, nombre, None)
            if e is not None:
                e.enabled = False
        for linea in getattr(self, "circulos", {}).values():
            linea.enabled = False

    # -- Lupa que sigue al foco --

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
        self._destino_lupa = (tarjeta.x + tarjeta.ancho / 2 - DIAMETRO_LUPA * 0.45, tarjeta.y)
        if inmediato or bv.reducir_movimiento():
            self.lente.x, self.lente.y = self._destino_lupa
        lineas = ui.lineas_de(fragmento_lupa(self.partida.zonas[self.foco]["texto"]), PX_LUPA, DIAMETRO_LUPA * 0.8, True)
        self.lente_txt.text = "\n".join(lineas[:3])

    # -- Círculo de rotulador al marcar --

    def alternar(self, i):
        super().alternar(i)
        if getattr(self, "_listo", False) and not self._lupa_rota:
            self._vigilar(self._circulo, i)

    def _circulo(self, i):
        if i in self.partida.marcadas:
            linea = self.circulos.get(i)
            if linea is None:
                linea = Linea(ROJO, 4, parent=self, z=-0.08)
                self.circulos[i] = linea
            tarjeta = self.tarjetas[i]
            linea.position = (tarjeta.x, tarjeta.y, -0.08)
            linea.enabled = True
            self._t_circulo[i] = 0.0
            self._pintar_circulo(i)
        elif i in self.circulos:
            self.circulos[i].enabled = False
            self._t_circulo.pop(i, None)

    def _pintar_circulo(self, i):
        tarjeta = self.tarjetas[i]
        puntos = calc.circulo_rotulador(tarjeta.ancho / 2 + 0.012, tarjeta.alto / 2 + 0.012, semilla=i)
        avance = calc.avance_trazo(self._t_circulo.get(i, 1.0), reducir=bv.reducir_movimiento())
        self.circulos[i].fijar(calc.parcial(puntos, avance))

    # -- Momento estrella: la captura se despega --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if getattr(self, "_listo", False) and not self._lupa_rota:
            self._vigilar(self._despegar)

    def _despegar(self):
        self.lente.enabled = False
        arriba = max(t.y + t.alto / 2 for t in self.tarjetas)
        abajo = min(t.y - t.alto / 2 for t in self.tarjetas)
        alto = arriba - abajo + 0.05
        self.pegatina = Entity(parent=self, position=(self.x_tel, (arriba + abajo) / 2, -0.14))
        ui.rect(self.pegatina, ANCHO_TEL + MARCO_TEL, alto, estilo.COLOR_TARJETA, (0, 0), z=0.002, radio_px=14)
        ui.rect(self.pegatina, ANCHO_TEL + MARCO_TEL - 0.02, alto - 0.02, (52, 56, 72), (0, 0), z=0.001, radio_px=12)
        Text("CAPTURA EDITADA", parent=self.pegatina, origin=(0, 0), z=-0.001, scale=escala_fuente(30),
             font=tipografia.FUENTE_TITULO, color=_rgba(ROJO), rotation_z=-8)
        self._t_pegatina = 0.0
        if not bv.reducir_movimiento():
            try:
                from frontend.mundo_digital_glitch import GlitchOverlay
                self._glitch = GlitchOverlay()
                self._glitch.poner(0.8)
                self._glitch.desvanecer(0.5)
            except Exception as error:  # noqa: BLE001  sin glitch la pegatina se despega igual
                bv.avisar_una_vez("senales_glitch", error)
                self._glitch = None

    def on_destroy(self):
        glitch = getattr(self, "_glitch", None)
        if glitch is not None:
            try:
                glitch.cancelar()
                from ursina import destroy
                destroy(glitch)
            except Exception:            # noqa: BLE001
                pass
            self._glitch = None

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not getattr(self, "_listo", False) or self._lupa_rota:
            return
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        if self.lente.enabled and getattr(self, "_destino_lupa", None) is not None and not reducir:
            dx, dy = self._destino_lupa
            self.lente.x = fx_calc.acercar(self.lente.x, dx, dt, 0.07)
            self.lente.y = fx_calc.acercar(self.lente.y, dy, dt, 0.07)
        for i in list(self._t_circulo):
            self._t_circulo[i] += dt
            self._pintar_circulo(i)
            if self._t_circulo[i] > 0.4:
                del self._t_circulo[i]
        if self._t_pegatina is not None:
            self._t_pegatina += dt
            k = max(0.0, min(1.0, (self._t_pegatina - 0.35) / DUR_PEGATINA))
            suave = k * k
            if reducir:
                self.pegatina.alpha = 1 - k
                for hijo in self.pegatina.children:
                    hijo.alpha = 1 - k
            else:
                self.pegatina.rotation_z = -35 * suave
                self.pegatina.x = self.x_tel + 0.5 * suave
                self.pegatina.scale = 1.0 - 0.45 * suave
            if k >= 1.0:
                self.pegatina.enabled = False
                self._t_pegatina = None
                if self._glitch is not None:
                    self._glitch.cancelar()
