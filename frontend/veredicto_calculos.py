# Avisos del cierre de una misión y contenido de la pantalla de finales (Python puro: NO importa ursina; se prueba con
# pytest). Traduce lo que deja el backend a texto listo para pintar:
#
#   texto_pago(resultado)        Resultado de dinero.pagar_mision -> «Recibiste R$ 85.» / «Sin pago: ...» / "" (pago 0)
#   texto_veredicto(veredicto)   FlujoConGameState.ultimo_veredicto -> «Rumor bien juzgado · Confianza de Policía +5»
#   ColaAvisos                   muestra los avisos de uno en uno, cada uno DURACION_AVISO s (varias misiones digitales
#                                pueden cerrarse en cadena y dejar varios pagos de golpe)
#   contenido_final(final, ...)  dict de confianza_misiones.evaluar_final -> títulos, párrafo, barras y resumen
#
# Las reglas (quién acierta, cuánto se mueve la confianza, qué final sale) viven en backend/logica/confianza_misiones.py;
# aquí solo se redacta.

from backend.datos import finales_textos

DURACION_AVISO = 3.2            # s que se ve cada aviso
PAUSA_ENTRE_AVISOS = 0.25       # s sin aviso entre dos seguidos (se nota que cambió)

TEXTO_PASADA = "Rumor bien juzgado"
TEXTO_FALLADA = "Rumor mal juzgado"
TEXTO_DIGITAL = "Misión digital cerrada"

# Tono de cada final (roles de frontend/estilo.py; aquí solo el nombre para no importar colores en las pruebas).
TONO_FINAL = {"bueno": "exito", "neutro": "aviso", "malo": "error"}


def _numero(valor):
    """«5», «2,5»: sin decimales si es entero, con coma decimal si no."""
    valor = round(float(valor), 1)
    if valor == int(valor):
        return str(int(valor))
    return f"{valor:.1f}".replace(".", ",")


def _con_signo(delta):
    return ("+" if delta >= 0 else "−") + _numero(abs(delta))


def texto_pago(resultado):
    """Aviso del pago de una misión; "" si no hay nada que decir (misión sin pago)."""
    if resultado is None:
        return ""
    mensaje = (getattr(resultado, "mensaje", "") or "").strip()
    if getattr(resultado, "ok", False):
        return mensaje
    return f"Sin pago: {mensaje}" if mensaje else "Sin pago"


def texto_veredicto(veredicto):
    """Aviso del veredicto aplicado a la confianza; "" si no hubo (None, o un dict sin grupo conocido)."""
    if not veredicto:
        return ""
    grupo = finales_textos.NOMBRES_GRUPOS.get(veredicto.get("grupo"))
    if grupo is None:
        return ""
    delta = veredicto.get("delta") or 0
    cabeza = {"pasada": TEXTO_PASADA, "fallada": TEXTO_FALLADA}.get(veredicto.get("veredicto"), TEXTO_DIGITAL)
    if str(veredicto.get("mision", "")).startswith(("parkour", "investigacion")):
        cabeza = TEXTO_DIGITAL
    if delta == 0:
        return f"{cabeza} · Confianza de {grupo} sin cambios"
    return f"{cabeza} · Confianza de {grupo} {_con_signo(delta)}"


class ColaAvisos:
    """Avisos de uno en uno. agregar(texto) encola; avanzar(dt) devuelve el texto que debe verse ahora (None = ninguno)."""

    def __init__(self, duracion=DURACION_AVISO, pausa=PAUSA_ENTRE_AVISOS):
        self.duracion, self.pausa = duracion, pausa
        self._cola = []
        self.actual = None
        self._resta = 0.0
        self._espera = 0.0

    def agregar(self, texto):
        if texto:
            self._cola.append(str(texto))

    def pendientes(self):
        return len(self._cola) + (self.actual is not None)

    def vaciar(self):
        self._cola.clear()
        self.actual, self._resta, self._espera = None, 0.0, 0.0

    def avanzar(self, dt):
        if self.actual is not None:
            self._resta -= dt
            if self._resta > 0.0:
                return self.actual
            self.actual = None
            self._espera = self.pausa if self._cola else 0.0
            return None
        if self._espera > 0.0:
            self._espera -= dt
            return None
        if self._cola:
            self.actual = self._cola.pop(0)
            self._resta = self.duracion
        return self.actual


def contenido_final(final, indicadores=None):
    """Lo que pinta la pantalla de finales a partir del dict de evaluar_final:
    {"clave", "tono", "titulo", "texto", "barras": [(nombre visible, valor entero 0-100)], "resumen": [líneas]}.
    `indicadores` (opcional): los de la ciudad (EstadoPartida.indicadores()), que se añaden al resumen."""
    clave = final["final"]
    textos = finales_textos.texto_final(clave)
    barras = [(nombre, max(0, min(100, int(final["confianza"][grupo] + 0.5))))
              for grupo, nombre in finales_textos.NOMBRES_GRUPOS.items()]
    resumen = [finales_textos.lineas_resumen(final)[0], f"Confianza media de la ciudad: {_numero(final['indice'])} de 100"]
    critico = final.get("grupo_critico")
    if critico is not None:
        resumen.append(f"{finales_textos.NOMBRES_GRUPOS[critico]} dejó de confiar: por eso la ciudad no levanta.")
    if indicadores:
        partes = [f"{etiqueta} {int(indicadores[nombre])}" for nombre, etiqueta in
                  (("convivencia", "Convivencia"), ("confianza", "Confianza en Civitas"),
                   ("desinformacion", "Desinformación")) if nombre in indicadores]
        if partes:
            resumen.append(" · ".join(partes))
    return {"clave": clave, "tono": TONO_FINAL[clave], "titulo": textos["titulo"], "texto": textos["texto"],
            "barras": barras, "resumen": resumen}
