# Reloj de la partida en el HUD: cálculos PUROS (sin ursina; se prueban con pytest). Los usa frontend/registro_reloj.py.
#
#   texto_chip(reloj)                 «Día 3 · 14:30» (lo que pinta el chip del HUD)
#   icono_de(hora)                    "sol" | "luna" (de día entre las 06:00 y las 18:00)
#   fraccion_semana(reloj)            0..1 de la semana ya gastada (barra fina del chip)
#   motivo_de_pausa(...)              por qué NO corre el tiempo ahora (None = corre). Regla única del punto 1 del plan
#   AvisosFin                         «Último día» / «Quedan 2 horas»: cada umbral se avisa una sola vez por partida
#   texto_efecto(aviso)               aviso de causa-efecto de un efecto retardado -> texto listo para pintar
#   ColaAvisosCausa                   ColaAvisos con tope de pendientes (sin spam)
#   contenido_final_semana(...)       lo que pinta la pantalla final a partir de flujo.resumen_final()
#
# CUÁNDO CORRE EL TIEMPO (decisión, docs/PLAN_FINAL.md §8): solo cuando el jugador MANDA sobre su personaje en el mundo.
# No corre: sin reloj (ALCALDE_RELOJ=0), en línea, con la partida terminada, en pausa, en cinemáticas (entrar / salir de
# un edificio), con el mapa grande abierto, con un panel modal (inventario, tienda, Archivo de casos, diálogos), con el
# teléfono abierto, durante un fundido y mientras la misión está en el minijuego o cerrándose. Los interiores, el
# minijuego, el trabajo, el mundo digital y el parkour son OTRAS escenas: allí el HUD del mundo está apagado y el vigía
# que avanza el reloj no corre, así que tampoco gastan la semana. Conducir (bici, moto) SÍ gasta tiempo: es moverse.

from backend.datos import finales_textos
from frontend import veredicto_calculos as vc

HORA_AMANECER = 6.0
HORA_ANOCHECER = 18.0

# Motivos de pausa, en el orden en que se comprueban.
SIN_RELOJ, EN_LINEA, TERMINADA, PAUSA, CINEMATICA, MAPA, PANEL, TELEFONO, MISION, TRANSICION = (
    "sin_reloj", "en_linea", "terminada", "pausa", "cinematica", "mapa", "panel", "telefono", "mision", "transicion")

# (horas de juego que quedan, texto). De mayor a menor: cada uno se avisa UNA vez al cruzarlo.
UMBRALES_FIN = (
    (24.0, "Último día: la semana termina esta medianoche."),
    (2.0, "Quedan 2 horas para que termine la semana."),
)

DURACION_CAUSA = 6.5        # s que se ve cada aviso de causa-efecto (son frases largas)
PAUSA_CAUSA = 1.0           # s sin aviso entre dos seguidos
MAX_EN_COLA = 4             # avisos pendientes como mucho: los más viejos se descartan

ETIQUETAS_INDICADOR = {"convivencia": "Convivencia", "confianza": "Confianza", "desinformacion": "Desinformación"}
TEXTO_MOTIVO = {"tiempo": "Se acabó la semana", "misiones": "No quedan misiones"}
NOMBRES_NIVEL = {"florece": "florece", "sano": "sana", "tenso": "tensa", "apagado": "apagada"}


def texto_chip(reloj):
    """«Día 3 · 14:30»; "" si no hay reloj."""
    return "" if reloj is None else reloj.hora_texto()


def icono_de(hora):
    """"sol" de 06:00 a 18:00 (sin incluir las 18:00); "luna" el resto."""
    return "sol" if HORA_AMANECER <= float(hora) % 24.0 < HORA_ANOCHECER else "luna"


def fraccion_semana(reloj):
    return 0.0 if reloj is None else max(0.0, min(1.0, float(reloj.fraccion_partida())))


def motivo_de_pausa(con_reloj=True, en_linea=False, terminada=False, en_pausa=False, cinematica=False,
                    mapa_abierto=False, panel_abierto=False, telefono_abierto=False, mision_ocupada=False,
                    transicion=False):
    """Por qué el tiempo de la partida NO corre en este frame; None si corre. Solo booleanos: se prueba sin ventana."""
    for motivo, cierto in ((SIN_RELOJ, not con_reloj), (EN_LINEA, en_linea), (TERMINADA, terminada), (PAUSA, en_pausa),
                           (CINEMATICA, cinematica), (MAPA, mapa_abierto), (PANEL, panel_abierto),
                           (TELEFONO, telefono_abierto), (MISION, mision_ocupada), (TRANSICION, transicion)):
        if cierto:
            return motivo
    return None


class AvisosFin:
    """Avisos de que la semana se acaba. reiniciar(horas) al empezar o continuar una partida (los umbrales ya pasados
    no se repiten); revisar(horas) devuelve los textos de los umbrales recién cruzados (si se cruzan varios de golpe,
    solo el más urgente)."""

    def __init__(self, umbrales=UMBRALES_FIN):
        self._umbrales = tuple(sorted(umbrales, reverse=True))
        self._avisados = set()

    def reiniciar(self, horas_restantes):
        self._avisados = {limite for limite, _ in self._umbrales if horas_restantes <= limite}

    def revisar(self, horas_restantes):
        if horas_restantes <= 0.0:
            return []
        nuevos = [(limite, texto) for limite, texto in self._umbrales
                  if horas_restantes <= limite and limite not in self._avisados]
        self._avisados.update(limite for limite, _ in nuevos)
        return [nuevos[-1][1]] if nuevos else []


def _cambios(aviso):
    partes = []
    for nombre, etiqueta in ETIQUETAS_INDICADOR.items():
        delta = (aviso.get("deltas") or {}).get(nombre)
        if delta:
            partes.append(f"{etiqueta} {vc._con_signo(delta)}")
    return " · ".join(partes)


def texto_efecto(aviso):
    """Texto de un aviso de causa-efecto (dict de FlujoConTiempo): el mensaje y, entre paréntesis, lo que cambió en la
    ciudad: «Ayer compartiste sin verificar «…»: hoy el bulo volvió a circular. (Desinformación +3 · Confianza −2)».
    "" si el aviso no trae mensaje."""
    if not isinstance(aviso, dict):
        return ""
    mensaje = str(aviso.get("mensaje") or "").strip()
    if not mensaje:
        return ""
    cambios = _cambios(aviso)
    return f"{mensaje} ({cambios})" if cambios else mensaje


class ColaAvisosCausa(vc.ColaAvisos):
    """ColaAvisos para las frases largas de causa-efecto: más tiempo en pantalla, más pausa y, para no hacer spam, como
    mucho `maximo` pendientes (se descartan los más viejos) y sin repetir un texto que ya espera o se está viendo."""

    def __init__(self, duracion=DURACION_CAUSA, pausa=PAUSA_CAUSA, maximo=MAX_EN_COLA):
        super().__init__(duracion, pausa)
        self.maximo = maximo
        self.descartados = 0

    def agregar(self, texto):
        if not texto or str(texto) == self.actual or str(texto) in self._cola:
            return
        super().agregar(texto)
        sobran = len(self._cola) - self.maximo
        if sobran > 0:
            del self._cola[:sobran]
            self.descartados += sobran


def _entero(valor):
    return max(0, min(100, int(float(valor) + 0.5)))


def contenido_final_semana(resumen, indicadores=None, nivel_ambiente=None):
    """Lo que pinta la pantalla final a partir de flujo.resumen_final() (con o sin GameState):
    {"clave", "tono", "titulo", "subtitulo", "texto", "barras_grupos": [(nombre, valor)] (vacía sin GameState),
     "barras_ciudad": [(nombre, valor, mas_es_mejor)], "resumen": [líneas]}.
    `indicadores`: los de la ciudad (por defecto los del resumen). `nivel_ambiente`: Ambiente.nivel, opcional."""
    clave = resumen["final"]
    textos = finales_textos.texto_final(clave)
    indicadores = indicadores if indicadores else (resumen.get("indicadores") or {})
    motivo = TEXTO_MOTIVO.get(resumen.get("motivo"), "Fin de la campaña")
    hora = resumen.get("hora_texto")
    subtitulo = f"{motivo} · {hora}" if hora else motivo
    confianza = resumen.get("confianza") or {}
    barras_grupos = [(nombre, _entero(confianza[grupo])) for grupo, nombre in finales_textos.NOMBRES_GRUPOS.items()
                     if grupo in confianza]
    barras_ciudad = [(etiqueta, _entero(indicadores[nombre]), nombre != "desinformacion")
                     for nombre, etiqueta in (("convivencia", "Convivencia"), ("confianza", "Confianza en Civitas"),
                                              ("desinformacion", "Desinformación")) if nombre in indicadores]
    lineas = [f"Misiones acertadas: {int(resumen.get('pasadas', 0))} · falladas: {int(resumen.get('falladas', 0))}",
              f"Índice de la ciudad: {vc._numero(resumen['indice'])} de 100"]
    critico = resumen.get("grupo_critico")
    if critico in finales_textos.NOMBRES_GRUPOS:
        lineas.append(f"{finales_textos.NOMBRES_GRUPOS[critico]} dejó de confiar: por eso la ciudad no levanta.")
    elif nivel_ambiente in NOMBRES_NIVEL:
        lineas.append("La ciudad florece." if nivel_ambiente == "florece"
                      else f"La ciudad quedó {NOMBRES_NIVEL[nivel_ambiente]}.")
    return {"clave": clave, "tono": vc.TONO_FINAL[clave], "titulo": textos["titulo"], "subtitulo": subtitulo,
            "texto": textos["texto"], "barras_grupos": barras_grupos, "barras_ciudad": barras_ciudad, "resumen": lineas}
