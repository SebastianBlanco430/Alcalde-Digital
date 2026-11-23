# «Señales de edición» en 3D (familia mesa): la misma mesa de madera con la LÁMPARA de escritorio encendida (luz cálida
# normal), una CAPTURA IMPRESA sobre la mesa (cada zona del caso es una burbuja de la captura) y una nota «PISTA» al lado;
# el protagonista, de pie junto a la mesa, sostiene un PLUMÓN ROJO: al marcar una zona (igual que hoy: clic, Enter o
# Espacio) la mano TRAZA un círculo rojo de tinta sobre el papel en 0,4 s, que queda pegado al papel. En reposo el
# plumón espera fuera de la captura y la otra mano cuelga junto al costado, detrás del borde de la mesa: ninguna mano
# tapa texto salvo la del plumón mientras traza (retoques 23-nov).
#
# El minijuego ES la vista 2D de hoy (MinijuegoSenales / SenalesVisual), viva y sin dibujar: las zonas salen de su partida
# (`partida.zonas`), el clic en una burbuja es el clic en su tarjeta (raton.vincular), las teclas llegan como siempre, la
# pista es el texto de la vista (lupa / revisión / contador) y los botones de abajo llaman a los de la vista. La captura
# se RECONSTRUYE con las mismas reglas de reparto de la vista visual (senales_piezas_calculos), con letra más grande
# (legibilidad en 3D). El máximo de marcas y desmarcar son los de hoy (la lógica es la de siempre).
# Bandera: ALCALDE_3D_SENALES (y la general ALCALDE_MINIJUEGOS_3D). Cualquier fallo -> la escena cae al 2D de hoy.

import math

from ursina import Entity, color

from frontend import estilo
from frontend.componentes import destruir_arbol, rgb
from frontend.minijuegos import ui as ui_2d
from frontend.minijuegos_3d import mesa_calculos as mc
from frontend.minijuegos_3d import mesa_piezas as mp
from frontend.minijuegos_3d import papel_3d, raton, sonidos
from frontend.minijuegos_3d.base import Minijuego3D
from frontend.minijuegos_visual import senales_piezas_calculos as sc
from frontend.piezas import MASCARA_LUZ

# Composición (rework-3d/familia-mesa/busqueda_senales*.py; la primera, con el personaje en el borde cercano, se probó en
# ventana y su cuerpo y su brazo tapaban media captura al dar el paso para llegar a las zonas): el personaje al otro lado
# de la mesa, de cara a la cámara; la captura en la banda del fondo (la que alcanza su mano); la cámara casi cenital desde
# el lado cercano. Nada del cuerpo tapa la captura; solo la mano con el plumón cuando dibuja.
PIE_SENALES = (-0.35, 1.19, 180.0)      # (x, z, rumbo) MUNDO: detrás de la mesa, mirando hacia la cámara
ESQUINA_ENTRADA = (-1.15, 1.19)         # rodea la mesa por la izquierda al entrar (no la atraviesa)
# Toma (corrección tras el verificador): más baja y más cerca (debajo de la lámpara de techo del set, que está en x 0,
# z 0,3, y = 2,3) y mirando a la banda cercana, para que la cabeza del personaje (también el afro de la influencer) quede
# POR ENCIMA de la captura en pantalla: con el torso derecho no la tapa (búsqueda en el informe).
TOMA = {"objetivo": (0.15, 0.25), "inclinacion": 80.0, "rumbo": 0.0, "distancia": 1.3, "fov": 55.0}
INCLINACION_TORSO = 0.0                  # grados: en Señales el torso NO se inclina (la cabeza taparía la captura)
CAPTURA = {"centro": (0.0, 0.295), "ancho": 0.70, "alto": 0.40}      # banda del fondo: al alcance de la mano
NOTA = {"x": 0.62, "arriba": 0.43, "ancho": 0.34}
ALTO_ZONA = 0.026                        # m de letra de las burbujas
ALTO_NOTA = 0.024
ALTO_TITULO = 0.024
ANCHO_ETIQUETA = 0.115                   # m de mesa a la vista entre el borde de la pantalla y la captura
ALTO_ETIQUETA_MIN = 0.020
ALTO_ETIQUETA_DOS = 0.022                 # en dos renglones: más baja (no pisa la etiqueta de la zona de al lado)
ALTO_ETIQUETA = 0.028                     # etiquetas del cierre, sobre la madera
BARRA = 0.05                              # barra amarilla de la captura (cuenta / título)
MARGEN = 0.012
PAPEL_VIEJO = (236, 224, 190)
AMARILLO = (255, 220, 60)
NOTA_TONO = (255, 236, 150)
ROJO = estilo.ESTADO_ERROR
VERDE = estilo.ESTADO_EXITO
GRIS = (130, 132, 140)
ALTURA_ESPERA = 0.07                      # m sobre el papel: el plumón espera encima de la zona con el foco
MANO_LIBRE = "i"                          # la que no lleva el plumón: cuelga junto al costado (poses.mano_reposo)


class Plumon(Entity):
    """Plumón rojo (cuerpo, capuchón y punta). Se coloca con la punta en un punto y el cuerpo hacia la mano."""

    def __init__(self, padre):
        super().__init__(parent=padre)
        from ursina.shaders import lit_with_shadows_shader
        Entity(parent=self, model="cube", color=rgb((200, 34, 40)), scale=(0.017, 0.017, 0.11), z=0.07,
               shader=lit_with_shadows_shader)
        Entity(parent=self, model="cube", color=rgb((240, 236, 228)), scale=(0.019, 0.019, 0.02), z=0.125,
               shader=lit_with_shadows_shader)
        Entity(parent=self, model="cube", color=rgb((150, 20, 26)), scale=(0.008, 0.008, 0.016), z=0.008,
               shader=lit_with_shadows_shader)

    def colocar(self, punta, mano):
        from panda3d.core import Point3
        if not (mc.finito(punta) and mc.finito(mano)) or math.dist(punta, mano) < 1e-4:
            return
        self.world_position = punta
        self.look_at(Point3(*mano))


class Senales3D(Minijuego3D):

    FAMILIA = "mesa"
    DIBUJAR_VISTA_2D = False
    MOSTRAR_AYUDA = True

    def _colocar_personaje(self):
        """Entra por la puerta, rodea la mesa por la izquierda y se pone detrás de ella, de cara a la cámara."""
        self.set.pie = PIE_SENALES
        p = self.poses
        x0, z0 = self.set.puerta
        x, z, rumbo = PIE_SENALES
        p.de_pie(x0, z0, 0.0)
        p.caminar_a(ESQUINA_ENTRADA[0], ESQUINA_ENTRADA[1], 90.0, duracion=self.DURACION_CAMINAR,
                    al_llegar=lambda: p.caminar_a(x, z, rumbo, duracion=0.6))

    def toma_juego(self):
        objetivo = self.set.anclas["mesa"].mundo(TOMA["objetivo"][0], TOMA["objetivo"][1], 0)
        return mc.toma_mesa(objetivo, TOMA["inclinacion"], TOMA["rumbo"], TOMA["distancia"], TOMA["fov"],
                            techo=self.set.techo)

    # -- Construcción --

    def construir(self):
        mj = self.minijuego
        mesa = self.mesa = self.set.anclas["mesa"]
        self.set.luz_techo(True)                 # lámpara y luz normal: sin oscuridad
        self.normal = mesa.datos_toma()["normal"]
        mp.tablero(mesa)
        cx, cy = CAPTURA["centro"]
        w, h = CAPTURA["ancho"], CAPTURA["alto"]
        self.hoja = papel_3d.papel(mesa.entidad, w, h, posicion=(cx, cy), giro=-1.2)
        caso = getattr(mj, "caso", None) or {}
        # marco del teléfono (tinta) y barra amarilla con el título de la captura
        mp_quad = lambda pos, esc, tono, z: Entity(parent=self.hoja, model="quad", position=(pos[0], pos[1], z),  # noqa: E731
                                                   scale=esc, color=rgb(tono), shader=self.hoja.hoja.shader)
        mp_quad((0, 0), (w - 0.02, h - 0.02), estilo.TINTA, -0.0004)
        mp_quad((0, 0), (w - 0.032, h - 0.032), estilo.PAPEL, -0.0006)
        yb = h / 2 - 0.016 - BARRA / 2
        mp_quad((0, yb), (w - 0.032, BARRA), AMARILLO, -0.0008)
        Entity(parent=self.hoja, model="circle", position=(-w / 2 + 0.05, yb, -0.001), scale=0.036, color=rgb(estilo.TINTA),
               shader=self.hoja.hoja.shader)
        titulo = "Captura que circula: " + str(caso.get("titulo", ""))
        self.titulo = papel_3d.texto_en_papel(self.hoja, titulo, alto_linea=ALTO_TITULO, ancho=w - 0.14, negrita=True,
                                              posicion=(-w / 2 + 0.08, yb + ALTO_TITULO * 0.62))
        # burbujas: mismas reglas de reparto que la vista visual (senales_piezas_calculos), en metros
        zonas = mj.partida.zonas
        area = w - 0.06
        anchos = [sc.ancho_burbuja(max(mp.ancho_mayor(l, ALTO_ZONA, area - 0.03) for l in str(z["texto"]).split("\n")),
                                   area, minimo=0.24, margen=0.014, reserva=0.0) for z in zonas]
        altos = [mp.n_lineas(z["texto"], ALTO_ZONA, anchos[i] - 0.028) * ALTO_ZONA * mc.LINEA + 0.014
                 for i, z in enumerate(zonas)]
        arriba = yb - BARRA / 2 - 0.012
        abajo = -h / 2 + 0.022
        altos, centros = sc.repartir(altos, arriba, abajo, hueco=0.008, tope_extra=0.006)
        self.burbujas = []
        for i, z in enumerate(zonas):
            x = sc.x_burbuja(anchos[i], area, 0.0, sc.lado_de(i, z["texto"]))
            b = Entity(parent=self.hoja, position=(x, centros[i], 0))
            b.ancho, b.alto = anchos[i], altos[i]
            b.foco = Entity(parent=b, model="quad", scale=(anchos[i] + 0.014, altos[i] + 0.014), z=-0.0009,
                            color=rgb(AMARILLO), shader=self.hoja.hoja.shader)
            b.foco.enabled = False
            Entity(parent=b, model="quad", scale=(anchos[i] + 0.005, altos[i] + 0.005), z=-0.0010, color=rgb(estilo.TINTA),
                   shader=self.hoja.hoja.shader)
            Entity(parent=b, model="quad", scale=(anchos[i], altos[i]), z=-0.0011, color=rgb(PAPEL_VIEJO),
                   shader=self.hoja.hoja.shader)
            b.texto = papel_3d.texto_en_papel(self.hoja, z["texto"], alto_linea=ALTO_ZONA, ancho=anchos[i] - 0.028,
                                              posicion=(x - anchos[i] / 2 + 0.014, centros[i] + altos[i] / 2 - 0.007))
            b.golpe = Entity(parent=b, model="quad", scale=(anchos[i], altos[i]), z=-0.003, collider="box", visible=False)
            raton.vincular(b.golpe, mj.tarjetas[i].golpe)          # clic en la burbuja = clic en su tarjeta 2D
            b.trazo = None
            b.cierre = None
            self.burbujas.append(b)
        # nota «PISTA» con el texto de la vista 2D
        self.nota = None
        self._nota_textos = None
        self._pintar_nota()
        # plumón en la mano y alcance
        d = mesa.datos_toma()
        self.poses.limitar(d["centro"], d["normal"])
        if hasattr(self.poses, "inclinacion_max"):        # poses_3d (tanda 2): tope de inclinación del torso por instancia
            self.poses.inclinacion_max = INCLINACION_TORSO
        self.plumon = Plumon(self.set.raiz)
        self.plumon.enabled = False
        for e in [self.plumon, *self.plumon.children]:
            e.hide(MASCARA_LUZ)
        self._marcadas = set()
        self._trazando = []                     # [(burbuja, t)]
        self._volver_pendiente = False          # tras trazar: volver a PIE_SENALES si dio un paso de lado
        self._botones = None

    # -- Nota «PISTA» --

    def _textos_nota(self):
        mj = self.minijuego
        titulo = getattr(getattr(mj, "lupa_titulo", None), "text", "") or "Pista"
        cuerpo = getattr(getattr(mj, "lupa", None), "text", "") or ""
        revision = getattr(getattr(mj, "revision", None), "text", "") or ""
        marcas = getattr(getattr(mj, "marcas_txt", None), "text", "") or ""
        cuerpo = " ".join(cuerpo.split())
        revision = revision.replace("\n  ", " ").strip()
        return (str(titulo), cuerpo, revision, str(marcas))

    def _pintar_nota(self):
        textos = self._textos_nota()
        if textos == self._nota_textos:
            return
        self._nota_textos = textos
        if self.nota is not None:
            destruir_arbol(self.nota)
        titulo, cuerpo, revision, marcas = textos
        ancho = NOTA["ancho"]
        ancho_txt = ancho - 0.04
        bloques = [(titulo, ALTO_TITULO, True)]
        if revision:
            bloques += [(r, ALTO_NOTA, False) for r in revision.split("\n") if r.strip()]
        elif cuerpo:
            bloques.append((cuerpo, ALTO_NOTA, False))
        if marcas:
            bloques.append((marcas, ALTO_NOTA, True))
        alto = 0.03 + sum(mp.n_lineas(t, a, ancho_txt, n) * a * mc.LINEA + 0.01 for t, a, n in bloques)
        self.nota = papel_3d.papel(self.mesa.entidad, ancho, alto, posicion=(NOTA["x"], NOTA["arriba"] - alto / 2), giro=1.5,
                                   tono=NOTA_TONO, capa=1)
        y = alto / 2 - 0.015
        for t, a, negrita in bloques:
            texto = papel_3d.texto_en_papel(self.nota, t, alto_linea=a, ancho=ancho_txt, negrita=negrita,
                                            posicion=(-ancho_txt / 2, y))
            y -= texto.alto + 0.01

    # -- Capa en pantalla: los dos botones de la vista 2D --

    def _montar_capa(self):
        if self.capa is None or self._botones is not None:
            return
        mj = self.minijuego
        conf = ui_2d.Boton(self._etiqueta(mj.boton_confirmar), lambda: self._pulsar("boton_confirmar"), 0.40, 0.075, 18,
                           primario=True, parent=self.capa, position=(0.2, -0.39, -0.01))
        clase = getattr(ui_2d, "BotonTinta", ui_2d.Boton)
        nada = clase(self._etiqueta(mj.boton_nada), lambda: self._pulsar("boton_nada"), 0.40, 0.075, 18,
                     parent=self.capa, position=(0.64, -0.39, -0.01))
        self._botones = {"boton_confirmar": conf, "boton_nada": nada}

    @staticmethod
    def _etiqueta(boton):
        return getattr(boton, "_etiqueta", "") or getattr(getattr(boton, "texto", None), "text", "")

    def _pulsar(self, nombre):
        boton = getattr(self.minijuego, nombre, None)
        if boton is not None:
            boton._clic()

    def _reflejar_botones(self):
        mj = self.minijuego
        for nombre, propio in self._botones.items():
            b = getattr(mj, nombre, None)
            if b is None:
                continue
            foco = b in mj.focables and mj.foco == mj.focables.index(b) and not mj.terminado
            habil = bool(getattr(b, "habilitado", True))
            if propio._foco != foco or propio.habilitado != habil or propio._etiqueta != self._etiqueta(b):
                propio.habilitado = habil
                propio._etiqueta = self._etiqueta(b)
                propio.fijar_foco(foco)

    # -- Cada frame --

    def avanzar_3d(self, dt):
        mj = self.minijuego
        self._montar_capa()
        if self._botones is not None and self.resultado_3d is None:
            self._reflejar_botones()
        self._pintar_nota()
        f = mj.foco if (not mj.terminado and mj.focables and mj.foco < len(self.burbujas)) else None
        for i, b in enumerate(self.burbujas):
            b.foco.enabled = i == f
        if self.resultado_3d is None:
            self._reflejar_marcas()
        self._avanzar_trazos(dt)
        self._mover_mano(f, dt)

    def _reflejar_marcas(self):
        marcadas = set(getattr(self.minijuego.partida, "marcadas", ()))
        for i in sorted(marcadas - self._marcadas):
            b = self.burbujas[i]
            if b.trazo is not None:
                destruir_arbol(b.trazo)
            b.trazo = mp.Trazo(self.hoja, (b.x, b.y), b.ancho / 2 + 0.018, b.alto / 2 + 0.014, inicio=100.0 + 37 * i)
            self._trazando.append([b, 0.0])
            sonidos.sonar("trazo")
        for i in self._marcadas - marcadas:
            b = self.burbujas[i]
            self._trazando = [t for t in self._trazando if t[0] is not b]
            if b.trazo is not None:
                destruir_arbol(b.trazo)
                b.trazo = None
        self._marcadas = marcadas

    def _avanzar_trazos(self, dt):
        habia = bool(self._trazando)
        for item in list(self._trazando):
            item[1] += dt
            item[0].trazo.progreso(mc.progreso_trazo(item[1]))
            if item[1] >= mc.DURACION_TRAZO:
                self._trazando.remove(item)
        if habia and not self._trazando:
            self._volver_pendiente = True
        if self._trazando:
            self._volver_pendiente = False
        elif getattr(self, "_volver_pendiente", False):
            self._volver_al_pie()

    def _volver_al_pie(self):
        """Tras trazar, si dio un paso de lado para llegar a la zona, vuelve a su sitio (sin girarse) en cuanto termina
        ese paso: desplazado, su torso quedaba encima de la barra del título de la captura (retoques 23-nov)."""
        p = self.poses
        if getattr(p, "_camino", None) is not None or not self.listo or self.resultado_3d is not None:
            return
        self._volver_pendiente = False
        x, z, rumbo = PIE_SENALES
        base = self.set.personaje.world_position
        if math.hypot(base[0] - x, base[2] - z) > 0.03:
            p.caminar_a(x, z, rumbo, duracion=0.5, girar=False)

    def _mover_mano(self, f, dt=1 / 60):
        if not self.listo or self.resultado_3d is not None:
            return
        self._mano_libre_en_reposo()
        n = self.normal
        reposo = None if self._trazando else self.poses.mano_reposo("d")
        if self._trazando:
            b = self._trazando[-1][0]
            x, y = b.trazo.punta()
            punta = self._mundo_hoja(x, y, -0.004)
        elif reposo is not None and mc.finito(reposo):
            # en reposo la mano del plumón cuelga junto al costado, detrás del borde de la mesa (como la otra): ni la mano
            # ni el plumón tapan la captura, y el personaje no da pasos para «esperar» encima de una zona lejana. Solo
            # entra en la captura mientras traza (retoques 23-nov)
            r = math.radians(getattr(self.set.personaje, "rumbo", 0.0))
            adelante = (math.sin(r), 0.0, math.cos(r))
            punta = tuple(reposo[i] - n[i] * 0.11 + adelante[i] * 0.08 for i in range(3))   # inversa de _mano_para
        elif f is not None:
            # en reposo el plumón espera FUERA de la captura, en el borde de su lado, a la altura (x) de la zona con foco:
            # la mano y el brazo no tapan la captura hasta que traza
            b = self.burbujas[f]
            p = self._mundo_hoja(b.x, CAPTURA["alto"] / 2 + 0.05, -0.004)
            punta = tuple(p[i] + n[i] * ALTURA_ESPERA for i in range(3))
        else:
            punta = self._mundo_hoja(-0.1, CAPTURA["alto"] / 2 + 0.04, -0.004)      # junto al borde de su lado
            punta = tuple(punta[i] + n[i] * ALTURA_ESPERA for i in range(3))
        mano = self._mano_para(punta)
        if not mc.finito(mano):
            return
        self.poses.mano_a(mano, "d")
        real = self._mano_real() or mano
        # la punta va donde llega la mano (si aún no llega, el plumón viaja con ella: nunca flota separado)
        punta_real = tuple(punta[i] + (real[i] - mano[i]) for i in range(3))
        # nunca por debajo del papel (la tinta va 2,5 mm encima: la punta, a 3 mm como mínimo)
        base = self._mundo_hoja(0.0, 0.0, -0.003)
        h = sum((punta_real[i] - base[i]) * n[i] for i in range(3))
        if h < 0:
            punta_real = tuple(punta_real[i] - n[i] * h for i in range(3))
        self.plumon.enabled = True
        self.plumon.colocar(punta_real, real)

    def _mano_libre_en_reposo(self):
        """La mano que NO lleva el plumón cuelga junto al costado, detrás del borde de la mesa. Antes la dejaba la
        animación (Idle): con el personaje pegado al borde, adelantaba los dedos ~17 cm y en la toma casi cenital caían
        sobre la barra del título de la captura («Una cadena de «premios»»), también en reposo (retoques 23-nov)."""
        punto = self.poses.mano_reposo(MANO_LIBRE)
        if punto is not None and mc.finito(punto):
            self.poses.mano_a(punto, MANO_LIBRE)

    def _mundo_hoja(self, x, y, z):
        from ursina import scene
        p = scene.getRelativePoint(self.hoja, (x, y, z))
        return (p[0], p[1], p[2])

    def _mano_para(self, punta):
        """Mano 11 cm por encima de la punta y 8 cm hacia el cuerpo: el plumón va inclinado (desde arriba se ve entero, no
        queda escondido bajo la mano)."""
        r = math.radians(getattr(self.set.personaje, "rumbo", 0.0))
        adelante = (math.sin(r), 0.0, math.cos(r))
        n = self.normal
        return tuple(punta[i] + n[i] * 0.11 - adelante[i] * 0.08 for i in range(3))

    def _mano_real(self):
        try:
            from ursina import scene
            nodo = self.set.personaje.mano("d")
            if nodo is None:
                return None
            q = nodo.getPos(scene)
            q = (q[0], q[1], q[2])
            return q if mc.finito(q) else None
        except Exception:                # noqa: BLE001
            return None

    # -- Cierre --

    def al_resultado(self, resultado):
        self.plumon.enabled = False
        # la base suelta los dos brazos a la animación: colgarían sobre la captura (que ahora enseña la revisión); van
        # juntos al costado, sin salto (alcanzar parte de donde está la mano)
        for lado in ("d", MANO_LIBRE):
            punto = self.poses.mano_reposo(lado)
            if punto is not None and mc.finito(punto):
                self.poses.alcanzar(punto, 0.4, None, lado, altura=0.0)
        for b in (self._botones or {}).values():
            b.enabled = False
        for i, t in enumerate(self.minijuego.tarjetas):
            b = self.burbujas[i]
            b.foco.enabled = False
            estado = getattr(t, "estado", "normal")
            texto = getattr(getattr(t, "etiqueta", None), "text", "") or ""
            if estado == "encontrada":
                self._etiqueta_cierre(b, texto or "LA VISTE", VERDE)
            elif estado == "perdida":
                mp.aro(self.hoja, b.ancho / 2 + 0.02, b.alto / 2 + 0.016, VERDE, posicion=(b.x, b.y, -0.0026),
                       discontinuo=True)
                self._etiqueta_cierre(b, texto or "SE TE PASÓ", VERDE)
            elif estado == "falsa_alarma":
                mp.plano(self.hoja, (b.ancho * 0.7, 0.006), GRIS, (b.x, b.y, -0.003), giro=-8)
                self._etiqueta_cierre(b, texto or "ESTABA BIEN", GRIS)

    def _etiqueta_cierre(self, b, texto, tono):
        """Etiqueta del cierre (la de la tarjeta 2D: «LA VISTE», «SE TE PASÓ», «ESTABA BIEN») a la izquierda de la
        captura, a la altura de su burbuja: no tapa el texto de la zona."""
        # entre el borde izquierdo de la pantalla y la captura caben ~0,12 m de mesa (toma de juego): la etiqueta se parte
        # por palabras y la letra baja lo justo para que la palabra más larga quepa; va pegada a la captura
        ancho = ANCHO_ETIQUETA
        # un renglón si cabe con letra >= ALTO_ETIQUETA_MIN (las etiquetas de zonas seguidas no se pisan); si no, por palabras
        alto = (mp.alto_que_cabe(texto, ALTO_ETIQUETA, ALTO_ETIQUETA_MIN, ancho, True, entero=True)
                or mp.alto_que_cabe(texto, ALTO_ETIQUETA_DOS, ALTO_ETIQUETA_MIN, ancho, True))
        lineas = mp.n_lineas(texto, alto, ancho, True)
        usado = mp.ancho_mayor(texto, alto, ancho, True)
        return papel_3d.texto_en_papel(self.hoja, texto, alto_linea=alto, ancho=ancho, negrita=True,
                                       tono=estilo.tono_legible(tono, (196, 150, 104)),
                                       posicion=(-self.hoja.ancho / 2 - usado - 0.012,
                                                 b.y + lineas * alto * mc.LINEA / 2))

    def destruir(self):
        raton.desvincular()


CLASE_3D = Senales3D
