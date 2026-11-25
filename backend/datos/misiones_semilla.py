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

import os

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
        pista="Operarios descargan tarimas junto a la fuente; en un poste, el permiso sellado.", dia=1,
    ),
    Mision(
        "periodista_prefeitura", "periodista", "Rumor en la Prefeitura",
        "Corre un rumor sin fuente sobre la Prefeitura. Compruébalo en persona.", "Prefeitura",
        pago=30, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="La Prefeitura multará a quien comparta noticias sin autorización previa.",
        pista="En la puerta hay un cartel de multas nuevas: todas por basura y por ruido nocturno.", dia=6,
    ),
    Mision(
        "influencer_parque", "influencer", "Parque en obras",
        "Dicen que el Parque do Povo cierra de noche por obras. Míralo con tus ojos.", "Parque do Povo",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="policia",
        rumor="Cambiarán las luminarias por seguridad y el parque cerrará de noche mientras dure el trabajo.",
        pista="Cinta amarilla en un sendero, faroles nuevos en cajas y un aviso de cierre a las 19 h.", dia=2,
    ),
    Mision(
        "candidato_morro", "candidato", "Voces del morro",
        "Dicen que van a desalojar casas del Morro da Esperança. Revisa qué pasa allí.", "Morro da Esperança",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="La alcaldía ordenó desalojar casas de la ladera para abrir una avenida.",
        pista="Maquinaria y casas marcadas con pintura; el cartel de la obra dice «red de agua».", dia=5,
    ),
    Mision(
        "generica_santa_casa", None, "Alerta sanitaria",
        "Circula una alerta sanitaria en el Hospital Santa Casa. Ve a ver qué hay de cierto.", "Hospital Santa Casa",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="El Hospital Santa Casa cerró urgencias por un brote contagioso.",
        pista="Una puerta lateral está clausurada con cinta; por la principal entran ambulancias.", dia=3,
    ),
    Mision(
        "generica_rodoviaria", None, "Horarios de buses",
        "Dicen que la Rodoviária cambió los horarios de salida de los buses. Confírmalo allí.", "Rodoviária",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Los buses hacia la capital ahora salen a las 6 y a las 18 horas.",
        pista="Ningún bus en el andén a media mañana; el tablero marca salidas a las 6:00 y a las 18:00.", dia=1,
    ),
    Mision(
        "generica_universidade", None, "Becas en la universidad",
        "Dicen que la Universidade de Ciudad Nova abre becas esta semana. Revisa qué pasa allí.",
        "Universidade de Ciudad Nova",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="La universidad recibe solicitudes de becas de transporte hasta el viernes.",
        pista="Un cartel con fechas y un buzón de formularios de becas en el hall, junto a secretaría.", dia=2,
    ),
    Mision(
        "periodista_radio", "periodista", "Micrófono abierto",
        "Leyeron al aire un audio sin fuente en la Rádio Comunitária. Confírmalo allí.", "Rádio Comunitária",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="Un audio leído al aire asegura que el impuesto predial subirá el próximo mes.",
        pista="La pizarra del estudio trae solo música hoy; el registro de audios no cita el predial.", dia=4,
    ),
    Mision(
        "influencer_samba", "influencer", "Ensayo abierto",
        "Dicen que la Escola de Samba abre sus ensayos del sábado. Míralo con tus ojos.", "Escola de Samba",
        pago=25, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Los ensayos son abiertos al público cada sábado a las 8 de la noche.",
        pista="El galpón está cerrado y nadie ensaya hoy; el pizarrón dice «sábados 20 h, entrada libre».", dia=1,
    ),
    Mision(
        "candidato_mercado", "candidato", "Precio de la feria",
        "Dicen que los precios del Mercado Municipal se duplican. Míralo con tus ojos.", "Mercado Municipal",
        pago=20, dificultad="facil",
        es_verdadera=False, grupo="instituciones",
        rumor="Todos los precios del mercado se duplicaron esta semana por orden municipal.",
        pista="El tomate subió al doble por las lluvias; las demás etiquetas siguen la lista de siempre.", dia=3,
    ),
    Mision(
        "ciudadano_teleferico", "ciudadano", "Teleférico parado",
        "Dicen que cierran para siempre la Estação do Teleférico. Revisa qué pasa allí.",
        "Estação do Teleférico",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="policia",
        rumor="La estación del teleférico cerrará de forma definitiva y retirarán las cabinas.",
        pista="Un cartel de «cerrado» en la boletería: por mantenimiento, solo el martes.", dia=2,
    ),
    # Antes apuntaba al Morro da Esperança, el lugar de inicio del ciudadano (nacía ya «llegado»).
    Mision(
        "generica_mutirao", None, "Mutirão sospechoso",
        "Un mutirão en la Escola de Samba pide datos bancarios. Compruébalo en persona.", "Escola de Samba",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Los organizadores del mutirão exigen el número de cuenta a cada vecino que se apunte.",
        pista="Las planillas de la mesa piden nombre y calle; ninguna casilla para números de cuenta.", dia=3,
    ),
    Mision(
        "generica_corrente", None, "Corrente do zap",
        "Una cadena promete premios en la Praça da Sé. Ve a ver qué hay de cierto.", "Praça da Sé",
        pago=20, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Quien reenvíe la cadena a diez contactos recibirá un premio en la plaza.",
        pista="Hay un stand con globos y una urna: es la rifa de la parroquia, con boletos numerados.", dia=1,
    ),
    Mision(
        "generica_feira", None, "Feria de trueque",
        "Anuncian una feria de trueque en el Parque do Povo el domingo. Confírmalo allí.", "Parque do Povo",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="El domingo habrá una feria de trueque con puestos inscritos de antemano.",
        pista="Mesas apiladas con números y la lista de inscritos del domingo clavada en un poste.", dia=2,
    ),
)

# Hilo conductor (docs/HILO_CONDUCTOR.md; ALCALDE_HILO_LEY_SECA=0 o ALCALDE_HILO=0 vuelven al de antes): el rumor
# VERDADERO de la ley seca suena alarmista («¡Atención!»), para que «alarmista» no sea sinónimo de «falso». Solo cambia el
# mensaje; el rumor y la pista son los de siempre. Se lee al importar.
_MENSAJE_LEY_SECA = ("¡Atención! El Mercado Municipal ya no vende licor por la elección. Compruébalo en persona."
                     if os.environ.get("ALCALDE_HILO_LEY_SECA", os.environ.get("ALCALDE_HILO", "1")).strip().lower()
                     not in ("0", "false", "no", "off")
                     else "Dicen que el Mercado Municipal no vende licor por la elección. Compruébalo en persona.")

# REPARTO POR DÍAS (sesión D, 2026-11-23; ALCALDE_MISIONES_DIAS, backend/logica/reparto_dias.py). 21 misiones nuevas: con
# las 14 de arriba son 35, cinco por día de la semana (`dia`). Cada partida sortea 4 por día (28); las de un mismo `arco`
# entran o salen juntas y se juegan en orden de `paso`. Los rumores escalan: días 1-2 cotidianos; 3-5 dinero, salud y
# servicios; 6-7 la elección. Patrones reales de desinformación (cadenas, subsidios, audios «de un primo», encuestas,
# montajes, compra de votos) con nombres ficticios; ningún rumor nombra a un candidato. Cumplen todas las reglas del
# encabezado (lo vigila tests/test_misiones_dias_datos.py). Tabla completa: sesiones-24nov/misiones/catalogo.md.
# Veredicto: 14 falsas y 7 verdaderas (total 22/35 = 63 % falsas). Policía: agua_corte, primo_hospital, agua_turbia,
# canastas_votos y teleferico_eleccion (total 8/35 = 23 %). Arcos: «primo» (días 1 y 4), «subsidio» (3, 4 y 5), «agua»
# (3 y 5) y «urnas» (6 y 7). Con ALCALDE_MISIONES_DIAS=0 este bloque no se usa: el catálogo son las 14 de siempre.
MISIONES_NUEVAS_DIAS = (
    # -- Día 1 --
    Mision(
        "generica_primo_audio", None, "El primo de la terminal",
        "Un audio dice que el pasaje sube al doble en la Rodoviária. Ve a ver qué hay de cierto.", "Rodoviária",
        pago=30, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Un primo que trabaja en la terminal avisa por audio que el pasaje costará el doble desde el lunes.",
        pista="En la taquilla, la tabla de tarifas de siempre; debajo: «sin cambios de precio este año».",
        dia=1, arco="primo", paso=1,
    ),
    # -- Día 2 --
    Mision(
        "ciudadano_biblioteca", "ciudadano", "Biblioteca abierta",
        "Dicen que la Universidade de Ciudad Nova presta libros al barrio. Míralo con tus ojos.",
        "Universidade de Ciudad Nova",
        pago=20, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Desde este mes cualquier vecino puede llevarse libros de la biblioteca con un carné vecinal.",
        pista="En la puerta: «Préstamo a domicilio con carné vecinal: trámite en el mostrador».",
        dia=2,
    ),
    # -- Día 3 --
    Mision(
        "generica_subsidio_cadena", None, "Subsidio por enlace",
        "Una cadena dice que la Prefeitura da R$600 por un enlace. Ve a ver qué hay de cierto.", "Prefeitura",
        pago=30, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="La alcaldía entrega un subsidio de R$600 a quien llene hoy mismo el formulario del enlace.",
        pista="La cartelera oficial no anuncia ningún subsidio; un aviso pide no abrir enlaces ajenos.",
        dia=3, arco="subsidio", paso=1,
    ),
    Mision(
        "generica_agua_corte", None, "Corte de agua",
        "Avisan que cortan el agua en el Morro da Esperança el jueves. Revisa qué pasa allí.",
        "Morro da Esperança",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="policia",
        rumor="El jueves no habrá agua en la ladera de 8 a 14 horas por la reparación de una tubería principal.",
        pista="Nadie trabaja aún en la calle; en cada poste, el aviso de la empresa: jueves, 8 a 14 h.",
        dia=3, arco="agua", paso=1,
    ),
    # -- Día 4 -- (periodista_vacunas va aquí, antes del rótulo de abajo, para no cambiar el orden del fondo)
    Mision(
        "periodista_vacunas", "periodista", "Vacunas sin cita",
        "Dicen que el Hospital Santa Casa vacuna sin cita este sábado. Compruébalo en persona.",
        "Hospital Santa Casa",
        pago=50, dificultad="dificil",
        es_verdadera=True, grupo="instituciones",
        rumor="El sábado habrá jornada de vacunación contra la gripe para todas las edades, por orden de llegada.",
        pista="Nadie en la sala de vacunas hoy; el cartel: «Sábado 8 a 16 h, todas las edades, sin cita».",
        dia=4,
    ),
    Mision(
        "generica_subsidio_gestor", None, "El gestor del subsidio",
        "Dicen que un gestor oficial tramita el subsidio en el Mercado Municipal. Confírmalo allí.", "Mercado Municipal",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Un gestor autorizado por la alcaldía tramita el subsidio en un puesto y pide la clave de la tarjeta.",
        pista="Una mesa plegable, un cartel a mano y una libreta con claves; ningún sello municipal.",
        dia=4, arco="subsidio", paso=2,
    ),
    Mision(
        "generica_primo_hospital", None, "El primo, otra vez",
        "Otro audio del primo: el Hospital Santa Casa, sin oxígeno. Revisa qué pasa allí.", "Hospital Santa Casa",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="El mismo primo jura en un audio nuevo que el hospital se quedó sin oxígeno y rechaza pacientes.",
        pista="Un camión descarga cilindros en el patio; la planilla de la puerta: «reserva: 9 días».",
        dia=4, arco="primo", paso=2,
    ),
    Mision(
        "influencer_te_dengue", "influencer", "Té contra el dengue",
        "Una captura dice que un té del Mercado Municipal cura el dengue. Revisa qué pasa allí.", "Mercado Municipal",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="El puesto de hierbas vende un té que cura el dengue en dos días, según una captura del hospital.",
        pista="El puesto vende manzanilla y boldo; su letrero dice «no reemplaza la consulta médica».",
        dia=4,
    ),
    # -- Día 5 --
    Mision(
        "generica_auxilio_transporte", None, "Auxilio de transporte",
        "Dicen que la Prefeitura abre un auxilio de transporte el lunes. Compruébalo en persona.", "Prefeitura",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Desde el lunes, la alcaldía recibe en ventanilla, en persona, las inscripciones al auxilio de transporte.",
        pista="Ventanilla 3 cerrada hoy; en el vidrio, el edicto: inscripción presencial desde el lunes.",
        dia=5, arco="subsidio", paso=3,
    ),
    Mision(
        "generica_agua_turbia", None, "Agua turbia",
        "Dicen que el agua del Morro da Esperança volvió contaminada. Ve a ver qué hay de cierto.",
        "Morro da Esperança",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="Tras el corte, el agua de la ladera llegó contaminada y ya hay vecinos hospitalizados por tomarla.",
        pista="El agua sale turbia un minuto y luego clara; el aviso de la empresa pide dejarla correr.",
        dia=5, arco="agua", paso=2,
    ),
    Mision(
        "candidato_tarifa_luz", "candidato", "La luz, 40 % más cara",
        "Anuncian en la Rádio Comunitária que la luz sube 40 %. Compruébalo en persona.", "Rádio Comunitária",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="Un decreto firmado esta semana sube la tarifa de la luz un 40 % a partir del próximo recibo.",
        pista="El boletín de la cabina habla de un ajuste del 4 %; del decreto, ni número ni fecha.",
        dia=5,
    ),
    Mision(
        "ciudadano_tarjeta_bus", "ciudadano", "Tarjeta bloqueada",
        "Un SMS dice que la Rodoviária multa a quien no registre su tarjeta. Revisa qué pasa allí.", "Rodoviária",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="La terminal multará con R$150 a quien no registre hoy su tarjeta del bus en el enlace que llega por SMS.",
        pista="Los torniquetes aceptan las tarjetas; el cartel: «registro voluntario, en la taquilla».",
        dia=5,
    ),
    # -- Día 6 --
    Mision(
        "generica_encuesta", None, "La encuesta del 82 %",
        "Pegaron en la Praça da Sé una encuesta que da 82 % a un candidato. Míralo con tus ojos.", "Praça da Sé",
        pago=30, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Otra encuesta «de la universidad» da el 82 % de los votos a un solo candidato a días de la elección.",
        pista="El afiche no trae ficha técnica ni fecha; el logo de la universidad está estirado.",
        dia=6,
    ),
    Mision(
        "periodista_foto_mitin", "periodista", "El parque lleno",
        "Una foto muestra el Parque do Povo repleto en un mitin de anoche. Confírmalo allí.", "Parque do Povo",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="Anoche hubo un mitin que llenó el parque de punta a punta, como muestra la foto que circula.",
        pista="La tarima de anoche ocupa un rincón chico; la foto que circula tiene adornos de carnaval.",
        dia=6,
    ),
    Mision(
        "candidato_debate", "candidato", "Debate en la radio",
        "Dicen que hay debate de candidatos en la Rádio Comunitária el sábado. Míralo con tus ojos.",
        "Rádio Comunitária",
        pago=40, dificultad="media",
        es_verdadera=True, grupo="instituciones",
        rumor="Los candidatos a la alcaldía debatirán en vivo el sábado a las 19 horas, con preguntas del barrio.",
        pista="No hay nadie en el estudio; en la puerta, la programación: «Sábado 19 h, debate en vivo».",
        dia=6,
    ),
    Mision(
        "generica_canastas_votos", None, "Canastas por votos",
        "Dicen que cambian canastas por votos en la Escola de Samba. Ve a ver qué hay de cierto.", "Escola de Samba",
        pago=50, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="Esta noche dan canastas a quien prometa mandar la foto de su voto del domingo, y los agentes lo permiten.",
        pista="Hay canastas apiladas: son de la colecta del barrio; la lista no pide ni nombre ni voto.",
        dia=6, arco="urnas", paso=1,
    ),
    # -- Día 7 --
    Mision(
        "generica_mesas_votacion", None, "Mesas trasladadas",
        "Dicen que ya no se vota en la Universidade de Ciudad Nova. Confírmalo allí.",
        "Universidade de Ciudad Nova",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="A última hora trasladaron todas las mesas de votación al otro lado de la ciudad, sin aviso previo.",
        pista="En el hall arman las cabinas; el listado oficial de mesas sigue pegado en la entrada.",
        dia=7, arco="urnas", paso=2,
    ),
    Mision(
        "influencer_voto_celular", "influencer", "Votar desde el celular",
        "Un volante en la Estação do Teleférico dice que se vota por celular. Míralo con tus ojos.",
        "Estação do Teleférico",
        pago=40, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Este año se puede votar desde el celular con un enlace, sin ir a la mesa, hasta el mediodía.",
        pista="El volante no lleva sello y su enlace acaba en «.xyz»; el cartel oficial: «solo en mesa».",
        dia=7,
    ),
    Mision(
        "ciudadano_teleferico_eleccion", "ciudadano", "Teleférico el domingo",
        "Dicen que la Estação do Teleférico no cobra el domingo. Ve a ver qué hay de cierto.",
        "Estação do Teleférico",
        pago=25, dificultad="facil",
        es_verdadera=True, grupo="policia",
        rumor="El domingo de la elección el teleférico funcionará sin costo de 6 a 18 horas para ir a votar.",
        pista="La boletería cobra hoy como siempre; el aviso sellado: «domingo, pasaje libre, 6 a 18 h».",
        dia=7,
    ),
    Mision(
        "periodista_boletin", "periodista", "Resultados adelantados",
        "Circula un boletín de la Prefeitura con el ganador electoral. Confírmalo allí.", "Prefeitura",
        pago=40, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="Un boletín con sello municipal ya da el nombre del ganador antes de que cierren las urnas.",
        pista="La cartelera oficial solo trae el horario de votación; el boletín lleva otro escudo.",
        dia=7,
    ),
    Mision(
        "candidato_ley_seca", "candidato", "Ley seca",
        _MENSAJE_LEY_SECA,
        "Mercado Municipal",
        pago=30, dificultad="media",
        es_verdadera=True, grupo="instituciones",
        rumor="Desde la víspera y hasta que cierren las urnas, ningún puesto puede vender bebidas alcohólicas.",
        pista="Los estantes de licor están tapados con lonas; en cada puesto, el decreto de ley seca.",
        dia=7,
    ),
)

# Las 35 del reparto por días, ordenadas por día (orden estable: dentro de un día, primero las de siempre y luego las
# nuevas). Es el «fondo» del que cada partida sortea su semana (backend/logica/reparto_dias.py).
CATALOGO_MISIONES_DIAS = tuple(sorted(CATALOGO_MISIONES + MISIONES_NUEVAS_DIAS, key=lambda m: m.dia))


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
    digitales (ver catalogo_solo).
    Sesión D: con el reparto por días (ALCALDE_MISIONES_DIAS, encendido por defecto) devuelve el FONDO de 35 misiones
    ordenado por día; el sorteo de la semana lo hace quien reparte (SistemaMisiones / ReservaMisiones) con su semilla.
    Con ALCALDE_MISIONES_DIAS=0, las 14 de siempre en su orden de siempre."""
    from backend.logica import reparto_dias
    return CATALOGO_MISIONES_DIAS if reparto_dias.activo() else CATALOGO_MISIONES


def catalogo_solo(mundo, con_game_state, solo_digitales=False):
    """Catálogo de la partida de SOLO (hot-seat): catalogo_de_mundo(mundo) + las misiones digitales del mapa, al final,
    únicamente si hay GameState y su nivel/caso existe y carga (si no, se omiten en silencio; el motivo lo da
    misiones_digitales.evaluar). Sin GameState devuelve el catálogo de siempre.
    `solo_digitales` (DEPURACIÓN, ALCALDE_SOLO_DIGITALES=1): devuelve ÚNICAMENTE las digitales del mapa para probarlas sin
    jugar antes las de verificar; si no hay ninguna disponible (sin GameState) se ignora y devuelve el catálogo de siempre.
    Sesión A (ALCALDE_FISCALIA_V2, encendida por defecto): con GameState las digitales son SOLO las misiones de los casos
    v2 (misiones_digitales.misiones_de_casos(): las tres de arriba se fusionan en «investigacion_cuentas», en la Fiscalía).
    Si no hay ningún caso v2 válido, caen a las tres de siempre. Con la bandera en 0, las tres de siempre sin cambios."""
    from backend.logica import fiscalia_bandera        # import local: el resto del archivo es de otras sesiones
    base = catalogo_de_mundo(mundo)
    digitales = MISIONES_DIGITALES_CHICO
    if con_game_state and fiscalia_bandera.activa():
        ids_base = {m.id for m in base}
        digitales = tuple(m for m in misiones_digitales.misiones_de_casos() if m.id not in ids_base) or digitales
    disponibles = tuple(misiones_digitales.disponibles(digitales, con_game_state))
    if solo_digitales and disponibles:
        return disponibles
    return tuple(base) + disponibles
