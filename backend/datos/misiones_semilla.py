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
# MISIONES_DIGITALES_CHICO / _GRANDE (ver más abajo).
#
# PAGO: min(60, R$20 + R$5 por cada 60 m en línea recta entre la Praça da Sé y el destino) x multiplicador de dificultad
# (facil 1, media 1,5, dificil 2), redondeado a múltiplo de R$5 (mitades hacia arriba) y con tope duro de R$120. Las
# distancias son en metros del mundo grande (el núcleo ya va multiplicado por ESCALA_MUNDO). Cada Mision lleva el `pago`
# literal; tests/test_misiones_semilla.py recalcula la fórmula contra COORDENADAS_GRANDES.
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


# Misiones de los 13 lugares nuevos del mapa grande (backend/datos/ciudad_grande.py), una por lugar y todas genéricas
# (rol None). NO están en CATALOGO_MISIONES: SistemaMisiones exige que cada destino exista en el mapa, y el mundo chico
# no tiene estos lugares. El mapa grande usa CATALOGO_MISIONES_GRANDE (= el catálogo de siempre + estas + las extra, al
# final: el orden importa porque SistemaMisiones y la reserva del online reparten en orden de catálogo).
MISIONES_MAPA_GRANDE = (
    Mision(
        "generica_posto", None, "Vacuna milagrosa",
        "Un audio vende «vacuna milagrosa» en el Posto de Saúde Vila Nova. Míralo con tus ojos.",
        "Posto de Saúde Vila Nova",
        pago=70, dificultad="dificil",
        es_verdadera=False, grupo="policia",
        rumor="Un preparado llamado «vacuna milagrosa» se aplica en el puesto de salud sin receta.",
        pista="En la nevera solo hay vacunas del calendario oficial; ningún frasco sin etiqueta.",
    ),
    Mision(
        "generica_mototaxi", None, "Tarifa fantasma",
        "Hay capturas de tarifas triples en el Ponto de Mototáxi da Entrada. Revisa qué pasa allí.",
        "Ponto de Mototáxi da Entrada",
        pago=85, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="El mototaxi cobra el triple por cada carrera desde la entrada del barrio.",
        pista="El cartel de tarifas no cambió; los recibos de hoy marcan el precio de siempre.",
    ),
    Mision(
        "generica_padaria", None, "Pan envenenado",
        "Dicen que el pan de la Padaria Pão Quente está «adulterado». Compruébalo en persona.",
        "Padaria Pão Quente",
        pago=90, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="El pan de la panadería lleva aditivos que enferman a quien lo come.",
        pista="Sin avisos sanitarios ni reclamos en el tablón; el sello de inspección es de este mes.",
    ),
    Mision(
        "generica_supermercado", None, "Oferta que no existe",
        "Un cupón de 80 % circula para el Supermercado Dois Irmãos. Ve a ver qué hay de cierto.",
        "Supermercado Dois Irmãos",
        pago=40, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Un cupón da el 80 % de descuento en toda la compra durante este fin de semana.",
        pista="Carteles de 10 y 20 % en los pasillos; ninguna caja tiene lector ni aviso de cupones.",
    ),
    Mision(
        "generica_oficina", None, "Foto trucada",
        "Una foto muestra un «robo» en la Oficina do Seu Zé que nadie vio. Confírmalo allí.",
        "Oficina do Seu Zé",
        pago=60, dificultad="media",
        es_verdadera=False, grupo="policia",
        rumor="Una foto muestra a unos ladrones vaciando el taller anoche.",
        pista="Persiana y candados sin forzar; ninguna herramienta falta en el tablero del taller.",
    ),
    Mision(
        "generica_bar", None, "Rumor en la sinuca",
        "Se rumorea en la sinuca del Bar do Cabo un cobro por «seguridad». Míralo con tus ojos.",
        "Bar do Cabo",
        pago=75, dificultad="media",
        es_verdadera=False, grupo="policia",
        rumor="El bar exige a los clientes una cuota mensual por «seguridad» para poder entrar.",
        pista="Hay un guardia en la puerta y una alcancía rotulada «aporte voluntario para el torneo».",
    ),
    Mision(
        "generica_igreja", None, "Colecta parroquial",
        "Piden transferencias para la Igreja Nossa Senhora da Esperança. Revisa qué pasa allí.",
        "Igreja Nossa Senhora da Esperança",
        pago=55, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="La parroquia recauda fondos para reparar el techo y publica una cuenta a nombre de la iglesia.",
        pista="Goteras marcadas en el techo y un cartel con el presupuesto y la cuenta de la parroquia.",
    ),
    Mision(
        "generica_escola", None, "Clases suspendidas",
        "Dicen que la Escuela Barrio Esperanza cierra mañana. Compruébalo en persona.",
        "Escola Bairro Esperança",
        pago=45, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Mañana no habrá clases en la escuela por una jornada de formación docente.",
        pista="Hoy hay clases y nada parece distinto; en el portón: «mañana, jornada docente».",
    ),
    Mision(
        "generica_salao", None, "Tinte prohibido",
        "En el Salão da Dona Lu dicen que un tinte causa daños. Ve a ver qué hay de cierto.",
        "Salão da Dona Lu",
        pago=75, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Un tinte que usa el salón provoca quemaduras y caída del cabello.",
        pista="Ninguna queja en el cuaderno de clientas; los frascos de tinte tienen registro vigente.",
    ),
    Mision(
        "generica_varzea", None, "Final vigilada",
        "Dicen que la final del Campo de Várzea tendrá vigilancia en las gradas. Confírmalo allí.",
        "Campo de Várzea",
        pago=50, dificultad="facil",
        es_verdadera=True, grupo="policia",
        rumor="La final del domingo contará con agentes y vallas para evitar incidentes.",
        pista="Ni un agente hoy en la cancha; hay vallas apiladas y un aviso de control para el domingo.",
    ),
    Mision(
        "generica_feira_ladeira", None, "Frutas «orgánicas»",
        "Un video vende frutas «orgánicas» al triple en la Feira da Ladeira. Míralo con tus ojos.",
        "Feira da Ladeira",
        pago=85, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Una vendedora cobra el triple por fruta común presentada como «orgánica».",
        pista="Un puesto tiene letrero «orgánico» y cobra lo mismo que los puestos vecinos.",
    ),
    Mision(
        "generica_mirante", None, "Luces en el cielo",
        "Una publicación cuenta luces extrañas vistas desde el Mirante do Alto. Sube y comprueba.",
        "Mirante do Alto",
        pago=60, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Anoche aparecieron luces extrañas sobre la ciudad que no eran de ningún avión.",
        pista="Restos de cohetes por el suelo y un afiche de la comparsa: «fuegos, anoche a las 22 h».",
    ),
    Mision(
        "generica_estacao_alto", None, "Cabina detenida",
        "Corre que una cabina quedó colgada en la Estação Alto do Morro. Revisa qué pasa allí.",
        "Estação Alto do Morro",
        pago=110, dificultad="dificil",
        es_verdadera=True, grupo="policia",
        rumor="Una cabina quedó detenida a medio trayecto durante la tarde y evacuaron a los pasajeros.",
        pista="Las cabinas circulan y nada parece roto; en el andén queda el parte de evacuación.",
    ),
)


# Misiones EXTRA del mapa grande: 4 por rol y 4 genéricas, repartidas por todo el mapa. Van AL FINAL del catálogo:
# SistemaMisiones asigna primero las del rol en orden de catálogo, así que dentro de cada rol están ordenadas de la más
# cercana a su spawn a la más lejana (ciudadano 56,-20; periodista 24,-32; influencer 24,24; candidato -32,-4) y nadie
# recibe un destino a 600 m recién empezada la partida. Cada cuento aparece una sola vez en todo el catálogo (premios
# gratis, pago por adelantado, teleférico detenido): lo comprueba tests/test_misiones_semilla.py.
MISIONES_EXTRA_GRANDE = (
    # -- Ciudadano --
    Mision(
        "ciudadano_posto", "ciudadano", "Turnos por número",
        "Dicen que el Posto de Saúde Vila Nova atiende por número desde hoy. Confírmalo allí.",
        "Posto de Saúde Vila Nova",
        pago=55, dificultad="media",
        es_verdadera=True, grupo="policia",
        rumor="El puesto de salud entrega fichas numeradas para ordenar la atención desde este mes.",
        pista="La fila llega a la calle y no se ve orden alguno; cada paciente lleva una ficha numerada.",
    ),
    Mision(
        "ciudadano_supermercado", "ciudadano", "Despidos en el súper",
        "Dicen que el Supermercado Dois Irmãos despedirá personal. Compruébalo en persona.",
        "Supermercado Dois Irmãos",
        pago=60, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="El supermercado despedirá a la mitad de sus empleados a fin de mes.",
        pista="Dos cajas están cerradas esta tarde; en la puerta, un cartel busca cajeros y repositores.",
    ),
    Mision(
        "ciudadano_padaria", "ciudadano", "Harina a mitad de precio",
        "Dicen que la Padaria Pão Quente vende harina a mitad de precio. Confírmalo allí.",
        "Padaria Pão Quente",
        pago=45, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Hoy hay una oferta de harina a mitad de precio por exceso de stock.",
        pista="El cartel de la vitrina tiene la fecha de hoy y el precio de la harina tachado a la mitad.",
    ),
    Mision(
        "ciudadano_feira", "ciudadano", "Cierre de la feria",
        "Un audio dice que la Feira da Ladeira cierra el sábado. Confírmalo allí.",
        "Feira da Ladeira",
        pago=55, dificultad="facil",
        es_verdadera=True, grupo="policia",
        rumor="La feria no abrirá el sábado: la policía de tránsito cerrará la calle para el desfile.",
        pista="Conos y vallas apilados en la esquina; un aviso de tránsito anuncia el corte del sábado.",
    ),
    # -- Periodista --
    Mision(
        "periodista_igreja", "periodista", "Milagro en video",
        "En la Igreja Nossa Senhora da Esperança un video promete un «milagro». Contrástalo allí.",
        "Igreja Nossa Senhora da Esperança",
        pago=70, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="Un video muestra una curación milagrosa dentro de la iglesia, sin explicación médica.",
        pista="Cámaras y luces dentro de la nave: un cartel avisa del rodaje de una telenovela.",
    ),
    Mision(
        "periodista_oficina", "periodista", "Taller clausurado",
        "Dicen que clausuraron la Oficina do Seu Zé, sin fuente. Contrástalo antes de publicar.",
        "Oficina do Seu Zé",
        pago=60, dificultad="media",
        es_verdadera=False, grupo="instituciones",
        rumor="Las autoridades clausuraron el taller por incumplir normas de seguridad.",
        pista="Ningún sello ni faja en la persiana; adentro hay luz y ruido de herramientas.",
    ),
    Mision(
        "periodista_escola", "periodista", "Notas filtradas",
        "Filtran una «lista de reprobados» de la Escuela Barrio Esperanza. Confírmalo allí.",
        "Escola Bairro Esperança",
        pago=90, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="Circula la lista con los nombres de los alumnos reprobados del año.",
        pista="El tablón solo tiene el calendario, ninguna lista; las notas van en sobre cerrado.",
    ),
    # Antes hablaba de un servicio suspendido por falla (el mismo cuento que el teleférico cerrado); ahora es el pasaje.
    Mision(
        "periodista_estacao", "periodista", "Pasaje más caro",
        "Un audio anuncia un pasaje más caro en la Estação Alto do Morro. Confírmalo allí.",
        "Estação Alto do Morro",
        pago=85, dificultad="media",
        es_verdadera=True, grupo="instituciones",
        rumor="El pasaje del teleférico sube de R$ 4 a R$ 5 desde el lunes.",
        pista="La boletería todavía no cobra más: R$ 4; un aviso sellado fija R$ 5 desde el lunes.",
    ),
    # -- Influencer --
    Mision(
        "influencer_posto", "influencer", "Reto del suero",
        "Dicen que el Posto de Saúde Vila Nova avala el «suero casero». Revisa qué pasa allí.",
        "Posto de Saúde Vila Nova",
        pago=70, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Un reto en redes afirma que el puesto de salud recomienda beber suero casero.",
        pista="Un afiche del puesto habla de suero: indica el de sobre y advierte contra las mezclas.",
    ),
    Mision(
        "influencer_padaria", "influencer", "Pan gigante",
        "Un video muestra un «pan gigante» que hornea la Padaria Pão Quente. Míralo con tus ojos.",
        "Padaria Pão Quente",
        pago=45, dificultad="facil",
        es_verdadera=True, grupo="ciudadanos",
        rumor="La panadería hornea un pan gigante de un metro todos los sábados.",
        pista="Hoy no hay ningún pan grande en la vitrina; cuelga un molde de un metro: «sábados».",
    ),
    # Antes regalaba «premios» (el mismo cuento que generica_corrente); ahora es un reto viral sobre el horario.
    Mision(
        "influencer_bar", "influencer", "Reto de las 24 horas",
        "Un reto viral jura que el Bar do Cabo abre las 24 horas. Ve a ver qué hay de cierto.",
        "Bar do Cabo",
        pago=50, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="El bar atiende las 24 horas todos los días del año.",
        pista="Un neón dice «abierto 24 h»; debajo, en papel: «solo en carnaval; el resto, hasta las 0».",
    ),
    Mision(
        "influencer_mirante", "influencer", "Amanecer prohibido",
        "Una foto dice que cierran el acceso al Mirante do Alto. Sube y comprueba.",
        "Mirante do Alto",
        pago=90, dificultad="media",
        es_verdadera=True, grupo="policia",
        rumor="La guardia municipal cerró el acceso al mirante esta semana por el riesgo de la baranda rota.",
        pista="Hay gente arriba y nada les impide pasar: saltaron la cinta; el aviso de cierre cayó.",
    ),
    # -- Candidato --
    Mision(
        "candidato_igreja", "candidato", "Promesa en el atrio",
        "Un volante de «promesas» en la Igreja Nossa Senhora da Esperança. Decide qué responder.",
        "Igreja Nossa Senhora da Esperança",
        pago=70, dificultad="dificil",
        es_verdadera=False, grupo="instituciones",
        rumor="La parroquia reparte volantes que prometen empleo a quienes voten por un candidato.",
        pista="Hay volantes en el atrio: anuncian la bolsa de empleo parroquial, abierta a todo vecino.",
    ),
    Mision(
        "candidato_oficina", "candidato", "Obra sin permiso",
        "Dicen que la Oficina do Seu Zé amplió el local sin permiso. Revisa qué pasa allí.",
        "Oficina do Seu Zé",
        pago=60, dificultad="media",
        es_verdadera=True, grupo="instituciones",
        rumor="El taller construyó una ampliación sin licencia de obra.",
        pista="El muro es nuevo; la única licencia de la fachada es de 2019 y no autoriza más que pintar.",
    ),
    Mision(
        "candidato_varzea", "candidato", "Cancha prometida",
        "Dicen que el Campo de Várzea tendrá techo pagado por la alcaldía. Revisa qué pasa allí.",
        "Campo de Várzea",
        pago=75, dificultad="media",
        es_verdadera=True, grupo="instituciones",
        rumor="La alcaldía licitó un techo para la tribuna del campo con fondos propios.",
        pista="Un letrero de licitación municipal, con monto y fecha de inicio, junto a la tribuna.",
    ),
    Mision(
        "candidato_salao", "candidato", "Voto en la peluquería",
        "En el Salão da Dona Lu repiten que ya hay ganador de la elección. Míralo con tus ojos.",
        "Salão da Dona Lu",
        pago=50, dificultad="facil",
        es_verdadera=False, grupo="instituciones",
        rumor="Una encuesta cerrada ya definió al ganador de la elección y no hace falta votar.",
        pista="El único cartel electoral anuncia la fecha de votación; ninguna encuesta ni resultado.",
    ),
    # -- Genéricas en lugares de trabajo --
    # La Lan House da Praça es un comercio DENTRO de la Praça da Sé: el destino es la plaza y el texto lo dice.
    Mision(
        "generica_lanhouse", None, "Wifi ilimitado",
        "Un cartel de la Lan House da Praça pide tus datos por wifi ilimitado. Ve a la Praça da Sé.",
        "Praça da Sé",
        pago=20, dificultad="facil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="La lan house exige tu documento y tu teléfono para darte acceso al wifi ilimitado.",
        pista="Nadie anota documentos ni teléfonos; el wifi se activa con una clave del mostrador.",
    ),
    Mision(
        "generica_taller_turno", None, "Turnos de taller",
        "Se reenvía que los turnos en la Oficina do Seu Zé pagan el doble. Compruébalo en persona.",
        "Oficina do Seu Zé",
        pago=60, dificultad="media",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Los turnos de fin de semana del taller pagan el doble de lo normal.",
        pista="El aviso de vacantes ofrece «pago doble»: únicamente el feriado del día 15.",
    ),
    Mision(
        "generica_entregas", None, "Entrega que no llega",
        "Acusan al Ponto de Mototáxi da Entrada de cobrar entregas falsas. Compruébalo en persona.",
        "Ponto de Mototáxi da Entrada",
        pago=110, dificultad="dificil",
        es_verdadera=False, grupo="ciudadanos",
        rumor="Los mototaxistas cobran por entregas que nunca llegan a su destino.",
        pista="Paquetes pendientes en un estante, con etiqueta «devuelto: casa cerrada» y nueva fecha.",
    ),
    Mision(
        "generica_feira_turno", None, "Sorteo de puestos",
        "Sortearán los puestos de la Feira da Ladeira el lunes. Ve a ver qué hay de cierto.",
        "Feira da Ladeira",
        pago=85, dificultad="media",
        es_verdadera=True, grupo="ciudadanos",
        rumor="Los puestos libres se asignan por sorteo público el lunes.",
        pista="Un aviso sellado cita al sorteo del lunes; hay una urna cerrada y la lista de interesados.",
    ),
)

CATALOGO_MISIONES_GRANDE = CATALOGO_MISIONES + MISIONES_MAPA_GRANDE + MISIONES_EXTRA_GRANDE


# Misiones DIGITALES (una de parkour y una de investigación por mapa), SOLO para la partida de solo con GameState: no están
# en los catálogos de arriba porque en línea/coop no hay GameState y la partida termina al completar todas (serían
# imposibles). Se completan por señal (backend/logica/misiones_digitales.py), no en el lugar. El destino es el lugar al
# que apunta el HUD: el que queda junto a la «Terminal de la Fiscalía» (zona `mercado`; a ~40 m de «Mercado Municipal» en
# el chico y a ~43 m de «Feira da Ladeira» en el grande). Ids distintos por mapa. Mensaje: cierre propio de su tipo
# (parkour «...hasta la meta.», investigación «...Terminal de la Fiscalía.»); no nombran el destino sino el terminal.
# Dificultad por tema: el parkour es «media»; la investigación (acusar, datos), «dificil». Pago: fórmula de §10 aplicada
# a su destino y dificultad (la comprueba tests/test_misiones_semilla.py).
MISIONES_DIGITALES_CHICO = (
    Mision(
        "parkour_sector_1", None, "Servidor fantasma",
        "Un servidor fantasma guarda un rastro. En la Terminal de la Fiscalía, cruza hasta la meta.",
        "Mercado Municipal",
        pago=30, dificultad="media", tipo="parkour", objetivo="sector_1", grupo="policia",
    ),
    Mision(
        "investigacion_cuentas", None, "Cuentas fantasma",
        "Hay cuentas falsas en Civitas. Revisa el caso en la Terminal de la Fiscalía.",
        "Mercado Municipal",
        pago=40, dificultad="dificil", tipo="investigacion", objetivo="cuentas_fantasma", grupo="policia",
    ),
)

MISIONES_DIGITALES_GRANDE = (
    Mision(
        "parkour_sector_1_grande", None, "Servidor fantasma",
        "Un servidor fantasma guarda un rastro. En la Terminal de la Fiscalía, cruza hasta la meta.",
        "Feira da Ladeira",
        pago=85, dificultad="media", tipo="parkour", objetivo="sector_1", grupo="policia",
    ),
    Mision(
        "investigacion_cuentas_grande", None, "Cuentas fantasma",
        "Hay cuentas falsas en Civitas. Revisa el caso en la Terminal de la Fiscalía.",
        "Feira da Ladeira",
        pago=110, dificultad="dificil", tipo="investigacion", objetivo="cuentas_fantasma", grupo="policia",
    ),
)


def _es_mundo_grande(mundo):
    return hasattr(mundo, "contenido_de_chunk") and hasattr(mundo, "muros_de_chunk")


def catalogo_de_mundo(mundo):
    """El catálogo de misiones que corresponde al mundo: un MundoGrande (con chunks) usa CATALOGO_MISIONES_GRANDE; cualquier otro
    (el chico de siempre, o los falsos de las pruebas), CATALOGO_MISIONES. Lo usan main.py, el anfitrión y los clientes online
    para que todos hablen del mismo catálogo. NUNCA incluye misiones digitales (ver catalogo_solo)."""
    return CATALOGO_MISIONES_GRANDE if _es_mundo_grande(mundo) else CATALOGO_MISIONES


def catalogo_solo(mundo, con_game_state, solo_digitales=False):
    """Catálogo de la partida de SOLO (hot-seat): catalogo_de_mundo(mundo) + las misiones digitales del mapa, al final,
    únicamente si hay GameState y su nivel/caso existe y carga (si no, se omiten en silencio; el motivo lo da
    misiones_digitales.evaluar). Sin GameState devuelve el catálogo de siempre.
    `solo_digitales` (DEPURACIÓN, ALCALDE_SOLO_DIGITALES=1): devuelve ÚNICAMENTE las digitales del mapa para probarlas sin
    jugar antes las de verificar; si no hay ninguna disponible (sin GameState) se ignora y devuelve el catálogo de siempre."""
    base = catalogo_de_mundo(mundo)
    digitales = MISIONES_DIGITALES_GRANDE if _es_mundo_grande(mundo) else MISIONES_DIGITALES_CHICO
    disponibles = tuple(misiones_digitales.disponibles(digitales, con_game_state))
    if solo_digitales and disponibles:
        return disponibles
    return tuple(base) + disponibles
