# «Chat del barrio» visual (Ursina): el mismo minijuego (frontend/minijuegos/chat.py, lógica chat_calculos) como un chat de
# grupo VIVO que presiona:
#   - el panel del chat va dentro de un teléfono de Civitas (frontend/telefono_marco.py) con hora y batería;
#   - cada mensaje nuevo llega tras unos puntitos de «X está escribiendo…» (cada vez más gente escribiendo a la vez), con
#     el sonido de mensaje; los avatares del grupo se enrojecen con la presión;
#   - una viñeta oscura cierra la pantalla poco a poco con la presión y el teléfono vibra al cruzar cada umbral;
#   - al pasar el foco por una respuesta se resaltan en rojo los DATOS que entregaría (leídos del texto, nunca del valor);
#   - al final: si protegiste a tu amigo su avatar se ilumina con un «¡gracias!»; si cediste datos, el dato «vuela» por la
#     red hasta un perfil desconocido.
#
# No cambia la partida ni el resultado: hereda de MinijuegoChat, llama a super() y solo dibuja. El tiempo del turno corre
# igual que siempre (las respuestas se ven desde el primer momento; el «escribiendo…» solo retrasa el globo del mensaje).
#
# APAGADO: ALCALDE_CHAT_VISUAL=0 (o CHAT_VISUAL = False): la vista de siempre con la capa común.
# REDUCIR MOVIMIENTO: sin vibración, la viñeta más suave y el final aparece sin animación.
# GUARDIÁN: un fallo de la vista nueva avisa una vez por stderr, esconde lo añadido y deja el chat de siempre.

import math

from panda3d.core import TransparencyAttrib
from PIL import Image
from ursina import Entity, Text, Texture, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.chat import MinijuegoChat
from frontend.minijuegos_visual import chat_piezas_calculos as pc
from frontend.minijuegos_visual import chat_visual_calculos as calc
from frontend.minijuegos_visual import piezas_chat as pz
from frontend.minijuegos_visual.capa import CapaVisual

CHAT_VISUAL = True
VARIABLE = "ALCALDE_CHAT_VISUAL"

ANCHO_TEL = 0.56               # pantalla de papel del móvil
X_TEL = -0.36
RESERVA_ABAJO = 0.058          # franja inferior del panel para avatares y «escribiendo…»
ROJO = (235, 87, 87)
VERDE = (88, 214, 141)
TONOS_AVATAR = ((120, 170, 230), (230, 170, 90), (170, 130, 220), (110, 200, 170))
DUR_FINAL = 2.4

_textura_vineta = None


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def textura_vineta():
    """Degradado radial: transparente en el centro, negro en los bordes (se crea una vez)."""
    global _textura_vineta
    if _textura_vineta is None:
        lado = 128
        imagen = Image.new("RGBA", (lado, lado))
        datos = []
        for y in range(lado):
            for x in range(lado):
                dx, dy = (x - lado / 2) / (lado / 2), (y - lado / 2) / (lado / 2)
                d = (dx * dx + dy * dy) ** 0.5
                alfa = max(0.0, min(1.0, (d - 0.62) / 0.6))
                datos.append((0, 0, 0, int(255 * alfa ** 1.4)))
        imagen.putdata(datos)
        _textura_vineta = Texture(imagen)
    return _textura_vineta


def _sonar(nombre, volumen=1.0, pitch=1.0):
    try:
        from frontend import audio
        audio.obtener().efecto(nombre, volumen=volumen, pitch=pitch)
    except Exception:                    # noqa: BLE001
        pass


class ChatVisual(CapaVisual, MinijuegoChat):

    _vista_rota = False
    _listo = False

    def construir(self):
        self._t_escribiendo = None
        self._presion_antes = 0.0
        self._t_vis = 0.0
        self._t_final = None
        super().construir()
        try:
            self._construir_vista()
            self._listo = True
            self._rehacer_opciones()
            self._pintar_chat()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    # -- Construcción --

    def _construir_vista(self):
        from frontend.telefono_marco import MarcoTelefono
        cy = self.y_panel - self.alto_chat / 2
        self.vista = Entity(parent=self)
        self.x_tel = X_TEL
        # Se oculta lo de la vista base (se conserva: el tutorial o el cierre pueden tocarlo).
        for e in (self.panel, self.texto_chat, self.rotulo, self.barra, self.pie):
            e.enabled = False
        self._valores_log = {}
        self.telefono = MarcoTelefono(ANCHO_TEL, self.alto_chat, (self.x_tel, cy), parent=self.vista)
        self._barra_estado_en_tinta()
        ui.rect(self.vista, ANCHO_TEL, self.alto_chat, estilo.PAPEL, (self.x_tel, cy), z=0.006, radio_px=12)
        # Cabecera amarilla con avatar del grupo.
        y_cab = self.y_panel - 0.055
        ui.rect(self.vista, ANCHO_TEL, 0.07, estilo.COLOR_ACENTO, (self.x_tel, y_cab), z=0.005, radio_px=8)
        pz.avatar(self.vista, "Grupo", 3, (self.x_tel - ANCHO_TEL / 2 + 0.04, y_cab - 0.004), 0.04, z=-0.001)
        Text("Chat del barrio", parent=self.vista, origin=(-0.5, 0), position=(self.x_tel - ANCHO_TEL / 2 + 0.075, y_cab + 0.008, -0.003),
             scale=escala_fuente(15), font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
        Text("3 en línea", parent=self.vista, origin=(-0.5, 0), position=(self.x_tel - ANCHO_TEL / 2 + 0.075, y_cab - 0.014, -0.003),
             scale=escala_fuente(11), color=_rgba(estilo.TINTA, 0.8))
        self.y_burb_abajo = self.y_panel - self.alto_chat + RESERVA_ABAJO + 0.01
        self.y_burb_arriba = self.y_panel - 0.115
        self.burbujas = Entity(parent=self.vista, z=-0.01)
        # Presión: reloj circular + tres avatares «esperando».
        nombres = [calc.nombre_corto(t["de"]) for t in self.partida.turnos]
        self.nombres = list(dict.fromkeys(nombres))[:4] or ["Grupo"]
        rx, ry = pc.RELOJ_CENTRO
        self.reloj = pz.RelojPresion(pc.RELOJ_DIAMETRO, parent=self.vista, position=(rx, ry, -0.02))
        self.avatares = []
        self._avatares_raiz = []
        for i in range(3):
            nombre = self.nombres[i % len(self.nombres)]
            x = pc.X_AVATARES + i * pc.PASO_AVATARES
            raiz, cara = pz.avatar(self.vista, nombre, i, (x, ry), 0.036, z=-0.02)
            tono = pc.color_de_rol(nombre, i)
            self._avatares_raiz.append(raiz)
            self.avatares.append((raiz, cara, tono))
        self.alarma = Text("!", parent=self.vista, origin=(0, 0), position=(pc.X_AVATARES - 0.04, ry, -0.03),
                           scale=escala_fuente(18), font=tipografia.FUENTE_TITULO, color=_rgba(ROJO, 1), enabled=False)
        # Franja inferior del móvil: «escribiendo…» del grupo.
        y_franja = self.y_panel - self.alto_chat + RESERVA_ABAJO / 2 + 0.004
        self.escribiendo_txt = Text("", parent=self.vista, origin=(-0.5, 0),
                                    position=(self.x_tel - ANCHO_TEL / 2 + 0.03, y_franja, -0.008),
                                    scale=escala_fuente(12), color=_rgba(estilo.TINTA, 0.8))
        # Aviso de datos (debajo de las respuestas) y resalte rojo de la respuesta con el foco.
        self.resalte = Entity(parent=self.vista, model="quad", color=_rgba(ROJO, 0.0), enabled=False)
        self.aviso_txt = ui.texto(self.vista, "", 15, pc.ANCHO_RESPUESTAS, ROJO, (pc.X_RESPUESTAS - pc.ANCHO_RESPUESTAS / 2, -0.2), negrita=True)
        # Viñeta de presión (delante de todo, sin colisionador: no tapa los clics).
        self.vineta_e = Entity(parent=self.vista, model="quad", texture=textura_vineta(), scale=(16 / 9, 1), z=-0.25,
                               color=_rgba((255, 255, 255), 0.0))
        self.vineta_e.setTransparency(TransparencyAttrib.M_alpha)
        self.final = Entity(parent=self.vista, z=-0.2, enabled=False)

    def _quitar_vista(self):
        self._vista_rota = True
        self._listo = False
        vista = getattr(self, "vista", None)
        if vista is not None:
            vista.enabled = False
        for nombre in ("panel", "texto_chat", "rotulo", "barra", "pie"):
            e = getattr(self, nombre, None)
            if e is not None:
                e.enabled = True
        try:
            MinijuegoChat._pintar_chat(self)
        except Exception:                # noqa: BLE001
            pass

    # -- Chat: «escribiendo…» antes del mensaje nuevo, y franja inferior reservada --

    def _pintar_turno(self):
        n_antes = len(getattr(self, "log", []))
        super()._pintar_turno()
        if self._listo and not self._vista_rota:
            self._rehacer_opciones()
        if self._fx is not None and n_antes:
            self._vigilar(self._entrada_en_cascada, self.opciones)          # las respuestas del turno nuevo también entran con rebote
        if self._listo and len(self.log) > n_antes and self.log[-1][2] == "msg":
            reducir = self._fx.reducir if self._fx is not None else False
            self._t_escribiendo = 0.0
            if reducir:
                self._t_escribiendo = calc.DEMORA_ESCRIBIENDO
            self._pintar_chat()

    def _rehacer_opciones(self):
        """Las 3 respuestas como globos de papel (siguen siendo `opciones`/`focables`), arriba a la derecha sin tapar el reloj."""
        from frontend.componentes import destruir_arbol
        try:
            for o in self.opciones:
                destruir_arbol(o)
            self.opciones, self.focables = [], []
            turno = self.partida.turno_actual()
            if turno is None:
                return
            y = pc.Y_RESPUESTAS_ARRIBA
            for i, o in enumerate(turno["opciones"]):
                alto = ui.Tarjeta.alto_necesario(o["texto"], pc.ANCHO_RESPUESTAS, 17, "", 13, minimo=0.085,
                                                 reserva=pz.GloboRespuesta.RESERVA)
                t = pz.GloboRespuesta(pc.ANCHO_RESPUESTAS, alto, o["texto"], i + 1, 17, parent=self,
                                      position=(pc.X_RESPUESTAS, y - alto / 2), al_clic=lambda i=i: self.responder(i),
                                      al_cursor=lambda i=i: self.poner_foco(i))
                self.opciones.append(t)
                self.focables.append(t)
                y -= alto + pc.SEPARACION_RESPUESTAS
            self.foco = 0
            self._pintar_foco()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    def _barra_estado_en_tinta(self):
        """La barra de estado del móvil (hora, «Civitas», señal, batería) es clara: sobre el papel crema se pasa a tinta."""
        for e in self.telefono.children:
            if e.z <= -0.027 and e is not self.telefono._bateria:
                e.color = _rgba(estilo.TINTA, 0.9)

    def responder(self, i):
        """Igual que siempre; además anota si la respuesta protegió (palomita) o cedió un dato (aspa y temblor corto)."""
        turno = None if self.terminado else self.partida.turno_actual()
        valor = turno["opciones"][i]["valor"] if turno is not None and 0 <= i < len(turno["opciones"]) else None
        indice = len(self.log)
        super().responder(i)
        if valor is None or len(self.log) <= indice or not self._listo or self._vista_rota:
            return
        self._valores_log[indice] = valor
        self._pintar_chat()
        if valor == 0 and self._fx is not None and not self._fx.reducir:
            self._vigilar(self._fx.temblor, self.burbujas)

    def _pintar_chat(self):
        if not self._listo or self._vista_rota:
            return super()._pintar_chat()
        try:
            self._pintar_chat_visual()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    def _pintar_chat_visual(self):
        """Burbujas reales: entrantes de papel con cola y avatar, salientes cian, reacciones/visto en gris."""
        from frontend.componentes import destruir_arbol
        for hijo in list(self.burbujas.children):
            destruir_arbol(hijo)
        log = self.log
        escribiendo = self._t_escribiendo is not None and self._t_escribiendo < calc.DEMORA_ESCRIBIENDO
        if escribiendo and log and log[-1][2] == "msg":
            log = log[:-1]
        px = 15
        ancho_max = 0.36
        items = []
        for idx, (quien, cuerpo, tipo) in enumerate(log):
            tx = "En visto" if self._es_en_visto(cuerpo, tipo) else cuerpo
            if tx == "En visto":
                tipo = "visto"
            lineas = ui.lineas_de(tx, px, ancho_max - 0.03)
            ancho = min(ancho_max, max(ui.medir(l, px) for l in lineas) + 0.034) if lineas else 0.1
            alto = pc.alto_globo(len(lineas) + (1 if tipo == "msg" else 0), a_unidades(px) * ui.LINEA)
            items.append((quien, tipo, lineas, ancho, alto, idx))
        if escribiendo:
            items.append(("", "puntos", [], 0.1, 0.05, -1))
        pos = pc.posiciones_burbujas([it[4] for it in items], self.y_burb_abajo, self.y_burb_arriba)
        x_izq = self.x_tel - ANCHO_TEL / 2 + 0.075
        x_der = self.x_tel + ANCHO_TEL / 2 - 0.03
        self._puntos = []
        for i, y in pos:
            quien, tipo, lineas, ancho, alto, idx = items[i]
            if tipo == "msg" or tipo == "puntos":
                nombre = quien or calc.nombre_corto(self.partida.turno_actual()["de"] if self.partida.turno_actual() else "")
                cx = x_izq + ancho / 2
                pz.globo(self.burbujas, ancho, alto, (cx, y), estilo.PAPEL, "izq")
                pz.avatar(self.burbujas, nombre, self.nombres.index(calc.nombre_corto(nombre)) if calc.nombre_corto(nombre) in self.nombres else 0,
                          (x_izq - 0.04, y - alto / 2 + 0.025), 0.05)
                if tipo == "puntos":
                    for k in range(3):
                        self._puntos.append(Entity(parent=self.burbujas, model="circle", scale=0.012, color=_rgba(estilo.TINTA),
                                                   position=(cx - 0.025 + k * 0.025, y, -0.01)))
                else:
                    Text(calc.nombre_corto(quien), parent=self.burbujas, origin=(-0.5, 0),
                         position=(cx - ancho / 2 + 0.014, y + alto / 2 - 0.016, -0.01), scale=escala_fuente(11),
                         font=tipografia.FUENTE_TITULO, color=_rgba(pc.color_de_rol(quien), 1))
                    self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.03, estilo.TINTA)
            elif tipo == "tu":
                cx = x_der - ancho / 2
                pz.globo(self.burbujas, ancho, alto, (cx, y), pc.COLOR_CIAN, "der")
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, estilo.TINTA)
                tipo_marca = pc.marca_de_valor(self._valores_log.get(idx))
                if tipo_marca:       # palomita verde (protegió) o aspa roja (cedió un dato), en una chapa sobre el globo
                    px_m, py_m = cx - ancho / 2 - 0.002, y + alto / 2 - 0.002
                    Entity(parent=self.burbujas, model="circle", color=_rgba(estilo.TINTA), position=(px_m, py_m, -0.012), scale=0.05)
                    Entity(parent=self.burbujas, model="circle", color=_rgba(estilo.PAPEL), position=(px_m, py_m, -0.013), scale=0.044)
                    pz.marca(self.burbujas, tipo_marca, (px_m, py_m), 0.026, z=-0.016)
            elif tipo == "visto":    # tiempo agotado: burbuja gris «En visto» a tu lado del chat
                cx = x_der - ancho / 2
                pz.globo(self.burbujas, ancho, alto, (cx, y), (205, 205, 212), "der")
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, (90, 92, 106))
            else:   # contexto y reacciones: globo gris pequeño centrado / en visto
                cx = self.x_tel
                pz.globo(self.burbujas, ancho, alto, (cx, y), (214, 214, 220), "izq", con_cola=False)
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, estilo.TINTA)

    @staticmethod
    def _es_en_visto(cuerpo, tipo):
        from frontend.minijuegos.chat_calculos import TEXTO_EN_VISTO
        return tipo == "reaccion" and cuerpo == TEXTO_EN_VISTO

    def _texto_globo(self, lineas, px, x, y, tono):
        t = ui.texto(self.burbujas, "\n".join(lineas), px, None, tono, (x, y))
        t.z = -0.01
        return t

    # -- Foco: datos que entregaría la respuesta --

    def _pintar_foco(self):
        super()._pintar_foco()
        if self._listo and not self._vista_rota:
            self._vigilar(self._pintar_aviso)

    def _pintar_aviso(self):
        turno = self.partida.turno_actual()
        tarjeta = self.focables[self.foco] if self.focables and 0 <= self.foco < len(self.focables) else None
        texto = ""
        if turno is not None and tarjeta is not None and not self.terminado and self.foco < len(turno["opciones"]):
            texto = calc.aviso_datos(turno["opciones"][self.foco]["texto"])
        self.aviso_txt.text = "\n".join(ui.lineas_de(texto, 15, pc.ANCHO_RESPUESTAS)) if texto else ""
        if texto and tarjeta is not None:
            ultimo = self.opciones[-1]
            self.aviso_txt.y = ultimo.y - ultimo.alto / 2 - 0.02
            self.resalte.model = ui.modelo_redondeado(tarjeta.ancho, tarjeta.alto, 8)
            self.resalte.scale = (tarjeta.ancho, tarjeta.alto)
            self.resalte.position = (tarjeta.x, tarjeta.y, -0.06)
            self.resalte.color = _rgba(ROJO, 0.16)
            self.resalte.enabled = True
        else:
            self.resalte.enabled = False

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not self._listo or self._vista_rota:
            return
        try:
            self._animar(dt)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    def _animar(self, dt):
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        self._t_vis += dt
        if self._t_escribiendo is not None:
            self._t_escribiendo += dt
            if self._t_escribiendo >= calc.DEMORA_ESCRIBIENDO:
                self._t_escribiendo = None
                self._pintar_chat()
                _sonar("mensaje_civitas", 0.6)
        presion = 0.0 if self.terminado else self.partida.presion()
        # Viñeta y avatares enfadados.
        self.vineta_e.color = _rgba((255, 255, 255), calc.vineta(presion, reducir))
        enfado = calc.enfado(presion)
        for i, (raiz, cara, tono) in enumerate(self.avatares):
            mezcla = tuple(tono[k] + (ROJO[k] - tono[k]) * enfado for k in range(3))
            cara.color = _rgba(mezcla, 1)
            raiz.rotation_z = 0.0 if reducir else pc.inclinacion_avatar(presion, i)
        self.reloj.fijar(0.0 if self.terminado else 1.0 - presion)
        self.alarma.enabled = (not self.terminado) and pc.muestra_alarma(presion)
        for k, punto in enumerate(getattr(self, "_puntos", [])):
            if not punto.is_empty():
                base = getattr(punto, "_y0", None)
                if base is None:
                    base = punto._y0 = punto.y
                punto.y = base if reducir else base + 0.008 * math.sin(self._t_vis * 7 + k * 1.2)
        turno = self.partida.turno_actual()
        if turno is not None and not self.terminado:
            if self._t_escribiendo is not None:
                rotulo = calc.nombre_corto(turno["de"]) + " está escribiendo" + calc.puntos_escribiendo(self._t_vis)
            else:
                otros = [n for n in self.nombres if n != calc.nombre_corto(turno["de"])] or self.nombres
                rotulo = calc.escribiendo(otros, presion) if presion > 0.3 else ""
            self.escribiendo_txt.text = rotulo
        else:
            self.escribiendo_txt.text = ""
        # Vibración del teléfono al cruzar umbrales de presión.
        if calc.vibra(self._presion_antes, presion) and not self.terminado:
            if self._fx is not None and not reducir:
                for e in (self.panel, self.texto_chat, self.telefono):
                    self._fx.temblor(e)
            _sonar("clic_ui", 0.5, 0.45)
        self._presion_antes = presion
        if self._t_final is not None:
            self._animar_final(dt, reducir)

    # -- Final: «¡gracias!» o el dato que vuela --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if not self._listo or self._vista_rota:
            return
        self._vigilar(self._preparar_final)

    def _preparar_final(self):
        self.resalte.enabled = False
        self.aviso_txt.text = ""
        self.escribiendo_txt.text = ""
        self.vineta_e.color = _rgba((255, 255, 255), 0.0)
        for e in [self.reloj, self.alarma] + self._avatares_raiz:      # la presión ya no corre: se quita
            e.enabled = False
        self._protegido = self.partida.datos_cedidos() == 0
        # Tapa todo el chat entre el título y la franja de avatares.
        arriba = self.y_panel - 0.05
        abajo = self.y_panel - self.alto_chat + RESERVA_ABAJO + 0.006
        cx, cy = self.x_tel, (arriba + abajo) / 2
        ancho, alto = ANCHO_TEL - 0.012, arriba - abajo
        self._caja_final = (cx, cy, ancho, alto)
        ui.rect(self.final, ancho, alto, estilo.PAPEL, (cx, cy), z=0.002, radio_px=10)
        if self._protegido:
            self._halo = Entity(parent=self.final, model="circle", color=_rgba(VERDE, 0.0), position=(cx, cy + 0.02, 0.001),
                                scale=0.11)
            Entity(parent=self.final, model="circle", color=_rgba(estilo.TINTA, 1), position=(cx, cy + 0.02, 0), scale=0.078)
            Entity(parent=self.final, model="circle", color=_rgba(TONOS_AVATAR[1], 1), position=(cx, cy + 0.02, -0.001),
                   scale=0.07)
            Text("Tu amigo", parent=self.final, origin=(0, 0), position=(cx, cy - 0.045, -0.002), scale=escala_fuente(14),
                 color=_rgba(estilo.TINTA, 1))
            self._gracias = Text("¡Gracias por no pasar mis datos!", parent=self.final, origin=(0, 0),
                                 position=(cx, cy + 0.09, -0.002), scale=escala_fuente(17), font=tipografia.FUENTE_TITULO,
                                 color=_rgba(VERDE, 1))
        else:
            self._ruta = [(cx + x * ancho, cy + y * alto) for x, y in calc.ruta_dato()]
            for x, y in self._ruta[1:-1]:
                Entity(parent=self.final, model="circle", color=_rgba(estilo.TINTA, 0.7), position=(x, y, 0),
                       scale=0.028)
            for (ax, ay), (bx, by) in zip(self._ruta, self._ruta[1:]):
                largo = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                Entity(parent=self.final, model="quad", color=_rgba(estilo.TINTA, 0.3),
                       position=((ax + bx) / 2, (ay + by) / 2, 0.001), scale=(largo, 0.004),
                       rotation_z=-math.degrees(math.atan2(by - ay, bx - ax)))
            fx_, fy = self._ruta[-1]
            Entity(parent=self.final, model="circle", color=_rgba(ROJO, 1), position=(fx_, fy, 0), scale=0.06)
            Text("?", parent=self.final, origin=(0, 0), position=(fx_, fy, -0.002), scale=escala_fuente(24),
                 font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            Text("Perfil desconocido", parent=self.final, origin=(0, 0), position=(fx_ - 0.03, fy - 0.05, -0.002),
                 scale=escala_fuente(12), color=_rgba(ROJO, 1))
            Text("El dato salió del grupo y ya no sabes quién lo tiene.", parent=self.final, origin=(0, 0),
                 position=(cx, cy + alto / 2 - 0.025, -0.002), scale=escala_fuente(14), color=_rgba(estilo.TINTA, 1))
            sx, sy = self._ruta[0]
            Entity(parent=self.final, model="circle", color=_rgba(TONOS_AVATAR[0], 1), position=(sx, sy, 0), scale=0.05)
            Text("Tú", parent=self.final, origin=(0, 0), position=(sx, sy, -0.002), scale=escala_fuente(13),
                 font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            # La ficha termina justo encima del perfil desconocido (no lo tapa).
            self._ruta_chip = self._ruta[:-1] + [(fx_, fy + 0.055)]
            self._chip = Entity(parent=self.final, position=(sx, sy + 0.045, -0.01))
            ui.rect(self._chip, 0.11, 0.032, ROJO, (0, 0), z=0.001, radio_px=6)
            Text("el dato", parent=self._chip, origin=(0, 0), z=-0.002, scale=escala_fuente(13),
                 font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
        resumen = pc.resumen_final(self.partida.respuestas)
        if resumen:
            Text("\n".join(ui.lineas_de(resumen, 13, ancho - 0.04)), parent=self.final, origin=(0, 0),
                 position=(cx, cy - alto / 2 + 0.135, -0.002), scale=escala_fuente(13), color=_rgba(estilo.TINTA, 1))
        self.final.enabled = True
        if self._fx is not None:
            self._vigilar(self._fx.sello, "A SALVO" if self._protegido else "DATOS REGALADOS", (cx, cy - alto / 2 + 0.05),
                          estilo.ESTADO_EXITO if self._protegido else estilo.ESTADO_ERROR)
        retardo = 1.4
        self._t_final = -retardo

    def _animar_final(self, dt, reducir):
        self._t_final += dt
        t = self._t_final
        f = 1.0 if reducir else max(0.0, min(1.0, t / DUR_FINAL))
        if t < 0 and not reducir:
            self.final.enabled = False
            return
        self.final.enabled = True
        if self._protegido:
            self._halo.color = _rgba(VERDE, 0.55 * f if reducir else 0.25 + 0.3 * abs(((t * 1.3) % 2) - 1))
            self._gracias.scale = escala_fuente(17) * fx_calc.rebote(max(0.0, t), desde=0.0, reducir=reducir)
        else:
            x, y = calc.punto_en_ruta(self._ruta_chip, f)
            self._chip.position = (x, y, -0.01)
        if f >= 1.0 and (reducir or t > DUR_FINAL + 1.0):
            self._t_final = None
