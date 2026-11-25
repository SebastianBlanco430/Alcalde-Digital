# Pantalla de carga del arranque (M7.3): título, barra con el progreso REAL y una línea de estado en camera.ui.
#
# Mientras main.crear_aplicacion construye las escenas Python no suelta el hilo y Ursina no dibuja: la ventana se
# quedaba negra ~28 s. Los constructores llaman a `avance(etapa, fraccion)` entre sus pasos; aquí se actualiza la barra
# y, como mucho cada INTERVALO_DIBUJO s, se fuerza UN cuadro con graphicsEngine.renderFrame() + flipFrame() (el flip
# lleva el búfer trasero a la ventana ya, sin esperar al cuadro siguiente). renderFrame no corre el taskMgr: no hay
# update() de entidades, ni input, ni lógica de juego. Durante ese cuadro la cámara 3D está desactivada (la ciudad a
# medio construir ni se recorre ni se sube a la GPU antes de tiempo) y se deja después tal como estaba.
# Depurar: ALCALDE_CARGA_TRAZA=1 imprime el instante de cada etapa y lo que cuesta cada cuadro.
#
# Sin pantalla activa (tests, scripts que no llaman a iniciar, bandera apagada) `avance` no hace nada.
# Cálculo del progreso, pesos y recalibrado: frontend/pantalla_carga_calculos.py.
# BANDERA: ALCALDE_PANTALLA_CARGA=0 -> no se crea nada ni se dibuja ningún cuadro extra (el arranque de antes).
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW, =0 o Ajustes › Estilo la apagan): fondo violeta, título en cursiva y barra
# amarilla del menú de inicio.

import os
import sys
import time

from frontend import pantalla_carga_calculos as calc

ganchos_dibujo = []       # callables(pantalla) tras cada cuadro dibujado (scripts de captura/depuración)
_pantalla = None
_avisado = False
_TRAZA = os.environ.get("ALCALDE_CARGA_TRAZA", "") == "1"


def activa():
    return _pantalla is not None


def iniciar():
    """Crea la pantalla y dibuja el primer cuadro. None si la bandera la apaga o algo falla (se arranca sin ella)."""
    global _pantalla
    if _pantalla is not None:
        return _pantalla
    if not calc.pantalla_carga_activa():
        return None
    try:
        pesos = calc.pesos_recalibrados(calc.leer_tiempos(calc.ruta_tiempos()))
        _pantalla = PantallaCarga(calc.ProgresoCarga(pesos))
        _pantalla.dibujar()
    except Exception as error:      # noqa: BLE001  la pantalla de carga nunca impide arrancar
        _fallo(error)
    return _pantalla


def avance(etapa, fraccion=None):
    """Punto de control: `etapa` (nombre de pantalla_carga_calculos.ETAPAS) con `fraccion` 0..1 hecha."""
    if _pantalla is None:
        return
    try:
        _pantalla.avance(etapa, fraccion)
    except Exception as error:      # noqa: BLE001
        _fallo(error)


def terminar():
    """Destruye la pantalla y guarda los tiempos de cada etapa para recalibrar la próxima carga."""
    global _pantalla
    pantalla, _pantalla = _pantalla, None
    if pantalla is None:
        return
    try:
        pantalla.cerrar()
    except Exception as error:      # noqa: BLE001
        _avisar(error)


def _fallo(error):
    global _pantalla
    _avisar(error)
    pantalla, _pantalla = _pantalla, None
    if pantalla is not None:
        try:
            pantalla.destruir()
        except Exception:           # noqa: BLE001
            pass


def _avisar(error):
    global _avisado
    if not _avisado:
        _avisado = True
        print(f"[Carga] pantalla de carga desactivada: {error!r}", file=sys.stderr)


class PantallaCarga:

    ANCHO_BARRA = 0.9
    ALTO_BARRA = 0.022

    def __init__(self, progreso):
        from ursina import Entity, Text, camera
        from frontend import estilo, tipografia, ui_botw_calculos
        from frontend.componentes import escala_fuente, rgb
        tono = ui_botw_calculos.tono

        self.progreso = progreso
        self._limitador = calc.Limitador()
        self._t0 = time.perf_counter()
        self.cuadros = 0
        self._ultima_traza = None
        self.segundos_dibujando = 0.0
        # Delante de cualquier otra UI que se cree mientras tanto (z menor = más cerca en camera.ui).
        self.raiz = Entity(parent=camera.ui, z=-0.9, add_to_scene_entities=False)
        Entity(parent=self.raiz, model="quad", scale=(8, 2), z=0.02, color=rgb(tono(estilo.COLOR_FONDO)),
               add_to_scene_entities=False)
        try:
            self.titulo = Text("Alcalde Digital", font=tipografia.fuente_piel(titulo=True), parent=self.raiz, origin=(0, 0),
                               y=0.09, scale=escala_fuente(54), color=rgb(estilo.COLOR_TEXTO),
                               add_to_scene_entities=False)
        except Exception:           # noqa: BLE001  sin la fuente de títulos, la de texto
            self.titulo = Text("Alcalde Digital", parent=self.raiz, origin=(0, 0), y=0.09, scale=escala_fuente(54),
                               color=rgb(estilo.COLOR_TEXTO), add_to_scene_entities=False)
        y_barra = -0.03
        Entity(parent=self.raiz, model="quad", scale=(self.ANCHO_BARRA, self.ALTO_BARRA), y=y_barra, z=0.01,
               color=rgb(tono(estilo.COLOR_BARRA_FONDO)), add_to_scene_entities=False)
        self.relleno = Entity(parent=self.raiz, model="quad", origin=(-0.5, 0), x=-self.ANCHO_BARRA / 2, y=y_barra,
                              scale=(0.001, self.ALTO_BARRA), color=rgb(tono(estilo.COLOR_ACENTO)),
                              add_to_scene_entities=False)
        self.estado = Text(progreso.texto, parent=self.raiz, origin=(-0.5, 0), x=-self.ANCHO_BARRA / 2,
                           y=y_barra - 0.045, z=-0.01, scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO_TENUE),
                           add_to_scene_entities=False)
        self.porcentaje = Text("0 %", parent=self.raiz, origin=(0.5, 0), x=self.ANCHO_BARRA / 2, y=y_barra - 0.045,
                               z=-0.01, scale=escala_fuente(20), color=rgb(estilo.COLOR_TEXTO_TENUE),
                               add_to_scene_entities=False)

    def avance(self, etapa, fraccion=None):
        self.progreso.avance(etapa, fraccion)
        if _TRAZA and etapa != self._ultima_traza:     # ALCALDE_CARGA_TRAZA=1: instante de cada etapa (medir pesos)
            self._ultima_traza = etapa
            print(f"[Carga] {time.perf_counter() - self._t0:7.3f} s  {etapa} {fraccion}", flush=True)
        if self._limitador.toca(time.perf_counter()):
            self.dibujar()

    def _refrescar(self):
        valor = self.progreso.progreso
        self.relleno.scale_x = max(0.001, self.ANCHO_BARRA * valor)
        if self.estado.text != self.progreso.texto:
            self.estado.text = self.progreso.texto
        self.porcentaje.text = f"{int(valor * 100)} %"

    # Un cuadro YA en la ventana, solo con la UI: renderFrame dibuja en el búfer trasero y flipFrame lo presenta.
    # La cámara 3D se desactiva durante ese cuadro: ni se recorre `scene` (calcular los volúmenes de la ciudad a medio
    # construir costaba hasta 80 ms por cuadro, y en parte se tiraba al combinar) ni se sube nada a la GPU.
    def dibujar(self):
        from ursina import application
        t = time.perf_counter()
        self._limitador.toca(t, forzar=True)
        self._refrescar()
        self._ajustar_lente_ui()
        t_ref = time.perf_counter()
        motor = application.base.graphicsEngine
        camara = application.base.camNode
        activa = camara.is_active()
        camara.set_active(False)
        try:
            motor.renderFrame()
            t_render = time.perf_counter()
            motor.flipFrame()
        finally:
            camara.set_active(activa)
        if _TRAZA:
            print(f"[Carga] cuadro {self.cuadros} ({self.progreso.etapa}, {motor.getNumWindows()} búferes): "
                  f"{1000 * (t_ref - t):.1f} ms barra + {1000 * (t_render - t_ref):.1f} ms render + "
                  f"{1000 * (time.perf_counter() - t_render):.1f} ms flip", flush=True)
        self.cuadros += 1
        self.segundos_dibujando += time.perf_counter() - t
        for gancho in list(ganchos_dibujo):
            gancho(self)

    # La lente de camera.ui nace con película 1x1 y Ursina la ajusta al aspecto de la ventana en el primer evento de
    # ventana, que lo procesa el taskMgr (aún no ha corrido): sin esto la UI sale 20 veces más grande. Se pone el mismo
    # valor que pondrá window.update_aspect_ratio (sin tocar nada más: ni prev_size ni la x de la UI).
    @staticmethod
    def _ajustar_lente_ui():
        from ursina import application, camera
        ancho, alto = application.base.win.getSize()
        if ancho > 0 and alto > 0:
            mitad = camera._ui_size * .5
            camera.ui_lens.set_film_size(mitad * ancho / alto, mitad)

    def cerrar(self):
        self.progreso.terminar()
        total = time.perf_counter() - self._t0
        try:
            calc.guardar_tiempos(calc.ruta_tiempos(), self.progreso.tiempos())
        finally:
            self.destruir()
        print(f"[Carga] {total:.1f} s; {self.cuadros} cuadros de la pantalla de carga "
              f"({self.segundos_dibujando:.2f} s dibujándolos)", flush=True)

    def destruir(self):
        from frontend.componentes import destruir_arbol
        if self.raiz is not None:
            destruir_arbol(self.raiz)
            self.raiz = None
