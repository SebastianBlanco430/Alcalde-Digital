# Pantalla previa de un minijuego de verificar (Ursina): la PORTADA DE CASO que enseña EscenaMinijuego entre el clic en la
# puerta y el minijuego. Estilo cómic cívico (tinta, papel, cinta amarilla, sombra plana):
#   - el rumor como RECORTE DE PERIÓDICO (papel + cinta amarilla) a la derecha;
#   - el objeto del minijuego dibujado a la izquierda con primitivas simples (una ilustración por minijuego; si la vista no
#     recibe `minijuego_id`, una genérica de papel y chincheta);
#   - «CÓMO SE JUEGA» en 3 pasos CORTOS (<= 8 palabras) numerados, y «LO QUE PRACTICAS EN REDES» como post-it de una frase;
#   - botón «Empezar» grande (Enter, Espacio o clic).
# Los textos viven en backend/datos/minijuegos_instrucciones.py (se recortan con frontend/minijuegos/previa_calculos.py).
# GUARDIÁN: si el dibujo rico falla, se cae a un dibujo mínimo funcional (título, rumor y botón). Sin animación.

from ursina import Entity, Text, destroy

from frontend import estilo
from frontend.componentes import a_unidades, escala_fuente, rgb
from frontend.minijuegos import previa_calculos as calc
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Y_ENCABEZADO

Y_BOTON = -0.397
Y_ARRIBA = 0.35                 # arriba del contenido (bajo el título)
Y_ABAJO = -0.28                 # abajo del contenido (sobre el botón)
ALTO_ILUSTRACION_MIN = 0.50
ALTO_ILUSTRACION_MAX = 0.64
SEPARACION = 0.045              # vertical entre bloques de la columna derecha
PAPEL = estilo.PAPEL
TINTA = estilo.TINTA
POSTIT = (255, 236, 130)
AMARILLO = estilo.COLOR_ACENTO
CORCHO = (176, 130, 84)
ROJO = estilo.ESTADO_ERROR
CIAN = estilo.ESTADO_INFO


class _BotonEmpezar(ui.Boton):
    """Botón grande: el foco se ve en el borde amarillo, sin «>>» delante de la etiqueta."""

    def fijar_foco(self, valor):
        super().fijar_foco(valor)
        if not self.is_empty():
            self.texto.text = self._etiqueta


def _r(padre, ancho, alto, tono, x=0.0, y=0.0, z=0.0, radio=3):
    return ui.rect(padre, ancho, alto, tono, (x, y), z, radio)


def _hoja(padre, ancho, alto, x, y, z, rayas=3, tono=PAPEL, rot=0.0):
    """Hoja de papel con borde de tinta y unas rayas de «texto»."""
    h = Entity(parent=padre, position=(x, y, z), rotation_z=rot)
    _r(h, ancho + 0.008, alto + 0.008, TINTA, z=0.002)
    _r(h, ancho, alto, tono, z=0.001)
    for i in range(rayas):
        _r(h, ancho * (0.7 if i % 2 else 0.82), alto * 0.07, TINTA, -ancho * 0.05, alto * 0.3 - i * alto * 0.22, -0.001, 2)
    return h


def _chincheta(padre, x, y, z=-0.01, tono=ROJO):
    c = Entity(parent=padre, model="circle", scale=0.03, color=rgb(TINTA), position=(x, y, z))
    Entity(parent=padre, model="circle", scale=0.022, color=rgb(tono), position=(x, y, z - 0.001))


def _hilo(padre, x1, y1, x2, y2, z=-0.004, tono=ROJO, grosor=0.006):
    import math
    largo = math.hypot(x2 - x1, y2 - y1)
    Entity(parent=padre, model="quad", color=rgb(tono), scale=(largo, grosor),
           position=((x1 + x2) / 2, (y1 + y2) / 2, z), rotation_z=math.degrees(math.atan2(y2 - y1, x2 - x1)))


# -- Ilustraciones: cada una dibuja en un panel de (w, h) centrado en el origen local --

def _ilu_rastrear(p, w, h):        # corcho con hojas unidas por un hilo
    _r(p, w * 0.92, h * 0.92, CORCHO, z=-0.002, radio=6)
    a, b, c = (-w * 0.25, h * 0.2), (w * 0.12, -h * 0.05), (-w * 0.1, -h * 0.3)
    _hilo(p, a[0], a[1], b[0], b[1])
    _hilo(p, b[0], b[1], c[0], c[1])
    for (x, y), rot in ((a, 4), (b, -5), (c, 3)):
        _hoja(p, w * 0.3, h * 0.2, x, y, -0.006, rot=rot)
        _chincheta(p, x, y + h * 0.1, -0.012)


def _ilu_comparar(p, w, h):        # dos hojas lado a lado; una línea cambiada
    _hoja(p, w * 0.38, h * 0.62, -w * 0.22, 0.0, -0.004, rayas=4)
    _hoja(p, w * 0.38, h * 0.62, w * 0.22, 0.0, -0.004, rayas=4)
    _r(p, w * 0.3, h * 0.05, ROJO, w * 0.22, h * 0.09, -0.012, 2)
    Entity(parent=p, model="circle", scale=h * 0.12, color=rgb(AMARILLO), position=(0, -h * 0.34, -0.008))
    _r(p, w * 0.06, h * 0.012, TINTA, 0, -h * 0.34, -0.012, 1)
    _r(p, w * 0.012, h * 0.06, TINTA, 0, -h * 0.34, -0.012, 1)


def _ilu_cronologia(p, w, h):      # viñetas de cómic
    ancho, alto = w * 0.38, h * 0.36
    for i, (x, y) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        cx, cy = x * w * 0.22, y * h * 0.21
        _r(p, ancho + 0.008, alto + 0.008, TINTA, cx, cy, -0.004)
        _r(p, ancho, alto, (PAPEL, (206, 238, 250), POSTIT, (250, 214, 206))[i], cx, cy, -0.006)
        Entity(parent=p, model="circle", scale=alto * 0.28, color=rgb(TINTA), position=(cx, cy, -0.01))
        _r(p, ancho * 0.7, alto * 0.08, TINTA, cx, cy - alto * 0.32, -0.01, 2)


def _ilu_chat(p, w, h):            # móvil con globos
    _r(p, w * 0.5 + 0.012, h * 0.9 + 0.012, TINTA, z=-0.003, radio=10)
    _r(p, w * 0.5, h * 0.9, (60, 66, 96), z=-0.005, radio=9)
    for i, (x, ancho, tono) in enumerate(((-0.07, 0.62, PAPEL), (0.07, 0.55, CIAN), (-0.06, 0.5, PAPEL))):
        _r(p, w * 0.5 * ancho, h * 0.12, tono, w * 0.5 * x, h * (0.25 - 0.22 * i), -0.008, 6)
        _r(p, w * 0.5 * ancho * 0.7, h * 0.02, TINTA, w * 0.5 * x, h * (0.25 - 0.22 * i), -0.012, 1)
    _r(p, w * 0.3, h * 0.04, TINTA, 0, -h * 0.4, -0.01, 2)


def _ilu_senales(p, w, h):         # captura con lupa
    _r(p, w * 0.72 + 0.01, h * 0.62 + 0.01, TINTA, -w * 0.06, h * 0.05, -0.003)
    _r(p, w * 0.72, h * 0.62, PAPEL, -w * 0.06, h * 0.05, -0.005)
    _r(p, w * 0.72, h * 0.1, (120, 130, 170), -w * 0.06, h * 0.31, -0.008, 3)
    for i in range(3):
        _r(p, w * 0.5, h * 0.05, TINTA, -w * 0.12, h * (0.14 - 0.14 * i), -0.008, 2)
    _r(p, w * 0.16, h * 0.06, ROJO, w * 0.12, h * 0.14, -0.01, 2)
    Entity(parent=p, model="circle", scale=h * 0.3, color=rgb(TINTA), position=(w * 0.16, -h * 0.18, -0.012))
    Entity(parent=p, model="circle", scale=h * 0.25, color=rgb((206, 238, 250)), position=(w * 0.16, -h * 0.18, -0.014))
    _hilo(p, w * 0.24, -h * 0.28, w * 0.36, -h * 0.4, -0.012, TINTA, 0.02)


def _ilu_contrarreloj(p, w, h):    # mesa con mapa y chinchetas
    _r(p, w * 0.9, h * 0.62, (122, 90, 60), 0, -h * 0.05, -0.003, 6)
    _r(p, w * 0.78 + 0.01, h * 0.5 + 0.01, TINTA, 0, -h * 0.05, -0.005)
    _r(p, w * 0.78, h * 0.5, (200, 222, 170), 0, -h * 0.05, -0.007)
    _hilo(p, -w * 0.28, -h * 0.17, -w * 0.02, h * 0.03, -0.01, CIAN, 0.01)
    _hilo(p, -w * 0.02, h * 0.03, w * 0.28, -h * 0.12, -0.01, CIAN, 0.01)
    for x, y in ((-w * 0.28, -h * 0.17), (-w * 0.02, h * 0.03), (w * 0.28, -h * 0.12)):
        _chincheta(p, x, y, -0.014)
    Entity(parent=p, model="circle", scale=h * 0.22, color=rgb(TINTA), position=(w * 0.3, h * 0.32, -0.01))
    Entity(parent=p, model="circle", scale=h * 0.18, color=rgb(PAPEL), position=(w * 0.3, h * 0.32, -0.012))
    _hilo(p, w * 0.3, h * 0.32, w * 0.3, h * 0.39, -0.014, TINTA, 0.008)


def _ilu_generica(p, w, h):        # papel con chincheta
    _hoja(p, w * 0.6, h * 0.7, 0, -h * 0.02, -0.004, rayas=5, rot=-3)
    _chincheta(p, 0, h * 0.3, -0.012)


_ILUSTRACIONES = {"rastrear": _ilu_rastrear, "comparar": _ilu_comparar, "cronologia": _ilu_cronologia, "chat": _ilu_chat,
                  "senales": _ilu_senales, "contrarreloj": _ilu_contrarreloj, calc.GENERICA: _ilu_generica}


class PantallaPrevia(Entity):

    def __init__(self, titulo, rumor, instrucciones, ayuda, al_empezar, corta=False, al_ver_tutorial=None,
                 minijuego_id=None, **opciones):
        super().__init__(**opciones)
        self.al_empezar = al_empezar
        self.al_ver_tutorial = al_ver_tutorial
        self.tarjetas = []
        self.boton_tutorial = None
        try:
            self._construir(titulo, rumor, instrucciones, corta, minijuego_id)
        except Exception:                          # noqa: BLE001  guardián: se queda un dibujo mínimo pero funcional
            self._dibujo_minimo(titulo, rumor)
        self._poner_botones()

    # -- Dibujo completo --

    def _construir(self, titulo, rumor, instrucciones, corta, minijuego_id):
        m = calc.repartir(ANCHO_UTIL, corta)
        x0 = m["x0"]
        ui.texto(self, "ANTES DE EMPEZAR", 14, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE, (x0, Y_ENCABEZADO), negrita=True)
        ui.texto(self, titulo, 30, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, Y_ENCABEZADO - a_unidades(24)), negrita=True)

        xr, wr = m["x_derecha"], m["ancho_derecha"]
        y = Y_ARRIBA
        margen = a_unidades(12)

        # Recorte de periódico con el rumor: papel, borde de tinta, cinta amarilla.
        texto_rumor = "«" + calc.recortar_rumor(rumor) + "»"
        n_l = len(ui.lineas_de(texto_rumor, 20, wr - 2 * margen, True))
        alto_r = 2 * margen + ui.alto_de(1, 13) + a_unidades(4) + ui.alto_de(n_l, 20)
        papel = Entity(parent=self, position=(xr + wr / 2, y - alto_r / 2, 0))
        _r(papel, wr + a_unidades(10), alto_r + a_unidades(10), (8, 9, 16), a_unidades(4), -a_unidades(5), 0.006, 4)
        _r(papel, wr + a_unidades(6), alto_r + a_unidades(6), TINTA, z=0.004, radio=3)
        _r(papel, wr, alto_r, PAPEL, z=0.003, radio=2)
        ui.texto(papel, "RUMOR A VERIFICAR", 13, wr - 2 * margen, (120, 40, 40), (-wr / 2 + margen, alto_r / 2 - margen),
                 negrita=True)
        ui.texto(papel, texto_rumor, 20, wr - 2 * margen, TINTA,
                 (-wr / 2 + margen, alto_r / 2 - margen - ui.alto_de(1, 13) - a_unidades(4)), negrita=True)
        # Cinta en la esquina superior derecha, sobre el borde: no tapa ninguna palabra.
        cinta = Entity(parent=papel, position=(wr / 2 - 0.09, alto_r / 2 + a_unidades(2), -0.01), rotation_z=5)
        _r(cinta, 0.14 + a_unidades(4), 0.034 + a_unidades(4), TINTA, z=0.001, radio=1)
        _r(cinta, 0.14, 0.034, (255, 226, 90), z=0, radio=1)
        y -= alto_r + SEPARACION

        # Cómo se juega: tres pasos cortos, numerados (sólo en la versión completa).
        if m["con_pasos"]:
            pasos = calc.recortar_pasos(instrucciones["pasos"])
            wp = m["ancho_paso"]
            px = 18
            alto_t = max(ui.alto_de(len(ui.lineas_de(p, px, wp - 2 * margen)), px) for p in pasos)
            alto_p = 2 * margen + ui.alto_de(1, 14) + a_unidades(34) + alto_t
            t = ui.Tarjeta(wr, alto_p, "", "CÓMO SE JUEGA", px, 14, parent=self, margen_px=12,
                           position=(xr + wr / 2, y - alto_p / 2))
            t.golpe.collider = None
            self.tarjetas.append(t)
            for i, p in enumerate(pasos):
                px_i = xr + i * (wp + m["hueco_pasos"])
                y_disco = y - margen - ui.alto_de(1, 14) - a_unidades(18)
                Entity(parent=self, model="circle", scale=a_unidades(34), color=rgb(TINTA),
                       position=(px_i + margen + a_unidades(16), y_disco, -0.01))
                Entity(parent=self, model="circle", scale=a_unidades(28), color=rgb(AMARILLO),
                       position=(px_i + margen + a_unidades(16), y_disco, -0.012))
                Text(str(i + 1), parent=self, origin=(0, 0), position=(px_i + margen + a_unidades(16), y_disco, -0.02),
                     scale=escala_fuente(20), color=rgb(TINTA), font=ui.tipografia.FUENTE_TITULO)
                ui.texto(self, p, px, wp - 2 * margen, estilo.COLOR_TEXTO,
                         (px_i + margen, y_disco - a_unidades(22)))
            y -= alto_p + SEPARACION

        # Lo que practicas en redes: post-it de una frase.
        frase = calc.frase_redes(instrucciones["redes"])
        n_f = len(ui.lineas_de(frase, 19, wr - 2 * margen, True))
        alto_f = 2 * margen + ui.alto_de(1, 13) + a_unidades(4) + ui.alto_de(n_f, 19)
        nota = ui.Tarjeta(wr, alto_f, "", "", 19, 13, tono=POSTIT, parent=self, margen_px=12,
                          position=(xr + wr / 2, y - alto_f / 2))
        nota.golpe.collider = None
        nota.borde.color = rgb(TINTA)
        self.tarjetas.append(nota)
        ui.texto(self, "LO QUE PRACTICAS EN REDES", 13, wr - 2 * margen, (90, 70, 20), (xr + margen, y - margen), negrita=True)
        ui.texto(self, frase, 19, wr - 2 * margen, TINTA, (xr + margen, y - margen - ui.alto_de(1, 13) - a_unidades(4)),
                 negrita=True)

        # Ilustración a la izquierda: panel de tinta con el objeto del minijuego; su alto sigue al de la columna derecha
        # (así no queda un vacío debajo de los bloques) y el conjunto se centra entre el título y el botón.
        y_fin = y - alto_f
        wi = m["ancho_ilustracion"]
        hi = max(ALTO_ILUSTRACION_MIN, min(ALTO_ILUSTRACION_MAX, Y_ARRIBA - y_fin))
        cx, cy = x0 + wi / 2, Y_ARRIBA - hi / 2
        marco = Entity(parent=self, position=(cx, cy, 0))
        _r(marco, wi + a_unidades(12), hi + a_unidades(12), (8, 9, 16), a_unidades(5), -a_unidades(6), 0.006, 10)   # sombra plana
        _r(marco, wi + a_unidades(6), hi + a_unidades(6), TINTA, z=0.004, radio=10)
        _r(marco, wi, hi, estilo.COLOR_PANEL, z=0.003, radio=8)
        _ILUSTRACIONES[calc.ilustracion_de(minijuego_id)](marco, wi, hi)

    # -- Dibujo mínimo (guardián) --

    def _dibujo_minimo(self, titulo, rumor):
        for hijo in list(self.children):
            destroy(hijo)
        self.tarjetas = []
        x0 = -ANCHO_UTIL / 2
        ui.texto(self, titulo, 28, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, Y_ENCABEZADO), negrita=True)
        ui.texto(self, "Rumor a verificar: «" + str(rumor) + "»", 18, ANCHO_UTIL, estilo.COLOR_ACENTO, (x0, 0.3))

    def _poner_botones(self):
        self.boton = _BotonEmpezar("Empezar", self._empezar, 0.5, 0.1, 28, primario=True, parent=self, position=(0, Y_BOTON))
        self.boton.fijar_foco(True)
        if self.al_ver_tutorial is not None:      # pequeño, a la izquierda: volver a ver el tutorial de este minijuego
            self.boton_tutorial = ui.Boton("Ver tutorial", self._ver_tutorial, 0.26, 0.055, 16, parent=self,
                                           position=(-ANCHO_UTIL / 2 + 0.13, Y_BOTON))

    def _empezar(self):
        callback, self.al_empezar = self.al_empezar, None      # una sola vez
        if callback is not None:
            callback()

    def _ver_tutorial(self):
        callback, self.al_ver_tutorial = self.al_ver_tutorial, None      # una sola vez
        if callback is not None:
            callback()
