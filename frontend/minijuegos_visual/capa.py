# Capa común de efectos para TODOS los minijuegos de verificar (Ursina). Es una «mezcla» que se pone DELANTE de la vista de
# siempre en el MRO (frontend/minijuegos_visual.con_capa), así ninguna vista se reescribe:
#
#   - al construir: las tarjetas y botones entran en cascada con un pequeño rebote;
#   - con el foco: la tarjeta crece un poco; al elegir: se encoge y vuelve;
#   - al terminar: repasa la revisión de la vista (tarjetas CORRECTA / INCORRECTA...) con destellos, temblores y racha,
#     deja caer el sello «VERIFICADO» o «BULO» sobre el rumor y enseña de 0 a 3 estrellas y, la primera vez que se logra un
#     resultado perfecto en ese minijuego, una medalla (backend/logica/logros_minijuegos.py, archivo aparte y opcional).
#
# NO cambia el resultado: llama siempre a super() primero y solo lee. avanzar_visual(dt) lo llama la escena cada frame,
# también después de terminar (la escena deja de llamar a avanzar() cuando ya hay resultado).
#
# GUARDIÁN: cualquier fallo de la capa avisa una vez por stderr, devuelve las tarjetas a su sitio y apaga la capa; el
# minijuego sigue exactamente como el de siempre.

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as calc


class CapaVisual:

    _fx = None
    _capa_rota = False

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self._capa_rota:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("capa_minijuego", error)
            self._romper_capa()
            return None

    def _romper_capa(self):
        self._capa_rota = True
        if self._fx is not None:
            self._fx.apagar()

    # -- Ciclo de vida --

    def empezar(self, contexto):
        super().empezar(contexto)
        self._vigilar(self._montar_capa)

    def _montar_capa(self):
        from frontend.efectos_ui import EfectosUI
        self._fx = EfectosUI(parent=self)
        self._entrada_en_cascada(self._piezas_de_entrada())
        self._pintar_foco_visual()
        self.al_montar_visual()

    def al_montar_visual(self):
        """Gancho para las vistas propias: decorados extra una vez montada la capa."""

    def _piezas_de_entrada(self):
        piezas = list(self.focables)
        for nombre in ("filas", "tarjetas", "izq"):
            for pieza in getattr(self, nombre, None) or ():
                if pieza not in piezas:
                    piezas.append(pieza)
        return piezas

    def _entrada_en_cascada(self, piezas):
        if self._fx is None:
            return
        for pieza, retardo in zip(piezas, calc.retardos_escalonados(len(piezas))):
            self._fx.rebote(pieza, retardo)

    # -- Foco y elección --

    def _pintar_foco(self):
        super()._pintar_foco()
        if self._fx is not None:
            self._vigilar(self._pintar_foco_visual)

    def _pintar_foco_visual(self):
        for i, pieza in enumerate(self.focables):
            self._fx.foco(pieza, i == self.foco and not self.terminado)

    def activar_foco(self):
        pieza = self.focables[self.foco] if self.focables else None
        if pieza is not None and self._fx is not None:
            self._vigilar(self._fx.pulso, pieza)
        super().activar_foco()

    # -- Fin --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        self._vigilar(self._celebrar_final, resultado)

    def _celebrar_final(self, resultado):
        if self._fx is None:
            return
        for i, pieza in enumerate(self.focables):
            self._fx.foco(pieza, False)
        retardo = self.repasar_revision()
        texto = calc.texto_sello(getattr(self.mision, "es_verdadera", None))
        self._fx.sello(texto, posicion=self.posicion_sello(), retardo=retardo + 0.15)
        cantidad = calc.estrellas(resultado.fraccion, resultado.bien, resultado.completado)
        self._fx.estrellas(cantidad, posicion=self.posicion_estrellas(), retardo=retardo + 0.55)
        from backend.logica import logros_minijuegos
        perfecto = cantidad == 3
        anotado = logros_minijuegos.registrar(getattr(self.mision, "id", ""), resultado.minijuego, cantidad, perfecto)
        if anotado.get("medalla_nueva"):
            x, y = self.posicion_estrellas()
            self._fx.medalla("¡Medalla nueva: primer perfecto!", posicion=(x - 0.04, y), retardo=retardo + 1.0)

    def repasar_revision(self):
        """Destello / temblor sobre cada tarjeta de la revisión, en orden. Devuelve cuánto dura el repaso (s)."""
        tarjetas = [t for t in _tarjetas_de(self) if calc.veredicto_de_estado(t.estado) is not None]
        paso = 0.16
        for i, tarjeta in enumerate(tarjetas):
            veredicto = calc.veredicto_de_estado(tarjeta.estado)
            sonar = i < 6
            if veredicto == "acierto":
                self._fx.programar(i * paso, lambda t=tarjeta, s=sonar: self._fx.acierto(t, sonar=s))
            else:
                self._fx.programar(i * paso, lambda t=tarjeta, s=sonar: self._fx.error(t, sonar=s))
        return len(tarjetas) * paso

    def posicion_sello(self):
        return (0.45, 0.385)

    def posicion_estrellas(self):
        return (0.64, 0.335)

    # -- Bucle --

    def avanzar_visual(self, dt):
        """Lo llama la escena cada frame (también tras terminar). Nunca lanza."""
        if self._fx is not None and not self._capa_rota:
            self._vigilar(self._fx.sincronizar, dt)
            self._vigilar(self.avanzar_visual_propio, dt)

    def avanzar_visual_propio(self, dt):
        """Gancho para las vistas propias (animaciones que siguen tras terminar)."""


def _tarjetas_de(raiz):
    """Tarjetas (frontend/minijuegos/ui.Tarjeta) activas bajo `raiz`, en orden de creación."""
    from frontend.minijuegos.ui import Tarjeta
    salida = []
    pila = list(reversed(raiz.children))
    while pila:
        nodo = pila.pop()
        if isinstance(nodo, Tarjeta):
            if nodo.enabled and not nodo.is_empty():
                salida.append(nodo)
            continue
        pila.extend(reversed(getattr(nodo, "children", []) or []))
    return salida
