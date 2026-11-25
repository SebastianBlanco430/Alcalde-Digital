# «Chat del barrio» visual (Ursina): el mismo minijuego (frontend/minijuegos/chat.py, lógica chat_calculos) como un chat de
# grupo VIVO que presiona:
#   - el panel del chat va dentro de un teléfono de PAPEL (piezas_chat.TelefonoPapel: borde de tinta 3 px y sombra dura) con hora y batería;
#   - cada mensaje nuevo llega tras unos puntitos de «X está escribiendo…» (cada vez más gente escribiendo a la vez), con
#     el sonido de mensaje; los avatares del grupo se enrojecen con la presión;
#   - el reloj de papel muestra los segundos que quedan en número grande y el teléfono vibra al cruzar cada umbral de presión
#     (ya no hay viñeta oscura: la mesa de papel de detrás la pone la capa común);
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
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

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
from frontend.minijuegos.limite_texto import MAX_OPCION, limitar_texto
from frontend.minijuegos_visual import chat_piezas_calculos as pc
from frontend.minijuegos_visual import chat_visual_calculos as calc
from frontend.minijuegos_visual import piezas_chat as pz
from frontend.minijuegos_visual.capa import CapaVisual

CHAT_VISUAL = True
VARIABLE = "ALCALDE_CHAT_VISUAL"

ANCHO_TEL = 0.56               # ancho base del móvil (antes del +15 %, pc.ESCALA_TELEFONO)
X_TEL = -0.34
Y_AREA_ARRIBA = 0.315          # franja útil: debajo del rumor y encima del panel de resultado
Y_AREA_ABAJO = -0.25
RESERVA_ABAJO = 0.058          # franja inferior de la pantalla para «escribiendo…»
RELOJ_C = (0.745, 0.235)       # reloj de papel arriba a la derecha, sobre las respuestas
RELOJ_D = 0.15
Y_RESPUESTAS_CENTRO = -0.055   # las respuestas se centran en vertical en lo que queda bajo el reloj
Y_RESPUESTAS_TOPE = 0.16
ROJO = (235, 87, 87)
ROJO_TEXTO = (150, 36, 36)     # rojo oscuro para texto sobre papel (contraste >= 4,5)
VERDE = (88, 214, 141)
TONOS_AVATAR = ((120, 170, 230), (230, 170, 90), (170, 130, 220), (110, 200, 170))
DUR_FINAL = 2.4

_textura_vineta = None


def _rgba(tono, alfa=1.0):
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
        self.vista = Entity(parent=self)
        # Se oculta lo de la vista base (se conserva: el tutorial o el cierre pueden tocarlo).
        for e in (self.panel, self.texto_chat, self.rotulo, self.barra, self.pie):
            e.enabled = False
        self._valores_log = {}
        self.x_tel = X_TEL
        ancho, alto, y_arriba, cy = pc.medidas_telefono(Y_AREA_ARRIBA - Y_AREA_ABAJO, (Y_AREA_ARRIBA + Y_AREA_ABAJO) / 2,
                                                          ancho_base=ANCHO_TEL)
        self.ancho_tel, self.alto_tel, self.y_tel = ancho, alto, cy
        self.telefono = pz.TelefonoPapel(ancho, alto, (self.x_tel, cy), parent=self.vista)
        px_, py_, pw, ph = self.telefono.pantalla()
        self.pant = (px_, py_, pw, ph)
        pant_izq, pant_arriba, pant_abajo = px_ - pw / 2, py_ + ph / 2, py_ - ph / 2
        # Cabecera amarilla con el retrato del grupo (filo de tinta debajo).
        alto_cab = 0.075
        y_cab = pant_arriba - alto_cab / 2
        ui.rect(self.vista, pw, alto_cab + a_unidades(3), estilo.TINTA, (px_, y_cab - a_unidades(1.5)), z=0.0055, radio_px=8)
        ui.rect(self.vista, pw, alto_cab, estilo.COLOR_ACENTO, (px_, y_cab), z=0.005, radio_px=8)
        pz.avatar(self.vista, "Grupo", 3, (pant_izq + 0.05, y_cab), 0.052, z=-0.001)
        Text("Chat del barrio", parent=self.vista, origin=(-0.5, 0), position=(pant_izq + 0.095, y_cab + 0.012, -0.003),
             scale=escala_fuente(17), font=tipografia.fuente_piel(titulo=True), color=_rgba(estilo.TINTA, 1))
        Text("3 en línea", parent=self.vista, origin=(-0.5, 0), position=(pant_izq + 0.095, y_cab - 0.014, -0.003),
             scale=escala_fuente(13), color=_rgba(estilo.TINTA, 1))
        self.y_burb_abajo = pant_abajo + RESERVA_ABAJO + 0.01
        self.y_burb_arriba = pant_arriba - alto_cab - 0.02
        self.burbujas = Entity(parent=self.vista, z=-0.01)
        # Presión: reloj de papel con los segundos en número grande (se quitó la fila de avatares «esperando»).
        nombres = [calc.nombre_corto(t["de"]) for t in self.partida.turnos]
        self.nombres = list(dict.fromkeys(nombres))[:4] or ["Grupo"]
        self.reloj = pz.RelojPresion(RELOJ_D, parent=self.vista, position=(RELOJ_C[0], RELOJ_C[1], -0.02))
        self.avatares = []
        self._avatares_raiz = []
        self.alarma = Entity(parent=self.vista, position=(RELOJ_C[0] - RELOJ_D / 2 - 0.13, RELOJ_C[1], -0.03), enabled=False)
        ui.rect(self.alarma, 0.2 + a_unidades(6), 0.058 + a_unidades(6), estilo.TINTA, (0, 0), z=0.002, radio_px=8)
        ui.rect(self.alarma, 0.2, 0.058, estilo.PAPEL, (0, 0), z=0.001, radio_px=6)
        Text("¡Rápido!", parent=self.alarma, origin=(0, 0), position=(0, 0, -0.002), scale=escala_fuente(19),
             font=tipografia.fuente_piel(titulo=True), color=_rgba(ROJO_TEXTO, 1))
        # Franja inferior del móvil: «escribiendo…» del grupo.
        y_franja = pant_abajo + RESERVA_ABAJO / 2 + 0.004
        self.escribiendo_txt = Text("", parent=self.vista, origin=(-0.5, 0), position=(pant_izq + 0.03, y_franja, -0.008),
                                    scale=escala_fuente(13), color=_rgba(estilo.TINTA, 1))
        # Aviso de datos (en una placa de papel bajo las respuestas) y resalte rojo de la respuesta con el foco.
        self.resalte = Entity(parent=self.vista, model="quad", color=_rgba(ROJO, 0.0), enabled=False)
        self.aviso_placa = Entity(parent=self.vista, enabled=False)
        self._placa_borde = Entity(parent=self.aviso_placa, model="quad", color=_rgba(estilo.TINTA), z=0.002)
        self._placa_fondo = Entity(parent=self.aviso_placa, model="quad", color=_rgba(estilo.PAPEL), z=0.001)
        self.aviso_txt = ui.texto(self.vista, "", 16, pc.ANCHO_RESPUESTAS - 0.04, estilo.TINTA,
                                  (pc.X_RESPUESTAS - pc.ANCHO_RESPUESTAS / 2 + 0.02, -0.2), negrita=True)
        self.aviso_txt.z = -0.02
        # Sin viñeta oscura (la mesa la pone la capa común): se conserva la entidad, apagada, por compatibilidad.
        self.vineta_e = Entity(parent=self.vista, enabled=False)
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
            altos = [ui.Tarjeta.alto_necesario(limitar_texto(o["texto"], MAX_OPCION), pc.ANCHO_RESPUESTAS, 17, "", 13, minimo=0.085,
                                               reserva=pz.GloboRespuesta.RESERVA) for o in turno["opciones"]]
            ys, _arriba = pc.reparto_respuestas(altos, Y_RESPUESTAS_CENTRO, Y_RESPUESTAS_TOPE)
            for i, o in enumerate(turno["opciones"]):
                t = pz.GloboRespuesta(pc.ANCHO_RESPUESTAS, altos[i], limitar_texto(o["texto"], MAX_OPCION), i + 1, 17, parent=self,
                                      position=(pc.X_RESPUESTAS, ys[i]), al_clic=lambda i=i: self.responder(i),
                                      al_cursor=lambda i=i: self.poner_foco(i))
                self.opciones.append(t)
                self.focables.append(t)
            self.foco = 0
            self._pintar_foco()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("chat_visual", error)
            self._quitar_vista()

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
        px = 16
        ancho_max = 0.40
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
        x_izq = self.pant[0] - self.pant[2] / 2 + 0.085
        x_der = self.pant[0] + self.pant[2] / 2 - 0.03
        self._puntos = []
        for i, y in pos:
            quien, tipo, lineas, ancho, alto, idx = items[i]
            if tipo == "msg" or tipo == "puntos":
                nombre = quien or calc.nombre_corto(self.partida.turno_actual()["de"] if self.partida.turno_actual() else "")
                cx = x_izq + ancho / 2
                indice = self.nombres.index(calc.nombre_corto(nombre)) if calc.nombre_corto(nombre) in self.nombres else 0
                de_rol = self._de_completo(nombre)
                pz.globo(self.burbujas, ancho, alto, (cx, y), pc.tono_globo(de_rol, indice), "izq")
                pz.avatar(self.burbujas, de_rol, indice, (x_izq - 0.05, y - alto / 2 + 0.03), 0.056)
                if tipo == "puntos":
                    for k in range(3):
                        self._puntos.append(Entity(parent=self.burbujas, model="circle", scale=0.012, color=_rgba(estilo.TINTA),
                                                   position=(cx - 0.025 + k * 0.025, y, -0.01)))
                else:
                    Text(calc.nombre_corto(quien), parent=self.burbujas, origin=(-0.5, 0),
                         position=(cx - ancho / 2 + 0.014, y + alto / 2 - 0.017, -0.01), scale=escala_fuente(12),
                         font=tipografia.fuente_piel(titulo=True), color=_rgba(estilo.TINTA, 1))
                    self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.03, estilo.TINTA)
            elif tipo == "tu":
                cx = x_der - ancho / 2
                pz.globo(self.burbujas, ancho, alto, (cx, y), estilo.COLOR_ACENTO, "der")
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, estilo.TINTA)
                tipo_marca = pc.marca_de_valor(self._valores_log.get(idx))
                if tipo_marca:       # palomita verde (protegió) o aspa roja (cedió un dato), en una chapa sobre el globo
                    px_m, py_m = cx - ancho / 2 - 0.036, y
                    Entity(parent=self.burbujas, model="circle", color=_rgba(estilo.TINTA), position=(px_m, py_m, -0.012), scale=0.054)
                    Entity(parent=self.burbujas, model="circle", color=_rgba(estilo.PAPEL), position=(px_m, py_m, -0.013), scale=0.047)
                    pz.marca(self.burbujas, tipo_marca, (px_m, py_m), 0.026, z=-0.016)
            elif tipo == "visto":    # tiempo agotado: burbuja gris «En visto» a tu lado del chat
                cx = x_der - ancho / 2
                pz.globo(self.burbujas, ancho, alto, (cx, y), (205, 205, 212), "der")
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, (90, 92, 106))
            else:   # contexto y reacciones: globo gris pequeño centrado / en visto
                cx = self.x_tel
                pz.globo(self.burbujas, ancho, alto, (cx, y), (214, 214, 220), "izq", con_cola=False)
                self._texto_globo(lineas, px, cx - ancho / 2 + 0.014, y + alto / 2 - 0.012, estilo.TINTA)

    def _de_completo(self, nombre):
        """«Marcela» -> «Marcela (organizadora)» (el rol decide color y retrato); si no se encuentra, el mismo texto."""
        corto = calc.nombre_corto(nombre)
        for t in self.partida.turnos:
            if calc.nombre_corto(t["de"]) == corto:
                return t["de"]
        return nombre

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
        ancho_txt = pc.ANCHO_RESPUESTAS - 0.04
        lineas = ui.lineas_de(texto, 16, ancho_txt, negrita=True) if texto else []
        self.aviso_txt.text = "\n".join(lineas)
        if texto and tarjeta is not None:
            ultimo = self.opciones[-1]
            alto_txt = len(lineas) * a_unidades(16) * ui.LINEA + 0.02
            ancho_placa = min(pc.ANCHO_RESPUESTAS, max(ui.medir(l, 16, negrita=True) for l in lineas) + 0.05)
            y_placa = ultimo.y - ultimo.alto / 2 - 0.03 - alto_txt / 2
            x_placa = pc.X_RESPUESTAS - pc.ANCHO_RESPUESTAS / 2 + ancho_placa / 2
            borde = a_unidades(estilo.GROSOR_BORDE_PX)
            self._placa_borde.model = ui.modelo_redondeado(ancho_placa + 2 * borde, alto_txt + 2 * borde, 8)
            self._placa_borde.scale = (ancho_placa + 2 * borde, alto_txt + 2 * borde)
            self._placa_fondo.model = ui.modelo_redondeado(ancho_placa, alto_txt, 6)
            self._placa_fondo.scale = (ancho_placa, alto_txt)
            self.aviso_placa.position = (x_placa, y_placa, -0.015)
            self.aviso_placa.enabled = True
            self.aviso_txt.x = x_placa - ancho_placa / 2 + 0.025
            self.aviso_txt.y = y_placa + alto_txt / 2 - 0.01
            self.resalte.model = ui.modelo_redondeado(tarjeta.ancho, tarjeta.alto, 8)
            self.resalte.scale = (tarjeta.ancho, tarjeta.alto)
            self.resalte.position = (tarjeta.x, tarjeta.y, -0.06)
            self.resalte.color = _rgba(ROJO, 0.16)
            self.resalte.enabled = True
        else:
            self.aviso_placa.enabled = False
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
        # Avatares enfadados (ya no hay fila de avatares ni viñeta oscura: la presión la dicen el reloj y el temblor).
        enfado = calc.enfado(presion)
        for i, (raiz, cara, tono) in enumerate(self.avatares):
            mezcla = tuple(tono[k] + (ROJO[k] - tono[k]) * enfado for k in range(3))
            cara.color = _rgba(mezcla, 1)
            raiz.rotation_z = 0.0 if reducir else pc.inclinacion_avatar(presion, i)
        self.reloj.fijar(0.0 if self.terminado else 1.0 - presion,
                         0 if self.terminado else pc.segundos_restantes(self.partida.restante))
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
        self.aviso_placa.enabled = False
        for e in [self.reloj, self.alarma] + self._avatares_raiz:      # la presión ya no corre: se quita
            e.enabled = False
        self._protegido = self.partida.datos_cedidos() == 0
        # Tapa todo el chat entre la cabecera amarilla y la franja inferior de la pantalla del móvil.
        px_, py_, pw, ph = self.pant
        arriba = py_ + ph / 2 - 0.085          # por debajo de la cabecera amarilla del móvil
        abajo = py_ - ph / 2 + RESERVA_ABAJO + 0.006
        cx, cy = px_, (arriba + abajo) / 2
        ancho, alto = pw - 0.012, arriba - abajo
        self._caja_final = (cx, cy, ancho, alto)
        ui.rect(self.final, ancho, alto, estilo.PAPEL, (cx, cy), z=0.002, radio_px=10)
        if self._protegido:
            self._halo = Entity(parent=self.final, model="circle", color=_rgba(VERDE, 0.0), position=(cx, cy + 0.02, 0.001),
                                scale=0.15)
            pz.avatar(self.final, "Dani (amigo)", 1, (cx, cy + 0.02), 0.11, z=-0.001)
            Text("Tu amigo", parent=self.final, origin=(0, 0), position=(cx, cy - 0.062, -0.002), scale=escala_fuente(15),
                 color=_rgba(estilo.TINTA, 1))
            self._gracias = Text("¡Gracias por no pasar mis datos!", parent=self.final, origin=(0, 0),
                                 position=(cx, cy + 0.11, -0.002), scale=escala_fuente(18), font=tipografia.fuente_piel(titulo=True),
                                 color=_rgba(estilo.TINTA, 1))
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
            Entity(parent=self.final, model="circle", color=_rgba(estilo.TINTA, 1), position=(fx_, fy, 0.001), scale=0.07)
            Entity(parent=self.final, model="circle", color=_rgba(ROJO, 1), position=(fx_, fy, 0), scale=0.064)
            Text("?", parent=self.final, origin=(0, 0), position=(fx_, fy, -0.002), scale=escala_fuente(26),
                 font=tipografia.fuente_piel(titulo=True), color=_rgba(estilo.TINTA, 1))
            Text("Perfil desconocido", parent=self.final, origin=(0, 0), position=(fx_ - 0.06, fy - 0.058, -0.002),
                 scale=escala_fuente(14), font=tipografia.fuente_piel(titulo=True), color=_rgba(ROJO_TEXTO, 1))
            Text("\n".join(ui.lineas_de("El dato salió del grupo y ya no sabes quién lo tiene.", 14, ancho - 0.05)), parent=self.final,
                 origin=(0, 0), position=(cx, cy + alto / 2 - 0.085, -0.002), scale=escala_fuente(14),
                 color=_rgba(estilo.TINTA, 1))
            sx, sy = self._ruta[0]
            pz.avatar(self.final, "Tú (ciudadano)", 0, (sx, sy), 0.06, z=-0.001)
            Text("Tú", parent=self.final, origin=(0, 0), position=(sx, sy - 0.05, -0.002), scale=escala_fuente(14),
                 font=tipografia.fuente_piel(titulo=True), color=_rgba(estilo.TINTA, 1))
            # La ficha termina justo encima del perfil desconocido (no lo tapa).
            self._ruta_chip = self._ruta[:-1] + [(fx_ - 0.04, fy + 0.055)]
            self._chip = Entity(parent=self.final, position=(sx, sy + 0.06, -0.01))
            ui.rect(self._chip, 0.11 + a_unidades(6), 0.034 + a_unidades(6), estilo.TINTA, (0, 0), z=0.002, radio_px=6)
            ui.rect(self._chip, 0.11, 0.034, ROJO, (0, 0), z=0.001, radio_px=5)
            Text("el dato", parent=self._chip, origin=(0, 0), z=-0.002, scale=escala_fuente(13),
                 font=tipografia.fuente_piel(titulo=True), color=_rgba(estilo.TINTA, 1))
        resumen = pc.resumen_final(self.partida.respuestas)
        if resumen:
            Text("\n".join(ui.lineas_de(resumen, 13, ancho - 0.04)), parent=self.final, origin=(0, 0),
                 position=(cx, cy + alto / 2 - 0.03, -0.002), scale=escala_fuente(13), color=_rgba(estilo.TINTA, 1))
        self.final.enabled = True
        if self._fx is not None:
            # Más pequeño y pegado al borde inferior del panel: no tapa «Tu amigo» ni se sale del móvil.
            self._vigilar(lambda: self._fx.sello("A SALVO" if self._protegido else "REGALADOS", (cx, cy - alto / 2 + 0.04),
                                                 estilo.ESTADO_EXITO if self._protegido else estilo.ESTADO_ERROR,
                                                 escala=0.7))
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
