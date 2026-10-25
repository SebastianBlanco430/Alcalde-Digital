# Cálculos puros (sin ursina ni panda3d) de la red social «Civitas» de la escena de juego, con
# aspecto de red tipo X: autores, @usuarios, insignias, horas relativas, contadores, comentarios,
# tendencias y la vista previa de cada publicación. Todo sale de un HASH ESTABLE del texto de la
# noticia (sha256), nunca de `random` ni de `hash()` (que cambia entre ejecuciones): la misma
# noticia se ve siempre igual. Los textos son de ficción; no hay marcas ni personas reales.
#
# También trae el Animador (pequeño motor de tweens con dt, sin motor gráfico) y utilidades de
# disposición, para probarlos con pytest sin abrir ventana.

import hashlib
import math
import unicodedata

from backend.datos.nombres_visibles import glosa_etiqueta, glosar_texto


# --------------------------------------------------------------------------- azar estable

# Flujo de números reproducible: cada llamada pide el siguiente sha256(base|n).
class AzarEstable:

    def __init__(self, base):
        self._base = str(base)
        self._n = 0

    def _siguiente(self):
        resumen = hashlib.sha256(f"{self._base}|{self._n}".encode("utf-8")).digest()
        self._n += 1
        return int.from_bytes(resumen[:8], "big")

    def entero(self, n):
        return self._siguiente() % max(1, n)

    def entre(self, minimo, maximo):
        return minimo + self.entero(maximo - minimo + 1)

    def real(self):
        return (self._siguiente() % 1_000_000) / 1_000_000

    def elegir(self, secuencia):
        return secuencia[self.entero(len(secuencia))]

    def barajar(self, secuencia):
        lista = list(secuencia)
        for i in range(len(lista) - 1, 0, -1):
            j = self.entero(i + 1)
            lista[i], lista[j] = lista[j], lista[i]
        return lista


def crear_azar(texto, sal=""):
    return AzarEstable(f"{sal}#{texto}")


# --------------------------------------------------------------------------- formato

# 1234 -> «1,2 K», 1500000 -> «1,5 M»; por debajo de mil, el número tal cual. Coma decimal.
def formatear_numero(n):
    n = max(0, int(n))
    if n < 1000:
        return str(n)
    for divisor, sufijo in ((1_000_000, "M"), (1_000, "K")):
        if n >= divisor:
            valor = n / divisor
            if valor < 100:
                valor = int(valor * 10 + 0.5) / 10
                if valor >= 100:      # 99,96 K se redondea a 100 K
                    return f"{int(valor)} {sufijo}"
                texto = str(int(valor)) if valor == int(valor) else f"{valor:.1f}".replace(".", ",")
            else:
                texto = str(int(valor + 0.5))
            if sufijo == "K" and texto in ("1000", "1 000"):
                return "1 M"
            return f"{texto} {sufijo}"
    return str(n)


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


# «Tío Chucho» -> «tio_chucho» (para el @usuario).
def slug_usuario(nombre):
    base = _sin_acentos(nombre).lower()
    base = "".join(c if c.isalnum() else "_" for c in base)
    while "__" in base:
        base = base.replace("__", "_")
    return base.strip("_")


# Recorta `texto` con «...» hasta que `medir(texto)` quepa en `ancho` (medir lo aporta quien llama).
def recortar_a_ancho(texto, medir, ancho):
    if medir(texto) <= ancho:
        return texto
    while texto and medir(texto + "...") > ancho:
        texto = texto[:-1]
    return (texto.rstrip() + "...") if texto else ""


# --------------------------------------------------------------------------- autores

COLORES_AVATAR = (
    (232, 84, 150), (46, 184, 116), (66, 133, 244), (240, 150, 40),
    (140, 110, 200), (60, 180, 170), (214, 62, 62), (255, 220, 60),
)
AZUL_VERIFICADO = (64, 160, 255)
DORADO_VERIFICADO = (255, 200, 80)

# Las listas solo CRECEN por el final (2026-10: lugares nuevos y vecinos del grafo social): cambiar su tamaño cambia
# qué autor, tendencia o comentario sale para cada noticia, pero sigue siendo determinista (crear_azar con el texto).
_MEDIOS = ("Diario Nova", "Nova al Día", "Radio Ladera", "Noticias del Barrio", "El Pregonero", "Canal Civitas",
           "Rádio Comunitária 98,7", "Jornal do Morro")
_PERSONAS = (
    "Paola Reyes", "Andrés Quintero", "Marta Lozano", "Camila Duarte", "Joao Mendes", "Luciana Prado",
    "Tío Chucho", "Sebas Ramírez", "Dani Ocampo", "Valentina Cruz", "Don Efraín", "Rafa Torres",
    "Mariana Silva", "Bruno Almeida",
    "Luana Ferreira", "Kauã Oliveira", "Dona Quitéria", "Seu Otávio", "Nayara Santos", "Marcos do Morro",
    "Mestre Zé do Pandeiro",
)
_ANONIMAS = ("Vecino Indignado", "La Voz del Barrio", "Cuenta Anónima", "Nova Alerta 24", "Chisme Nova", "Ojo con Nova",
            "Fofoca da Laje", "Zap do Morro")
_INSTITUCIONES = (
    "Prefeitura de Ciudad Nova", "Universidade de Nova", "Hospital Santa Casa", "Comisión Electoral",
    "Rodoviária", "Secretaría de Cultura",
    "Mercado Municipal", "Escola de Samba Unidos da Esperança", "Estação do Teleférico",
)
_BOTS = ("Nova Premios", "Gana Ya", "Oferta Total", "Sorteo Nova", "Cripto Nova")


def _color_texto_sobre(rgb):
    luz = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return (18, 20, 32) if luz > 150 else (250, 244, 228)


def _autor(nombre, tipo, azar, verificado=None, con_numero=False):
    handle = slug_usuario(nombre)
    if con_numero:
        handle += str(azar.entre(1, 99))
    color = azar.elegir(COLORES_AVATAR)
    return {
        "nombre": nombre, "handle": "@" + handle, "inicial": nombre[0].upper(),
        "color_avatar": color, "color_letra": _color_texto_sobre(color),
        "verificado": verificado, "tipo": tipo,
    }


# Insignia según el tipo de cuenta (azul = persona/cuenta, dorada = organización).
def _verificado_de(tipo, azar):
    suerte = azar.real()
    if tipo == "medio":
        return "dorada" if suerte < 0.55 else ("azul" if suerte < 0.75 else None)
    if tipo == "institucion":
        return "dorada" if suerte < 0.85 else "azul"
    if tipo == "persona":
        return "azul" if suerte < 0.22 else None
    return None


# Autor de la publicación principal: solo medios, personas y cuentas anónimas (las instituciones
# oficiales no firman las noticias del juego, para no dar pistas falsas sobre la veracidad).
def autor_de_noticia(texto):
    azar = crear_azar(texto, "autor")
    tipo = azar.elegir(("medio", "persona", "persona", "anonima"))
    nombre = azar.elegir({"medio": _MEDIOS, "persona": _PERSONAS, "anonima": _ANONIMAS}[tipo])
    return _autor(nombre, tipo, azar, _verificado_de(tipo, azar), con_numero=tipo != "medio")


# Cuentas sugeridas de «A quién seguir» (distintas entre sí).
def autores_a_seguir(texto, cantidad=3):
    azar = crear_azar(texto, "seguir")
    conjunto = [(n, "institucion") for n in _INSTITUCIONES] + [(n, "medio") for n in _MEDIOS] \
        + [(n, "persona") for n in _PERSONAS[:6]]
    resultado = []
    for nombre, tipo in azar.barajar(conjunto)[:cantidad]:
        resultado.append(_autor(nombre, tipo, azar, _verificado_de(tipo, azar), con_numero=tipo == "persona"))
    return resultado


# Cuenta del jugador (barra lateral): el color sale del rol para que sea estable.
def autor_jugador(nombre, rol):
    azar = crear_azar(f"{nombre}|{rol}", "jugador")
    autor = _autor(nombre or "Jugador", "persona", azar, None)
    autor["handle"] = "@" + (slug_usuario(nombre or "jugador") or "jugador")
    return autor


HORAS = ("ahora", "1 min", "2 min", "4 min", "7 min", "12 min", "18 min", "26 min", "41 min", "1 h", "2 h", "3 h")


def hora_relativa(azar):
    return azar.elegir(HORAS)


# --------------------------------------------------------------------------- contadores

# Contadores de la publicación: vistas -> me gusta -> republicaciones -> respuestas.
def contadores_de(texto):
    azar = crear_azar(texto, "contadores")
    vistas = azar.entre(2_400, 180_000)
    me_gusta = max(3, int(vistas * (0.008 + azar.real() * 0.05)))
    republicaciones = max(2, int(me_gusta * (0.18 + azar.real() * 0.3)))
    respuestas = max(1, int(me_gusta * (0.05 + azar.real() * 0.14)))
    return {"respuestas": respuestas, "republicaciones": republicaciones, "me_gusta": me_gusta, "vistas": vistas}


# Cuánto sube cada contador al decidir. Compartir empuja republicaciones, me gusta y vistas;
# reportar solo suma unas vistas (el reporte no hace viral a nadie).
def incremento_por_decision(contadores, tipo):
    if tipo == "compartir":
        return {
            "respuestas": 0,
            "republicaciones": max(2, int(contadores["republicaciones"] * 0.07) + 1),
            "me_gusta": max(3, int(contadores["me_gusta"] * 0.05) + 1),
            "vistas": max(40, int(contadores["vistas"] * 0.04)),
        }
    return {"respuestas": 0, "republicaciones": 0, "me_gusta": 0, "vistas": max(8, int(contadores["vistas"] * 0.005))}


def sumar_contadores(contadores, incremento):
    return {k: contadores[k] + incremento.get(k, 0) for k in contadores}


# --------------------------------------------------------------------------- animaciones (tweens)

def ease_out_cubic(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_out_back(p, sobreimpulso=1.4):
    p = max(0.0, min(1.0, p))
    c3 = sobreimpulso + 1
    return 1 + c3 * (p - 1) ** 3 + sobreimpulso * (p - 1) ** 2


# Factor de escala de un «pop»: 1 -> 1 + extra -> 1 a lo largo de p en [0, 1].
def pop(p, extra=0.4):
    p = max(0.0, min(1.0, p))
    return 1 + extra * math.sin(math.pi * p) * (1 - 0.35 * p)


# Valor entero que sube de `inicio` a `fin` con ease-out según `progreso` (0..1).
def cuenta_animada(inicio, fin, progreso):
    return int(round(inicio + (fin - inicio) * ease_out_cubic(progreso)))


# Motor mínimo de tweens: cada tween llama fn(p) con p en [0, 1] entre `retraso` y retraso+duracion
# y, al final, al_fin(). avanzar(dt) lo mueve; terminar_todo() salta al final de todo (para no
# acumular animaciones si el jugador decide rápido).
class Animador:

    def __init__(self):
        self._tweens = []

    def agregar(self, duracion, funcion, al_fin=None, retraso=0.0):
        self._tweens.append({"d": max(1e-6, duracion), "f": funcion, "fin": al_fin, "t": -retraso})

    def activo(self):
        return bool(self._tweens)

    def avanzar(self, dt):
        instantanea, self._tweens = self._tweens, []
        vivos, terminados = [], []
        for tw in instantanea:
            tw["t"] += dt
            if tw["t"] < 0:
                vivos.append(tw)
                continue
            p = min(1.0, tw["t"] / tw["d"])
            tw["f"](p)
            (terminados if p >= 1.0 else vivos).append(tw)
        self._tweens = vivos + self._tweens     # los al_fin pueden agregar tweens nuevos
        for tw in terminados:
            if tw["fin"] is not None:
                tw["fin"]()

    def terminar_todo(self):
        # Los callbacks al_fin pueden agregar más tweens: se repite hasta vaciar.
        for _ in range(16):
            if not self._tweens:
                return
            pendientes, self._tweens = self._tweens, []
            for tw in pendientes:
                tw["f"](1.0)
            for tw in pendientes:
                if tw["fin"] is not None:
                    tw["fin"]()

    def cancelar(self):
        self._tweens = []


# --------------------------------------------------------------------------- comentarios

_COMENTARIOS = {
    "indignado": (
        "¡Qué vergüenza! Esto no se puede quedar así.",
        "Ya nadie respeta a Ciudad Nova. Increíble.",
        "Siempre lo mismo y nadie dice nada. ¡Basta!",
        "Isso é um absurdo! ¿Hasta cuándo, Ciudad Nova?",
    ),
    "esceptico": (
        "¿Alguien tiene la fuente? No me cuadra.",
        "Hmm, esto huele raro. ¿Hay enlace al comunicado?",
        "Antes de creerlo esperaría una confirmación oficial.",
        "Tá, mas cadê a fonte? Sin enlace no me lo creo.",
    ),
    "bot": (
        "GANA $$$ desde casa >> premios.civitas.invalid #Gratis",
        "Sigue a @promo_nova y recibe tu bono. Escríbeme ya!!",
        "Mira esto >> increible.civitas.invalid",
        "Ganhe dinheiro fácil >> sorte.civitas.invalid #Promo",
    ),
    "apoyo": (
        "Gracias por compartir, ojalá más gente lo vea.",
        "Justo lo que estaba buscando, gracias.",
        "Buen dato. Lo comparto con mi familia.",
        "Valeu por avisar, lo paso al grupo de la familia.",
    ),
    "chiste": (
        "Y yo aquí esperando el bus, jaja.",
        "Esto parece sacado de una telenovela, jajaja.",
        "Lo único estable en Nova es el trancón.",
        "Más enredado que los cables de un poste del morro, jaja.",
    ),
    "verificador": (
        "Ojo: aún no hay confirmación. Esperemos antes de compartir.",
        "Contrasten con fuentes oficiales, por favor.",
        "Revisen la fecha y la fuente antes de reenviar.",
        "Antes de mandarlo al grupo, confirma con la Rádio Comunitária.",
    ),
}
ARQUETIPOS = tuple(_COMENTARIOS)


# Hasta `cantidad` respuestas falsas, de arquetipos distintos, con su autor, hora y me gusta.
def comentarios_de(texto, cantidad=3):
    azar = crear_azar(texto, "comentarios")
    resultado = []
    # Nombres distintos entre sí y distintos del autor de la publicación.
    libres = [n for n in azar.barajar(_PERSONAS) if n != autor_de_noticia(texto)["nombre"]]
    for arquetipo in azar.barajar(ARQUETIPOS)[:cantidad]:
        if arquetipo == "bot":
            nombre = azar.elegir(_BOTS)
            autor = _autor(nombre, "bot", azar, None)
            autor["handle"] = "@" + slug_usuario(nombre) + str(azar.entre(1000, 99999))
        else:
            nombre = libres.pop(0)
            autor = _autor(nombre, "persona", azar, _verificado_de("persona", azar), con_numero=True)
        resultado.append({
            "autor": autor, "arquetipo": arquetipo, "texto": azar.elegir(_COMENTARIOS[arquetipo]),
            "hora": hora_relativa(azar), "me_gusta": azar.entre(2, 480),
        })
    return resultado


# --------------------------------------------------------------------------- tendencias

_TENDENCIAS = (
    ("Ciudad Nova", "#CiudadNova"), ("Política", "#PrefeituraAberta"),
    ("Tendencia", "#VerificaAntes"), ("Barrio", "#MorroDaEsperança"),
    ("Política", "#DebateNova"), ("Salud", "#AguaSegura"),
    ("Movilidad", "#BusesNocturnos"), ("Educación", "#BecasNova"),
    ("Civitas", "#Civitas"), ("Elecciones", "#VotaInformado"),
    ("Cultura", "#EnsaioDeSamba"), ("Movilidad", "#TeleféricoNova"), ("Economía", "#PreçoDaFeira"),
    ("Barrio", "#RádioDoMorro"),
)


# [(categoría corta, hashtag, «12,4 K publicaciones»)], distintos entre sí; cambian con cada noticia.
def tendencias_de(texto, cantidad=3):
    azar = crear_azar(texto, "tendencias")
    resultado = []
    for categoria, etiqueta in azar.barajar(_TENDENCIAS)[:cantidad]:
        resultado.append((categoria, etiqueta, formatear_numero(azar.entre(1_200, 240_000)) + " publicaciones"))
    return resultado


# --------------------------------------------------------------------------- vista previa

_TITULOS_ENLACE = (
    "Lo que sabemos hasta ahora", "Comunicado completo y cronología", "Minuto a minuto desde Ciudad Nova",
    "Lo que dicen los vecinos del barrio", "Todo lo que debes saber en 3 minutos", "Análisis: ¿qué hay detrás de esto?",
    "Lo que se comenta en la laje",
)
_DOMINIOS = ("diarionova.civitas.invalid", "novaaldia.civitas.invalid", "radioladera.civitas.invalid", "elpregonero.civitas.invalid",
             "jornaldomorro.civitas.invalid")
VARIANTES_IMAGEN = ("ciudad", "multitud", "captura", "calle", "video")
TIPOS_MEDIA = ("ninguna", "imagen", "enlace")


# Vista previa de la publicación: ninguna (≈35 %), imagen generada por código (≈40 %) o enlace (≈25 %).
def media_de(texto):
    azar = crear_azar(texto, "media")
    suerte = azar.real()
    tipo = "ninguna" if suerte < 0.35 else ("imagen" if suerte < 0.75 else "enlace")
    return {
        "tipo": tipo, "variante": azar.elegir(VARIANTES_IMAGEN), "semilla": azar.entero(10_000),
        "titulo_enlace": azar.elegir(_TITULOS_ENLACE), "dominio": azar.elegir(_DOMINIOS),
    }


# Todo lo que dibuja una publicación, calculado de una vez a partir del texto de la noticia.
def publicacion_de(texto, media=None):
    azar = crear_azar(texto, "hora")
    datos = {
        "texto": texto,
        "autor": autor_de_noticia(texto),
        "hora": hora_relativa(azar),
        "contadores": contadores_de(texto),
        "media": media_de(texto) if media is None else media,
        "comentarios": comentarios_de(texto),
        "tendencias": tendencias_de(texto),
        "seguir": autores_a_seguir(texto),
    }
    return datos


# Copia de una publicación para dibujarla, con los nombres brasileños traducidos (nombres_visibles). Va DESPUÉS de
# publicacion_de: el azar sale del texto original. «A quién seguir» no se traduce: recorta a 0,19 y no cabría.
def publicacion_visible(datos):
    visibles = dict(datos)
    visibles["texto"] = glosar_texto(datos["texto"])
    visibles["autor"] = dict(datos["autor"], nombre=glosar_texto(datos["autor"]["nombre"]))
    visibles["comentarios"] = [
        dict(c, texto=glosar_texto(c["texto"]), autor=dict(c["autor"], nombre=glosar_texto(c["autor"]["nombre"])))
        for c in datos["comentarios"]]
    visibles["tendencias"] = [tendencia_visible(t) for t in datos["tendencias"]]
    media = datos.get("media")
    if media and media.get("titulo_enlace"):
        visibles["media"] = dict(media, titulo_enlace=glosar_texto(media["titulo_enlace"]))
    return visibles


# «12,4 K publicaciones» -> «12,4 K».
def cuenta_corta(cuenta):
    return cuenta.replace(" publicaciones", "")


# La traducción de la etiqueta va en la línea de la categoría: «Barrio · Radio del cerro».
def tendencia_visible(tendencia):
    categoria, etiqueta, cuenta = tendencia
    glosa = glosa_etiqueta(etiqueta)
    return (f"{categoria} · {glosa}" if glosa else categoria), etiqueta, cuenta


# --------------------------------------------------------------------------- disposición

# Centros y borde inferior de bloques apilados hacia abajo desde `y_inicio` (y decrece).
# Devuelve ([centro_y de cada bloque], y_final).
def apilar(alturas, separacion, y_inicio):
    centros = []
    y = y_inicio
    for alto in alturas:
        centros.append(y - alto / 2)
        y -= alto + separacion
    return centros, y + separacion


# Cuántos bloques de `alturas` caben apilados con `separacion` en `disponible` de alto.
def cuantos_caben(alturas, separacion, disponible):
    usado = 0.0
    for i, alto in enumerate(alturas):
        usado += alto + (separacion if i else 0)
        if usado > disponible:
            return i
    return len(alturas)
