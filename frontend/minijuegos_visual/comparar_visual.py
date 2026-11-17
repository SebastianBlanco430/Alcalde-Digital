# «Comparar dos versiones» visual (Ursina): el mismo minijuego (frontend/minijuegos/comparar.py, lógica comparar_calculos)
# sobre una MESA DE LUZ:
#   - las dos hojas (original y copia) descansan sobre una mesa iluminada;
#   - la línea con el foco se SUPERPONE: la copia se dibuja translúcida en rojo encima del original, con la misma letra y
#     el mismo ancho. Donde el texto coincide, las letras se funden; donde cambia, se ven dobles y desfasadas. No es una
#     pista añadida: es lo que verías al poner una hoja encima de la otra (hay que seguir leyendo para decidir);
#   - marcar una línea es pasarle un rotulador FOSFORITO (la barra amarilla crece de izquierda a derecha);
#   - momento estrella: al confirmar, la palabra alterada salta grande en el centro («R$ 5  →  R$ 50»).
# No cambia la partida ni el resultado. APAGADO: ALCALDE_COMPARAR_VISUAL=0. GUARDIÁN: un fallo quita lo añadido.

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.comparar import MinijuegoComparar
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual

COMPARAR_VISUAL = True
VARIABLE = "ALCALDE_COMPARAR_VISUAL"

LUZ = (236, 238, 214)
FOSFORITO = (255, 236, 60)
ROJO_FANTASMA = (255, 70, 90)
DUR_FOSFORITO = 0.25
DUR_SALTO = 3.2


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class CompararVisual(CapaVisual, MinijuegoComparar):

    _mesa_rota = False

    def construir(self):
        self._listo = False
        super().construir()
        try:
            self._montar_mesa()
            self._listo = True
            self._pintar_fantasma()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("comparar_visual", error)
            self._quitar_mesa()

    def _montar_mesa(self):
        arriba = Y_CONTENIDO_ARRIBA + 0.012
        abajo = min(t.y - t.alto / 2 for t in self.tarjetas) - 0.015
        self.mesa = Entity(parent=self)
        ui.rect(self.mesa, ANCHO_UTIL + 0.05, arriba - abajo + 0.05, (60, 64, 52), (0, (arriba + abajo) / 2 - 0.02), z=0.3,
                radio_px=12)
        ui.rect(self.mesa, ANCHO_UTIL + 0.03, arriba - abajo + 0.03, LUZ, (0, (arriba + abajo) / 2 - 0.02), z=0.29,
                radio_px=10)
        # Rejilla tenue de la mesa de luz.
        for k in range(1, 8):
            x = -ANCHO_UTIL / 2 + k * ANCHO_UTIL / 8
            Entity(parent=self.mesa, model="quad", color=_rgba((200, 202, 180)), scale=(0.002, arriba - abajo),
                   position=(x, (arriba + abajo) / 2 - 0.02, 0.28))
        self.fantasma = Text("", parent=self, origin=(-0.5, 0.5), color=_rgba(ROJO_FANTASMA, 0.62), enabled=False)
        self.fosforitos = {}
        self._t_fosforito = {}
        self._t_salto = None

    def _quitar_mesa(self):
        self._mesa_rota = True
        self._listo = False
        for nombre in ("mesa", "fantasma", "salto"):
            e = getattr(self, nombre, None)
            if e is not None:
                e.enabled = False
        for barra in getattr(self, "fosforitos", {}).values():
            barra.enabled = False

    # -- La copia superpuesta sobre el original --

    def _pintar_foco(self):
        super()._pintar_foco()
        if getattr(self, "_listo", False) and not self._mesa_rota:
            self._vigilar(self._pintar_fantasma)

    def _pintar_fantasma(self):
        if self.terminado or not self.focables or self.foco >= len(self.tarjetas):
            self.fantasma.enabled = False
            return
        i = self.foco
        original = self.izq[i]
        linea = self.partida.lineas[i]
        cuerpo = original.cuerpo
        px = max(10, round(cuerpo.scale_x / escala_fuente(1)))
        ancho = original.ancho - 2 * a_unidades(7)
        texto = f"{linea['etiqueta']}: {linea['copia']}"
        self.fantasma.text = "\n".join(ui.lineas_de(texto, px, ancho))
        self.fantasma.scale = cuerpo.scale
        self.fantasma.line_height = cuerpo.line_height
        self.fantasma.position = (original.x + cuerpo.x, original.y + cuerpo.y, -0.06)
        self.fantasma.enabled = True

    # -- Fosforito al marcar --

    def alternar(self, i):
        super().alternar(i)
        if getattr(self, "_listo", False) and not self._mesa_rota:
            self._vigilar(self._fosforito, i)

    def _fosforito(self, i):
        tarjeta = self.tarjetas[i]
        if i in self.partida.marcadas:
            barra = self.fosforitos.get(i)
            if barra is None:
                barra = Entity(parent=tarjeta, model="quad", origin=(-0.5, 0), color=_rgba(FOSFORITO, 0.38),
                               position=(-tarjeta.ancho / 2 + 0.01, 0, -0.012))
                self.fosforitos[i] = barra
            barra.scale = (0.0001, tarjeta.alto * 0.7)
            barra.enabled = True
            self._t_fosforito[i] = 0.0 if not bv.reducir_movimiento() else DUR_FOSFORITO
        elif i in self.fosforitos:
            self.fosforitos[i].enabled = False
            self._t_fosforito.pop(i, None)

    # -- Momento estrella --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if getattr(self, "_listo", False) and not self._mesa_rota:
            self._vigilar(self._salto_palabra)

    def _salto_palabra(self):
        self.fantasma.enabled = False
        alteradas = sorted(self.partida.alteradas())
        if not alteradas:
            return
        linea = self.partida.lineas[alteradas[0]]
        rotulo = calc.texto_salto(linea["original"], linea["copia"])
        if rotulo is None:
            return
        self.salto = Entity(parent=self, position=(0, 0.02, -0.15))
        ui.rect(self.salto, 1.16, 0.15, estilo.TINTA, (0, 0), z=0.002, radio_px=12)
        ui.rect(self.salto, 1.14, 0.13, estilo.COLOR_PANEL, (0, 0), z=0.001, radio_px=10)
        Text(f"Lo que cambiaron en «{calc.recortar(linea['etiqueta'], 30)}»", parent=self.salto, origin=(0, 0),
             position=(0, 0.04, -0.001), scale=escala_fuente(14), color=_rgba(estilo.COLOR_TEXTO_TENUE))
        self.salto_txt = Text(rotulo, parent=self.salto, origin=(0, 0), position=(0, -0.015, -0.001), scale=escala_fuente(32),
                              font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_ACENTO))
        self._t_salto = 0.0

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not getattr(self, "_listo", False) or self._mesa_rota:
            return
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        for i in list(self._t_fosforito):
            self._t_fosforito[i] += dt
            k = min(1.0, self._t_fosforito[i] / DUR_FOSFORITO)
            tarjeta = self.tarjetas[i]
            self.fosforitos[i].scale_x = max(0.0001, (tarjeta.ancho - 0.02) * k)
            if k >= 1.0:
                del self._t_fosforito[i]
        if self._t_salto is not None:
            self._t_salto += dt
            t = self._t_salto
            self.salto_txt.scale = escala_fuente(32) * fx_calc.rebote(t, desde=0.3, reducir=reducir)
            if t > DUR_SALTO:
                self.salto.enabled = False
                self._t_salto = None
