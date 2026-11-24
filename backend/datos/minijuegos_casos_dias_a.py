# Casos propios de las misiones del reparto por días (sesión D). Formato: backend/datos/minijuegos_casos.py.
# Módulo (a): 10 misiones; 4 de comparar, 4 de señales y 2 de rastrear. Cada caso habla de SU rumor (`misiones` con su id) y
# lleva `temas` vacío: así solo sale para su misión y las 14 misiones de siempre siguen jugando sus casos de siempre.
# Cada texto respeta el largo del texto equivalente más largo de los casos de siempre (tests/test_misiones_dias_casos_a.py).
# El «primo Wilmer» es el mismo personaje en los dos casos de su arco (días 1 y 4).

# ---------------------------------------------------------------------------------------------------------------------
# COMPARAR DOS VERSIONES (las cuatro misiones son de rumor falso: la copia trae las líneas alteradas en «c»).
# ---------------------------------------------------------------------------------------------------------------------
COMPARAR = [
    {
        # Hábito: un audio «de alguien que trabaja allí» no es la fuente; la fuente es la tabla de la taquilla.
        "id": "c_primo_terminal", "temas": [], "misiones": ["generica_primo_audio"],
        "titulo": "El audio del primo Wilmer",
        "original": "La tabla de tarifas de la taquilla", "copia": "Lo que dice el audio del primo",
        "lineas": [
            {"e": "Destino", "o": "Hacia la capital"},
            {"e": "Precio del pasaje", "o": "El de siempre", "c": "El doble"},
            {"e": "Desde cuándo", "o": "Sin cambios este año", "c": "Desde el lunes"},
            {"e": "Quién lo dice", "o": "Administración de la Rodoviária", "c": "«Un primo que trabaja allí»"},
            {"e": "Horario de la taquilla", "o": "De 6:00 a 20:00"},
        ],
    },
    {
        # Hábito: una fuente que ya falló una vez merece más dudas, no menos; se contrasta con el registro del lugar.
        "id": "c_primo_oxigeno", "temas": [], "misiones": ["generica_primo_hospital"],
        "titulo": "Otro audio del primo Wilmer",
        "original": "La planilla de la puerta del hospital", "copia": "El nuevo audio del primo Wilmer",
        "lineas": [
            {"e": "Oxígeno", "o": "Reserva para 9 días", "c": "Se acabó esta mañana"},
            {"e": "Entrega de hoy", "o": "Un camión con cilindros", "c": "No llega ningún camión"},
            {"e": "Pacientes", "o": "Se atiende a todos", "c": "Rechazan a los que llegan"},
            {"e": "Urgencias", "o": "Abiertas"},
            {"e": "Quién informa", "o": "Dirección del hospital", "c": "El primo Wilmer, por audio"},
            {"e": "Hora del dato", "o": "Hoy, 7:00"},
        ],
    },
    {
        # Hábito: una foto vieja reciclada con otra fecha; buscar la imagen original y mirar los detalles que no encajan.
        "id": "c_parque_lleno", "temas": [], "misiones": ["periodista_foto_mitin"],
        "titulo": "La foto del parque lleno",
        "original": "La foto original (carnaval del año pasado)", "copia": "La foto que circula del mitin",
        "lineas": [
            {"e": "Fecha", "o": "Febrero del año pasado", "c": "Anoche"},
            {"e": "Evento", "o": "Desfile de carnaval", "c": "Mitin de un candidato"},
            {"e": "Adornos", "o": "Serpentinas y máscaras"},
            {"e": "Escenario", "o": "Sin tarima: pasa una comparsa", "c": "Una tarima con banderas"},
            {"e": "Autor", "o": "Fotógrafo del diario del barrio", "c": "Sin autor ni crédito"},
            {"e": "Lugar", "o": "Parque do Povo"},
        ],
    },
    {
        # Hábito: comparar con la fuente oficial; ningún resultado sale antes de cerrar las urnas, y un escudo se imita.
        "id": "c_boletin_ganador", "temas": [], "misiones": ["periodista_boletin"],
        "titulo": "Un boletín «con sello municipal»",
        "original": "La cartelera oficial de la Prefeitura", "copia": "El boletín que circula en los grupos",
        "lineas": [
            {"e": "Escudo", "o": "El de Ciudad Nova", "c": "Otro escudo, parecido al oficial"},
            {"e": "Contenido", "o": "Horario de votación: 8 a 16 h", "c": "El nombre del ganador"},
            {"e": "Resultados", "o": "Después del cierre de las urnas", "c": "Ya definidos, antes del cierre"},
            {"e": "Firma", "o": "Secretaría de Gobierno", "c": "Sin firma ni número"},
            {"e": "Día", "o": "Domingo de elección"},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------------
# SEÑALES DE EDICIÓN (las cuatro misiones son de rumor falso: 3 zonas con `falla`, 3 que no delatan nada).
# ---------------------------------------------------------------------------------------------------------------------
SENALES = [
    {
        # Hábito: urgencia artificial + dominio que imita al oficial + piden claves = estafa de «subsidio».
        "id": "s_subsidio_enlace", "temas": [], "misiones": ["generica_subsidio_cadena"],
        "titulo": "Una cadena del subsidio", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Subsidio de R$600: llena el formulario HOY", "lupa": "El titular del mensaje", "falla": True,
             "explica": "La prisa («solo hoy») es una trampa. La cartelera oficial no anuncia ningún subsidio."},
            {"id": "z2", "texto": "Enlace: alcaldia-nova.subsidios-ya.com", "lupa": "La dirección del enlace", "falla": True,
             "explica": "No es la página oficial de la alcaldía: es otro dominio con un nombre parecido."},
            {"id": "z3", "texto": "Pide documento, clave y foto de la tarjeta", "lupa": "Los datos que pide", "falla": True,
             "explica": "Ningún trámite oficial pide claves. Con esos datos se roban cuentas."},
            {"id": "z4", "texto": "Escudo de la ciudad en la esquina", "lupa": "La imagen del encabezado", "falla": False,
             "explica": "Un escudo se copia en un segundo: no prueba nada."},
            {"id": "z5", "texto": "Enviado por: Grupo «Vecinos del Centro»", "lupa": "Quién lo compartió", "falla": False,
             "explica": "Quien lo reenvía suele creerlo; no es quien lo escribió."},
            {"id": "z6", "texto": "Leído por 1.204 personas", "lupa": "El contador del mensaje", "falla": False,
             "explica": "Que mucha gente lo lea no lo hace verdadero."},
        ],
    },
    {
        # Hábito: en salud, desconfiar de «curas» garantizadas, de membretes mal copiados y del «secreto que esconden».
        "id": "s_te_dengue", "temas": [], "misiones": ["influencer_te_dengue"],
        "titulo": "Una captura «del hospital»", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "«Cura el dengue en dos días, garantizado»", "lupa": "La promesa principal", "falla": True,
             "explica": "Ningún té cura el dengue. Con fiebre, lo indicado es ir a la consulta médica."},
            {"id": "z2", "texto": "Membrete: «Hospital Santa Kasa»", "lupa": "El membrete de la hoja", "falla": True,
             "explica": "El nombre está mal escrito: es «Santa Casa». Un membrete copiado a la ligera."},
            {"id": "z3", "texto": "«Los médicos no quieren que lo sepas»", "lupa": "Una frase en negrita", "falla": True,
             "explica": "Hablar de un secreto que «esconden» los médicos es un truco típico de los bulos de salud."},
            {"id": "z4", "texto": "Foto de un vaso de té con hojas", "lupa": "La imagen del centro", "falla": False,
             "explica": "Una foto de un té no dice nada sobre lo que cura."},
            {"id": "z5", "texto": "Venta: Mercado Municipal, puesto de hierbas", "lupa": "El dato del puesto", "falla": False,
             "explica": "El puesto existe y vende hierbas, pero eso no prueba la promesa."},
            {"id": "z6", "texto": "Hora de la captura: 10:42", "lupa": "La hora", "falla": False,
             "explica": "Una hora normal: no delata nada."},
        ],
    },
    {
        # Hábito: una encuesta seria trae ficha técnica (quién, cuándo, a cuántos, margen); el logo se copia fácil.
        "id": "s_encuesta_82", "temas": [], "misiones": ["generica_encuesta"],
        "titulo": "La encuesta del 82 %", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Logo de la universidad, estirado a lo ancho", "lupa": "El logo del encabezado", "falla": True,
             "explica": "Un logo deformado suele ser un recorte pegado de otra imagen."},
            {"id": "z2", "texto": "Ficha técnica: (no aparece)", "lupa": "El pie del afiche", "falla": True,
             "explica": "Una encuesta seria dice a cuántas personas preguntó, cuándo, cómo y con qué margen de error."},
            {"id": "z3", "texto": "Realizada: «esta semana»", "lupa": "Cuándo se hizo", "falla": True,
             "explica": "Sin una fecha exacta no se sabe si es vieja, ni siquiera si se hizo."},
            {"id": "z4", "texto": "Un candidato: 82 %", "lupa": "El resultado", "falla": False,
             "explica": "Una cifra alta llama la atención, pero sola no prueba nada: hay que ver la ficha."},
            {"id": "z5", "texto": "Gráfico de torta en dos colores", "lupa": "El gráfico", "falla": False,
             "explica": "El gráfico suma 100 %: no tiene errores a la vista."},
            {"id": "z6", "texto": "Pegado en un poste de la Praça da Sé", "lupa": "Dónde está el afiche", "falla": False,
             "explica": "El lugar no dice nada sobre si la encuesta es real."},
        ],
    },
    {
        # Hábito: mirar el dominio del enlace y quién firma; los trámites del voto solo los anuncia la autoridad electoral.
        "id": "s_voto_celular", "temas": [], "misiones": ["influencer_voto_celular"],
        "titulo": "Votar desde el celular", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Vota aquí: votonova.xyz", "lupa": "El enlace del volante", "falla": True,
             "explica": "Termina en «.xyz»: no es una dirección oficial. Se vota solo en la mesa, en persona."},
            {"id": "z2", "texto": "Firma: «Organización electoral»", "lupa": "Quién lo firma", "falla": True,
             "explica": "No lleva sello ni el nombre de ninguna autoridad: cualquiera puede escribir esa firma."},
            {"id": "z3", "texto": "«¡Solo hasta el mediodía, apúrate!»", "lupa": "El aviso de la esquina", "falla": True,
             "explica": "La prisa busca que no compruebes. El horario oficial está en el cartel de la estación."},
            {"id": "z4", "texto": "Dibujo de una urna y un celular", "lupa": "La imagen del volante", "falla": False,
             "explica": "Un dibujo no dice nada."},
            {"id": "z5", "texto": "Repartido en la Estação do Teleférico", "lupa": "Dónde lo encontraste", "falla": False,
             "explica": "El lugar no lo hace ni más ni menos cierto."},
            {"id": "z6", "texto": "Papel impreso a color", "lupa": "El papel", "falla": False,
             "explica": "Imprimir a color es fácil: no prueba que sea oficial."},
        ],
    },
]

# ---------------------------------------------------------------------------------------------------------------------
# RASTREAR LA FUENTE (la PRIMERA opción de cada salto es la correcta: la más antigua y no reenviada; la lógica las baraja).
# ---------------------------------------------------------------------------------------------------------------------
RASTREAR = [
    {
        # Rumor VERDADERO. Hábito: aunque suene bien, se llega a la fuente primaria (el comunicado) antes de publicarlo.
        "id": "r_vacunas_sabado", "temas": [], "misiones": ["periodista_vacunas"],
        "intro": "En los grupos dicen: «{rumor}». Antes de publicarlo, busca quién lo dijo primero.",
        "hops": [
            {"pregunta": "Tu vecina Lucía te pasó la foto. ¿Quién se la mandó a ella?", "opciones": [
                {"de": "Enfermera Dalva (vecina)", "hora": "ayer 17:30", "texto": "Foto que tomé en la entrada del hospital."},
                {"de": "Grupo «Salud del barrio»", "hora": "ayer 20:10", "texto": "Reenviado: ¡vacunas el sábado!"},
                {"de": "Tío Fermín", "hora": "hoy 07:15", "texto": "Reenviado. ¿Será verdad?"}]},
            {"pregunta": "El cartel de la foto cita un comunicado. ¿Cuál circuló primero?", "opciones": [
                {"de": "Secretaría de Salud (comunicado)", "hora": "ayer 09:00", "texto": "Jornada contra la gripe: sábado, 8 a 16 h."},
                {"de": "Página «Nova al día»", "hora": "ayer 12:40", "texto": "Resumen del comunicado, con el enlace."},
                {"de": "Cuenta «Opinión libre»", "hora": "ayer 15:00", "texto": "Copiado de la página, sin enlace."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: la Secretaría de Salud", "detalle": "Comunicado firmado: sábado, 8 a 16 h, todas las edades y por orden de llegada."},
            "f": {"titulo": "Origen: una imagen sin fuente", "detalle": "Nadie en el hospital conoce esa jornada: el comunicado no existe."}},
    },
    {
        # Rumor FALSO. Hábito: ir al documento original; una cifra puede «crecer» al copiarse (un cero de más) y un decreto
        # sin número ni fecha no es un decreto.
        "id": "r_tarifa_luz", "temas": [], "misiones": ["candidato_tarifa_luz"],
        "intro": "En la radio y en los chats repiten: «{rumor}». Busca de dónde salió esa cifra.",
        "hops": [
            {"pregunta": "El locutor lo leyó de un mensaje. ¿Quién lo mandó primero?", "opciones": [
                {"de": "Grupo «Comerciantes del Centro»", "hora": "ayer 19:10", "texto": "Captura: «la luz sube 40 %», sin número de decreto."},
                {"de": "Oyente Marlene", "hora": "hoy 06:40", "texto": "Reenviado del grupo. ¡Qué abuso!"},
                {"de": "Chat «Vecinos de la Sé»", "hora": "hoy 07:05", "texto": "Reenviado muchas veces, sin fuente."}]},
            {"pregunta": "Esa captura recorta otra publicación. ¿Cuál es la más antigua?", "opciones": [
                {"de": "Boletín de la empresa de energía", "hora": "ayer 10:00", "texto": "Ajuste del 4 % a partir del próximo recibo."},
                {"de": "Cuenta «@alerta_tarifas»", "hora": "ayer 16:30", "texto": "Captura del boletín, con la cifra retocada."},
                {"de": "Página «Nova indignada»", "hora": "ayer 18:00", "texto": "Copia de la captura: «¡40 % más!»"}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: el decreto oficial", "detalle": "El decreto tiene número y fecha, y dice 40 %, igual que el rumor."},
            "f": {"titulo": "Origen: el boletín del 4 %", "detalle": "El boletín real dice 4 %. Alguien le sumó un cero; el decreto no tiene número ni fecha."}},
    },
]

CASOS_DIAS = {"comparar": COMPARAR, "senales": SENALES, "rastrear": RASTREAR}
