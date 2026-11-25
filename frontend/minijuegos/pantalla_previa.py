# Pantalla previa de un minijuego de verificar (Ursina): la PORTADA DE CASO que enseña EscenaMinijuego entre el clic en la
# puerta y el minijuego. Estilo cómic cívico (tinta, papel, cinta amarilla, sombra plana):
#   - el rumor como RECORTE DE PERIÓDICO (papel + cinta amarilla) a la derecha;
#   - el objeto del minijuego dibujado a la izquierda con primitivas simples (una ilustración por minijuego; si la vista no
#     recibe `minijuego_id`, una genérica de papel y chincheta);
#   - «CÓMO SE JUEGA» en 3 pasos CORTOS (<= 8 palabras) numerados, y «LO QUE PRACTICAS EN REDES» como post-it de una frase;
#   - botón «Empezar» grande (Enter, Espacio o clic).
# Los textos viven en backend/datos/minijuegos_instrucciones.py (se recortan con frontend/minijuegos/previa_calculos.py).
# GUARDIÁN: si el dibujo rico falla, se cae a un dibujo mínimo funcional (título, rumor y botón). Sin animación.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Text, color, destroy

from frontend import banderas_visuales as bv
from frontend import estilo
from frontend.componentes import a_unidades, escala_fuente, rgb
from frontend.minijuegos import previa_calculos as calc
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Y_ENCABEZADO
# Imports PEREZOSOS (guardián): se cargan en `_marco_activo`; si fallan solo cae la portada nueva.
mc = None
marco_mesa = None

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


class _BotonEmpezarTinta(ui.BotonTintaPrimario):
    """«Empezar» con la receta de tinta en amarillo: el foco se ve en el borde grueso (sin «>>» delante de la etiqueta)."""

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


def _flecha_abajo(p, x, y, tam):
    for rot, dx in ((45, -tam * 0.3), (-45, tam * 0.3)):
        _r(p, tam * 0.7, tam * 0.22, TINTA, x + dx, y, -0.014, 1).rotation_z = rot


def _ilu_cronologia(p, w, h):      # tira de 3 viñetas numeradas con flechas y un globo «?»
    ancho, alto = w * 0.58, h * 0.22
    cx = -w * 0.1
    tonos = (PAPEL, (206, 238, 250), POSTIT)
    for i in range(3):
        cy = h * (0.3 - 0.3 * i)
        _r(p, ancho + 0.008, alto + 0.008, TINTA, cx, cy, -0.004)
        _r(p, ancho, alto, tonos[i], cx, cy, -0.006)
        Entity(parent=p, model="circle", scale=alto * 0.34, color=rgb(TINTA), position=(cx - ancho * 0.22, cy + alto * 0.05, -0.01))
        _r(p, ancho * 0.34, alto * 0.14, TINTA, cx + ancho * 0.15, cy + alto * 0.16, -0.01, 2)
        _r(p, ancho * 0.26, alto * 0.14, TINTA, cx + ancho * 0.15, cy - alto * 0.12, -0.01, 2)
        px, py = cx - ancho / 2, cy + alto / 2
        Entity(parent=p, model="circle", scale=a_unidades(30), color=rgb(TINTA), position=(px, py, -0.012))
        Entity(parent=p, model="circle", scale=a_unidades(24), color=rgb(AMARILLO), position=(px, py, -0.014))
        Text(str(i + 1), parent=p, origin=(0, 0), position=(px, py, -0.02), scale=escala_fuente(17), color=rgb(TINTA),
             font=ui.tipografia.fuente_piel(titulo=True))
        if i < 2:
            _flecha_abajo(p, cx, cy - alto / 2 - h * 0.04, h * 0.05)
    gx, gy = w * 0.34, h * 0.3
    _r(p, w * 0.2 + 0.008, w * 0.17 + 0.008, TINTA, gx, gy, -0.006, 8)
    _r(p, w * 0.2, w * 0.17, PAPEL, gx, gy, -0.008, 7)
    Text("?", parent=p, origin=(0, 0), position=(gx, gy, -0.02), scale=escala_fuente(34), color=rgb(ROJO),
         font=ui.tipografia.fuente_piel(titulo=True))
    _r(p, a_unidades(14), a_unidades(14), TINTA, gx - w * 0.05, gy - w * 0.1, -0.006, 1).rotation_z = 45
    _r(p, a_unidades(9), a_unidades(9), PAPEL, gx - w * 0.05, gy - w * 0.095, -0.009, 1).rotation_z = 45


def _globo(p, x, y, ancho, alto, tono, cola):    # globo de chat con cola hacia la izquierda (-1) o la derecha (+1)
    xc = x + cola * ancho * 0.36
    _r(p, a_unidades(16), a_unidades(16), TINTA, xc, y - alto * 0.5, -0.006, 1).rotation_z = 45
    _r(p, ancho + 0.008, alto + 0.008, TINTA, x, y, -0.007, 8)
    _r(p, a_unidades(10), a_unidades(10), tono, xc, y - alto * 0.49, -0.009, 1).rotation_z = 45
    _r(p, ancho, alto, tono, x, y, -0.008, 7)
    for i, f in enumerate((0.74, 0.5)):
        _r(p, ancho * f, alto * 0.1, TINTA, x - ancho * 0.37 + ancho * f / 2, y + alto * (0.16 - 0.3 * i), -0.012, 2)


def _ilu_chat(p, w, h):            # dos globos de conversación con cola, uno a cada lado
    _globo(p, -w * 0.1, h * 0.2, w * 0.62, h * 0.26, PAPEL, -1)
    _globo(p, w * 0.1, -h * 0.14, w * 0.62, h * 0.26, CIAN, 1)
    for i in range(3):
        Entity(parent=p, model="circle", scale=a_unidades(12), color=rgb(TINTA),
               position=(-w * 0.34 + i * a_unidades(20), -h * 0.38, -0.012))


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


def _ilu_cronologia_clasica(p, w, h):      # viñetas de cómic
    ancho, alto = w * 0.38, h * 0.36
    for i, (x, y) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        cx, cy = x * w * 0.22, y * h * 0.21
        _r(p, ancho + 0.008, alto + 0.008, TINTA, cx, cy, -0.004)
        _r(p, ancho, alto, (PAPEL, (206, 238, 250), POSTIT, (250, 214, 206))[i], cx, cy, -0.006)
        Entity(parent=p, model="circle", scale=alto * 0.28, color=rgb(TINTA), position=(cx, cy, -0.01))
        _r(p, ancho * 0.7, alto * 0.08, TINTA, cx, cy - alto * 0.32, -0.01, 2)


def _ilu_chat_clasica(p, w, h):            # móvil con globos
    _r(p, w * 0.5 + 0.012, h * 0.9 + 0.012, TINTA, z=-0.003, radio=10)
    _r(p, w * 0.5, h * 0.9, (60, 66, 96), z=-0.005, radio=9)
    for i, (x, ancho, tono) in enumerate(((-0.07, 0.62, PAPEL), (0.07, 0.55, CIAN), (-0.06, 0.5, PAPEL))):
        _r(p, w * 0.5 * ancho, h * 0.12, tono, w * 0.5 * x, h * (0.25 - 0.22 * i), -0.008, 6)
        _r(p, w * 0.5 * ancho * 0.7, h * 0.02, TINTA, w * 0.5 * x, h * (0.25 - 0.22 * i), -0.012, 1)
    _r(p, w * 0.3, h * 0.04, TINTA, 0, -h * 0.4, -0.01, 2)


_ILUSTRACIONES = {"rastrear": _ilu_rastrear, "comparar": _ilu_comparar, "cronologia": _ilu_cronologia, "chat": _ilu_chat,
                  "senales": _ilu_senales, "contrarreloj": _ilu_contrarreloj, calc.GENERICA: _ilu_generica}


_ILUSTRACIONES_CLASICAS = {"cronologia": _ilu_cronologia_clasica, "chat": _ilu_chat_clasica}   # sin marco de papel


class PantallaPrevia(Entity):

    def __init__(self, titulo, rumor, instrucciones, ayuda, al_empezar, corta=False, al_ver_tutorial=None,
                 minijuego_id=None, **opciones):
        super().__init__(**opciones)
        self.al_empezar = al_empezar
        self.al_ver_tutorial = al_ver_tutorial
        self.tarjetas = []
        self.boton_tutorial = None
        self.mesa = None
        try:
            self._construir(titulo, rumor, instrucciones, corta, minijuego_id)
        except Exception:                          # noqa: BLE001  guardián: se queda un dibujo mínimo pero funcional
            self._dibujo_minimo(titulo, rumor)
        self._poner_botones()

    # -- Dibujo completo --

    def _construir(self, titulo, rumor, instrucciones, corta, minijuego_id):
        marco = self._marco_activo()
        m = calc.repartir(ANCHO_UTIL, corta)
        x0 = m["x0"]
        # Con el marco de papel la columna derecha lleva SIEMPRE «CÓMO SE JUEGA» (si hay versión corta, no cuenta como tarjeta).
        pasos_extra = bool(marco) and not m["con_pasos"]
        m["con_pasos"] = m["con_pasos"] or bool(marco)
        if marco:
            self._cabecera_marco(titulo, ANCHO_UTIL, x0)
        else:
            ui.texto(self, "ANTES DE EMPEZAR", 14, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE, (x0, Y_ENCABEZADO), negrita=True)
            ui.texto(self, titulo, 30, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, Y_ENCABEZADO - a_unidades(24)), negrita=True)

        xr, wr = m["x_derecha"], m["ancho_derecha"]
        y = Y_ARRIBA
        margen = a_unidades(12)
        px_e = 17 if marco else 13           # etiquetas informativas: >= 17 px con el marco de papel
        sep = 0.03 if marco else SEPARACION

        # Recorte de periódico con el rumor: papel, borde de tinta, cinta amarilla.
        texto_rumor = "«" + calc.recortar_rumor(rumor) + "»"
        n_l = len(ui.lineas_de(texto_rumor, 20, wr - 2 * margen, True))
        alto_r = 2 * margen + ui.alto_de(1, px_e) + a_unidades(4) + ui.alto_de(n_l, 20)
        papel = Entity(parent=self, position=(xr + wr / 2, y - alto_r / 2, 0))
        _r(papel, wr + a_unidades(10), alto_r + a_unidades(10), (8, 9, 16), a_unidades(4), -a_unidades(5), 0.006, 4)
        _r(papel, wr + a_unidades(6), alto_r + a_unidades(6), TINTA, z=0.004, radio=3)
        _r(papel, wr, alto_r, PAPEL, z=0.003, radio=2)
        ui.texto(papel, "RUMOR A VERIFICAR", px_e, wr - 2 * margen, (120, 40, 40), (-wr / 2 + margen, alto_r / 2 - margen),
                 negrita=True)
        ui.texto(papel, texto_rumor, 20, wr - 2 * margen, TINTA,
                 (-wr / 2 + margen, alto_r / 2 - margen - ui.alto_de(1, px_e) - a_unidades(4)), negrita=True)
        # Cinta en la esquina superior derecha, sobre el borde: no tapa ninguna palabra.
        cinta = Entity(parent=papel, position=(wr / 2 - 0.09, alto_r / 2 + a_unidades(2), -0.01), rotation_z=5)
        _r(cinta, 0.14 + a_unidades(4), 0.034 + a_unidades(4), TINTA, z=0.001, radio=1)
        _r(cinta, 0.14, 0.034, (255, 226, 90), z=0, radio=1)
        y -= alto_r + sep

        # Cómo se juega: tres pasos cortos, numerados (sólo en la versión completa).
        if m["con_pasos"]:
            pasos = calc.recortar_pasos(instrucciones["pasos"])
            wp = m["ancho_paso"]
            px = 18
            alto_t = max(ui.alto_de(len(ui.lineas_de(p, px, wp - 2 * margen)), px) for p in pasos)
            alto_p = 2 * margen + ui.alto_de(1, px_e + 1) + a_unidades(34) + alto_t
            if marco:
                self._sombra_papel(xr + wr / 2, y - alto_p / 2, wr, alto_p)
            t = ui.Tarjeta(wr, alto_p, "", "CÓMO SE JUEGA", px, px_e + 1, tono=PAPEL if marco else None, parent=self, margen_px=12,
                           position=(xr + wr / 2, y - alto_p / 2))
            t.golpe.collider = None
            if marco and t.titulo is not None:
                t.titulo.color = rgb(mc.TEXTO_SUAVE)
            if not pasos_extra:
                self.tarjetas.append(t)
            else:                                     # cinta de papel en la esquina: «apunta esto»
                cinta_p = Entity(parent=self, position=(xr + a_unidades(30), y + a_unidades(2), -0.03), rotation_z=-3)
                _r(cinta_p, 0.13 + a_unidades(4), 0.03 + a_unidades(4), TINTA, z=0.001, radio=1)
                _r(cinta_p, 0.13, 0.03, (255, 226, 90), z=0, radio=1)
            for i, p in enumerate(pasos):
                px_i = xr + i * (wp + m["hueco_pasos"])
                y_disco = y - margen - ui.alto_de(1, px_e + 1) - a_unidades(18)
                Entity(parent=self, model="circle", scale=a_unidades(34), color=rgb(TINTA),
                       position=(px_i + margen + a_unidades(16), y_disco, -0.01))
                Entity(parent=self, model="circle", scale=a_unidades(28), color=rgb(AMARILLO),
                       position=(px_i + margen + a_unidades(16), y_disco, -0.012))
                Text(str(i + 1), parent=self, origin=(0, 0), position=(px_i + margen + a_unidades(16), y_disco, -0.02),
                     scale=escala_fuente(20), color=rgb(TINTA), font=ui.tipografia.fuente_piel(titulo=True))
                ui.texto(self, p, px, wp - 2 * margen, TINTA if marco else estilo.COLOR_TEXTO,
                         (px_i + margen, y_disco - a_unidades(22)))
            y -= alto_p + sep

        # Lo que practicas en redes: post-it de una frase.
        frase = calc.frase_redes(instrucciones["redes"])
        n_f = len(ui.lineas_de(frase, 19, wr - 2 * margen, True))
        alto_f = 2 * margen + ui.alto_de(1, px_e) + a_unidades(4) + ui.alto_de(n_f, 19)
        if marco:
            self._sombra_papel(xr + wr / 2, y - alto_f / 2, wr, alto_f)
        nota = ui.Tarjeta(wr, alto_f, "", "", 19, px_e, tono=POSTIT, parent=self, margen_px=12,
                          position=(xr + wr / 2, y - alto_f / 2))
        nota.golpe.collider = None
        nota.borde.color = rgb(TINTA)
        self.tarjetas.append(nota)
        ui.texto(self, mc.ETIQUETA_REDES if marco else "LO QUE PRACTICAS EN REDES", px_e, wr - 2 * margen, (90, 70, 20),
                 (xr + margen, y - margen), negrita=True)
        if marco:
            _chincheta(self, xr + wr - 0.05, y, -0.03)
        ui.texto(self, frase, 19, wr - 2 * margen, TINTA, (xr + margen, y - margen - ui.alto_de(1, px_e) - a_unidades(4)),
                 negrita=True)

        # Ilustración a la izquierda: panel de tinta con el objeto del minijuego; su alto sigue al de la columna derecha
        # (así no queda un vacío debajo de los bloques) y el conjunto se centra entre el título y el botón.
        y_fin = y - alto_f
        self._y_fin_columna = y_fin
        wi = m["ancho_ilustracion"]
        hi = max(ALTO_ILUSTRACION_MIN, min(ALTO_ILUSTRACION_MAX, Y_ARRIBA - y_fin))
        if marco:
            hi = max(hi, 0.6)
        cx, cy = x0 + wi / 2, Y_ARRIBA - hi / 2
        lamina = Entity(parent=self, position=(cx, cy, 0))
        _r(lamina, wi + a_unidades(12), hi + a_unidades(12), (8, 9, 16), a_unidades(5), -a_unidades(6), 0.006, 10)   # sombra plana
        _r(lamina, wi + a_unidades(6), hi + a_unidades(6), TINTA, z=0.004, radio=10)
        if marco:       # papel con el acento del minijuego, ligeramente torcido, con cinta
            lamina.rotation_z = mc.rotacion_portada(bv.reducir_movimiento())
            _r(lamina, wi, hi, mc.acento_portada(minijuego_id), z=0.003, radio=8)
        else:
            _r(lamina, wi, hi, estilo.COLOR_PANEL, z=0.003, radio=8)
        clave = calc.ilustracion_de(minijuego_id)
        dibujo = _ILUSTRACIONES if marco else {**_ILUSTRACIONES, **_ILUSTRACIONES_CLASICAS}
        dibujo[clave](lamina, wi, hi)
        if marco:
            cinta = Entity(parent=lamina, position=(0, hi / 2 - a_unidades(6), -0.03), rotation_z=-3)
            _r(cinta, 0.2 + a_unidades(4), 0.036 + a_unidades(4), TINTA, z=0.001, radio=1)
            _r(cinta, 0.2, 0.036, (255, 226, 90), z=0, radio=1)

    # -- Marco de papel (T1, T2, E1, E2) --

    def _marco_activo(self):
        global mc, marco_mesa
        try:
            from frontend.minijuegos_visual import marco_calculos as _mc
            from frontend.minijuegos_visual import marco_mesa as _mm
            mc, marco_mesa = _mc, _mm
            if not mc.activo():
                return False
            self.mesa = marco_mesa.montar_mesa(self)
            return self.mesa is not None
        except Exception as error:                 # noqa: BLE001  guardián: la portada de siempre
            bv.avisar_una_vez("marco_previa", error)
            return False

    def _cabecera_marco(self, titulo, ancho, x0):
        """«ANTES DE EMPEZAR» en pestaña de cinta y título con contorno de tinta."""
        txt = mc.ETIQUETA_ANTES
        ancho_c = ui.medir(txt, mc.PX_ETIQUETA, True) + a_unidades(24)
        alto_c = a_unidades(mc.PX_ETIQUETA) * 1.9
        cinta = Entity(parent=self, position=(x0 + ancho_c / 2, Y_ENCABEZADO - alto_c / 2 + a_unidades(4), -0.01), rotation_z=-1.5)
        _r(cinta, ancho_c + a_unidades(4), alto_c + a_unidades(4), TINTA, z=0.001, radio=1)
        _r(cinta, ancho_c, alto_c, (255, 226, 90), z=0, radio=1)
        Text(txt, parent=cinta, origin=(0, 0), position=(0, 0, ui.Z_TEXTO), scale=escala_fuente(mc.PX_ETIQUETA),
             color=rgb(TINTA), font=ui.tipografia.fuente_piel(titulo=True))
        marco_mesa.titulo_con_contorno(self, titulo, mc.PX_TITULO, ancho, (x0, Y_ENCABEZADO - alto_c - a_unidades(2)))

    def _sombra_papel(self, x, y, ancho, alto):
        """Sombra dura (4, -5) detrás de una tarjeta de papel."""
        dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
        s = ui.rect(self, ancho + a_unidades(8), alto + a_unidades(8), color.rgba32(*TINTA, estilo.ALFA_SOMBRA),
                    (x + a_unidades(dx), y + a_unidades(dy)), 0.006, 10)
        return s

    # -- Dibujo mínimo (guardián) --

    def _dibujo_minimo(self, titulo, rumor):
        for hijo in list(self.children):
            destroy(hijo)
        self.tarjetas = []
        self.mesa = None
        x0 = -ANCHO_UTIL / 2
        ui.texto(self, titulo, 28, ANCHO_UTIL, estilo.COLOR_TEXTO, (x0, Y_ENCABEZADO), negrita=True)
        ui.texto(self, "Rumor a verificar: «" + str(rumor) + "»", 18, ANCHO_UTIL, estilo.COLOR_ACENTO, (x0, 0.3))

    def _poner_botones(self):
        if getattr(self, "mesa", None) is not None:
            self._poner_botones_marco()
            return
        self.boton = _BotonEmpezar("Empezar", self._empezar, 0.5, 0.1, 28, primario=True, parent=self, position=(0, Y_BOTON))
        self.boton.fijar_foco(True)
        if self.al_ver_tutorial is not None:      # pequeño, a la izquierda: volver a ver el tutorial de este minijuego
            self.boton_tutorial = ui.Boton("Ver tutorial", self._ver_tutorial, 0.26, 0.055, 16, parent=self,
                                           position=(-ANCHO_UTIL / 2 + 0.13, Y_BOTON))

    def _poner_botones_marco(self):
        """«Empezar» alineado con la columna de texto y «Ver tutorial» al lado, del mismo alto."""
        m = calc.repartir(ANCHO_UTIL, False)
        alto = 0.095
        y_b = calc.y_botones(getattr(self, "_y_fin_columna", None), alto, Y_BOTON)
        ancho_t = 0.34 if self.al_ver_tutorial is not None else 0.0
        ancho_e = m["ancho_derecha"] - (ancho_t + 0.04 if ancho_t else 0.0)
        x_e = m["x_derecha"] + ancho_e / 2
        self.boton = _BotonEmpezarTinta("Empezar", self._empezar, ancho_e, alto, 28, parent=self, position=(x_e, y_b))
        self.boton.fijar_foco(True)
        if self.al_ver_tutorial is not None:      # al lado de «Empezar», mismo alto
            self.boton_tutorial = ui.BotonTinta("Ver tutorial", self._ver_tutorial, ancho_t, alto, 20, parent=self,
                                                position=(m["x_derecha"] + ancho_e + 0.04 + ancho_t / 2, y_b))

    def _empezar(self):
        callback, self.al_empezar = self.al_empezar, None      # una sola vez
        if callback is not None:
            callback()

    def _ver_tutorial(self):
        callback, self.al_ver_tutorial = self.al_ver_tutorial, None      # una sola vez
        if callback is not None:
            callback()
