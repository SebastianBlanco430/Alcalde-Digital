# Carteles de campaña de Tomás Arenas con el sello de la Torre de la Tradición: el «espejo» del día 5 del hilo
# conductor (docs/HILO_CONDUCTOR.md). Desde el día 5 aparecen en el mundo CARTELES (poste + tablero) en tres plazas con
# el mismo sello que firma los rumores falsos: el jugador puede atar cabos; ningún texto lo dice. Además, la mañana del
# día 5 llega al teléfono del jugador activo el anuncio del debate de la campaña (remitente y texto en
# backend/datos/sello_rumores.json), con el sello pintado por frontend/hud.py.
#
# Entidades propias (no edita frontend/props_mundo.py ni la ciudad): cuelgan de la escena del mundo y se crean la primera
# vez que el reloj marca el día 5 o más. Sin colisión (decoración). main.py lo carga con extensiones.aplicar(...,
# modulos=MODULOS_HILO). En línea no hay reloj: no aparece.
#
# BANDERA: ALCALDE_HILO_SELLO=0 (o ALCALDE_HILO=0) -> registrar() no instala nada.

import math
import sys

from backend.logica import sello_rumores

DIA_ESPEJO = 5
LUGARES = ("Praça da Sé", "Mercado Municipal", "Morro da Esperança")
ALTO_POSTE = 2.6                # m (dos postes)
ANCHO_TABLERO, ALTO_TABLERO = 2.4, 1.3
TONO_TABLERO = (150, 46, 52)    # el granate del sello
TONO_MARCO = (226, 214, 186)
TONO_TEXTO = (238, 228, 205)
LINEAS = ("TOMÁS ARENAS", "Debate: sábado, 19 h", "Partido de la Tradición")   # nombre, debate, franja
# Escala de Text en el mundo (relativa al tablero); _texto_que_cabe la reduce si la línea no cabe en su hueco.
ESCALAS_TEXTO = (9.0, 6.0, 6.5)
ANCHO_LETRA = 0.0148           # m por letra y unidad de escala (ver ancho_estimado)
RADIO_CARTEL = 0.8              # m que reserva en el suelo: los dos postes (el tablero va en alto, a 1,6-2,9 m)
FRACCIONES_RADIO = (0.8, 0.7, 0.9, 1.0, 0.6, 1.1)
GIROS_CANDIDATOS = (0, 25, -25, 50, -50, 75, -75, 100, -100, 130, -130, 160, -160, 180)
PENDIENTE_MAX = 0.18            # desnivel por metro tolerado bajo el cartel
DISTANCIA_PUERTA = 3.5          # m libres delante de cada puerta (pasada relajada)


def posicion_cartel(centro, puerta, radio, lado=1.0):
    """(x, z, giro_y) del cartel: hacia la puerta del lugar a 0,8 del radio de la plaza, corrido 3 m a un `lado`, y
    mirando al centro de la plaza. Función pura (se prueba sin ventana). Es el primer candidato de sitio_cartel."""
    cx, cz = centro
    dx, dz = puerta[0] - cx, puerta[1] - cz
    largo = math.hypot(dx, dz) or 1.0
    ux, uz = dx / largo, dz / largo
    x = cx + ux * radio * 0.8 - uz * 3.0 * lado
    z = cz + uz * radio * 0.8 + ux * 3.0 * lado
    giro = math.degrees(math.atan2(cx - x, cz - z))
    return x, z, giro


def candidatos_cartel(centro, puerta, radio, lado=1.0):
    """Sitios (x, z, giro) en orden de preferencia: el de posicion_cartel y después puntos del borde de la plaza girando
    desde la dirección de la puerta hacia `lado`, a varias fracciones del radio. Todos miran al centro."""
    cx, cz = centro
    yield posicion_cartel(centro, puerta, radio, lado)
    base = math.atan2(puerta[0] - cx, puerta[1] - cz)
    for fraccion in FRACCIONES_RADIO:
        for grados in GIROS_CANDIDATOS:
            angulo = base + math.radians(grados * lado)
            x, z = cx + math.sin(angulo) * radio * fraccion, cz + math.cos(angulo) * radio * fraccion
            yield x, z, math.degrees(math.atan2(cx - x, cz - z))


def sitio_cartel(centro, puerta, radio, lado, *comprobadores):
    """El primer candidato que pasa el primer comprobador; si ninguno, el primero que pasa el segundo (más permisivo), y
    así. Si ninguno pasa nada, el de posicion_cartel (nunca falla). Pura."""
    candidatos = list(candidatos_cartel(centro, puerta, radio, lado))
    for cabe in comprobadores:
        for x, z, giro in candidatos:
            if cabe(x, z):
                return x, z, giro
    return posicion_cartel(centro, puerta, radio, lado)


def _frentes_comercios(mundo):
    """[(círculo, frente)] de todos los puestos de comercio (no solo los de sitio fijo): un círculo alrededor del
    dependiente y el pasillo delante del mostrador, como Reserva hace con los fijos. Sin esto un cartel podía taparle el
    frente a un puesto (el «Bar da Esquina» de la Praça)."""
    try:
        from backend.logica.comercios import resolver_comercios
        from frontend.props_mundo import ANCHO_FRENTE_PUESTO, FRENTE_PUESTO, RADIO_PUESTO_FIJO
        salida = []
        for comercio, (x, z, rumbo) in resolver_comercios(mundo):
            if comercio.tipo == "vendedor_calle":
                continue
            fx, fz = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))
            salida.append(((x, z, RADIO_PUESTO_FIJO + 0.6),
                           ((x, z), (x + fx * FRENTE_PUESTO, z + fz * FRENTE_PUESTO), ANCHO_FRENTE_PUESTO)))
        return salida
    except Exception as error:                  # noqa: BLE001  mundo sin comercios: solo la reserva de siempre
        print(f"[carteles] sin reserva de comercios ({type(error).__name__}: {error})", file=sys.stderr)
        return []


def _comprobadores(mundo, ocupados):
    """(estricto, relajado). ESTRICTO: la misma reserva que el decorado (frontend/props_mundo.Reserva: edificios, zonas
    como el mercadito, puestos fijos, pasillos plaza -> puerta, calles) más los obstáculos añadidos después (props) y
    todos los puestos de comercio. RELAJADO (plazas pequeñas donde no cabe nada): puede quedar junto a un camino, pero
    nunca sobre edificios, obstáculos, puestos, delante de un mostrador ni a menos de DISTANCIA_PUERTA de una puerta.
    Los dos: sin pendiente fuerte y lejos de los otros carteles. Sin la reserva (mundo de pruebas), solo eso último."""
    try:
        from frontend.props_mundo import Reserva, _distancia_a_segmento, pendiente
        reserva = Reserva(mundo)
        extra = getattr(mundo, "obstaculos_extra", None)
        if callable(extra):
            reserva.obstaculos += list(extra())
        for circulo, frente in _frentes_comercios(mundo):
            reserva.circulos.append(circulo)
            reserva.pasos.append(frente)
        frentes = [f for _c, f in _frentes_comercios(mundo)]
        puertas = [e.punto_entrada(1.0) for e in mundo.edificios()]
    except Exception as error:                  # noqa: BLE001
        print(f"[carteles] sin reserva del decorado ({type(error).__name__}: {error})", file=sys.stderr)
        reserva, pendiente = None, None

    def basico(x, z):
        if any(math.hypot(x - ox, z - oz) < 2 * RADIO_CARTEL + 2.0 for ox, oz in ocupados):
            return False
        return pendiente is None or pendiente(mundo.altura, x, z) <= PENDIENTE_MAX

    def estricto(x, z):
        return basico(x, z) and (reserva is None or reserva.cabe(x, z, RADIO_CARTEL, en_plaza=True))

    def relajado(x, z):
        if not basico(x, z):
            return False
        if reserva is None:
            return True
        r = RADIO_CARTEL
        if any(o.choca(x, z, r + 0.4) for o in reserva.obstaculos):
            return False
        for (x0, x1, z0, z1), margen in reserva.cajas:
            if math.hypot(x - min(max(x, x0), x1), z - min(max(z, z0), z1)) < r + min(margen, 0.8):
                return False
        if any(math.hypot(x - cx, z - cz) < cr + r for cx, cz, cr in reserva.circulos):
            return False
        if any(_distancia_a_segmento(x, z, a, b) < ancho + r for a, b, ancho in frentes):
            return False
        return all(math.hypot(x - px, z - pz) >= DISTANCIA_PUERTA for px, pz in puertas)

    return estricto, relajado


def ancho_estimado(linea, escala):
    """Ancho (m, en el tablero) de una línea: Text.width aún no está medido al crearla, así que se estima por letras
    (medido en el juego: «TOMÁS ARENAS» a escala 9 ocupa 1,6 m). Pura."""
    return len(linea) * ANCHO_LETRA * escala


def escala_que_cabe(linea, escala, ancho):
    """La escala pedida o, si la línea no cabe en `ancho`, la que la deja justa. Pura."""
    estimado = ancho_estimado(linea, escala)
    return escala if estimado <= ancho else escala * ancho / estimado


def _texto_que_cabe(Text, rgb, silenciar, texto_sin_tinta, padre, linea, escala, ancho, **opciones):
    texto = Text(linea, parent=padre, scale=escala_que_cabe(linea, escala, ancho), double_sided=True, **opciones)
    return silenciar(texto_sin_tinta(texto))


# Una cara del tablero: sello grande a la izquierda (lo que el jugador debe reconocer), nombre y debate a la derecha y
# una franja crema abajo, a todo lo ancho, con el partido.
def _pintar_cara(frente, sello_tradicion, rgb, Entity, Text, silenciar, texto_sin_tinta):
    medio_ancho = ANCHO_TABLERO / 2
    sello_tradicion.crear_sello(frente, 0.82, 1.0, (-medio_ancho + 0.5, 0.13, -0.001), double_sided=True)
    columna_x, columna_ancho = -medio_ancho + 1.02, ANCHO_TABLERO - 1.15
    nombre, debate, partido = LINEAS
    _texto_que_cabe(Text, rgb, silenciar, texto_sin_tinta, frente, nombre, ESCALAS_TEXTO[0], columna_ancho,
                    origin=(-0.5, 0), position=(columna_x, 0.3, -0.004), color=rgb(TONO_TEXTO))
    _texto_que_cabe(Text, rgb, silenciar, texto_sin_tinta, frente, debate, ESCALAS_TEXTO[1], columna_ancho,
                    origin=(-0.5, 0), position=(columna_x, 0.0, -0.004), color=rgb(TONO_TEXTO))
    Entity(parent=frente, model="quad", color=rgb(TONO_MARCO), scale=(ANCHO_TABLERO - 0.14, 0.27),
           position=(0, -ALTO_TABLERO / 2 + 0.2, -0.002), double_sided=True)
    _texto_que_cabe(Text, rgb, silenciar, texto_sin_tinta, frente, partido.upper(), ESCALAS_TEXTO[2],
                    ANCHO_TABLERO - 0.4, origin=(0, 0), position=(0, -ALTO_TABLERO / 2 + 0.2, -0.004),
                    color=rgb(TONO_TABLERO))


def _crear_cartel(padre, mundo, lugar, lado, ocupados=None):
    from ursina import Entity, Text

    from frontend import sello_tradicion
    from frontend.componentes import rgb
    from frontend.piezas import silenciar, texto_sin_tinta

    ocupados = [] if ocupados is None else ocupados
    x, z, giro = sitio_cartel(mundo.coordenada(lugar), mundo.punto_interaccion(lugar), mundo.radio_plaza, lado,
                              *_comprobadores(mundo, ocupados))
    ocupados.append((x, z))
    y = mundo.altura(x, z)
    cartel = Entity(parent=padre, position=(x, y, z), rotation_y=giro)
    # +z mira al centro de la plaza: los postes van detrás (z < 0) para no tapar el tablero visto desde la plaza.
    for px in (-ANCHO_TABLERO * 0.38, ANCHO_TABLERO * 0.38):
        Entity(parent=cartel, model="cube", color=rgb((90, 70, 52)), scale=(0.1, ALTO_POSTE, 0.1),
               position=(px, ALTO_POSTE / 2, -0.1))
    tablero = Entity(parent=cartel, y=ALTO_POSTE - ALTO_TABLERO / 2 + 0.3)
    # El marco va DENTRO del grosor del tablero (sus caras no coinciden con las rojas: sin parpadeo a distancia).
    Entity(parent=tablero, model="cube", color=rgb(TONO_MARCO), scale=(ANCHO_TABLERO + 0.12, ALTO_TABLERO + 0.12, 0.04))
    Entity(parent=tablero, model="cube", color=rgb(TONO_TABLERO), scale=(ANCHO_TABLERO, ALTO_TABLERO, 0.07))
    # Las dos caras miran a lados opuestos: se lee desde la plaza (+z) y desde atrás (-z).
    for cara, giro_cara in ((0.045, 180), (-0.045, 0)):
        frente = Entity(parent=tablero, z=cara, rotation_y=giro_cara)
        _pintar_cara(frente, sello_tradicion, rgb, Entity, Text, silenciar, texto_sin_tinta)
    return cartel


class CartelesCampana:
    """Crea los carteles la primera vez que el día de la partida es >= DIA_ESPEJO y avisa del debate al teléfono una vez
    por partida. `crear(lugar, lado)` es inyectable (pruebas)."""

    def __init__(self, escena, crear=None):
        self.escena = escena
        self.crear = crear
        self.carteles = []
        self._avisado = None            # id del flujo al que ya se le mandó el anuncio

    def avanzar(self):
        flujo = getattr(self.escena, "flujo", None)
        reloj = getattr(flujo, "reloj", None)
        if reloj is None or getattr(self.escena, "online", None) is not None:
            self._mostrar(False)
            return
        espejo = reloj.dia() >= DIA_ESPEJO
        if espejo and not self.carteles and self.crear is not None:
            for k, lugar in enumerate(LUGARES):
                try:
                    self.carteles.append(self.crear(lugar, 1.0 if k % 2 == 0 else -1.0))
                except Exception as error:      # un lugar que no existe en este mapa no impide los demás
                    print(f"[carteles] {lugar!r} omitido ({type(error).__name__}: {error})", file=sys.stderr)
        self._mostrar(espejo)
        if espejo and self._avisado != id(flujo):
            self._avisado = id(flujo)
            self._anunciar(flujo)

    def _mostrar(self, visible):
        for cartel in self.carteles:
            if cartel.enabled != visible:
                cartel.enabled = visible

    @staticmethod
    def _anunciar(flujo):
        datos = sello_rumores.datos()
        texto = datos.get("anuncio_debate")
        try:
            if texto:
                flujo.jugador_activo().telefono.notificar(texto, datos.get("remitente_campana", "Civitas"))
        except (AttributeError, TypeError) as error:
            print(f"[carteles] anuncio del debate omitido ({error})", file=sys.stderr)


def registrar(gestor, conexion, escena_mundo):
    if not sello_rumores.activo():
        return None
    try:
        from ursina import Entity

        mundo = escena_mundo._mundo
        raiz = Entity(parent=escena_mundo)
        ocupados = []
        carteles = CartelesCampana(escena_mundo,
                                   crear=lambda lugar, lado: _crear_cartel(raiz, mundo, lugar, lado, ocupados))

        class VigiaCarteles(Entity):
            def update(self):
                carteles.avanzar()

        vigia = VigiaCarteles(parent=escena_mundo.hud)
        vigia.carteles = carteles
        return vigia
    except Exception as error:
        print(f"[carteles] no instalados ({type(error).__name__}: {error})", file=sys.stderr)
        return None
