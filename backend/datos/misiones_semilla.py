# Catálogo semilla de misiones (datos puros). Formato y criterios: docs/DISENO.md, sección «Misiones».
#
# MENSAJE: una frase corta (<= 90 caracteres) con una afirmación concreta (el rumor) y UN verbo de acción que el juego
# puede verificar: ir al lugar, pulsar E y decidir sobre sus noticias. Nombra el destino tal cual. Sin prefijo «Civitas:»
# (el banner del HUD ya lo pone de encabezado) y sin pedir nada imposible («pregunta al encargado»: no hay diálogo).
# Los textos son neutros (no hablan en segunda persona del rol) porque SistemaMisiones reparte las misiones de roles que
# nadie juega entre los presentes. Los términos locales (sinuca, mutirão...) se glosan al mostrarlos (nombres_visibles.py).
#
# DIFICULTAD (por TEMA del rumor, no por distancia): «facil» = rumor evidente o simple de comprobar; «media» = hay que
# contrastar fuentes; «dificil» = rumor con matices o consecuencias (salud, dinero, datos, política). Cada mapa tiene los tres
# niveles. TIPO: las de los tres catálogos de siempre son «verificar»; parkour e investigacion viven aparte, en
# MISIONES_DIGITALES_CHICO (ver más abajo).
#
# PAGO: min(60, R$20 + R$5 por cada 60 m en línea recta entre la Praça da Sé y el destino) x multiplicador de dificultad
# (facil 1, media 1,5, dificil 2), redondeado a múltiplo de R$5 (mitades hacia arriba) y con tope duro de R$120. Las
# distancias son en metros del mundo (el núcleo ya va multiplicado por ESCALA_MUNDO). Cada Mision lleva el `pago`
# literal; tests/test_misiones_pago.py recalcula la fórmula.
#
# CIERRES: las misiones de verificar terminan con una de 5 frases (Compruébalo en persona. / Ve a ver qué hay de cierto. /
# Confírmalo allí. / Míralo con tus ojos. / Revisa qué pasa allí.), repartidas por orden de catálogo para que ninguna
# domine. Las de rol que piden decidir (qué responder, si impulsar) conservan su cierre propio.
#
# VEREDICTO (A2d): cada misión de verificar lleva es_verdadera (≈60 % falsas), rumor (solo la afirmación, <= 110), pista (lo que
# se ve al llegar, <= 90) y grupo de confianza (policia | ciudadanos | instituciones). El mensaje afirma lo mismo que el rumor.
# Ver docs/DISENO.md §10.
# PISTAS: son la evidencia JUSTA del veredicto (siempre se deduce comparando rumor y pista), pero su forma no lo delata: hay
# falsos con pista de PRESENCIA (algo hay, y es parcial o es otra cosa: «un cartel de multas... por basura») y verdaderos con
# pista de AUSENCIA aparente («ningún bus en el andén; el tablero marca...»). Lo vigila tests/test_misiones_semilla.py.
# POLICÍA: solo rumores de seguridad, orden o servicios públicos (20-25 % de cada mapa).
#
# Cada rol tiene al menos una misión cuyo destino NO es su lugar de inicio (si no, el jugador ya estaría «llegado» al
# aparecer). rol=None = genérica. El orden importa: SistemaMisiones y la reserva del online reparten en orden de catálogo.

from backend.logica import misiones_digitales
from backend.logica.misiones import Mision

# 14 misiones del mundo chico: 2 por rol y 6 genéricas, entre los 11 lugares del núcleo.
# Veredicto (A2d): 8 falsas y 6 verdaderas; grupo de confianza: policía 3, instituciones 4, ciudadanos 7.
# Policía: generica_santa_casa, influencer_parque y ciudadano_teleferico.
CATALOGO_MISIONES = (
    Mision(
        "ciudadano_praca", "ciudadano", "Concierto en la Praça",
        "Dicen que montan un concierto en la Praça da Sé este viernes. Compruébalo en persona.", "Praça da Sé",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="El viernes por la noche habrá un concierto con permiso municipal.",
        pista="Operarios descargan tarimas junto a la fuente; en un poste, el permiso sellado.",
    ),
    Mision(
        "periodista_prefeitura", "periodista", "Rumor en la Prefeitura",
        "Corre un rumor sin fuente sobre la Prefeitura. Compruébalo en persona.", "Prefeitura",
        pago=30, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="La Prefeitura multará a quien comparta noticias sin autorización previa.",
        pista="En la puerta hay un cartel de multas nuevas: todas por basura y por ruido nocturno.",
    ),
    Mision(
        "influencer_parque", "influencer", "Parque en obras",
        "Dicen que el Parque do Povo cierra de noche por obras. Míralo con tus ojos.", "Parque do Povo",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="policia",
        rumor="Cambiarán las luminarias por seguridad y el parque cerrará de noche mientras dure el trabajo.",
        pista="Cinta amarilla en un sendero, faroles nuevos en cajas y un aviso de cierre a las 19 h.",
    ),
    Mision(
        "candidato_morro", "candidato", "Voces del morro",
        "Dicen que van a desalojar casas del Morro da Esperança. Revisa qué pasa allí.", "Morro da Esperança",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="La alcaldía ordenó desalojar casas de la ladera para abrir una avenida.",
        pista="Maquinaria y casas marcadas con pintura; el cartel de la obra dice «red de agua».",
    ),
    Mision(
        "generica_santa_casa", None, "Alerta sanitaria",
        "Circula una alerta sanitaria en el Hospital Santa Casa. Ve a ver qué hay de cierto.", "Hospital Santa Casa",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="El Hospital Santa Casa cerró urgencias por un brote contagioso.",
        pista="Una puerta lateral está clausurada con cinta; por la principal entran ambulancias.",
    ),
    Mision(
        "generica_rodoviaria", None, "Horarios de buses",
        "Dicen que la Rodoviária cambió los horarios de salida de los buses. Confírmalo allí.", "Rodoviária",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Los buses hacia la capital ahora salen a las 6 y a las 18 horas.",
        pista="Ningún bus en el andén a media mañana; el tablero marca salidas a las 6:00 y a las 18:00.",
    ),
    Mision(
        "generica_universidade", None, "Becas en la universidad",
        "Dicen que la Universidade de Ciudad Nova abre becas esta semana. Revisa qué pasa allí.",
        "Universidade de Ciudad Nova",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="La universidad recibe solicitudes de becas de transporte hasta el viernes.",
        pista="Un cartel con fechas y un buzón de formularios de becas en el hall, junto a secretaría.",
    ),
    Mision(
        "periodista_radio", "periodista", "Micrófono abierto",
        "Leyeron al aire un audio sin fuente en la Rádio Comunitária. Confírmalo allí.", "Rádio Comunitária",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="Un audio leído al aire asegura que el impuesto predial subirá el próximo mes.",
        pista="La pizarra del estudio trae solo música hoy; el registro de audios no cita el predial.",
    ),
    Mision(
        "influencer_samba", "influencer", "Ensayo abierto",
        "Dicen que la Escola de Samba abre sus ensayos del sábado. Míralo con tus ojos.", "Escola de Samba",
        pago=25, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Los ensayos son abiertos al público cada sábado a las 8 de la noche.",
        pista="El galpón está cerrado y nadie ensaya hoy; el pizarrón dice «sábados 20 h, entrada libre».",
    ),
    Mision(
        "candidato_mercado", "candidato", "Precio de la feria",
        "Dicen que los precios del Mercado Municipal se duplican. Míralo con tus ojos.", "Mercado Municipal",
        pago=20, dificultad="facil",
        es_verdadera=False, grupo="instituciones",
        rumor="Todos los precios del mercado se duplicaron esta semana por orden municipal.",
        pista="El tomate subió al doble por las lluvias; las demás etiquetas siguen la lista de siempre.",
    ),
    Mision(
        "ciudadano_teleferico", "ciudadano", "Teleférico parado",
        "Dicen que cierran para siempre la Estação do Teleférico. Revisa qué pasa allí.",
        "Estação do Teleférico",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="policia",
        rumor="La estación del teleférico cerrará de forma definitiva y retirarán las cabinas.",
        pista="Un cartel de «cerrado» en la boletería: por mantenimiento, solo el martes.",
    ),
    # Antes apuntaba al Morro da Esperança, el lugar de inicio del ciudadano (nacía ya «llegado»).
    Mision(
        "generica_mutirao", None, "Mutirão sospechoso",
        "Un mutirão en la Escola de Samba pide datos bancarios. Compruébalo en persona.", "Escola de Samba",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Los organizadores del mutirão exigen el número de cuenta a cada vecino que se apunte.",
        pista="Las planillas de la mesa piden nombre y calle; ninguna casilla para números de cuenta.",
    ),
    Mision(
        "generica_corrente", None, "Corrente do zap",
        "Una cadena promete premios en la Praça da Sé. Ve a ver qué hay de cierto.", "Praça da Sé",
        pago=20, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Quien reenvíe la cadena a diez contactos recibirá un premio en la plaza.",
        pista="Hay un stand con globos y una urna: es la rifa de la parroquia, con boletos numerados.",
    ),
    Mision(
        "generica_feira", None, "Feria de trueque",
        "Anuncian una feria de trueque en el Parque do Povo el domingo. Confírmalo allí.", "Parque do Povo",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="El domingo habrá una feria de trueque con puestos inscritos de antemano.",
        pista="Mesas apiladas con números y la lista de inscritos del domingo clavada en un poste.",
    ),
)


# Misiones DIGITALES (una de parkour y una de investigación), SOLO para la partida de solo con GameState: no están
# en los catálogos de arriba porque en línea/coop no hay GameState y la partida termina al completar todas (serían
# imposibles). Se completan por señal (backend/logica/misiones_digitales.py), no en el lugar. El destino es el lugar al
# que apunta el HUD: el que queda junto a la «Terminal de la Fiscalía» (zona `mercado`; a ~40 m de «Mercado Municipal»).
# Mensaje: cierre propio de su tipo (parkour «...hasta la meta.», investigación «...Terminal de la Fiscalía.»); no nombran el destino sino el terminal.
# Dificultad por tema: el parkour es «media»; la investigación (acusar, datos), «dificil». Pago: fórmula de §10 aplicada
# a su destino y dificultad (la comprueba tests/test_misiones_pago.py).
MISIONES_DIGITALES_CHICO = (
    Mision(
        "parkour_sector_1", None, "Servidor fantasma",
        "Un servidor fantasma guarda un rastro. En la Terminal de la Fiscalía, cruza hasta la meta.",
        "Mercado Municipal",
        pago=30, dificultad="media", tipo="parkour", objetivo="sector_1", grupo="policia",
    ),
    Mision(
        "parkour_sector_2", None, "La granja de bots",
        "Las cuentas falsas salen de una granja de bots. En la Terminal de la Fiscalía, cruza su servidor hasta la meta.",
        "Mercado Municipal",
        pago=40, dificultad="dificil", tipo="parkour", objetivo="sector_2", grupo="policia",
    ),
    Mision(
        "investigacion_cuentas", None, "Cuentas fantasma",
        "Hay cuentas falsas en Civitas. Revisa el caso en la Terminal de la Fiscalía.",
        "Mercado Municipal",
        pago=40, dificultad="dificil", tipo="investigacion", objetivo="cuentas_fantasma", grupo="policia",
    ),
)

def catalogo_de_mundo(mundo):
    """El catálogo de misiones del mundo (CATALOGO_MISIONES; el parámetro se conserva por compatibilidad con quien lo llama).
    Lo usan main.py, el anfitrión y los clientes online para que todos hablen del mismo catálogo. NUNCA incluye misiones
    digitales (ver catalogo_solo)."""
    return CATALOGO_MISIONES


def catalogo_solo(mundo, con_game_state, solo_digitales=False):
    """Catálogo de la partida de SOLO (hot-seat): catalogo_de_mundo(mundo) + las misiones digitales del mapa, al final,
    únicamente si hay GameState y su nivel/caso existe y carga (si no, se omiten en silencio; el motivo lo da
    misiones_digitales.evaluar). Sin GameState devuelve el catálogo de siempre.
    `solo_digitales` (DEPURACIÓN, ALCALDE_SOLO_DIGITALES=1): devuelve ÚNICAMENTE las digitales del mapa para probarlas sin
    jugar antes las de verificar; si no hay ninguna disponible (sin GameState) se ignora y devuelve el catálogo de siempre."""
    base = catalogo_de_mundo(mundo)
    digitales = MISIONES_DIGITALES_CHICO
    disponibles = tuple(misiones_digitales.disponibles(digitales, con_game_state))
    if solo_digitales and disponibles:
        return disponibles
    return tuple(base) + disponibles
