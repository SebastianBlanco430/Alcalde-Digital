# Reloj de la partida EN LÍNEA en el cliente (paridad del multijugador; PURO: no importa ursina, se prueba en
# tests/test_b_multi_reloj.py). El anfitrión lleva el reloj de la sala (backend/red/multi_reloj.py) y lo reparte con el
# mensaje «reloj»; aquí se refleja con la MISMA cara que reloj_partida.RelojPartida y FlujoConTiempo, así lo que ya lee
# el reloj de la partida local funciona en línea sin tocarlo:
#
#   - frontend/registro_reloj.py: el chip «Día N · hh:mm» y el final por tiempo.
#   - frontend/radio_registro.py (con frontend/multi_radio_linea.py): radio de la mañana y de la noche; al ponerse la
#     mañana llama a flujo.pasar_noche(), que aquí AVISA al anfitrión («noche_lista») en vez de saltar la noche.
#   - frontend/ambiente_vivo.py: hora y día (ciclo de día y noche, sello de los rumores por días, NPC del día).
#
# Entre dos mensajes la hora avanza sola al ritmo del reloj (sin pasar del cierre del día); cada mensaje la corrige.
# Bandera ALCALDE_MULTI_PARIDAD (backend/red/multi_reloj.activo): apagada, FlujoEnLinea no cuelga este reloj.
#
#   RelojEspejo                      dia() hora() dias() hora_texto() terminado() noche_pendiente() ...
#   instalar(flujo, enviar_noche)    cuelga el reloj y los métodos de FlujoConTiempo de un FlujoEnLinea
#   aplicar(flujo, evento)           un mensaje «reloj» ya saneado

from backend.logica import reloj_partida
from backend.red import multi_reloj


class RelojEspejo:
    """Lo que el anfitrión dijo del reloj, con la hora interpolada entre mensajes."""

    def __init__(self, dias=reloj_partida.DIAS, seg_por_hora=None):
        self._dias = int(dias)
        self._seg_por_hora = float(seg_por_hora or reloj_partida.segundos_por_hora(True))
        self._dia = 1
        self._hora = reloj_partida.HORA_INICIO
        self._noche = False
        self._fin = False
        # Aún no llegó ningún «reloj» (la radio espera)
        self.recibido = False
        self._corre = False
        self._ultimo = None

    # -- Mensajes --

    def fijar(self, dia, hora, noche, fin):
        dia = max(1, min(self._dias, int(dia)))
        hora = max(0.0, min(reloj_partida.HORAS_POR_DIA, float(hora)))
        # Solo se interpola si la hora del anfitrión avanzó desde el mensaje anterior: con el reloj parado (el prólogo
        # del principio, multi_reloj.ESPERA_INICIO) la hora no corre aquí ni salta hacia atrás en cada mensaje.
        self._corre = self.recibido and (dia, hora) != self._ultimo
        self._ultimo = (dia, hora)
        self._dia, self._hora = dia, hora
        self._noche, self._fin = bool(noche), bool(fin)
        self.recibido = True

    def avanzar(self, dt):
        """Interpola la hora `dt` segundos reales (sin pasar del cierre del día ni moverse de noche o al terminar)."""
        if not self.recibido or not self._corre or self._noche or self._fin:
            return 0.0
        antes = self._hora
        self._hora = min(reloj_partida.HORA_CIERRE, self._hora + max(0.0, float(dt)) / self._seg_por_hora)
        return self._hora - antes

    # -- La cara de RelojPartida --

    def dia(self):
        return self._dia

    def hora(self):
        return self._hora

    def dias(self):
        return self._dias

    def noches(self):
        return True

    def noche_pendiente(self):
        return self._noche and not self._fin

    def terminado(self):
        return self._fin

    def en_pausa(self):
        return False

    def seg_por_hora(self):
        return self._seg_por_hora

    def tiempo_absoluto(self):
        return (self._dia - 1) * reloj_partida.HORAS_POR_DIA + self._hora

    def horas_restantes(self):
        fin = (self._dias - 1) * reloj_partida.HORAS_POR_DIA + reloj_partida.HORA_CIERRE
        return max(0.0, fin - self.tiempo_absoluto())

    def hora_texto(self):
        return reloj_partida.texto_de(self.tiempo_absoluto())

    def fraccion_partida(self):
        activas = reloj_partida.HORA_CIERRE - reloj_partida.HORA_INICIO
        hechas = (self._dia - 1) * activas + min(activas, max(0.0, self._hora - reloj_partida.HORA_INICIO))
        return min(1.0, max(0.0, hechas / (self._dias * activas)))


class TiempoEnLinea:
    """Los métodos de FlujoConTiempo que leen la radio y el vigía del reloj, sobre el reloj espejo."""

    def __init__(self, reloj, enviar_noche):
        self.reloj = reloj
        self._enviar_noche = enviar_noche
        self.diario = {}
        self.retener_noche = False
        # Día cuya noche ya se avisó al anfitrión
        self._avisada = None

    def aplicar(self, ev):
        self.reloj.fijar(ev["dia"], ev["hora"], ev["noche"], ev["fin"])
        if ev["noche"] and "diario" in ev:
            self.diario[int(ev["dia"])] = multi_reloj.diario_de_texto(ev["diario"])
        if not ev["noche"]:
            self._avisada = None

    # Sin radio que retenga la noche (apagada o rota), se avisa al anfitrión en cuanto llega: como en la partida local, donde
    # la noche se salta sola (FlujoConTiempo._revisar_noche); si no, este cliente haría esperar 20 s a la sala cada noche.
    def avanzar_tiempo(self, dt):
        self.reloj.avanzar(dt)
        if not self.retener_noche and self.reloj.noche_pendiente():
            self.pasar_noche()
        return []

    def noche_pendiente(self):
        return self.reloj.noche_pendiente()

    def retener_noches(self, si=True):
        self.retener_noche = bool(si)

    # La noche la salta el anfitrión cuando todos la cerraron (o a los 20 s): aquí solo se avisa, una vez por noche.
    def pasar_noche(self):
        dia = self.reloj.dia()
        if self.reloj.noche_pendiente() and self._avisada != dia:
            self._avisada = dia
            self._enviar_noche(dia)
        return False

    def diario_de(self, dia):
        return [dict(e) for e in self.diario.get(int(dia), [])]

    # Lo mismo que FlujoConTiempo.resumen_final con lo que mandó el anfitrión en «fin» (confianza, veredictos e
    # indicadores): el final por etapas (bueno / neutro / malo), el motivo y la hora. Con él frontend/registro_reloj
    # pinta en línea la cinemática del final y la pantalla final de la semana, como en la partida local. `flujo` es el
    # FlujoEnLinea (final_partida, estado).
    def resumen_final(self, flujo):
        from backend.logica import etapas_final
        from backend.logica.flujo_tiempo import evaluar_final_indicadores, final_ponderado_activo, ponderar_final
        indicadores = flujo.estado.indicadores()
        final = flujo.final_partida()
        if final is not None and final_ponderado_activo():
            final = ponderar_final(final, indicadores)
        if final is None:
            final = evaluar_final_indicadores(indicadores)
        if etapas_final.activo():
            forzado = etapas_final.indice_forzado()
            etapa = etapas_final.etapa_de_indice(final["indice"] if forzado is None else forzado)
            final = dict(final, final=etapas_final.final_de_etapa(etapa), etapa=etapa)
        motivo = "tiempo" if self.reloj.terminado() else "misiones"
        return dict(final, motivo=motivo, dia=self.reloj.dia(), hora_texto=self.reloj.hora_texto())

    def vaciar_avisos_retardados(self):
        return []


def instalar(flujo, enviar_noche):
    """Cuelga el reloj espejo de un FlujoEnLinea: `flujo.reloj` y los métodos de tiempo. Devuelve el TiempoEnLinea."""
    tiempo = TiempoEnLinea(RelojEspejo(), enviar_noche)
    flujo.tiempo_en_linea = tiempo
    flujo.reloj = tiempo.reloj
    for nombre in ("avanzar_tiempo", "noche_pendiente", "retener_noches", "pasar_noche", "diario_de",
                   "vaciar_avisos_retardados"):
        setattr(flujo, nombre, getattr(tiempo, nombre))
    flujo.resumen_final = lambda: tiempo.resumen_final(flujo)
    return tiempo


def aplicar(flujo, ev):
    """Un «reloj» del anfitrión. Sin reloj instalado (bandera apagada) no hace nada."""
    tiempo = getattr(flujo, "tiempo_en_linea", None)
    if tiempo is not None:
        tiempo.aplicar(ev)
