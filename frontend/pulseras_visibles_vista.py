# Mini-pulseras del HUD (M5.1, ALCALDE_PULSERAS_VISIBLES): las 2 cintas del brazalete en pequeño, sin texto, pegadas a la
# derecha del chip del reloj (misma fila de la pila de abajo a la izquierda). Usan la MISMA textura que el brazalete
# (color, tejido, nudos y desgaste: los 4 canales). Al cambiar de nivel una cinta late y enseña 30 s una flecha
# (arriba verde = mejor, abajo roja = peor). El brazalete grande (M3.2) y la tecla B siguen igual.
#
# La lógica pura está en frontend/pulseras_visibles_calculos.py y las medidas en frontend/hud_esquinas_calculos.py; aquí
# solo se dibuja. La crea registro_manillas._crear_vigia y la mueve ControlManillas.avanzar (pintar_minis).

from frontend import hud_esquinas_calculos as hec
from frontend import manillas_calculos as mcal
from frontend import pulseras_visibles_calculos as pv


def crear(escena, textura, chip_reloj):
    """`textura(clave)` -> Texture de la cinta (la caché del brazalete). `chip_reloj()` -> Entity del chip del reloj o
    None (las minis se pegan a él cada frame: siguen su anclaje y su puesto en la pila)."""
    from ursina import Circle, Entity, color

    from backend.logica import ajustes as modelo_ajustes
    from frontend import diseno_adaptable, estilo
    from frontend.componentes import panel_piel, rgb

    indicadores = mcal.INDICADORES_HUD[:2]
    ancho = hec.ancho_mini_pulseras(len(indicadores))

    def triangulo():
        """Una malla NUEVA por entidad: un Mesh es un NodePath y asignarlo a otra entidad lo arranca de la anterior."""
        return Circle(resolution=3)                      # vértice arriba

    class Mini:

        def __init__(self, padre, indicador, x_cinta, x_flecha):
            self.indicador, self.clave, self.direccion = indicador, None, None
            self.cinta = Entity(parent=padre, model="quad", position=(x_cinta, 0, -0.01),
                                scale=(hec.ANCHO_MINI_CINTA, hec.ALTO_MINI_CINTA))
            self.flecha = Entity(parent=padre, position=(x_flecha, 0, -0.012), enabled=False)
            lado = hec.LADO_FLECHA_MINI
            self.contorno = Entity(parent=self.flecha, model=triangulo(), scale=lado * 1.45, color=rgb(estilo.TINTA))
            self.relleno = Entity(parent=self.flecha, model=triangulo(), scale=lado, z=-0.001)

        def pintar(self, aspecto, direccion, escala):
            clave = mcal.clave_textura(aspecto)
            if clave != self.clave:
                self.clave = clave
                self.cinta.texture = textura(clave)
            self.cinta.scale = (hec.ANCHO_MINI_CINTA * escala, hec.ALTO_MINI_CINTA * escala)
            if direccion != self.direccion:
                self.direccion = direccion
                self.flecha.enabled = direccion != pv.IGUAL
                if direccion != pv.IGUAL:
                    arriba = direccion == pv.MEJOR
                    self.flecha.rotation_z = 0 if arriba else 180
                    self.flecha.y = hec.LADO_FLECHA_MINI * (0.35 if arriba else -0.35)
                    self.relleno.color = rgb(estilo.ESTADO_EXITO if arriba else estilo.ESTADO_ERROR)

    class VistaMiniPulseras:

        def __init__(self):
            self.chip = Entity(parent=escena.hud, enabled=False)
            # dos fondos: el de una fila (reloj solo) y el bloque de dos filas (reloj + dinero); las cintas van en
            # `contenido`, que se agranda con el bloque doble
            self.fondo_simple = panel_piel(self.chip, ancho, hec.ALTO_CHIP, tono=estilo.COLOR_FONDO,
                                           radio_px=estilo.RADIO_CHIP_PX, borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            self.fondo_doble = panel_piel(self.chip, hec.ancho_mini_pulseras_doble(len(indicadores)), hec.ALTO_MINI_DOBLE,
                                          tono=estilo.COLOR_FONDO, radio_px=estilo.RADIO_CHIP_PX,
                                          borde_px=estilo.GROSOR_BORDE_DENSO_PX)
            self.fondo_doble.enabled = False
            self.chip.fondo = self.fondo_simple
            self.contenido = Entity(parent=self.chip)
            self.doble = False
            self.minis = [Mini(self.contenido, ind, xc, xf)
                          for ind, (xc, xf) in zip(indicadores, hec.piezas_mini_pulseras(len(indicadores)))]
            # Puesto por defecto (reloj en la pila sin dinero); cada frame se pega al chip real del reloj.
            self.chip.position = hec.rect_mini_pulseras(diseno_adaptable.aspecto(), 0, len(indicadores)).centro
            self.estado = pv.EstadoMinis(indicadores)
            self._fundido = None
            self._alfa = None

        def _pegar_al_reloj(self):
            chip = chip_reloj()
            if chip is None:
                return
            try:
                # ¿hay chip del dinero debajo del reloj? (el reloj no está en el puesto de abajo de la pila)
                abajo = hec.centro_chip_pila(diseno_adaptable.aspecto(), 0)[1]
                doble = chip.y > abajo + hec.ALTO_CHIP / 2
                if doble != self.doble:
                    self.doble = doble
                    self.fondo_doble.enabled, self.fondo_simple.enabled = doble, not doble
                    self.chip.fondo = self.fondo_doble if doble else self.fondo_simple
                    self.contenido.scale = hec.ESCALA_MINI_DOBLE if doble else 1.0
                    if self._fundido is not None:
                        self._fundido.invalidar()
                self.chip.position = hec.centro_mini_pulseras_junto_a(chip.x, chip.y, len(indicadores), doble=doble)
            except Exception:
                pass

        def _modo(self):
            modo, minimo = pv.SIEMPRE, False
            try:
                modo = modelo_ajustes.obtener().actual.pulseras_hud if modelo_ajustes.AJUSTES else pv.SIEMPRE
            except Exception:
                pass
            control_hud = getattr(getattr(escena, "hud", None), "modo_hud", None)
            if control_hud is not None:
                minimo = bool(control_hud.minimo)
            return modo, minimo

        def pintar(self, aspectos, visible, dt):
            if aspectos is not None:
                self.estado.observar({i: aspectos[i]["nivel"] for i in self.estado.indicadores if i in aspectos})
            if visible:
                self.estado.avanzar(dt)
            modo, minimo = self._modo()
            alfa = self.estado.alfa(visible and aspectos is not None, pv.siempre_visibles(modo, minimo), dt)
            mostrar = alfa > 0.0
            if mostrar != self.chip.enabled:
                self.chip.enabled = mostrar
            if not mostrar:
                return
            self._pegar_al_reloj()
            for m in self.minis:
                m.pintar(aspectos[m.indicador], self.estado.flecha(m.indicador), self.estado.escala(m.indicador))
            self._aplicar_alfa(alfa)

        def _aplicar_alfa(self, alfa):
            if self._fundido is None:
                from frontend.fundido_ui import FundidoArbol
                self._fundido = FundidoArbol(self.chip)
            if alfa < 1.0 or self._alfa != alfa:
                self._fundido.invalidar()            # las flechas se encienden/apagan: se recogen las piezas de nuevo
            self._fundido.aplicar(alfa)
            self._alfa = alfa

    return VistaMiniPulseras()
