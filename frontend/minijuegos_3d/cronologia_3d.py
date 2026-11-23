# «Ordenar la cadena de difusión» en 3D (familia corcho). El minijuego es la vista 2D de hoy (CronologiaVisual /
# MinijuegoCronologia), viva y oculta: recibe teclas y clics como siempre y decide todo (partida.orden, agarrado, foco,
# comprobar). Aquí solo se REFLEJA en un corcho:
#   - arriba, la tira del rumor y la tarjeta con las 3 instrucciones de hoy (cronologia_marcas_calculos.PASOS);
#   - un CORDEL cruza el corcho con un hueco numerado por mensaje y, al final, la tarjeta roja FIN con el título del caso;
#   - cada mensaje es una tarjeta de cartón COLGADA CON PINZA: cabecera amarilla (quién y hora, «sin hora» si no tiene),
#     el dibujo de la viñeta (el MISMO de la vista 2D: cronologia_visual.dibujar_vineta con cronologia_vinetas_calculos) y
#     el globo con lo que dice;
#   - abajo, «Mover antes», «Mover después» y «Comprobar el orden» (papeles vinculados a los botones 2D: clic = clic).
# Agarrar (Enter/Espacio/clic): el personaje va y DESCUELGA la tarjeta, que queda en su mano; con las flechas la lleva a otro
# hueco (las demás se reacomodan como hoy); Enter la CUELGA. C: el personaje da un paso atrás y aparecen las marcas de hoy
# (palomita / aspa «ERA LA n.ª») y, si todo está en orden, el sello «EN ORDEN» en la tarjeta FIN.

import math

from ursina import Entity

from frontend.componentes import rgb
from frontend.minijuegos_3d import corcho_calculos as cc
from frontend.minijuegos_3d import corcho_piezas as cp
from frontend.minijuegos_3d import papel_3d, raton, sonidos
from frontend.minijuegos_3d.corcho_base import Corcho3D
from frontend.minijuegos_visual import cronologia_marcas_calculos as marcas
from frontend.minijuegos_visual import cronologia_vinetas_calculos as vin

CARTON = (236, 222, 192)
CORDEL = (172, 132, 86)
MADERA = (176, 128, 80)
AGARRE = (80, 200, 255)           # cian: como la vista 2D (se distingue del amarillo del foco)
VERDE_MARCA = (22, 112, 58)
ROJO_MARCA = (185, 38, 38)
ROJO_FIN = (210, 50, 50)
RAPIDEZ = 10.0                    # 1/s: las tarjetas se reacomodan con seguimiento suave
LEVANTADA = 0.11                  # m que se separa del corcho la tarjeta agarrada (en la mano)
DUR_COLGAR = 0.35
ESPERA_MARCAS = 0.55              # s tras comprobar: el personaje da el paso atrás y salen las marcas


def _triangulo():
    from ursina import Mesh
    return Mesh(vertices=[(-0.5, -0.5, 0), (0.5, -0.5, 0), (0, 0.5, 0)], triangles=[(0, 1, 2)], mode="triangle")


def cabecera_vineta(item, s, ancho_txt):
    """Cabecera amarilla de una viñeta: quién (hasta 2 líneas, recortado con «…») y la hora (o «sin hora», como la vista
    2D), que va SIEMPRE entera en una línea (si no cabe, su letra baja hasta LINEA_MINIMA). -> (quién, nº de líneas del
    quién, hora, alto de línea de la hora)."""
    lc = cc.LINEA_VINETA_QUIEN * s
    quien = cp.recortar_lineas(str(item.get("quien", "")), lc, ancho_txt, 2, True)
    lineas_q = cp.lineas(quien, lc, ancho_txt, True)
    hora = item.get("hora") or "sin hora"
    lh = cc.LINEA_VINETA_HORA * s
    while cp.lineas(hora, lh, ancho_txt, True) > 1 and lh > cc.LINEA_MINIMA * s:
        lh -= 0.001 * s
    return quien, lineas_q, hora, lh


def _dibujo(padre, item, caso, alto):
    """La escena de la viñeta: la MISMA función y las mismas primitivas que la vista 2D. Los textos del dibujo se
    protegen de la tinta (no escriben profundidad), como todo texto en el mundo."""
    from frontend.minijuegos_visual.cronologia_visual import dibujar_vineta
    from frontend.piezas import texto_sin_tinta
    figuras = vin.figuras(vin.escenario_de(caso), vin.actor_de(item), item.get("quien", ""))
    raiz = dibujar_vineta(padre, figuras, alto)
    for e in [raiz, *raiz.get_descendants()]:
        e.ignore = True
        if type(e).__name__ == "Text":
            texto_sin_tinta(e)
            e.setBin("transparent", 20)
    return raiz


class Cronologia3D(Corcho3D):

    # -- Construcción --

    def construir(self):
        corcho = self.preparar_corcho()
        mj = self.minijuego
        self.n = len(mj.partida.orden)
        self.disp = cc.disposicion_cronologia(corcho.ancho, corcho.alto, self.n)
        self.s = s = self.disp["s"]
        self.tira_rumor(self.disp["rumor"], self.disp["rumor_etiqueta_w"], cc.LINEA_TITULO * s)
        self._instrucciones()
        self._cordel()
        self._fin()
        self._botones()
        # Las tarjetas (cada una con su dibujo: ~30 piezas) se cuelgan UNA POR FRAME durante la transición de entrada (no
        # un solo frame largo al abrir). Si hace falta una antes de tiempo, se hace en ese momento (_asegurar).
        self.tarjetas = [None] * self.n
        self.obras = [lambda k=k: self._asegurar(k) for k in range(self.n)]
        self._vinculado = None
        self._agarrada = None            # índice (k) de la tarjeta en la mano, o None
        self._colgar_t = None            # s desde que se colgó (vuelta al reposo al acabar)
        self._comprobado_t = None
        self._marcas_puestas = False
        self._visto_terminado = False
        self.marcas = []
        self.sello_orden = None
        self._asegurar(0)
        self._sincronizar(0.0)

    def _asegurar(self, k):
        if self.tarjetas[k] is None:
            t = self._tarjeta(k, self.minijuego.partida.correcto[k])
            t.actual = self._sitio(self.minijuego.partida.orden.index(k))
            t.position = t.actual
            self.tarjetas[k] = t
            self._vinculado = None           # hay que vincular la nueva
        return self.tarjetas[k]

    def _obrar(self, presupuesto=0.006):
        import time
        t0 = time.perf_counter()
        while self.obras and time.perf_counter() - t0 < presupuesto:
            self.obras.pop(0)()

    def _instrucciones(self):
        s = self.s
        cx, cy, w, h = self.disp["instrucciones"]
        tarjeta = papel_3d.papel(self.raiz, w, h, posicion=(cx, cy), giro=0.2, tono=(40, 36, 52))
        lt = cc.LINEA_CABECERA * s
        partes = marcas.cintas(w, len(marcas.PASOS), 0.02 * s)
        self.textos_instrucciones = []
        for i, (x, ancho) in enumerate(partes):
            x0 = -w / 2 + x - ancho / 2
            cp.circulo(tarjeta, (x0 + 0.035 * s, 0), 0.05 * s, cp.AMARILLO, z=-0.001)
            cp.texto_centrado(tarjeta, str(i + 1), lt, 0.05 * s, 0.0, cp.TINTA, negrita=True, x=x0 + 0.035 * s)
            ancho_txt = ancho - 0.08 * s
            n = cp.lineas(marcas.PASOS[i], lt, ancho_txt)
            self.textos_instrucciones.append(cp.texto(tarjeta, marcas.PASOS[i], lt, ancho_txt, cp.PAPEL,
                                                      (x0 + 0.07 * s, cp.alto_texto(n, lt) / 2)))
        self.tarjeta_instrucciones = tarjeta

    def _cordel(self):
        s = self.s
        y = self.disp["cordel_y"]
        x0, x1 = self.disp["cordel_x"]
        cordel = cp.Cinta(self.raiz, tono=CORDEL, grosor=0.007 * s, z=-0.007)
        cordel.fijar(cc.hilo((x0, y), (x1, y), 0.004 * s, n=24))
        for x in (x0, x1):
            papel_3d.chincheta(self.raiz, (x, y), (150, 150, 165)).ignore = True
        # el número de cada hueco (no se mueve: «este es el 1.º», «el 2.º»...), sobre el cordel
        self.numeros = []
        for pos, x in enumerate(self.disp["vineta_x"]):
            c = Entity(parent=self.raiz, position=(x + self.disp["vineta"][0] / 2 - 0.035 * s, y + 0.03 * s,
                                                     papel_3d.Z_PAPEL), ignore=True)
            cp.circulo(c, (0, 0), 0.05 * s, cp.TINTA, z=0.0)
            cp.circulo(c, (0, 0), 0.04 * s, cp.PAPEL, z=-0.001)
            hoja = papel_3d.papel(c, 0.001, 0.001, capa=0)          # soporte sin escala para el texto
            hoja.hoja.enabled = False
            cp.texto_centrado(hoja, str(pos + 1), cc.LINEA_CABECERA * s, 0.05 * s, 0.0, cp.TINTA, negrita=True)
            self.numeros.append(c)

    def _sitio(self, pos):
        w, h = self.disp["vineta"]
        return (self.disp["vineta_x"][pos], self.disp["vineta_arriba"] - h / 2, 0.0)

    def _tarjeta(self, k, item):
        """Tarjeta de cartón de un mensaje (su contenido no cambia; cambia el hueco donde cuelga)."""
        s = self.s
        w, h = self.disp["vineta"]
        raiz = Entity(parent=self.raiz, ignore=True)          # se mueve entera (hueco, levantar, balanceo)
        borde = papel_3d.papel(raiz, w, h, tono=cp.TINTA, capa=0)
        borde.ignore = True
        raiz.papel = borde
        fondo = papel_3d.papel(borde, w - 0.01 * s, h - 0.01 * s, tono=CARTON, capa=0)
        margen = 0.016 * s
        ancho_txt = w - 0.01 * s - 2 * margen
        lc = cc.LINEA_VINETA_QUIEN * s
        quien, lineas_q, hora, lh = cabecera_vineta(item, s, ancho_txt)
        alto_cab = cp.alto_texto(lineas_q, lc) + cp.alto_texto(1, lh) + 0.02 * s
        y_arriba = (h - 0.01 * s) / 2
        banda = papel_3d.papel(fondo, w - 0.01 * s, alto_cab, posicion=(0, y_arriba - alto_cab / 2), tono=cp.AMARILLO)
        x0 = -(w - 0.01 * s) / 2 + margen
        raiz.quien = cp.texto(banda, quien, lc, ancho_txt, cp.TINTA, (x0, alto_cab / 2 - 0.008 * s), negrita=True)
        raiz.hora = cp.texto(banda, hora, lh, ancho_txt * 1.05, cp.TINTA,
                             (x0, alto_cab / 2 - 0.008 * s - cp.alto_texto(lineas_q, lc)), negrita=True)
        # el dibujo (a todo el ancho, debajo de la cabecera)
        ancho_dibujo = w - 0.01 * s - 2 * 0.008 * s
        alto_dibujo = ancho_dibujo / vin.ASPECTO
        y_dibujo = y_arriba - alto_cab - 0.008 * s - alto_dibujo / 2
        hueco = Entity(parent=fondo, position=(0, y_dibujo, -0.0025), ignore=True)
        _dibujo(hueco, item, self.minijuego.caso, alto_dibujo)
        raiz.y_dibujo, raiz.alto_dibujo = y_dibujo, alto_dibujo
        # globo con lo que dice
        abajo = -(h - 0.01 * s) / 2
        alto_globo = (y_dibujo - alto_dibujo / 2) - abajo - 0.03 * s
        y_globo = abajo + 0.01 * s + alto_globo / 2
        ancho_globo = w - 0.01 * s - 0.024 * s
        borde_globo = papel_3d.papel(fondo, ancho_globo + 0.006 * s, alto_globo + 0.006 * s, posicion=(0, y_globo),
                                     tono=cp.TINTA, capa=1)
        globo = papel_3d.papel(borde_globo, ancho_globo, alto_globo, tono=(255, 255, 255), capa=0)
        for esc, tono, dz in ((1.0, cp.TINTA, -0.0005), (0.7, (255, 255, 255), -0.0035)):
            Entity(parent=borde_globo, model=_triangulo(), color=rgb(tono), shader=None, ignore=True,
                   scale=(0.03 * s * esc, 0.03 * s * esc),
                   position=(ancho_globo * 0.28, alto_globo / 2 + 0.012 * s * esc, dz))
        lg = cc.LINEA_VINETA_GLOBO * s
        maximo = max(1, int((alto_globo - 0.012 * s) / (lg * 1.32)))
        from frontend.minijuegos import ui as ui_2d
        k_px = lg / cp.a_unidades(papel_3d.PX_REFERENCIA)
        lineas = ui_2d.lineas_de(str(item.get("texto", "")), papel_3d.PX_REFERENCIA, (ancho_globo - 0.02 * s) / k_px)
        if len(lineas) > maximo:
            lineas = lineas[:maximo]
            lineas[-1] = lineas[-1].rstrip(" .,") + "…"
        raiz.globo = cp.texto(globo, "\n".join(lineas), lg, ancho_globo * 1.2, cp.TINTA,
                              (-ancho_globo / 2 + 0.01 * s, len(lineas) * lg * 1.32 / 2))
        # la pinza (madera) que la sujeta al cordel
        pinza = Entity(parent=raiz, position=(0, h / 2 + 0.005 * s, -0.016), ignore=True)
        cp.rect(pinza, (-0.006 * s, 0), (0.014 * s, 0.06 * s), MADERA, z=0.0)
        cp.rect(pinza, (0.006 * s, 0), (0.014 * s, 0.06 * s), MADERA, z=-0.001)
        cp.rect(pinza, (0, -0.004 * s), (0.032 * s, 0.006 * s), (110, 112, 120), z=-0.002)
        raiz.k = k
        raiz.giro = self.disp["giros"][k % len(self.disp["giros"])]
        raiz.rotation_z = raiz.giro
        raiz.balanceo_t = None
        raiz.marca = None
        raiz.papel.hoja.collider = "box"
        return raiz

    def _fin(self):
        s = self.s
        w, h = self.disp["vineta"]
        x = self.disp["fin_x"]
        y = self.disp["vineta_arriba"] - h / 2
        borde = papel_3d.papel(self.raiz, w, h, posicion=(x, y), tono=cp.TINTA, giro=0.6)
        rojo = papel_3d.papel(borde, w - 0.01 * s, h - 0.01 * s, tono=ROJO_FIN, capa=0)
        caso = self.minijuego.caso or {}
        titulo = str(caso.get("titulo", "La cadena"))
        lt = cc.LINEA_TITULO * s
        ancho_txt = w - 0.05 * s
        n = min(4, cp.lineas(titulo, lt, ancho_txt, True))
        alto_caja = cp.alto_texto(n, lt) + 0.03 * s
        caja = papel_3d.papel(rojo, w - 0.04 * s, alto_caja, posicion=(0, 0.06 * s), tono=cp.AMARILLO, capa=0)
        cp.texto_centrado(caja, titulo, lt, ancho_txt, 0.0, cp.TINTA, negrita=True)
        banda = papel_3d.papel(rojo, w - 0.01 * s, 0.10 * s, posicion=(0, 0.06 * s - alto_caja / 2 - 0.08 * s),
                               tono=cp.TINTA, capa=0)
        self.banda_fin = banda
        self.texto_banda = cp.texto_centrado(banda, self._texto_banda(), cc.LINEA_CABECERA * s, w - 0.03 * s, 0.0,
                                             cp.PAPEL, negrita=True)
        self._banda_txt = self._texto_banda()
        cp.texto(rojo, "FIN", lt, 0.1 * s, cp.AMARILLO, (w / 2 - 0.09 * s, -h / 2 + 0.06 * s), negrita=True)
        papel_3d.chincheta(borde, (0, h / 2 - 0.02 * s), (150, 150, 165)).ignore = True
        self.tarjeta_fin = borde

    def _texto_banda(self):
        t = getattr(getattr(self.minijuego, "portada_txt", None), "text", None)
        return str(t) if t else "Se lee de izquierda a derecha"

    def _botones(self):
        s = self.s
        mj = self.minijuego
        self.botones = []
        datos = ((getattr(mj, "boton_subir", None), False), (getattr(mj, "boton_bajar", None), False),
                 (getattr(mj, "boton_comprobar", None), True))
        for (boton, primario), x, w in zip(datos, self.disp["botones_x"], self.disp["botones_w"]):
            if boton is None:
                continue
            h = self.disp["boton_alto"]
            borde = papel_3d.papel(self.raiz, w, h, posicion=(x, self.disp["botones_y"]), tono=cp.TINTA, giro=0.3)
            cara = papel_3d.papel(borde, w - 0.012 * s, h - 0.012 * s, tono=cp.AMARILLO if primario else cp.PAPEL, capa=0)
            etiqueta = str(getattr(boton, "_etiqueta", "") or getattr(getattr(boton, "texto", None), "text", ""))
            borde.texto = cp.texto_centrado(cara, etiqueta, cc.LINEA_BOTON * s, w * 1.2, 0.0, cp.TINTA, negrita=True)
            borde.cara, borde.boton, borde.primario = cara, boton, primario
            borde.hoja.collider = "box"
            borde.estado = None
            self.botones.append(borde)

    # -- Sincronizar (cada frame) --

    def avanzar_3d(self, dt):
        if self.minijuego.terminado and not self._visto_terminado:
            # La vista 2D acaba de comprobar (su frame más pesado: comprobar + revisión + banner de la escena). El 3D
            # reacciona en el frame siguiente (16 ms después) para no sumar nada a ese frame.
            self._visto_terminado = True
            return
        self._sincronizar(dt)
        if self.obras:
            self._obrar()
        self.avanzar_sello()

    def _sincronizar(self, dt):
        mj = self.minijuego
        p = mj.partida
        orden = list(p.orden)
        terminado = bool(mj.terminado)
        agarrada = None
        if getattr(mj, "agarrado", False) and not terminado and 0 <= mj.foco < self.n:
            agarrada = orden[mj.foco]
            self._asegurar(agarrada)
        if tuple(orden) != self._vinculado:
            self._vincular(orden)
        self._gestos(agarrada, orden, terminado, dt)
        k_suave = 1.0 - math.exp(-RAPIDEZ * dt) if dt > 0 else 1.0
        for pos, k in enumerate(orden):
            t = self.tarjetas[k]
            if t is None:
                continue
            x, y, z = self._sitio(pos)
            rot = t.giro
            if k == agarrada:
                z, y, rot = -LEVANTADA, y - 0.03 * self.s, -3.0
            ax, ay, az = t.actual
            t.actual = (ax + (x - ax) * k_suave, ay + (y - ay) * k_suave, az + (z - az) * k_suave)
            t.position = t.actual
            if t.balanceo_t is not None:
                t.balanceo_t += dt
                rot += cc.balanceo(t.balanceo_t)
                if t.balanceo_t > 2.5:
                    t.balanceo_t = None
            t.rotation_z = rot
            foco_2d = getattr(mj.filas[pos], "_foco", None) if pos < len(getattr(mj, "filas", [])) else None
            foco = (pos == mj.foco and not terminado) if foco_2d is None else bool(foco_2d)
            self._resaltar(t, AGARRE if k == agarrada else (cp.AMARILLO if foco else None))
        self._pintar_botones(terminado)
        self._pintar_fin(terminado)
        if terminado:
            self._comprobado(dt)

    def _resaltar(self, t, tono):
        """Borde de la tarjeta: amarillo (foco, como hoy), cian (agarrada, como hoy) o ninguno."""
        if getattr(t, "_tono_res", None) == tono:
            return
        papel_3d.resaltar(t.papel, False)
        if tono is not None:
            papel_3d.resaltar(t.papel, True, tono=None if tono == cp.AMARILLO else tono,
                              grosor=0.012 * self.s if tono == AGARRE else papel_3d.GROSOR_RESALTADO)
        t._tono_res = tono

    def _vincular(self, orden):
        raton.desvincular()
        mj = self.minijuego
        filas = getattr(mj, "filas", [])
        for pos, k in enumerate(orden):
            if pos < len(filas) and self.tarjetas[k] is not None:
                raton.vincular(self.tarjetas[k].papel.hoja, getattr(filas[pos], "golpe", filas[pos]))
        for b in self.botones:
            raton.vincular(b.hoja, getattr(b.boton, "golpe", b.boton))
        self._vinculado = tuple(orden)

    def _pintar_botones(self, terminado):
        bajo = raton.pieza_bajo_cursor()
        for b in self.botones:
            habil = bool(getattr(b.boton, "habilitado", True)) and not terminado and bool(getattr(b.boton, "enabled", True))
            foco = bool(getattr(b.boton, "_foco", False)) and habil
            encima = bajo is b.hoja and habil
            estado = (habil, foco, encima)
            if estado == b.estado:
                continue
            b.estado = estado
            if not habil:
                tono = (190, 184, 172)
            elif encima:
                tono = (255, 232, 110) if b.primario else (255, 246, 214)
            else:
                tono = cp.AMARILLO if b.primario else cp.PAPEL
            b.cara.hoja.color = rgb(tono)
            papel_3d.resaltar(b, foco)

    def _pintar_fin(self, terminado):
        texto = self._texto_banda()
        if texto != self._banda_txt:
            self._banda_txt = texto
            cp.destruir(self.texto_banda)
            self.texto_banda = cp.texto_centrado(self.banda_fin, texto, cc.LINEA_CABECERA * self.s,
                                                 self.disp["vineta"][0] - 0.03 * self.s, 0.0, cp.PAPEL, negrita=True)

    # -- El personaje imita: descolgar, llevar, colgar, paso atrás --

    def _gestos(self, agarrada, orden, terminado, dt):
        corcho = self._corcho()
        if agarrada != self._agarrada:
            antes, self._agarrada = self._agarrada, agarrada
            if antes is not None and cp.vivo(self.tarjetas[antes]):        # la cuelga: el hilo de su balanceo
                t = self.tarjetas[antes]
                t.balanceo_t = 0.0
                pos = orden.index(antes)
                x, y, _ = self._sitio(pos)
                self.poses.alcanzar(corcho.mundo(x, y + self.disp["vineta"][1] / 2, -0.03), DUR_COLGAR)
                sonidos.sonar("colgar")
                self._colgar_t = 0.0
            if agarrada is not None:                                       # la descuelga: va hasta ella
                sonidos.sonar("papel", 0.6)
                self._colgar_t = None
                self._hueco_mano = None
        if agarrada is not None:
            pos = orden.index(agarrada)
            t = self.tarjetas[agarrada]
            if pos != getattr(self, "_hueco_mano", None):
                self._hueco_mano = pos
                x, y, _ = self._sitio(pos)
                self.caminar_cerca(corcho.mundo(x, y, 0), duracion_max=0.6)
            ax, ay, az = t.actual
            self.poses.mano_a(corcho.mundo(ax, ay + 0.04 * self.s, az - 0.025))
        elif self._colgar_t is not None:
            self._colgar_t += dt
            if self._colgar_t > DUR_COLGAR + 0.35:
                self._colgar_t = None
                if not terminado:
                    self.volver_al_reposo()

    def _comprobado(self, dt):
        if self._comprobado_t is None:
            self._comprobado_t = 0.0
            self.retirarse_ya(atras=0.35)              # se aparta deprisa y da un paso atrás para mirar (D1, 23-nov)
            return
        self._comprobado_t += dt
        if self._comprobado_t >= ESPERA_MARCAS and not self._marcas_puestas:
            self._marcas_puestas = True
            for k in range(self.n):                       # una tarjeta por frame (no un frame largo)
                self.obras.append(lambda k=k: self._asegurar(k))
            self.obras += [lambda pos=pos: self._marca(pos) for pos in range(self.n)]
            self.obras.append(self._sello_orden)

    def _marca(self, pos):
        """Marca de hoy en la tarjeta del hueco `pos`: palomita (en su puesto) o aspa + «ERA LA n.ª» (texto de la vista 2D)."""
        mj = self.minijuego
        p = mj.partida
        s = self.s
        k = p.orden[pos]
        t = self._asegurar(k)
        bien = bool(p.en_su_puesto()[pos])
        filas = getattr(mj, "filas", [])
        fila = filas[pos] if pos < len(filas) else None
        etiqueta = getattr(fila, "_etiqueta", None) or getattr(fila, "_etiqueta_propia", None)
        texto = "" if bien else marcas.etiqueta_marca("incorrecta", etiqueta)
        w, _ = self.disp["vineta"]
        alto = 0.058 * s
        lt = cc.LINEA_VINETA_MARCA * s                    # rótulo en MAYÚSCULAS: necesita más alto de línea (ver informe)
        while texto and alto + cp.ancho_texto(texto, lt, w * 2, True) + 0.03 * s > w - 0.02 * s and lt > cc.LINEA_MINIMA * s:
            lt -= 0.001 * s
        ancho = alto if bien else min(w - 0.02 * s, alto + cp.ancho_texto(texto, lt, w * 2, True) + 0.03 * s)
        x = -w / 2 + 0.015 * s + ancho / 2
        y = t.y_dibujo - t.alto_dibujo / 2 + alto / 2 + 0.008 * s
        marco = papel_3d.papel(t.papel, ancho, alto, posicion=(x, y), tono=cp.PAPEL, capa=4)
        cara = papel_3d.papel(marco, ancho - 0.008 * s, alto - 0.008 * s, tono=VERDE_MARCA if bien else ROJO_MARCA, capa=0)
        icono = Entity(parent=cara, position=(0 if bien else -ancho / 2 + alto / 2, 0, -0.002), ignore=True)
        for x1, y1, x2, y2 in (marcas.palomita(alto) if bien else marcas.aspa(alto)):
            cx, cy, largo, ang = marcas.trazo(x1, y1, x2, y2)
            cp.rect(icono, (cx, cy), (largo, 0.007 * s), cp.PAPEL, z=0.0, giro=-ang, iluminado=False)
        marco.texto = None
        if texto:
            marco.texto = cp.texto(cara, texto, lt, ancho * 1.3, cp.PAPEL, (-ancho / 2 + alto + 0.004 * s, lt * 1.32 / 2),
                                   negrita=True)
        t.marca = marco
        self.marcas.append(marco)
        if pos == 0:
            sonidos.sonar("clavar")

    def _sello_orden(self):
        if marcas.todo_en_orden(self.minijuego.partida.en_su_puesto()) and self.sello_orden is None:
            s = self.s
            self.sello_orden = cp.sello(self.tarjeta_fin, marcas.TEXTO_EN_ORDEN, (0, self.disp["vineta"][1] / 2 - 0.06 * s),
                                        VERDE_MARCA, 0.032 * s, giro=-4, capa=4)


CLASE_3D = Cronologia3D
