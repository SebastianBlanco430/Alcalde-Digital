# «Rastrear la fuente» en 3D (familia corcho). El minijuego es la vista 2D de hoy (RastrearVisual / MinijuegoRastrear),
# viva y oculta: recibe las teclas como siempre y decide todo. Aquí solo se REFLEJA su estado en un tablero de corcho:
#   - arriba a la izquierda, el rumor (tira con la etiqueta roja «RUMOR»); arriba a la derecha, la polaroid «TÚ»;
#   - la CADENA: cada salto acertado clava una nota (quién y hora) a la izquierda de «TÚ», con un hilo rojo que se tensa;
#   - la tarjeta de la pregunta del salto con los círculos de ronda; a su derecha los ovillos y «INTENTOS: n de 2»;
#   - abajo, las 3 notas candidatas (cabecera amarilla con número, quién y hora; texto; sello «REENVIADO»), la enfocada
#     con el borde amarillo. Mouse: cada nota 3D está VINCULADA a la nota 2D (hover = foco, clic = elegir).
# Al elegir (1/2/3, Enter, clic, mando) el personaje va a la nota, la toma, la sube y la clava en la cadena (acierto) o la
# clava en su sitio y le pone una X roja (error). Los gestos van en una cola: la lógica nunca espera (si llega otro, el de
# curso termina al instante). En reposo el personaje está a la izquierda, FUERA del corcho: no tapa nada.
#
# RENDIMIENTO: todo lo que puede llegar a verse (candidatas de cada salto, tarjetas de la pregunta, rótulos de intentos,
# eslabones, hilos, origen, sello FUENTE) se construye OCULTO al abrir: lo del estado actual en construir() y el resto unas
# pocas piezas por frame durante la transición de entrada. Al jugar solo se muestran u ocultan: el frame en que la vista 2D
# decide (y rehace sus propias notas) no paga construcción 3D. Si algo aún no está hecho cuando hace falta, se hace ahí.

import math
import time

from ursina import Entity

from frontend.minijuegos.rastrear_calculos import MAX_ERRORES
from frontend.minijuegos_3d import camaras_calculos as ccal
from frontend.minijuegos_3d import corcho_calculos as cc
from frontend.minijuegos_3d import corcho_piezas as cp
from frontend.minijuegos_3d import papel_3d, raton, sonidos
from frontend.minijuegos_3d.corcho_base import Corcho3D

DUR_TOMAR = 0.30
DUR_LLEVAR = 0.70
DUR_CLAVAR = 0.80
DUR_PAUSA = 0.15
LEVANTAR = 0.07            # m que se separa del corcho la nota mientras viaja (no atraviesa otras notas)
PRESUPUESTO_OBRAS = 0.006  # s por frame para construir piezas ocultas


class _Gesto:

    def __init__(self, tipo, salto, opcion):
        self.tipo = tipo                 # "bien" | "error"
        self.salto = salto
        self.opcion = opcion
        self.fase = None
        self.t = 0.0
        self.dur = 0.0
        self.pieza = None                # bien: el eslabón que viaja a la cadena; error: la nota candidata
        self.desde = None                # (x, y) local de partida de la pieza
        self.hasta = None                # (x, y) local del eslabón
        self.hecho = False               # su efecto visual (chincheta + hilo / X roja) ya se aplicó


class Rastrear3D(Corcho3D):

    # -- Construcción --

    def construir(self):
        corcho = self.preparar_corcho()
        partida = self.minijuego.partida
        self.disp = cc.disposicion_rastrear(corcho.ancho, corcho.alto)
        self.s = self.disp["s"]
        self.tira_rumor(self.disp["rumor"], self.disp["rumor_etiqueta_w"], cc.LINEA_RUMOR * self.s)
        self.texto_rumor = self.tira.texto
        self.hueco_sello = self.disp["hueco_sello"]
        cp.polaroid_tu(self.raiz, self.disp)
        self._intentos()
        self.rondas = {}                  # salto -> [notas candidatas]
        self.preguntas = {}               # clave -> tarjeta de la pregunta
        self.rotulos_intentos = {}        # restantes -> Text
        self.eslabones = {}               # salto -> nota de la cadena (oculta hasta que se acierta)
        self.cadena = {}                  # salto -> eslabón ya clavado
        self.hilos = {}                   # salto -> [Cinta, t de tensado o None]
        self.notas = []                   # candidatas visibles
        self.indice_notas = None
        self.focables_vinculados = None
        self.tarjeta_pregunta = None
        self.texto_pregunta = None
        self.texto_intentos = None
        self._clave_pregunta = None
        self.origen = None
        self.fuente = None
        self.cola = cc.ColaGestos()
        self._cerrado = False                 # True: gestos cerrados tras el resultado
        self._foto = cc.foto_rastreo(partida)
        self.obras = []
        self._sincronizar()
        for k in range(len(partida.saltos)):
            self.obras += [lambda k=k: self._ronda(k), lambda k=k: self._pregunta(k), lambda k=k: self._eslabon(k)]
        self.obras += [lambda: self._pregunta("llegado"), lambda: self._pregunta("perdido"), self._origen_oculto,
                       self._fuente_oculta]
        self.obras += [lambda r=r: self._rotulo_intentos(r) for r in range(len(self.ovillos) + 1)]

    def _obrar(self, presupuesto=PRESUPUESTO_OBRAS):
        """Construye piezas pendientes hasta gastar `presupuesto` s de este frame."""
        t0 = time.perf_counter()
        while self.obras and time.perf_counter() - t0 < presupuesto:
            self.obras.pop(0)()

    def _intentos(self):
        s = self.s
        x, y = self.disp["intentos"]
        n = max(1, MAX_ERRORES - 1)
        self.ovillos = []
        for k in range(n):
            ox = x + (k - (n - 1) / 2) * 0.10 * s
            raiz = Entity(parent=self.raiz, position=(ox, y + 0.05 * s, papel_3d.Z_PAPEL), ignore=True)
            cp.circulo(raiz, (0, 0), 0.058 * s, cp.TINTA, z=0.0)
            bola = cp.circulo(raiz, (0, 0), 0.048 * s, cp.ROJO, z=-0.001)
            x_perdido = cp.aspa(raiz, 0.05 * s, 0.05 * s, cp.TINTA, grosor=0.008 * s, z=-0.003)
            x_perdido.enabled = False
            self.ovillos.append((bola, x_perdido))
        self.etiqueta_intentos = papel_3d.papel(self.raiz, 0.34 * s, 0.075 * s, posicion=(x, y - 0.04 * s), giro=0.5)
        self._restantes = None

    # -- Cada frame: reflejar la vista 2D --

    def avanzar_3d(self, dt):
        partida = self.minijuego.partida
        foto = cc.foto_rastreo(partida)
        if foto != self._foto:
            # La vista 2D acaba de decidir (y de rehacer sus notas: su frame más pesado). El 3D reacciona en el frame
            # SIGUIENTE (16 ms después, invisible) para no sumar su trabajo a ese frame. El mouse se desvincula ya: sus
            # objetivos 2D se acaban de destruir.
            for tipo, salto, opcion in cc.eventos_rastreo(self._foto, foto, partida):
                self._encolar(tipo, salto, opcion)
            self._foto = foto
            raton.desvincular()
            self.focables_vinculados = None
            if self.resultado_3d is None:
                return
            self._cerrado = False                 # con el resultado ya en pantalla: estos gestos se cierran ya
        self._sincronizar()
        if self.resultado_3d is not None and not self._cerrado:
            self._cerrar_gestos()
        self._avanzar_gestos(dt)
        self._avanzar_hilos(dt)
        if self.obras:
            self._obrar()
        self.avanzar_sello()

    def _sincronizar(self):
        mj = self.minijuego
        partida = mj.partida
        salto = partida.salto_actual()
        if salto is not None and self.indice_notas != partida.indice:
            self._mostrar_ronda(partida.indice)
        elif salto is None and self.notas and partida.llegado:
            self._quitar_candidatas()
        if partida.llegado:
            origen = self._origen_oculto()
            if origen is not None and not origen.enabled:
                origen.enabled = True
        self._pintar_pregunta(partida, salto)
        self._pintar_intentos(partida)
        if self.focables_vinculados is not mj.focables:     # la vista 2D rehace sus notas en cada elección
            self._vincular()
        for i, nota in enumerate(self.notas):
            foco = (i == mj.foco and not mj.terminado and i < len(mj.focables)
                    and getattr(mj.focables[i], "habilitada", True) and not nota.descartada)
            papel_3d.resaltar(nota, foco)

    def _vincular(self):
        raton.desvincular()
        focables = self.minijuego.focables
        for i, nota in enumerate(self.notas):
            if i < len(focables):
                raton.vincular(nota.hoja, getattr(focables[i], "golpe", focables[i]))
        self.focables_vinculados = focables

    # -- Candidatas --

    def _quitar_candidatas(self):
        for g in self._gestos_vivos():           # una X pendiente sobre una ronda que ya pasó no tiene dónde ir
            if g.tipo == "error" and any(g.pieza is n for n in self.notas):
                g.pieza = None
        for nota in self.notas:
            if cp.vivo(nota):
                papel_3d.resaltar(nota, False)
                nota.enabled = False
        self.notas = []
        self.indice_notas = None
        raton.desvincular()
        self.focables_vinculados = None

    def _ronda(self, k):
        """Las 3 candidatas del salto k (ocultas mientras no sea el actual)."""
        if k in self.rondas:
            return self.rondas[k]
        disp = self.disp
        notas = []
        for i, opcion in enumerate(self.minijuego.partida.saltos[k]["opciones"][:3]):
            nota = self._nota_candidata(opcion, i + 1, disp["notas_x"][i], disp["notas_arriba"], disp["giros"][i])
            nota.enabled = False
            notas.append(nota)
        self.rondas[k] = notas
        return notas

    def _mostrar_ronda(self, indice):
        self._quitar_candidatas()
        salto = self.minijuego.partida.saltos[indice]
        self.notas = list(self._ronda(indice))
        for i, nota in enumerate(self.notas):
            nota.enabled = True
            if i in salto["descartadas"]:
                self._descartar(nota)
        self.indice_notas = indice
        self.focables_vinculados = None

    def _nota_candidata(self, opcion, numero, x, arriba, giro):
        s = self.s
        w = self.disp["nota_w"]
        margen = 0.022 * s
        ancho_txt = w - 2 * margen
        lc, lb = cc.LINEA_CABECERA * s, cc.LINEA_CUERPO * s
        cabecera = texto_cabecera(numero, opcion, lc, ancho_txt)
        n_cab = cp.lineas(cabecera, lc, ancho_txt, True)
        cuerpo = str(opcion.get("texto", ""))
        n_cue = cp.lineas(cuerpo, lb, ancho_txt)
        reenvio = "reenviado" in cuerpo.lower()           # el mismo criterio que la vista 2D (sello «REENVIADO»)
        alto_cab = cp.alto_texto(n_cab, lc) + 0.026 * s
        alto_sello = 0.075 * s if reenvio else 0.0
        h = max(alto_cab + 0.022 * s + cp.alto_texto(n_cue, lb) + 0.03 * s + alto_sello, 0.24 * s)
        nota = papel_3d.papel(self.raiz, w, h, posicion=(x, arriba - h / 2), giro=giro)
        nota.ignore = True
        banda = papel_3d.papel(nota, w, alto_cab, posicion=(0, h / 2 - alto_cab / 2), tono=cp.AMARILLO)
        nota.cabecera = cp.texto(banda, cabecera, lc, ancho_txt, cp.TINTA, (-w / 2 + margen, cp.alto_texto(n_cab, lc) / 2),
                                 negrita=True)
        nota.cuerpo = cp.texto(nota, cuerpo, lb, ancho_txt, cp.TINTA, (-w / 2 + margen, h / 2 - alto_cab - 0.02 * s))
        nota.banda = banda
        if reenvio:
            cp.sello(nota, "REENVIADO", (w / 2 - 0.15 * s, -h / 2 + 0.05 * s), cp.ROJO, 0.028 * s, giro=-6, capa=2)
        nota.pin = (0, h / 2 - 0.002 * s)            # en el borde de arriba: no tapa el texto de la cabecera
        papel_3d.chincheta(nota, nota.pin, (150, 150, 165)).ignore = True
        nota.hoja.collider = "box"
        nota.descartada = False
        nota.marca = cp.aspa(nota, w, h, cp.ROJO, grosor=0.02 * s)
        nota.marca.enabled = False
        return nota

    def _descartar(self, nota):
        """Estado «descartada» (lo que hoy resta un intento): papel apagado y una X roja encima."""
        if not cp.vivo(nota) or nota.descartada:
            return
        nota.descartada = True
        nota.hoja.color = cp.rgb(cp.GRIS_PAPEL)
        nota.banda.hoja.color = cp.rgb((206, 184, 96))
        nota.marca.enabled = True
        papel_3d.resaltar(nota, False)

    # -- Pregunta, intentos, origen --

    def _pintar_pregunta(self, partida, salto):
        clave = partida.indice if salto is not None else ("llegado" if partida.llegado else "perdido")
        if clave == self._clave_pregunta:
            return
        self._clave_pregunta = clave
        if cp.vivo(self.tarjeta_pregunta):
            self.tarjeta_pregunta.enabled = False
        self.tarjeta_pregunta = self._pregunta(clave)
        self.tarjeta_pregunta.enabled = True
        self.texto_pregunta = self.tarjeta_pregunta.texto

    def _pregunta(self, clave):
        """Tarjeta de la pregunta del salto `clave` (o 'llegado' / 'perdido') con los círculos de ronda (oculta)."""
        if clave in self.preguntas:
            return self.preguntas[clave]
        partida = self.minijuego.partida
        total = len(partida.saltos)
        if clave == "llegado":
            cadena, hechos, actual = "Llegaste al origen.", total, None
        elif clave == "perdido":
            cadena, hechos, actual = "Perdiste el rastro: demasiados mensajes equivocados.", partida.indice, None
        else:
            cadena, hechos, actual = partida.saltos[clave]["pregunta"], clave, clave
        s = self.s
        cx, cy, w, h = self.disp["pregunta"]
        x_txt = -w / 2 + 0.035 * s + total * 0.038 * s + 0.02 * s
        ancho_txt = w / 2 - x_txt - 0.03 * s
        lt = cc.LINEA_TITULO * s
        n = cp.lineas(cadena, lt, ancho_txt)
        h = max(h, cp.alto_texto(n, lt) + 0.04 * s)
        tarjeta = papel_3d.papel(self.raiz, w, h, posicion=(cx, cy), giro=0.2)
        for k in range(total):
            x = -w / 2 + 0.035 * s + k * 0.038 * s
            cp.circulo(tarjeta, (x, 0), (0.03 if k == actual else 0.026) * s, cp.TINTA, z=-0.001)
            if k >= hechos:
                cp.circulo(tarjeta, (x, 0), (0.02 if k == actual else 0.017) * s,
                           cp.AMARILLO if k == actual else cp.PAPEL, z=-0.002)
        tarjeta.texto = cp.texto(tarjeta, cadena, lt, ancho_txt, cp.TINTA, (x_txt, cp.alto_texto(n, lt) / 2))
        tarjeta.ignore = True
        tarjeta.enabled = False
        self.preguntas[clave] = tarjeta
        return tarjeta

    def _pintar_intentos(self, partida):
        restantes = max(0, MAX_ERRORES - 1 - partida.errores)
        if restantes == self._restantes:
            return
        self._restantes = restantes
        for k, (bola, x_perdido) in enumerate(self.ovillos):
            vivo = k < restantes
            bola.color = cp.rgb(cp.ROJO if vivo else (214, 200, 168))
            x_perdido.enabled = not vivo
        for t in self.rotulos_intentos.values():
            t.enabled = False
        self.texto_intentos = self._rotulo_intentos(restantes)
        self.texto_intentos.enabled = True

    def _rotulo_intentos(self, restantes):
        if restantes not in self.rotulos_intentos:
            t = cp.texto_centrado(self.etiqueta_intentos, f"INTENTOS: {restantes} de {len(self.ovillos)}",
                                  cc.LINEA_INTENTOS * self.s, 0.33 * self.s, 0.0, cp.TINTA, negrita=True)
            t.enabled = restantes == self._restantes
            self.rotulos_intentos[restantes] = t
        return self.rotulos_intentos[restantes]

    def _origen_oculto(self):
        """Tarjeta del origen (título y detalle del caso, lo que la vista 2D enseña al llegar), oculta hasta llegar."""
        if self.origen is not None:
            return self.origen
        partida = self.minijuego.partida
        origen = partida.origen() or (partida.caso or {}).get("origen")
        if not isinstance(origen, dict) or "titulo" not in origen:
            return None
        s = self.s
        cx, cy, w, h = self.disp["origen"]
        lt, lb = cc.LINEA_RUMOR * s, cc.LINEA_CUERPO * s
        titulo, detalle = str(origen.get("titulo", "")), str(origen.get("detalle", ""))
        ancho_txt = w - 0.08 * s
        nt, nd = cp.lineas(titulo, lt, ancho_txt, True), cp.lineas(detalle, lb, ancho_txt)
        h = max(h, cp.alto_texto(nt, lt) + cp.alto_texto(nd, lb) + 0.14 * s)
        tarjeta = papel_3d.papel(self.raiz, w, h, posicion=(cx, self.disp["notas_arriba"] - h / 2), giro=-0.4)
        y = h / 2 - 0.03 * s
        tarjeta.titulo = cp.texto(tarjeta, titulo, lt, ancho_txt, cp.TINTA, (-w / 2 + 0.04 * s, y), negrita=True)
        y -= cp.alto_texto(nt, lt) + 0.012 * s
        tarjeta.detalle = cp.texto(tarjeta, detalle, lb, ancho_txt, cp.TINTA, (-w / 2 + 0.04 * s, y))
        cp.sello(tarjeta, "LLEGASTE AL ORIGEN", (w / 2 - 0.30 * s, -h / 2 + 0.05 * s), cp.VERDE, 0.03 * s, giro=-4)
        papel_3d.chincheta(tarjeta, (0, h / 2 - 0.016 * s)).ignore = True
        tarjeta.ignore = True
        tarjeta.enabled = False
        self.origen = tarjeta
        return tarjeta

    def _fuente_oculta(self):
        if self.fuente is None:
            xs = cc.posiciones_cadena(len(self.minijuego.partida.saltos), self.disp)
            w, h = self.disp["cadena_nota"]
            self.fuente = cp.sello(self.raiz, "FUENTE", (xs[-1], self.disp["cadena_y"] - h / 2 - 0.02 * self.s),
                                   cp.TINTA, 0.03 * self.s, giro=-6, capa=4)
            self.fuente.enabled = False
        return self.fuente

    # -- Cadena --

    def _eslabon(self, salto):
        """Nota de la cadena del salto (quién y hora de la opción correcta), oculta; su chincheta verde y su hilo también.
        Cuando se acierta, viaja desde la candidata (capa 12: delante de todo lo del corcho)."""
        if salto in self.eslabones:
            return self.eslabones[salto]
        s = self.s
        datos_salto = self.minijuego.partida.saltos[salto]
        datos = datos_salto["opciones"][datos_salto["correcta"]]
        w, h = self.disp["cadena_nota"]
        nota = papel_3d.papel(self.raiz, w, h, posicion=(0.0, self.disp["cadena_y"]), giro=_giro(datos.get("de", "")),
                              capa=12)
        lc = cc.LINEA_CADENA * s
        nombre = cp.recortar_lineas(str(datos.get("de", "")), lc, w - 0.03 * s, 2, True)
        partes = cp.lineas(nombre, lc, w - 0.03 * s, True)
        hora = datos.get("hora") or ""
        alto = cp.alto_texto(partes, lc) + (cp.alto_texto(1, lc) if hora else 0)
        y = alto / 2 + 0.008 * s
        nota.textos = [cp.texto(nota, nombre, lc, w - 0.03 * s, cp.TINTA, (0, y), negrita=True, centrado=True)]
        if hora:
            nota.textos.append(cp.texto(nota, hora, lc, w - 0.03 * s, cp.GRIS_TINTA, (0, y - cp.alto_texto(partes, lc)),
                                        centrado=True))
        nota.pin = (0, h / 2 - 0.016 * s)
        nota.capa_z = nota.z
        nota.pin_verde = papel_3d.chincheta(nota, nota.pin, cp.VERDE)
        nota.pin_verde.ignore = True
        nota.pin_verde.enabled = False
        nota.ignore = True
        nota.enabled = False
        hilo = cp.Cinta(self.raiz)
        hilo.enabled = False
        self.hilos[salto] = [hilo, None]
        self.eslabones[salto] = nota
        return nota

    # -- Gestos --

    def _gestos_vivos(self):
        return [g for g in [self.cola.actual, *self.cola.pendientes] if g is not None]

    def _encolar(self, tipo, salto, opcion):
        g = _Gesto(tipo, salto, opcion)
        nota = self.notas[opcion] if (self.indice_notas == salto and 0 <= opcion < len(self.notas)) else None
        if tipo == "error":
            g.pieza = nota
            g.desde = (nota.x, nota.y) if cp.vivo(nota) else None
        else:
            x0, y0 = (nota.x, nota.y) if cp.vivo(nota) else (self.disp["notas_x"][min(opcion, 2)], self.disp["notas_arriba"])
            g.pieza = self._eslabon(salto)
            g.pieza.position = (x0, y0, g.pieza.capa_z)
            g.pieza.enabled = True
            g.desde = (x0, y0)
            xs = cc.posiciones_cadena(len(self.minijuego.partida.saltos), self.disp)
            g.hasta = (xs[min(salto, len(xs) - 1)], self.disp["cadena_y"])
        self.cola.poner(g)

    def _avanzar_gestos(self, dt):
        while self.cola.hay_atraso():
            self._terminar_ya(self.cola.terminar_actual())
        if self.cola.actual is None:
            g = self.cola.siguiente()
            if g is not None:
                self._fase(g, "ir")
        g = self.cola.actual
        if g is None:
            return
        g.t += dt
        if g.fase == "llevar":
            self._mover_pieza(g, min(1.0, g.t / g.dur))
        if g.t >= g.dur:
            self._siguiente_fase(g)

    def _fase(self, g, fase):
        g.fase, g.t = fase, 0.0
        corcho = self._corcho()
        p = self.poses
        if fase == "ir":
            if g.desde is None or not cp.vivo(g.pieza):
                g.dur = 0.0
                return
            g.dur = self.caminar_cerca(corcho.mundo(g.desde[0], g.desde[1], 0))
        elif fase == "tomar":
            p.alcanzar(corcho.mundo(g.desde[0], g.desde[1], -0.03), DUR_TOMAR)
            g.dur = DUR_TOMAR
            sonidos.sonar("papel", 0.6)
        elif fase == "llevar":
            g.dur = DUR_LLEVAR
            self.caminar_cerca(corcho.mundo(g.hasta[0], g.hasta[1], 0), duracion=DUR_LLEVAR)
        elif fase == "clavar":
            g.dur = DUR_CLAVAR
            if cp.vivo(g.pieza):
                px, py = self._pin_local(g.pieza)
                p.clavar(corcho.mundo(px, py, 0), self.normal, al_clavar=lambda g=g: self._efecto(g), acercarse=False)
            else:
                self._efecto(g)
        elif fase == "pausa":
            g.dur = DUR_PAUSA
        elif fase == "volver":
            g.dur = self.volver_al_reposo()

    def _siguiente_fase(self, g):
        orden = ("ir", "tomar", "llevar", "clavar", "pausa", "volver") if g.tipo == "bien" else ("ir", "clavar", "pausa",
                                                                                                  "volver")
        if g.fase == "clavar" and not g.hecho:
            self._efecto(g)
        if g.fase == "llevar":
            self._mover_pieza(g, 1.0)
        i = orden.index(g.fase) if g.fase in orden else len(orden)
        if i + 1 < len(orden):
            self._fase(g, orden[i + 1])
        else:
            self.cola.terminar_actual()

    @staticmethod
    def _pin_local(pieza):
        """(x, y) local del corcho de la chincheta de una nota (con su giro)."""
        px, py = pieza.pin
        a = math.radians(-pieza.rotation_z)
        return (pieza.x + px * math.cos(a) - py * math.sin(a), pieza.y + px * math.sin(a) + py * math.cos(a))

    def _mover_pieza(self, g, k):
        pieza = g.pieza
        if not cp.vivo(pieza) or g.hasta is None:
            return
        e = ccal.suave(k)
        x = g.desde[0] + (g.hasta[0] - g.desde[0]) * e
        y = g.desde[1] + (g.hasta[1] - g.desde[1]) * e + math.sin(math.pi * k) * 0.06 * self.s
        z = pieza.capa_z - LEVANTAR * math.sin(math.pi * min(1.0, k * 1.15))
        if k >= 1.0:
            pieza.position = (g.hasta[0], g.hasta[1], papel_3d.Z_PAPEL - 0.002)
        else:
            pieza.position = (x, y, z)
            self.poses.mano_a(self._corcho().mundo(x, y, z - 0.02))

    def _efecto(self, g):
        """Lo que deja el gesto en el corcho: el eslabón clavado con su hilo, o la X roja en la candidata."""
        if g.hecho:
            return
        g.hecho = True
        sonidos.sonar("clavar")
        if g.tipo == "error":
            self._descartar(g.pieza)
            return
        pieza = g.pieza
        if not cp.vivo(pieza):
            return
        pieza.position = (g.hasta[0], g.hasta[1], papel_3d.Z_PAPEL - 0.002)
        pieza.pin_verde.enabled = True
        self.cadena[g.salto] = pieza
        self.hilos[g.salto][1] = 0.0
        self._fijar_hilo(g.salto)
        partida = self.minijuego.partida
        if partida.llegado and g.salto == len(partida.saltos) - 1:
            self._fuente_oculta().enabled = True

    def _cerrar_gestos(self):
        """Con el resultado en pantalla: todos los gestos pendientes terminan YA (su efecto queda: eslabón clavado con su
        hilo, X roja) y el personaje se aparta al reposo en DURACION_RETIRADA s. Antes la cola seguía (ir, tomar, llevar,
        clavar, pausa, volver: ~3 s) y el cuerpo y el brazo tapaban «Origen: …» y el banner (retoques 23-nov, D1). Los
        eventos que lleguen después (la vista 2D decide en el mismo frame que termina) también se cierran aquí."""
        while not self.cola.vacia():
            g = self.cola.actual if self.cola.actual is not None else self.cola.siguiente()
            if g is None:
                break
            self._terminar_ya(self.cola.terminar_actual())
        self._cerrado = True
        self.retirarse_ya()

    def al_resultado(self, resultado):
        super().al_resultado(resultado)
        self._cerrado = False            # avanzar_3d cierra los gestos en el frame siguiente (no en el más pesado)

    def _terminar_ya(self, g):
        """El jugador fue más rápido que la animación: el gesto termina AL INSTANTE (su efecto visual queda aplicado)."""
        if g is None:
            return
        if g.tipo == "bien":
            self._mover_pieza(g, 1.0)
        self._efecto(g)
        self.poses.soltar_mano("d")

    def _pin_de(self, salto):
        if salto < 0:
            return self.disp["pin_tu"]
        nota = self.cadena.get(salto)
        return self._pin_local(nota) if cp.vivo(nota) else None

    def _fijar_hilo(self, salto):
        hilo, t = self.hilos[salto]
        a, b = self._pin_de(salto - 1), self._pin_de(salto)
        if a is None or b is None:
            hilo.enabled = False
            return
        hilo.fijar(cc.hilo(a, b, cc.caida_hilo(t, self.s)))

    def _avanzar_hilos(self, dt):
        for salto, datos in self.hilos.items():
            if datos[1] is None:
                continue
            datos[1] += dt
            if datos[1] > 0.5:
                datos[1] = None
            self._fijar_hilo(salto)


def texto_cabecera(numero, opcion, alto_linea, ancho):
    """Cabecera de la nota candidata en UNA línea de `ancho` m con letra de `alto_linea` m (negrita), medida con la misma
    fuente y el mismo ajuste que la dibuja (corcho_piezas.lineas): si no cabe se recorta el nombre con «…», nunca la hora.
    (Antes se recortaba el nombre a 26 caracteres sin medir ni contar la hora: la cabecera se partía y la hora quedaba
    cortada en dos renglones, «ayer / 18:20».)"""
    return cc.cabecera_nota(numero, opcion.get("de", ""), opcion.get("hora") or "",
                            lambda c: cp.lineas(c, alto_linea, ancho, True) == 1)


def _giro(ident):
    """Giro pequeño y estable por nombre (como papel_calculos.giro_por_id de la vista 2D)."""
    try:
        from frontend.minijuegos_visual import papel_calculos
        return papel_calculos.giro_por_id(str(ident), 1.5)
    except Exception:                    # noqa: BLE001
        return 0.0


CLASE_3D = Rastrear3D
