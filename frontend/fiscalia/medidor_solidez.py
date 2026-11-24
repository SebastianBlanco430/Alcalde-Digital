# Medidor «Solidez del caso NN %» del caso de Fiscalía v2 (Ursina, en camera.ui), arriba al centro (y >= 0,40) y siempre
# visible durante el caso. Barra con marcas en los umbrales del caso (Indicios, Suficiente, Sólido...). Cuando la solidez
# cambia, la barra va del valor viejo al nuevo y al lado aparece «▲ +8 %» o «▼ −6 %» (el triángulo es una malla: la fuente
# no lo trae), que sube un poco y se va. Las pruebas nuevas salen en una ficha arriba a la derecha («Prueba nueva: …»):
# al instante y, si llegan varias seguidas, juntas en la misma ficha (ui_calculos.FichaPruebas; pendientes-a, P3).
# Reducir movimiento: la barra salta al valor nuevo y el «▲ +8 %» aparece y se va sin desplazarse.

import time

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, modelo_redondeado, panel_tinta, rgb
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import ajustar, ancho_real, triangulo

POS = (0.0, 0.452)
ANCHO, ALTO = 0.98, 0.078
X_TITULO = -ANCHO / 2 + 0.025
X_BARRA, ANCHO_BARRA, ALTO_BARRA = -0.06, 0.51, 0.02
Y_BARRA, Y_MARCAS = 0.012, -0.020           # relativas al centro del panel
POS_DELTA = (ANCHO / 2 + 0.035, -0.012)
POS_PRUEBA = (uc.CENTRO_FICHA_PRUEBA[0] - POS[0], uc.CENTRO_FICHA_PRUEBA[1] - POS[1])     # relativa al medidor
VERDE, ROJO = (88, 214, 141), (235, 87, 87)


class MedidorSolidez(Entity):

    def __init__(self, umbrales=None, **opciones):
        super().__init__(position=(*POS, 0), **opciones)
        self.umbrales = dict(umbrales or {})
        self.panel = panel_tinta(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL)
        self.titulo = Text("", parent=self, origin=(-0.5, 0), position=(X_TITULO, 0.0, -0.01),
                           scale=escala_fuente(uc.TAM["medidor"]), font=tipografia.FUENTE_TITULO,
                           color=rgb(estilo.COLOR_TEXTO))
        self.fondo_barra = Entity(parent=self, model=modelo_redondeado(ANCHO_BARRA, ALTO_BARRA, 4),
                                  position=(X_BARRA + ANCHO_BARRA / 2, Y_BARRA, -0.004), scale=(ANCHO_BARRA, ALTO_BARRA),
                                  color=rgb(estilo.COLOR_BARRA_FONDO))
        self.relleno = Entity(parent=self, model="quad", position=(X_BARRA, Y_BARRA, -0.006),
                              scale=(0.001, ALTO_BARRA), color=rgb(estilo.ESTADO_AVISO))
        self.marcas = []
        ultimo_borde = -1e9
        for x, nombre, valor in uc.marcas_umbrales(self.umbrales, ANCHO_BARRA):
            Entity(parent=self, model="quad", position=(X_BARRA + x, Y_BARRA, -0.008),
                   scale=(0.004, ALTO_BARRA + 0.014), color=rgb(estilo.PAPEL))
            etiqueta = Text(nombre, parent=self, origin=(0, 0), position=(X_BARRA + x, Y_MARCAS, -0.01),
                            scale=escala_fuente(uc.TAM["marca"]) * uc.escala_min(uc.TAM["marca"]),
                            color=rgb(estilo.COLOR_TEXTO_TENUE))
            medio = ancho_real(etiqueta) / 2
            if X_BARRA + x - medio < ultimo_borde + 0.01:
                etiqueta.enabled = False          # umbrales muy juntos: queda la marca, sin rótulo
            else:
                ultimo_borde = X_BARRA + x + medio
            self.marcas.append(etiqueta)
        # «▲ +8 %»
        self.delta = Entity(parent=self, position=(*POS_DELTA, -0.02), enabled=False)
        self.flecha_sube = triangulo(self.delta, (0.026, 0.022), True, VERDE, position=(0.0, 0.0))
        self.flecha_baja = triangulo(self.delta, (0.026, 0.022), False, ROJO, position=(0.0, 0.0))
        self.delta_txt = Text("", parent=self.delta, origin=(-0.5, 0), position=(0.022, 0.0, 0),
                              scale=escala_fuente(uc.TAM["delta"]), font=tipografia.FUENTE_TITULO)
        # Ficha de prueba nueva (un panel de una línea y otro de dos; el texto va encima del que toque)
        self.prueba = Entity(parent=self, position=(*POS_PRUEBA, -0.02), enabled=False)
        self._paneles_prueba = {n: panel_tinta(self.prueba, uc.ANCHO_FICHA_PRUEBA, alto, tono=estilo.COLOR_TARJETA)
                                for n, alto in uc.ALTO_FICHA_PRUEBA.items()}
        self.prueba_txt = Text("", parent=self.prueba, origin=(0, 0), z=-0.01, scale=escala_fuente(uc.TAM["prueba"]),
                               font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self._ficha = uc.FichaPruebas()
        self._texto_prueba = None
        self.valor = 0
        self._mostrado = 0.0
        self._desde = 0.0
        self._t_relleno = 9.0
        self._t_delta = None
        self.fijar(0)

    # -- API --

    def fijar(self, valor):
        self.valor = int(max(0, min(100, round(valor))))
        self._mostrado = self._desde = float(self.valor)
        self._t_relleno = 9.0
        self._pintar(self._mostrado)

    def cambiar(self, valor, delta, reducir=False):
        self._desde = self._mostrado
        self.valor = int(max(0, min(100, round(valor))))
        self._t_relleno = 0.0
        if delta:
            sube = delta > 0
            self.flecha_sube.enabled = sube
            self.flecha_baja.enabled = not sube
            self.delta_txt.text = uc.formatear_delta(delta)
            self.delta_txt.color = rgb(VERDE if sube else ROJO)
            self._t_delta = 0.0
            self.delta.enabled = True
        if reducir:
            self._mostrado = float(self.valor)
            self._pintar(self._mostrado)

    def prueba_nueva(self, nombre):
        self._ficha.agregar(nombre, time.monotonic())        # reloj real: solo agrupa las que llegan seguidas (S5)
        self._pintar_prueba()

    # -- Frame --

    def avanzar(self, dt, reducir=False):
        if self._t_relleno < uc.DUR_RELLENO:
            self._t_relleno += dt
            self._mostrado = uc.relleno(self._desde, self.valor, self._t_relleno, reducir=reducir)
            self._pintar(self._mostrado)
        if self._t_delta is not None:
            self._t_delta += dt
            alfa, dy = uc.anim_delta(self._t_delta, reducir=reducir)
            if self._t_delta >= uc.DUR_DELTA:
                self._t_delta = None
                self.delta.enabled = False
            else:
                self.delta.y = POS_DELTA[1] + dy
                self.delta_txt.alpha = alfa
                self.flecha_sube.alpha = alfa
                self.flecha_baja.alpha = alfa
        if self._ficha.visible:
            self._ficha.avanzar(dt)
            self._pintar_prueba()

    def _pintar_prueba(self):
        if not self._ficha.visible:
            self.prueba.enabled = False
            self._texto_prueba = None
            return
        self.prueba.enabled = True
        texto = self._ficha.texto()
        if texto != self._texto_prueba:            # rehacer el texto solo cuando cambia
            self._texto_prueba = texto
            plan = ajustar(self.prueba_txt, texto, uc.ANCHO_FICHA_PRUEBA - 0.04, uc.TAM["prueba"], max_lineas=2)
            lineas = len(plan["lineas"]) if isinstance(plan, dict) and plan.get("lineas") else 1
            for n, panel in self._paneles_prueba.items():
                panel.enabled = n == (2 if lineas > 1 else 1)
        self.prueba_txt.alpha = self._ficha.alfa()

    def _pintar(self, valor):
        v = max(0.0, min(100.0, valor))
        self.titulo.text = uc.texto_solidez(v)
        ancho = max(0.001, ANCHO_BARRA * v / 100.0)
        self.relleno.scale_x = ancho
        self.relleno.x = X_BARRA + ancho / 2
        self.relleno.enabled = v > 0
        self.relleno.color = rgb(uc.tono_solidez(v, self.umbrales))
