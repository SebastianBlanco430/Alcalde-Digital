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
from frontend.minijuegos.chat import ANCHO_CHAT, ANCHO_OPC, MinijuegoChat
from frontend.minijuegos_visual import chat_visual_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual

CHAT_VISUAL = True
VARIABLE = "ALCALDE_CHAT_VISUAL"

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
            self._pintar_chat()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    # -- Construcción --

    def _construir_vista(self):
        from frontend.telefono_marco import MarcoTelefono
        cy = self.y_panel - self.alto_chat / 2
        self.vista = Entity(parent=self)
        self.telefono = MarcoTelefono(ANCHO_CHAT, self.alto_chat, (self.x_chat, cy), parent=self.vista)
        # Franja inferior: avatares del grupo + «escribiendo…».
        y_franja = self.y_panel - self.alto_chat + RESERVA_ABAJO / 2 + 0.004
        x0 = self.x_chat - ANCHO_CHAT / 2 + 0.03
        ui.rect(self.vista, ANCHO_CHAT - 0.02, RESERVA_ABAJO - 0.008, (30, 33, 44), (self.x_chat, y_franja), z=-0.005,
                radio_px=6)
        nombres = [calc.nombre_corto(t["de"]) for t in self.partida.turnos]
        self.nombres = list(dict.fromkeys(nombres))[:4] or ["Grupo"]
        self.avatares = []
        for i, nombre in enumerate(self.nombres):
            x = x0 + i * 0.042
            borde = Entity(parent=self.vista, model="circle", scale=0.036, color=_rgba(estilo.TINTA, 1),
                           position=(x, y_franja, -0.006))
            cara = Entity(parent=self.vista, model="circle", scale=0.031, color=_rgba(TONOS_AVATAR[i % 4], 1),
                          position=(x, y_franja, -0.007))
            Text(calc.inicial(nombre), parent=self.vista, origin=(0, 0), position=(x, y_franja, -0.008),
                 scale=escala_fuente(13), font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            self.avatares.append((borde, cara, TONOS_AVATAR[i % 4]))
        self.escribiendo_txt = Text("", parent=self.vista, origin=(-0.5, 0),
                                    position=(x0 + len(self.nombres) * 0.042 + 0.005, y_franja, -0.008),
                                    scale=escala_fuente(13), color=_rgba(estilo.COLOR_TEXTO_TENUE, 1))
        # Aviso de datos (debajo de las respuestas) y resalte rojo de la respuesta con el foco.
        self.resalte = Entity(parent=self.vista, model="quad", color=_rgba(ROJO, 0.0), enabled=False)
        self.aviso_txt = ui.texto(self.vista, "", 15, ANCHO_OPC, ROJO, (self.x_opc - ANCHO_OPC / 2, -0.2), negrita=True)
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
        try:
            MinijuegoChat._pintar_chat(self)
        except Exception:                # noqa: BLE001
            pass

    # -- Chat: «escribiendo…» antes del mensaje nuevo, y franja inferior reservada --

    def _pintar_turno(self):
        n_antes = len(getattr(self, "log", []))
        super()._pintar_turno()
        if self._fx is not None and n_antes:
            self._vigilar(self._entrada_en_cascada, self.opciones)          # las respuestas del turno nuevo también entran con rebote
        if self._listo and len(self.log) > n_antes and self.log[-1][2] == "msg":
            reducir = self._fx.reducir if self._fx is not None else False
            self._t_escribiendo = 0.0
            if reducir:
                self._t_escribiendo = calc.DEMORA_ESCRIBIENDO
            self._pintar_chat()

    def _pintar_chat(self):
        if not self._listo or self._vista_rota:
            return super()._pintar_chat()
        try:
            self._pintar_chat_visual()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

    def _pintar_chat_visual(self):
        log = self.log
        if self._t_escribiendo is not None and self._t_escribiendo < calc.DEMORA_ESCRIBIENDO and log and log[-1][2] == "msg":
            log = log[:-1]
        ancho = ANCHO_CHAT - a_unidades(24)
        tope = int((self.alto_chat - a_unidades(60) - RESERVA_ABAJO) / (a_unidades(16) * ui.LINEA))
        bloques, usadas = [], 0
        for quien, cuerpo, tipo in reversed(log):
            lineas = ui.lineas_de(self._entrada(quien, cuerpo, tipo), 16, ancho) + [""]
            if usadas + len(lineas) - 1 > tope and bloques:
                break
            bloques.insert(0, lineas)
            usadas += len(lineas)
        self.texto_chat.text = "\n".join(l for b in bloques for l in b).rstrip("\n")

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
        self.aviso_txt.text = "\n".join(ui.lineas_de(texto, 15, ANCHO_OPC)) if texto else ""
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
        for borde, cara, tono in self.avatares:
            mezcla = tuple(tono[k] + (ROJO[k] - tono[k]) * enfado for k in range(3))
            cara.color = _rgba(mezcla, 1)
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
        self._protegido = self.partida.datos_cedidos() == 0
        # Tapa todo el chat entre el título y la franja de avatares.
        arriba = self.y_panel - 0.05
        abajo = self.y_panel - self.alto_chat + RESERVA_ABAJO + 0.006
        cx, cy = self.x_chat, (arriba + abajo) / 2
        ancho, alto = ANCHO_CHAT - 0.012, arriba - abajo
        self._caja_final = (cx, cy, ancho, alto)
        ui.rect(self.final, ancho, alto, (22, 24, 32), (cx, cy), z=0.002, radio_px=10)
        if self._protegido:
            self._halo = Entity(parent=self.final, model="circle", color=_rgba(VERDE, 0.0), position=(cx, cy + 0.02, 0.001),
                                scale=0.11)
            Entity(parent=self.final, model="circle", color=_rgba(estilo.TINTA, 1), position=(cx, cy + 0.02, 0), scale=0.078)
            Entity(parent=self.final, model="circle", color=_rgba(TONOS_AVATAR[1], 1), position=(cx, cy + 0.02, -0.001),
                   scale=0.07)
            Text("Tu amigo", parent=self.final, origin=(0, 0), position=(cx, cy - 0.045, -0.002), scale=escala_fuente(14),
                 color=_rgba(estilo.COLOR_TEXTO, 1))
            self._gracias = Text("¡Gracias por no pasar mis datos!", parent=self.final, origin=(0, 0),
                                 position=(cx, cy + 0.09, -0.002), scale=escala_fuente(17), font=tipografia.FUENTE_TITULO,
                                 color=_rgba(VERDE, 1))
        else:
            self._ruta = [(cx + x * ancho, cy + y * alto) for x, y in calc.ruta_dato()]
            for x, y in self._ruta[1:-1]:
                Entity(parent=self.final, model="circle", color=_rgba(estilo.COLOR_TEXTO_TENUE, 0.9), position=(x, y, 0),
                       scale=0.028)
            for (ax, ay), (bx, by) in zip(self._ruta, self._ruta[1:]):
                largo = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                Entity(parent=self.final, model="quad", color=_rgba(estilo.COLOR_TEXTO_TENUE, 0.35),
                       position=((ax + bx) / 2, (ay + by) / 2, 0.001), scale=(largo, 0.004),
                       rotation_z=-math.degrees(math.atan2(by - ay, bx - ax)))
            fx_, fy = self._ruta[-1]
            Entity(parent=self.final, model="circle", color=_rgba(ROJO, 1), position=(fx_, fy, 0), scale=0.06)
            Text("?", parent=self.final, origin=(0, 0), position=(fx_, fy, -0.002), scale=escala_fuente(24),
                 font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            Text("Perfil desconocido", parent=self.final, origin=(0, 0), position=(fx_ - 0.03, fy - 0.05, -0.002),
                 scale=escala_fuente(12), color=_rgba(ROJO, 1))
            Text("El dato salió del grupo y ya no sabes quién lo tiene.", parent=self.final, origin=(0, 0),
                 position=(cx, cy + alto / 2 - 0.025, -0.002), scale=escala_fuente(14), color=_rgba(estilo.COLOR_TEXTO, 1))
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
        self.final.enabled = True
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
