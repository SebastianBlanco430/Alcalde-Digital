# Cálculos puros de la interfaz del caso de Fiscalía v2 (sin ursina): tamaños de letra, textos del medidor y del reloj,
# tiempos de las animaciones, navegación de la rueda con teclado y mando, avisos del laboratorio y mallas de arcos.
# Los usan hud_caso.py y sus piezas (rueda, medidor, subtítulos, laboratorio, acusación, diagrama, pausa).

import math

# -- Letra ------------------------------------------------------------------------------------------------------------
# Las medidas de letra del repo son «px de referencia» sobre una pantalla de 600 px de alto (componentes.escala_fuente).
PX_REFERENCIA = 600
PX_MIN_720 = 14                 # regla de pantalla: >= 14 px a 720p
PX_MIN_1080 = 18                # y >= 18 px a 1080p
PX_REF_MINIMO = 12              # 12 px de referencia = 14,4 px a 720p y 21,6 px a 1080p: el piso de todo el HUD

TAM = {                          # px de referencia de cada texto del HUD (antes de encoger para caber)
    "subtitulo": 21, "nombre": 19, "dice": 19, "etiqueta": 20, "pista": 15, "numero": 14,
    "medidor": 19, "marca": 13, "delta": 21, "reloj": 19, "prueba": 16,
    "chip_titulo": 17, "chip": 15, "aviso": 19,
    "titulo": 34, "resultado": 18, "texto_final": 20, "boton": 21,
    "diagrama": 12, "diagrama_titulo": 24, "porcentaje": 18,
    "modal_titulo": 26, "modal_texto": 19, "ficha_nombre": 17, "ficha_etiqueta": 15,
}


def px_en_pantalla(px_ref, alto_ventana, factor=1.0):
    """Altura real en píxeles de una letra de `px_ref` (px de referencia) en una ventana de `alto_ventana` px."""
    return px_ref * factor * alto_ventana / PX_REFERENCIA


def px_minimo(alto_ventana):
    """Mínimo legible para ese alto de ventana (14 a 720p, 18 a 1080p, interpolado entre medias)."""
    if alto_ventana <= 720:
        return PX_MIN_720
    if alto_ventana >= 1080:
        return PX_MIN_1080
    return PX_MIN_720 + (PX_MIN_1080 - PX_MIN_720) * (alto_ventana - 720) / (1080 - 720)


def legible(px_ref, alto_ventana, factor=1.0):
    return px_en_pantalla(px_ref, alto_ventana, factor) >= px_minimo(alto_ventana) - 1e-9


TRATAMIENTOS = ("profesor", "profesora", "doctor", "doctora", "dr.", "dra.", "don", "doña", "señor", "señora", "fiscal")


def variantes_nombre(nombre):
    """Formas del nombre de más larga a más corta, para la ficha de la acusación: completo; sin el tratamiento
    («Profesor Eurico Matos» → «Eurico Matos»); nombre y último apellido. Sin repetidas."""
    palabras = str(nombre or "").split()
    out = [" ".join(palabras)]
    if len(palabras) > 2 and palabras[0].lower() in TRATAMIENTOS:
        palabras = palabras[1:]
        out.append(" ".join(palabras))
    if len(palabras) > 2:
        out.append(f"{palabras[0]} {palabras[-1]}")
    return [v for i, v in enumerate(out) if v and v not in out[:i]]


def escala_min(px_ref):
    """Lo más que se puede encoger un texto de `px_ref` sin bajar del piso legible (entre 0,7 y 1)."""
    return max(0.7, min(1.0, PX_REF_MINIMO / float(px_ref)))


# -- Textos -----------------------------------------------------------------------------------------------------------
MENOS = "−"                 # signo menos tipográfico (la fuente lo tiene; ▲ y ▼ no: se dibujan como malla)

NOMBRES_UMBRAL = {"solido": "Sólido", "suficiente": "Suficiente", "indicios": "Indicios"}
RESULTADOS = {"exito": ("Éxito", (80, 190, 110)), "parcial": ("Parcial", (215, 180, 60)),
              "fracaso": ("Fracaso", (214, 62, 62))}


def texto_solidez(valor):
    return f"Solidez del caso {int(round(valor))} %"


def formatear_delta(delta):
    """«+8 %» o «−6 %» (el triángulo va aparte, dibujado)."""
    delta = int(round(delta))
    return f"+{delta} %" if delta >= 0 else f"{MENOS}{abs(delta)} %"


def nombre_umbral(clave):
    clave = str(clave)
    return NOMBRES_UMBRAL.get(clave, clave.replace("_", " ").capitalize())


def marcas_umbrales(umbrales, ancho):
    """[(x relativa al borde izquierdo de la barra, nombre, valor)] ordenadas de menor a mayor."""
    marcas = []
    for clave, valor in (umbrales or {}).items():
        try:
            v = max(0, min(100, int(valor)))
        except (TypeError, ValueError):
            continue
        marcas.append((ancho * v / 100.0, nombre_umbral(clave), v))
    return sorted(marcas, key=lambda m: m[2])


def tono_solidez(valor, umbrales):
    """Color RGB del relleno: rojo por debajo del umbral más bajo, ámbar entre medias, verde desde el más alto."""
    valores = sorted(int(v) for v in (umbrales or {}).values() if isinstance(v, (int, float)))
    if not valores:
        valores = [34, 67]
    if valor < valores[0]:
        return (214, 62, 62)
    if valor >= valores[-1]:
        return (80, 190, 110)
    return (215, 180, 60)


def es_acotacion(texto):
    return str(texto or "").strip().startswith("(")


def texto_dice(texto):
    """La frase del jugador entre comillas latinas; una acotación «(…)» va tal cual, sin comillas."""
    texto = str(texto or "").strip()
    if not texto or es_acotacion(texto):
        return texto
    return f"«{texto}»"


def nombre_resultado(resultado):
    return RESULTADOS.get(resultado, (str(resultado or "").capitalize(), (170, 172, 190)))


def texto_porcentaje(vistos, total):
    pct = 0 if not total else int(round(100 * vistos / total))
    return f"Has visto el {pct} % del caso ({vistos} de {total} momentos)"


# -- Reloj ------------------------------------------------------------------------------------------------------------
UMBRAL_URGENTE = 4.0


def fraccion_reloj(restante, total):
    if restante is None or not total:
        return 0.0
    return max(0.0, min(1.0, float(restante) / float(total)))


def texto_reloj(restante):
    return str(max(0, int(math.ceil(float(restante) - 1e-6)))) if restante is not None else ""


def reloj_urgente(restante):
    return restante is not None and float(restante) < UMBRAL_URGENTE


def segmentos_visibles(fraccion, n):
    return max(0, min(n, int(math.ceil(fraccion * n - 1e-6))))


def pulso(t, activo, reducir=False, amplitud=0.12, frecuencia=2.0):
    """Factor de escala del pulso del reloj urgente (1 sin pulso o con reducir movimiento)."""
    if not activo or reducir:
        return 1.0
    return 1.0 + amplitud * max(0.0, math.sin(2 * math.pi * frecuencia * t))


# -- Tiempos ----------------------------------------------------------------------------------------------------------
LETRAS_POR_SEGUNDO = 55.0
TEXTO_CORTO = 60                 # con <= 60 letras la rueda entra antes de que termine la línea
RETARDO_RUEDA_CORTA = 0.35       # s de línea antes de que entre la rueda en ese caso
DUR_ENTRADA = 0.22               # entrada de la rueda (<= 0,25 s)
DUR_DICE = 1.6                   # frase del jugador en pantalla
DUR_DELTA = 1.8                  # «▲ +8 %»
DUR_PRUEBA = 2.8                 # ficha de una prueba nueva
DUR_RELLENO = 0.5                # la barra del medidor va del valor viejo al nuevo
DUR_TEMBLOR = 0.3                # «no» al elegir un hueco bloqueado
ESPERA_TRAS_DICE = 0.7           # la respuesta empieza a escribirse un poco después de la frase del jugador


def letras_visibles(t, total, cps=LETRAS_POR_SEGUNDO, reducir=False):
    if reducir or cps <= 0:
        return total
    return max(0, min(total, int(max(0.0, t) * cps)))


def rueda_entra(t_linea, largo_texto, completa):
    """¿Ya puede verse la rueda? Al terminar la línea o, si la línea es corta, poco después de empezar."""
    return bool(completa) or (largo_texto <= TEXTO_CORTO and t_linea >= RETARDO_RUEDA_CORTA)


def suave(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def entrada(t, dur=DUR_ENTRADA, reducir=False):
    """0..1 de la animación de entrada (1 de golpe con reducir movimiento)."""
    if reducir or dur <= 0:
        return 1.0
    return suave(t / dur)


def anim_delta(t, dur=DUR_DELTA, reducir=False, subida=0.025):
    """(alfa 0..1, desplazamiento y) del «▲ +8 %»: entra, se queda y se va. Con reducir no se desplaza."""
    if t < 0 or t >= dur:
        return 0.0, 0.0
    entra, sale = 0.15, 0.45
    if t < entra:
        alfa = t / entra
    elif t > dur - sale:
        alfa = max(0.0, (dur - t) / sale)
    else:
        alfa = 1.0
    dy = 0.0 if reducir else subida * suave(t / dur)
    return alfa, dy


# -- Ficha «Prueba nueva» (pendientes-a, P3) --------------------------------------------------------------------------
# Antes iba en cola, 2,8 s cada una, y con varias seguidas (o con la interfaz oculta en un fundido) salían mucho después,
# incluso en la acusación. Ahora hay UNA ficha: la prueba sale en cuanto llega; si llega otra mientras se ve, se suma a
# la misma ficha («Pruebas nuevas: A · B») y el tiempo vuelve a empezar. Nunca hay atraso acumulado.
# Sitio: arriba a la derecha, bajo el medidor y sobre la rueda (fiscalia-visual deja las caras en el centro-izquierda y
# la rueda fija en el tercio derecho, con techo en y = 0,13): no tapa ninguna cara ni la rueda.
CENTRO_FICHA_PRUEBA = (0.50, 0.29)        # en camera.ui
ANCHO_FICHA_PRUEBA = 0.62
ALTO_FICHA_PRUEBA = {1: 0.062, 2: 0.098}  # una o dos líneas
SEPARADOR_PRUEBAS = " · "


def rect_ficha_prueba(lineas=1):
    """(x0, y0, x1, y1) de la ficha en camera.ui."""
    cx, cy = CENTRO_FICHA_PRUEBA
    alto = ALTO_FICHA_PRUEBA[2 if lineas > 1 else 1]
    return (cx - ANCHO_FICHA_PRUEBA / 2, cy - alto / 2, cx + ANCHO_FICHA_PRUEBA / 2, cy + alto / 2)


class FichaPruebas:
    """Estado puro de la ficha: nombres que muestra y su tiempo. La vista solo copia texto() y alfa()."""

    def __init__(self, dur=DUR_PRUEBA):
        self.dur = dur
        self.nombres = []
        self.t = None                        # None = oculta
        self._ultima = None                  # reloj real (s) de la última prueba que llegó

    @property
    def visible(self):
        return self.t is not None

    def agregar(self, nombre, ahora=None):
        """`ahora`: reloj real en segundos (monótono). Solo se agrupan las pruebas que llegan SEGUIDAS (a menos de `dur`
        de la anterior en tiempo real). Sin esto, la ficha del primer terminal quedaba congelada mientras el HUD estaba
        oculto (sentarse, parkour: `avanzar` no corre) y la prueba del segundo terminal se le sumaba (S5)."""
        nombre = str(nombre)
        lejos = ahora is not None and self._ultima is not None and ahora - self._ultima > self.dur
        if ahora is not None:
            self._ultima = ahora
        if not self.visible or lejos:
            self.nombres = [nombre]
            self.t = 0.0
            return
        if nombre not in self.nombres:
            self.nombres.append(nombre)
        self.t = min(self.t, 0.15)           # se queda entera (sin volver a entrar) y cuenta de nuevo

    def avanzar(self, dt):
        if self.t is None:
            return
        self.t += max(0.0, float(dt or 0.0))
        if self.t >= self.dur:
            self.t = None
            self.nombres = []

    def texto(self):
        if not self.nombres:
            return ""
        if len(self.nombres) == 1:
            return f"Prueba nueva: {self.nombres[0]}"
        return "Pruebas nuevas: " + SEPARADOR_PRUEBAS.join(self.nombres)

    def alfa(self):
        if self.t is None:
            return 0.0
        return anim_delta(self.t, self.dur, reducir=True)[0]


def temblor(t, reducir=False, dur=DUR_TEMBLOR, amplitud=0.012):
    if reducir or t < 0 or t >= dur:
        return 0.0
    return amplitud * math.sin(t * 2 * math.pi * 5) * (1 - t / dur)


def relleno(desde, hasta, t, dur=DUR_RELLENO, reducir=False):
    if reducir or dur <= 0 or t >= dur:
        return hasta
    return desde + (hasta - desde) * suave(t / dur)


# -- Navegación de la rueda -------------------------------------------------------------------------------------------
# Huecos fijos: 0 arriba, 1 derecha, 2 abajo, 3 izquierda.
TECLAS_DIRECCION = {"up arrow": 0, "w": 0, "right arrow": 1, "d": 1, "down arrow": 2, "s": 2, "left arrow": 3, "a": 3}
TECLAS_NUMERO = {"1": 0, "2": 1, "3": 2, "4": 3}
TECLAS_ELEGIR = ("enter", "space", "gamepad a")
TECLAS_PAUSA = ("escape", "gamepad start")
UMBRAL_PALO = 0.5


def direccion_a_hueco(x, y, umbral=UMBRAL_PALO):
    """Hueco al que apunta el palo (x derecha, y arriba) o None si está casi quieto. Gana el eje dominante."""
    if math.hypot(x, y) < umbral:
        return None
    if abs(y) >= abs(x):
        return 0 if y > 0 else 2
    return 1 if x > 0 else 3


def hueco_de_tecla(tecla, ocupados):
    """Hueco que resalta una tecla de dirección o de número (solo si ese hueco tiene una opción), o None."""
    hueco = TECLAS_DIRECCION.get(tecla, TECLAS_NUMERO.get(tecla))
    return hueco if hueco is not None and hueco in ocupados else None


# -- Laboratorio ------------------------------------------------------------------------------------------------------
def estado_parkour(completado):
    return "Prueba obtenida" if completado else "Sin revisar"


def aviso_laboratorio(parkours, cerca=None, puerta=False):
    """Texto del aviso de E del laboratorio ("" si no hay nada cerca)."""
    if puerta:
        return "E — Pasar a la sala"
    for p in parkours or ():
        if getattr(p, "nivel", None) == cerca and cerca is not None:
            if getattr(p, "completado", False):
                return f"E — Repetir: {p.nombre}"
            return f"E — Sentarse: {p.nombre}"
    return ""


# -- Mallas (vértices puros: Ursina solo los copia) --------------------------------------------------------------------
def vertices_arco(r_in, r_out, a0, a1, n):
    """Triángulos (lista de vértices, de 3 en 3) de un arco de corona circular entre los ángulos a0 y a1 (radianes,
    0 = derecha, sentido antihorario), con n segmentos."""
    vs = []
    n = max(1, int(n))
    for i in range(n):
        t0 = a0 + (a1 - a0) * i / n
        t1 = a0 + (a1 - a0) * (i + 1) / n
        p0 = (r_in * math.cos(t0), r_in * math.sin(t0), 0)
        p1 = (r_out * math.cos(t0), r_out * math.sin(t0), 0)
        p2 = (r_out * math.cos(t1), r_out * math.sin(t1), 0)
        p3 = (r_in * math.cos(t1), r_in * math.sin(t1), 0)
        vs += [p0, p1, p2, p0, p2, p3]
    return vs


def arco_reloj(fraccion, r_in, r_out, n=48):
    """Vértices del anillo del reloj: empieza arriba y se vacía en sentido horario (lo que queda es `fraccion`)."""
    k = segmentos_visibles(fraccion, n)
    if k <= 0:
        return []
    a0 = math.pi / 2
    return vertices_arco(r_in, r_out, a0, a0 - 2 * math.pi * k / n, k)
