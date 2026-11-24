# Casos propios de las misiones del reparto por días (sesión D, subagente b). Formato: backend/datos/minijuegos_casos.py.
# Un caso por misión, con `misiones: [<id>]` y `temas: []`: solo salen para SU misión (las 14 de siempre juegan lo de siempre).
# Cada caso habla de su rumor y no contradice la `pista` real de la misión (misiones_semilla.MISIONES_NUEVAS_DIAS).
# Arcos: «subsidio» (h_subsidio_gestor -> k_auxilio_transporte: mismo chat del mercado, Don Ciro y Marlene), «agua»
# (t_agua_corte -> t_agua_turbia) y «urnas» (t_canastas_votos -> t_mesas_votacion). Lo vigila tests/test_misiones_dias_casos_b.py.

# =====================================================================================================================
# CHAT DEL BARRIO (3 turnos; valor 2 = protege y comprueba, 1 = a medias, 0 = cede un dato de otro o se deja llevar).
# =====================================================================================================================
CHAT = [
    {
        # Verdadero. Hábito: el trámite real es en persona; no se mandan documentos por chat (ni los de otro) y tampoco se
        # descarta un aviso cierto sin mirarlo.
        "id": "h_biblioteca", "temas": [], "misiones": ["ciudadano_biblioteca"],
        "titulo": "Chat «Vecinos lectores»", "amigo": "Joana",
        "intro": "Dicen que la biblioteca de la universidad presta libros con un carné vecinal. Joana quiere sacarlo.",
        "turnos": [
            {"de": "Rubén (grupo)", "texto": "Yo saco el carné por todos: pásenme foto del documento y su dirección.", "segundos": 20, "opciones": [
                {"texto": "El carné se tramita en persona, en el mostrador. No mando mi documento.", "valor": 2, "reaccion": "Rubén: «Ah, no sabía que era en persona»."},
                {"texto": "Lo pienso y te digo.", "valor": 1, "reaccion": "Rubén: «Apúrate, que se acaban»."},
                {"texto": "Ahí va la foto de mi documento.", "valor": 0, "reaccion": "Rubén: «Recibido, ya te tengo»."}]},
            {"de": "Rubén (grupo)", "texto": "¿Y el de Joana? Está ocupada. Mándame su documento, que tú lo tienes.", "segundos": 15, "opciones": [
                {"texto": "Que lo tramite ella en el mostrador. Yo no paso datos de otros.", "valor": 2, "reaccion": "Rubén: «Bueno, que vaya ella»."},
                {"texto": "Te reenvío la foto que ella me mandó.", "valor": 0, "reaccion": "Rubén: «Perfecto, gracias»."},
                {"texto": "Le pregunto a ella y te aviso.", "valor": 1, "reaccion": "Rubén: «Dale, rapidito»."}]},
            {"de": "Don Ernesto", "texto": "Eso de los libros es puro cuento: nadie presta nada. ¿Para qué ir?", "segundos": 20, "opciones": [
                {"texto": "En la puerta hay un aviso: trámite en el mostrador, de lunes a sábado.", "valor": 2, "reaccion": "Ernesto: «Entonces voy el lunes»."},
                {"texto": "No sé, puede que sí, puede que no.", "valor": 1, "reaccion": "Ernesto: «Pues yo no me muevo»."},
                {"texto": "Mejor que Rubén lo saque con los documentos de todos.", "valor": 0, "reaccion": "Ernesto: «Le mando el mío, entonces»."}]},
        ],
    },
    {
        # Falso (arco subsidio, paso 2). Hábito: nadie autorizado pide la clave de la tarjeta; ni la tuya ni la de otro; si
        # alguien ya la dio, que la bloquee. Desconfiar del «gestor» y de la urgencia de «último día».
        "id": "h_subsidio_gestor", "temas": [], "misiones": ["generica_subsidio_gestor"],
        "titulo": "Chat «Vecinos del Mercado»", "amigo": "Don Ciro",
        "intro": "Tras la cadena del enlace, ahora dicen que un gestor tramita el subsidio en el mercado. Don Ciro ya fue.",
        "turnos": [
            {"de": "Marlene (grupo)", "texto": "El gestor es autorizado. Solo pide la clave de la tarjeta. ¿Le mandas la tuya?", "segundos": 18, "opciones": [
                {"texto": "Nadie autorizado pide claves. ¿Dónde está el sello de la alcaldía?", "valor": 2, "reaccion": "Marlene: «Eh... sello no vi»."},
                {"texto": "Lo pienso, mañana te digo.", "valor": 1, "reaccion": "Marlene: «Mañana ya no hay cupo»."},
                {"texto": "Te paso mi clave y que él la anote.", "valor": 0, "reaccion": "Marlene: «Listo, ya la anotó»."}]},
            {"de": "Marlene (grupo)", "texto": "Don Ciro dejó su tarjeta, pero le falta la clave. Tú la sabes, ¿no?", "segundos": 15, "opciones": [
                {"texto": "No doy la clave de otro. Y Don Ciro debe bloquear su tarjeta ya.", "valor": 2, "reaccion": "Marlene: «¿Bloquearla? Uy, le aviso»."},
                {"texto": "Es la fecha de su cumpleaños, creo.", "valor": 0, "reaccion": "Marlene: «Perfecto, se la paso»."},
                {"texto": "Pregúntale a él, yo no me meto.", "valor": 1, "reaccion": "Marlene: «Ay, qué complicado»."}]},
            {"de": "Chat del mercado", "texto": "Si no le dan la clave al gestor, se quedan sin subsidio. ¡Hoy es el último día!", "segundos": 20, "opciones": [
                {"texto": "Esa mesa no tiene sello. Lo oficial se anuncia en la Prefeitura.", "valor": 2, "reaccion": "Chat: «Cierto, era un cartel a mano»."},
                {"texto": "Prefiero esperar a ver qué pasa.", "valor": 1, "reaccion": "Chat: «Tú te lo pierdes»."},
                {"texto": "Le mando también la clave de mi mamá.", "valor": 0, "reaccion": "Chat: «¡Así se hace!»."}]},
        ],
    },
    {
        # Falso. Hábito: un SMS que amenaza con una multa y manda a un enlace es una trampa; se comprueba en el lugar (el
        # torniquete y la taquilla) y no se reenvía.
        "id": "h_tarjeta_bus", "temas": [], "misiones": ["ciudadano_tarjeta_bus"],
        "titulo": "Chat «Los del bus 5»", "amigo": "Tati",
        "intro": "Llegó un SMS: o registras la tarjeta del bus en un enlace o te multan. Tati ya contestó.",
        "turnos": [
            {"de": "Número desconocido", "texto": "Registre su tarjeta hoy en tarjetabus-nova.xyz o pagará una multa de R$150.", "segundos": 18, "opciones": [
                {"texto": "No abro el enlace. Paso la tarjeta por el torniquete y lo compruebo.", "valor": 2, "reaccion": "Chat: «Buena idea, cuéntanos»."},
                {"texto": "Lo dejo para después.", "valor": 1, "reaccion": "SMS: «Último aviso: la multa corre hoy»."},
                {"texto": "Abro el enlace y lleno el registro.", "valor": 0, "reaccion": "SMS: «Gracias. Registro en proceso»."}]},
            {"de": "Kevin (grupo)", "texto": "Tati no sabe llenarlo. Dame su documento y el número de su tarjeta, yo lo hago.", "segundos": 15, "opciones": [
                {"texto": "Esos datos son solo de Tati. Que no los mande a nadie.", "valor": 2, "reaccion": "Kevin: «Bueno, se lo digo»."},
                {"texto": "Te paso los datos de Tati, los tengo.", "valor": 0, "reaccion": "Kevin: «Listo, ya los envié»."},
                {"texto": "Pregúntale a ella.", "valor": 1, "reaccion": "Kevin: «Ella no contesta»."}]},
            {"de": "Chat del bus", "texto": "¡Reenvíen el SMS a todos para que nadie pague la multa!", "segundos": 20, "opciones": [
                {"texto": "En la terminal el registro es voluntario y sin multas. No lo reenvíen.", "valor": 2, "reaccion": "Chat: «Uy, entonces es una trampa»."},
                {"texto": "Reenvíenlo solo a la familia.", "valor": 1, "reaccion": "Chat: «Bueno, algo es algo»."},
                {"texto": "Reenvío el SMS con el número de Tati.", "valor": 0, "reaccion": "Chat: «¡Gracias por avisar!»."}]},
        ],
    },
    {
        # Verdadero. Hábito: no dudar sin motivo de un aviso oficial (el decreto está a la vista); compartir el aviso con su
        # fecha, sin señalar ni pasar el teléfono de nadie.
        "id": "h_ley_seca", "temas": [], "misiones": ["candidato_ley_seca"],
        "titulo": "Chat «Puesteros»", "amigo": "Nelson",
        "intro": "Dicen que desde la víspera de la elección no se vende licor. Nelson tiene un puesto en el mercado.",
        "turnos": [
            {"de": "Fabio (grupo)", "texto": "Eso de la ley seca es un invento para arruinar a los puesteros. ¡No lo crean!", "segundos": 20, "opciones": [
                {"texto": "El decreto está pegado en cada puesto del mercado. Ya lo vi.", "valor": 2, "reaccion": "Fabio: «Mmm, si está pegado...»."},
                {"texto": "No sé, que cada uno crea lo que quiera.", "valor": 1, "reaccion": "Fabio: «Ves, nadie está seguro»."},
                {"texto": "Tienes razón, es un invento. Lo reenvío.", "valor": 0, "reaccion": "Fabio: «¡Eso, que se sepa!»."}]},
            {"de": "Fabio (grupo)", "texto": "Pásame el teléfono de Nelson: que me venda licor por la puerta de atrás.", "segundos": 15, "opciones": [
                {"texto": "No paso su teléfono. Y él cumple la ley seca, como todos.", "valor": 2, "reaccion": "Fabio: «Qué aburrido eres»."},
                {"texto": "Es 11 9444-7788, dile que vas de mi parte.", "valor": 0, "reaccion": "Fabio: «Gracias, lo llamo ya»."},
                {"texto": "Pregúntale tú en el mercado.", "valor": 1, "reaccion": "Fabio: «Ya veré»."}]},
            {"de": "Chat del barrio", "texto": "¿Compartimos el aviso de la ley seca? Pongan nombre y puesto de quien venda.", "segundos": 20, "opciones": [
                {"texto": "Sí: solo la foto del decreto, con su fecha. Sin señalar a nadie.", "valor": 2, "reaccion": "Chat: «Mejor así, sin nombres»."},
                {"texto": "Mejor no compartan nada.", "valor": 1, "reaccion": "Chat: «Pero es un aviso real»."},
                {"texto": "Sí, y pongo el puesto y el teléfono de Nelson.", "valor": 0, "reaccion": "Chat: «Listo, ya circula»."}]},
        ],
    },
]

# =====================================================================================================================
# CONTRARRELOJ (4 cartas propias: 2 veraces y 2 falsas; la carta del rumor de la misión se mezcla sola).
# =====================================================================================================================
CONTRARRELOJ = [
    {
        # Verdadero (arco agua, paso 1). Hábito: dejar pasar el aviso de la empresa y lo que se deriva de él; frenar lo que
        # exagera o pide pagar por el servicio.
        "id": "t_agua_corte", "temas": [], "misiones": ["generica_agua_corte"],
        "titulo": "Hora pico del chat: el agua en el morro",
        "cartas": [
            {"texto": "La empresa pide llenar baldes el miércoles por la noche (aviso en los postes).", "veraz": True, "ritmo": 13},
            {"texto": "Cortan el agua toda la semana y los carrotanques solo van a otros barrios.", "veraz": False, "ritmo": 9},
            {"texto": "La escuela del morro sale al mediodía el jueves (nota de la dirección).", "veraz": True, "ritmo": 14},
            {"texto": "Quien no pague una cuota al fontanero se queda sin agua tras el corte.", "veraz": False, "ritmo": 8},
        ],
    },
    {
        # Falso (arco agua, paso 2). Hábito: frenar lo que asusta sin fuente (y los «remedios» peligrosos); dejar pasar la
        # indicación de la empresa.
        "id": "t_agua_turbia", "temas": [], "misiones": ["generica_agua_turbia"],
        "titulo": "Hora pico del chat: el agua tras el corte",
        "cartas": [
            {"texto": "Tras el corte, deja correr la llave un minuto hasta que el agua salga clara.", "veraz": True, "ritmo": 13},
            {"texto": "Echen cloro de piso al tanque: así se limpia el agua del morro.", "veraz": False, "ritmo": 8},
            {"texto": "El servicio volvió en toda la ladera; la empresa terminó la reparación.", "veraz": True, "ritmo": 14},
            {"texto": "La empresa mezcló el agua con la de un río sucio para ahorrar.", "veraz": False, "ritmo": 9},
        ],
    },
    {
        # Falso (arco urnas, paso 1). Hábito: el voto no se vende ni se fotografía; frenar los mitos que meten miedo; dejar
        # pasar la colecta real y la norma electoral.
        "id": "t_canastas_votos", "temas": [], "misiones": ["generica_canastas_votos"],
        "titulo": "Hora pico del chat: la semana de la elección",
        "cartas": [
            {"texto": "La colecta del barrio recibe alimentos en la Escola de Samba hasta el viernes.", "veraz": True, "ritmo": 13},
            {"texto": "Manda la foto de tu voto y te pagan el recibo de la luz. Escribe a este chat.", "veraz": False, "ritmo": 8},
            {"texto": "Comprar o vender el voto es delito: se denuncia ante la autoridad electoral.", "veraz": True, "ritmo": 14},
            {"texto": "Ya saben por quién votas: la tinta del dedo trae un chip.", "veraz": False, "ritmo": 9},
        ],
    },
    {
        # Falso (arco urnas, paso 2). Hábito: el día de votar, buscar el listado oficial de mesas; frenar lo que busca que la
        # gente no vaya a votar.
        "id": "t_mesas_votacion", "temas": [], "misiones": ["generica_mesas_votacion"],
        "titulo": "Hora pico del chat: llega el día de votar",
        "cartas": [
            {"texto": "El listado oficial de mesas está pegado en la entrada de cada puesto.", "veraz": True, "ritmo": 13},
            {"texto": "Si llevas una camiseta de cierto color, no te dejan votar.", "veraz": False, "ritmo": 9},
            {"texto": "Para votar basta tu documento; el jurado de mesa te busca en la lista.", "veraz": True, "ritmo": 14},
            {"texto": "Si no llegas antes de las 10, otro vota por ti: ya hay listas de ausentes.", "veraz": False, "ritmo": 8},
        ],
    },
]

# =====================================================================================================================
# CRONOLOGÍA (5 mensajes YA en orden cronológico; el primero y el cierre dependen del veredicto).
# =====================================================================================================================
CRONOLOGIA = [
    {
        # Verdadero (arco subsidio, paso 3). Hábito: después de dos engaños, no descartarlo todo: buscar el edicto con sello y
        # fecha y ver quién lo dijo primero.
        "id": "k_auxilio_transporte", "temas": [], "misiones": ["generica_auxilio_transporte"],
        "titulo": "El auxilio que sí existe",
        "intro": "Tras tanta cadena, ahora dicen: «{rumor}». Ordena cómo se supo.",
        "items": [
            {"quien": {"v": "Edicto en la ventanilla 3", "f": "Cadena sin firma"},
             "texto": {"v": "Inscripción presencial al auxilio de transporte desde el lunes.", "f": "Hay otro auxilio: llena el enlace ya."},
             "hora": "viernes 09:00"},
            {"quien": "Funcionaria de ventanilla", "texto": "Confirmo: es en ventanilla y no se pide ninguna clave.", "hora": "viernes 11:30"},
            {"quien": "Don Ciro", "texto": "Después de lo del gestor, fui a ver el edicto yo mismo.", "hora": None},
            {"quien": "Chat «Vecinos del Mercado»", "texto": "Reenviado: foto del edicto, con sello y fecha.", "hora": "sábado 08:15"},
            {"quien": "Marlene", "texto": "¿Y si es otra trampa? Ah, no: aquí no piden claves.", "hora": "sábado 19:00"},
        ],
        "cierre": {"v": "El edicto con sello fue lo primero; los demás lo repitieron.",
                   "f": "Empezó con una cadena sin firma y nadie mostró el edicto."},
    },
    {
        # Verdadero. Hábito: ir a la fuente (la programación de la emisora) y ver cómo se fue contando.
        "id": "k_debate", "temas": [], "misiones": ["candidato_debate"],
        "titulo": "El debate de la radio",
        "intro": "Corre la voz: «{rumor}». Ordena los mensajes del primero al último.",
        "items": [
            {"quien": {"v": "Programación de la radio", "f": "Cuenta sin nombre"},
             "texto": {"v": "Sábado 19 h: debate en vivo de los candidatos.", "f": "Dicen que habrá un debate, no se sabe cuándo."},
             "hora": "lunes 10:00"},
            {"quien": "Locutora de la mañana", "texto": "Lo anunciamos al aire: manden sus preguntas del barrio.", "hora": "lunes 12:00"},
            {"quien": "Tía Rosa", "texto": "Lo oí en la radio de la cocina y se lo conté a mi hija.", "hora": None},
            {"quien": "Grupo «Vecinos de la Sé»", "texto": "Reenviado: el sábado, debate en la radio. ¡Pásalo!", "hora": "martes 09:30"},
            {"quien": "Beto", "texto": "¿Seguro que es el sábado? Voy a mirar el cartel de la puerta.", "hora": "martes 20:10"},
        ],
        "cierre": {"v": "La programación de la radio fue lo primero; lo demás la repitió.",
                   "f": "Nadie encontró la programación: se fue repitiendo solo."},
    },
    {
        # Verdadero. Hábito: un aviso con sello y fecha explica la aparente contradicción («hoy cobran»): la medida es solo
        # para el domingo.
        "id": "k_teleferico_eleccion", "temas": [], "misiones": ["ciudadano_teleferico_eleccion"],
        "titulo": "El teleférico del domingo",
        "intro": "Dicen: «{rumor}». Ordena la cadena desde el primer mensaje.",
        "items": [
            {"quien": {"v": "Aviso sellado (boletería)", "f": "Audio sin autor"},
             "texto": {"v": "Domingo de elección: pasaje libre de 6 a 18 h.", "f": "Parece que el domingo no se paga, o algo así."},
             "hora": "miércoles 08:00"},
            {"quien": "Boletera Clara", "texto": "Sí, es solo el domingo; hoy se cobra como siempre.", "hora": "miércoles 10:20"},
            {"quien": "Vecino del morro", "texto": "Clara me lo confirmó y le tomé foto al aviso.", "hora": None},
            {"quien": "Chat «Los del teleférico»", "texto": "Reenviado: el domingo, a votar en teleférico.", "hora": "jueves 18:00"},
            {"quien": "Nando", "texto": "Hoy me cobraron... Ah, claro: lo del aviso es el domingo.", "hora": "viernes 07:30"},
        ],
        "cierre": {"v": "El aviso sellado de la estación fue lo primero y tenía fecha.",
                   "f": "El primer mensaje era un audio sin autor y nadie lo comprobó."},
    },
]

CASOS_DIAS = {"chat": CHAT, "contrarreloj": CONTRARRELOJ, "cronologia": CRONOLOGIA}
