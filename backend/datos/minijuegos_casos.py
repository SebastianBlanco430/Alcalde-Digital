# Casos de los minijuegos de verificar (datos puros; sin ursina). Varios casos por minijuego para no repetir. Cada caso trae
# `temas` (ver minijuegos_asignacion.TEMAS) y, si se escribió pensando en un rumor concreto, `misiones` (ids de
# misiones_semilla). backend.logica.minijuegos.elegir_caso prefiere el caso hecho a propósito para la misión, luego el de su tema.
#
# Convenciones comunes:
#   - Un texto puede ser un str o {"v": ..., "f": ...}: «v» si el rumor de la misión es verdadero, «f» si es falso.
#   - {rumor}, {lugar} y {pista} se sustituyen por los de la misión (es el texto REAL del catálogo de misiones).
#   - Tono cotidiano (chat del barrio, carteles, capturas); sin cifras de indicadores.

# =====================================================================================================================
# 1. RASTREAR LA FUENTE. Cada salto (`hops`): la pregunta y 3 opciones; la PRIMERA es la correcta (el mensaje más antiguo y no
# reenviado); la lógica las baraja. `origen`: lo que se encuentra al final (verdadero / falso).
# =====================================================================================================================
RASTREAR = [
    {
        "id": "r_prefeitura", "temas": ["politica"], "misiones": ["periodista_prefeitura"],
        "intro": "En el chat del barrio todos repiten: «{rumor}». Tu trabajo: llegar a quien lo dijo primero.",
        "hops": [
            {"pregunta": "Beto, tu primo, te lo reenvió. ¿De dónde lo sacó él?", "opciones": [
                {"de": "Grupo «Vecinos de la Sé»", "hora": "ayer 21:05", "texto": "Mandan esto de la Prefeitura, avisen."},
                {"de": "Tía Rosa", "hora": "hoy 07:40", "texto": "Reenviado muchas veces. Me lo pasó una amiga."},
                {"de": "Lucho (taxista)", "hora": "hoy 08:15", "texto": "Reenviado: dicen que ya empezaron a multar."}]},
            {"pregunta": "Ese grupo lo copió de una cuenta. ¿Cuál publicó primero?", "opciones": [
                {"de": "@noticias_ya_ya", "hora": "ayer 19:30", "texto": "URGENTE: nueva norma. Sin enlace ni documento."},
                {"de": "@tuvecino_oficial", "hora": "ayer 22:10", "texto": "Confirmado por fuentes (copiado de @noticias_ya_ya)."},
                {"de": "Grupo «Alerta Barrio»", "hora": "hoy 06:00", "texto": "Reenviado. Compartan antes de que lo borren."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: la Prefeitura", "detalle": "Es un comunicado con sello y número de oficio en el sitio oficial."},
            "f": {"titulo": "Origen: @noticias_ya_ya", "detalle": "Cuenta creada anteayer, sin foto ni otras publicaciones. Nadie de la Prefeitura la conoce."}},
    },
    {
        "id": "r_morro", "temas": ["seguridad", "politica"], "misiones": ["candidato_morro"],
        "intro": "Dicen en el morro: «{rumor}». La gente está asustada. Averigua quién empezó esto.",
        "hops": [
            {"pregunta": "Doña Marta te mandó un audio. ¿A ella quién se lo pasó?", "opciones": [
                {"de": "Pedro, vecino de arriba", "hora": "ayer 17:20", "texto": "Vi las marcas de pintura en las casas, ojo."},
                {"de": "Grupo «Morro Unido»", "hora": "ayer 20:45", "texto": "Reenviado: nos sacan a todos. Pasen la voz."},
                {"de": "Comadre Nena", "hora": "hoy 06:50", "texto": "Reenviado, dicen que es seguro."}]},
            {"pregunta": "Pedro dice que lo vio en una publicación. ¿Cuál es la más antigua?", "opciones": [
                {"de": "Foto de la obra (vecino)", "hora": "ayer 15:10", "texto": "Máquinas en la ladera. No sé para qué es."},
                {"de": "@morro_denuncia", "hora": "ayer 18:00", "texto": "La foto de la obra ¡es un desalojo! (sin prueba)"},
                {"de": "Radio de pasillo", "hora": "ayer 23:30", "texto": "Reenviado: ya hay lista de casas."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: el aviso de la obra", "detalle": "El cartel oficial y el oficio de la alcaldía dicen lo mismo que el rumor."},
            "f": {"titulo": "Origen: una foto sin contexto", "detalle": "Una foto de maquinaria que alguien explicó mal. El cartel de la obra habla de otra cosa."}},
    },
    {
        "id": "r_estacion", "temas": ["dinero"], "misiones": ["periodista_estacao"],
        "intro": "Todos comentan: «{rumor}». Antes de publicarlo, rastrea de dónde viene.",
        "hops": [
            {"pregunta": "Un colega te pasó la captura. ¿De dónde la sacó?", "opciones": [
                {"de": "Boletería de la estación", "hora": "hoy 07:00", "texto": "Foto del aviso pegado en la ventanilla."},
                {"de": "Grupo «Los del teleférico»", "hora": "hoy 09:30", "texto": "Reenviado: lo vi por ahí, creo."},
                {"de": "Marquitos", "hora": "hoy 10:05", "texto": "Reenviado con carita de enojo."}]},
            {"pregunta": "La foto del aviso: ¿quién la tomó primero?", "opciones": [
                {"de": "Usuaria frecuente (Clara)", "hora": "hoy 06:55", "texto": "Foto original, con el sello visible."},
                {"de": "Página «Tarifa Justa»", "hora": "hoy 08:20", "texto": "Foto recortada (sin el sello)."},
                {"de": "Chat «Barrio Alto»", "hora": "hoy 09:00", "texto": "Reenviado de la página."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: el aviso de la empresa", "detalle": "El aviso tiene sello, firma y fecha de vigencia. Coincide con el rumor."},
            "f": {"titulo": "Origen: una foto recortada", "detalle": "Alguien recortó el aviso y quitó la parte que lo desmiente."}},
    },
    {
        "id": "r_licitacion", "temas": ["politica", "dinero"], "misiones": ["candidato_varzea", "candidato_oficina"],
        "intro": "En la calle se comenta: «{rumor}». ¿De quién salió?",
        "hops": [
            {"pregunta": "Un vecino te mostró su teléfono. ¿Quién se lo mandó?", "opciones": [
                {"de": "Secretaría de obras (boletín)", "hora": "ayer 10:00", "texto": "Boletín con número de expediente."},
                {"de": "Grupo «Deportes del Barrio»", "hora": "ayer 14:30", "texto": "Mira esto que sacaron (sin enlace)."},
                {"de": "Don Chico", "hora": "hoy 07:10", "texto": "Reenviado. Dicen que es cierto."}]},
            {"pregunta": "El boletín cita un documento. ¿Cuál fue el primero en circular?", "opciones": [
                {"de": "Diario oficial (copia sellada)", "hora": "ayer 09:00", "texto": "Publicación con fecha, monto y firma."},
                {"de": "Blog del barrio", "hora": "ayer 12:00", "texto": "Resumen del diario oficial."},
                {"de": "Cuenta «Opina ya»", "hora": "ayer 16:20", "texto": "Reenviado del blog, con opinión."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: el documento oficial", "detalle": "Tiene sello, fecha y firma. El dato del rumor está tal cual en el documento."},
            "f": {"titulo": "Origen: alguien lo inventó", "detalle": "El documento que citan no existe; nadie pudo mostrarlo."}},
    },
    {
        "id": "r_general", "temas": ["general", "evento", "estafa", "datos", "salud", "seguridad", "dinero", "politica", "imagen"], "misiones": [],
        "intro": "Te llega esto: «{rumor}». Sigue la cadena de reenvíos hasta el primero que lo dijo.",
        "hops": [
            {"pregunta": "Quien te lo pasó dice que lo vio en otro grupo. ¿Cuál es el más antiguo?", "opciones": [
                {"de": "Chat «Vecinos de {lugar}»", "hora": "ayer 18:20", "texto": "Alguien que estuvo allí lo cuenta con detalles."},
                {"de": "Grupo «Todo el barrio»", "hora": "ayer 21:40", "texto": "Reenviado. No sé quién lo escribió."},
                {"de": "Cadena «Pásalo ya»", "hora": "hoy 07:00", "texto": "Reenviado muchas veces."}]},
            {"pregunta": "Esa persona lo escuchó de alguien más. ¿Cuál mensaje salió primero?", "opciones": [
                {"de": "Mensaje de voz de Nando", "hora": "ayer 17:00", "texto": "Lo vio con sus propios ojos y da la hora."},
                {"de": "Captura de pantalla (sin nombre)", "hora": "ayer 19:45", "texto": "Recortada, sin fecha ni autor."},
                {"de": "Pariente lejano", "hora": "ayer 23:00", "texto": "Reenviado con muchos signos de exclamación."}]},
        ],
        "origen": {
            "v": {"titulo": "Origen: alguien que lo vio", "detalle": "Tiene nombre, hora y lugar; coincide con lo que se ve en {lugar}."},
            "f": {"titulo": "Origen: nadie lo vio", "detalle": "No hay un testigo: es un mensaje anónimo que se fue copiando."}},
    },
]

# =====================================================================================================================
# 2. COMPARAR DOS VERSIONES. `lineas`: {"e": etiqueta, "o": lo que dice el original, "c": lo que dice la copia (SOLO si el rumor es
# falso: es la línea alterada)}. Con un rumor verdadero la copia es igual al original (la salida correcta es «son iguales»).
# =====================================================================================================================
COMPARAR = [
    {
        "id": "c_radio", "temas": ["imagen", "dinero"], "misiones": ["periodista_radio"],
        "titulo": "Un audio que circula",
        "original": "Registro de la radio (lo que se leyó al aire)", "copia": "Transcripción que circula en el chat",
        "lineas": [
            {"e": "Programa", "o": "Mañanas del barrio"},
            {"e": "Tema", "o": "Calendario de pago de la tasa de basura", "c": "Subida del impuesto predial"},
            {"e": "Fecha citada", "o": "Vence el día 30"},
            {"e": "Efecto", "o": "Sin cambios de valor", "c": "Sube el próximo mes"},
            {"e": "Quién habla", "o": "Locutora de la emisora", "c": "Una voz que no es de la emisora"},
            {"e": "Cierre", "o": "Más información en la ventanilla"},
        ],
    },
    {
        "id": "c_teleferico", "temas": ["seguridad", "evento"], "misiones": ["ciudadano_teleferico"],
        "titulo": "Un cartel de la boletería",
        "original": "El cartel pegado en la boletería", "copia": "La foto del cartel que circula",
        "lineas": [
            {"e": "Estado", "o": "Cerrado por mantenimiento", "c": "Cerrado de forma definitiva"},
            {"e": "Cuándo", "o": "Solo el martes", "c": "A partir de hoy"},
            {"e": "Reabre", "o": "El miércoles a las 7:00", "c": "No reabre"},
            {"e": "Las cabinas", "o": "Siguen en la estación", "c": "Las retirarán"},
            {"e": "Firma", "o": "Administración de la estación"},
        ],
    },
    {
        "id": "c_taller", "temas": ["seguridad", "imagen"], "misiones": ["generica_oficina"],
        "titulo": "Una foto del taller",
        "original": "La foto del taller tomada ayer", "copia": "La foto que circula con el rumor",
        "lineas": [
            {"e": "Hora de la foto", "o": "Ayer, 18:05 (con luz de día)", "c": "Anoche, 02:30"},
            {"e": "Persiana", "o": "Cerrada con candado", "c": "Forzada, a medio abrir"},
            {"e": "Tablero de herramientas", "o": "Completo", "c": "Vacío"},
            {"e": "La calle", "o": "Esquina del taller"},
            {"e": "Personas", "o": "Nadie en la foto", "c": "Dos siluetas con bolsas"},
        ],
    },
    {
        "id": "c_organico", "temas": ["dinero"], "misiones": ["generica_feira_ladeira"],
        "titulo": "Etiquetas de un puesto de la feria",
        "original": "La etiqueta del puesto (foto de hoy)", "copia": "La etiqueta que se ve en la publicación",
        "lineas": [
            {"e": "Letrero", "o": "Frutas de la huerta", "c": "Frutas orgánicas certificadas"},
            {"e": "Precio por kilo", "o": "Igual que los puestos vecinos", "c": "El triple que los vecinos"},
            {"e": "Producto", "o": "Fruta común"},
            {"e": "Sello", "o": "Sin sello de certificación", "c": "Sello de certificación"},
            {"e": "Vendedora", "o": "Puesto 14"},
        ],
    },
    {
        "id": "c_milagro", "temas": ["imagen", "salud"], "misiones": ["periodista_igreja"],
        "titulo": "Un video dentro de la iglesia",
        "original": "Lo que se ve al pasar por la nave", "copia": "El video que circula",
        "lineas": [
            {"e": "Motivo", "o": "Rodaje de una telenovela", "c": "Una curación sin explicación médica"},
            {"e": "Aviso en la puerta", "o": "«Rodaje en curso»", "c": "No se ve ningún aviso"},
            {"e": "Quiénes están", "o": "Equipo de cámaras y luces", "c": "Solo fieles rezando"},
            {"e": "Sonido", "o": "Voces del equipo: «¡corten!»", "c": "Música solemne añadida"},
            {"e": "Lugar", "o": "La nave de la iglesia"},
        ],
    },
    {
        "id": "c_lista", "temas": ["imagen", "politica"], "misiones": ["periodista_escola"],
        "titulo": "Una lista que circula",
        "original": "El tablón de la escuela", "copia": "La foto que circula en el chat",
        "lineas": [
            {"e": "Título", "o": "Calendario escolar", "c": "Lista de alumnos reprobados"},
            {"e": "Contenido", "o": "Fechas de exámenes y feriados", "c": "Nombres y notas"},
            {"e": "Notas", "o": "Se entregan en sobre cerrado"},
            {"e": "Sello", "o": "Sello de la dirección", "c": "Sin ningún sello"},
            {"e": "Lugar", "o": "Tablón del pasillo"},
        ],
    },
    {
        "id": "c_suero", "temas": ["salud"], "misiones": ["influencer_posto"],
        "titulo": "Un afiche del puesto de salud",
        "original": "El afiche original del puesto", "copia": "La imagen que usa el reto en redes",
        "lineas": [
            {"e": "Recomendación", "o": "Suero de sobre, preparado como indica", "c": "Suero casero, mezcla en casa"},
            {"e": "Advertencia", "o": "No uses mezclas caseras", "c": "(la advertencia no aparece)"},
            {"e": "Quién lo firma", "o": "Puesto de salud"},
            {"e": "Cuándo acudir", "o": "Si hay fiebre, ve al puesto"},
        ],
    },
    {
        "id": "c_volante", "temas": ["politica", "estafa"], "misiones": ["candidato_igreja"],
        "titulo": "Un volante de la parroquia",
        "original": "El volante en el atrio", "copia": "El volante que circula en las redes",
        "lineas": [
            {"e": "Título", "o": "Bolsa de empleo parroquial", "c": "Empleo para quienes voten por el candidato"},
            {"e": "A quién va", "o": "Abierta a todo vecino", "c": "Solo a quienes confirmen su voto"},
            {"e": "Quién convoca", "o": "La parroquia"},
            {"e": "Condición", "o": "Ninguna", "c": "Mostrar el comprobante de voto"},
        ],
    },
    {
        "id": "c_general", "temas": ["general", "evento", "dinero", "estafa", "datos", "salud", "seguridad"], "misiones": [],
        "titulo": "Un cartel que se volvió viral",
        "original": "El cartel tal como está en {lugar}", "copia": "La imagen que circula en el chat",
        "lineas": [
            {"e": "Título", "o": "Aviso a los vecinos"},
            {"e": "Día", "o": "El sábado", "c": "Hoy mismo"},
            {"e": "Hora", "o": "A las 10:00", "c": "A las 22:00"},
            {"e": "Costo", "o": "Gratis", "c": "R$ 50 por persona"},
            {"e": "Firma", "o": "Con sello del lugar", "c": "Sin firma"},
        ],
    },
]

# =====================================================================================================================
# 3. ORDENAR LA CADENA. `items` YA están en el orden cronológico correcto (el primero es el que empezó); la lógica los baraja.
# `hora` es opcional (si falta, hay que deducirlo del texto). `cierre`: frase al terminar según la veracidad.
# =====================================================================================================================
CRONOLOGIA = [
    {
        "id": "k_concierto", "temas": ["evento"], "misiones": ["ciudadano_praca"],
        "titulo": "El concierto que nadie sabe quién anunció",
        "intro": "Todos repiten: «{rumor}». Ordena los mensajes de lo primero que se dijo a lo último.",
        "items": [
            {"quien": {"v": "Cultura municipal (aviso)", "f": "Cuenta nueva sin foto"},
             "texto": {"v": "Se aprobó el permiso para el concierto del viernes en la plaza.", "f": "Dicen que habrá concierto el viernes, no sé dónde."},
             "hora": "lunes 09:10"},
            {"quien": "Radio del barrio", "texto": "Confirmaron el escenario junto a la fuente.", "hora": "lunes 12:30"},
            {"quien": "Tía Rosa", "texto": "Mi vecina lo escuchó en la radio y me avisó.", "hora": None},
            {"quien": "Grupo «Vecinos de la Sé»", "texto": "Reenviado: el viernes todos a la plaza. ¡Pásalo!", "hora": "martes 08:00"},
            {"quien": "Beto", "texto": "Ya lo vieron cientos de personas. ¿Alguien lo confirmó?", "hora": "martes 18:45"},
        ],
        "cierre": {"v": "El anuncio salió de la oficina de cultura y se fue repitiendo.", "f": "Nadie encontró el anuncio original: se fue repitiendo solo."},
    },
    {
        "id": "k_rodoviaria", "temas": ["evento", "servicios"], "misiones": ["generica_rodoviaria", "influencer_samba"],
        "titulo": "Los nuevos horarios",
        "intro": "Circula esto: «{rumor}». Ordena la cadena para ver cómo se fue contando.",
        "items": [
            {"quien": {"v": "Tablero de la terminal", "f": "Mensaje anónimo"},
             "texto": {"v": "Desde esta semana, salidas a las 6:00 y a las 18:00.", "f": "Cambian los horarios, creo que algo así."},
             "hora": "domingo 20:00"},
            {"quien": "Conductora Lía", "texto": "Confirmo el horario nuevo, lo vi en el tablero.", "hora": "lunes 06:30"},
            {"quien": "Chat «Viajeros»", "texto": "Reenviado: ¡atentos al horario nuevo!", "hora": None},
            {"quien": "Grupo «Familia Costa»", "texto": "Mañana salgo temprano, ya vi el cambio que mandaron.", "hora": "lunes 21:15"},
            {"quien": "Don Ernesto", "texto": "Fui a la terminal, nadie sabe nada. ¿Quién lo dijo?", "hora": "martes 07:20"},
        ],
        "cierre": {"v": "El tablero oficial fue lo primero; lo demás lo fue repitiendo.", "f": "El primer mensaje era anónimo y los demás lo repitieron sin comprobarlo."},
    },
    {
        "id": "k_escuela", "temas": ["evento"], "misiones": ["generica_escola"],
        "titulo": "¿Hay clases mañana?",
        "intro": "Todos preguntan: «{rumor}». Ordénalo para ver de dónde salió.",
        "items": [
            {"quien": {"v": "Dirección de la escuela", "f": "Mensaje sin firma"},
             "texto": {"v": "Mañana habrá jornada de formación docente: no hay clases.", "f": "Dicen que mañana no hay clases."},
             "hora": "jueves 14:00"},
            {"quien": "Profe Marta", "texto": "Confirmado en el portón: aviso pegado desde el mediodía.", "hora": "jueves 15:20"},
            {"quien": "Mamás de 4.º", "texto": "Reenviado: ¡mañana no hay clases!", "hora": None},
            {"quien": "Grupo «Padres Unidos»", "texto": "Gracias por avisar, ya organicé con mi hermana.", "hora": "jueves 19:00"},
            {"quien": "Nacho (alumno)", "texto": "Mi mamá dice que sí hay clases. ¿Quién tiene razón?", "hora": "jueves 21:30"},
        ],
        "cierre": {"v": "El aviso de la dirección estaba en el portón desde el primer momento.", "f": "Nadie mostró el aviso original."},
    },
    {
        "id": "k_feira", "temas": ["evento", "comercio"], "misiones": ["generica_feira", "ciudadano_feira", "generica_feira_turno"],
        "titulo": "La feria del fin de semana",
        "intro": "En el chat dicen: «{rumor}». Pon los mensajes en el orden en que aparecieron.",
        "items": [
            {"quien": {"v": "Aviso sellado en el poste", "f": "Audio sin autor"},
             "texto": {"v": "Inscripción abierta; el sorteo y la feria están en el aviso.", "f": "Se rumorea cambio de fecha de la feria."},
             "hora": "miércoles 10:00"},
            {"quien": "Puesto 3 (Doña Cleo)", "texto": "Ya me anoté, la lista está en el poste.", "hora": "miércoles 13:30"},
            {"quien": "Grupo «Feirantes»", "texto": "Pásenlo: lo dijo la organización.", "hora": None},
            {"quien": "Hijo de Cleo", "texto": "Subí la foto de la lista a las redes.", "hora": "jueves 09:00"},
            {"quien": "Cuenta «Todo Bonfim»", "texto": "Reenvío: todos al evento, ¡no falten!", "hora": "jueves 17:00"},
        ],
        "cierre": {"v": "El aviso con sello fue lo primero; lo demás lo repitió.", "f": "No había aviso: empezó como un audio sin autor."},
    },
    {
        "id": "k_panaderia", "temas": ["comercio", "evento", "dinero"], "misiones": ["ciudadano_padaria", "influencer_padaria"],
        "titulo": "La oferta de la panadería",
        "intro": "Corre la voz: «{rumor}». ¿Cómo se fue pasando?",
        "items": [
            {"quien": {"v": "Cartel de la vitrina", "f": "Publicación sin fecha"},
             "texto": {"v": "Oferta de hoy, con la fecha en el cartel.", "f": "Oferta increíble, ven ya."},
             "hora": "sábado 07:00"},
            {"quien": "Panadero Ito", "texto": "Sí, la oferta es de hoy, ven antes del mediodía.", "hora": "sábado 08:10"},
            {"quien": "Vecina Gloria", "texto": "Subí una foto del cartel al chat.", "hora": None},
            {"quien": "Grupo «Compras del barrio»", "texto": "Reenviado: ¡todos a la panadería!", "hora": "sábado 10:30"},
            {"quien": "Mari", "texto": "Fui a las 4 y ya no había nada. ¿Hasta cuándo era?", "hora": "sábado 16:00"},
        ],
        "cierre": {"v": "El cartel de la vitrina tenía fecha: por eso se pudo confirmar.", "f": "El mensaje original no tenía fecha ni autor."},
    },
    {
        "id": "k_general", "temas": ["general", "evento", "politica", "datos", "estafa", "salud", "seguridad", "dinero", "imagen"], "misiones": [],
        "titulo": "Cómo se fue regando",
        "intro": "Circula: «{rumor}». Ordena los mensajes desde el primero hasta el último.",
        "items": [
            {"quien": {"v": "Un testigo con nombre", "f": "Cuenta sin nombre"},
             "texto": {"v": "Lo vi hoy en {lugar}, con fecha y hora.", "f": "Dicen que pasó algo en {lugar}."},
             "hora": "ayer 11:00"},
            {"quien": "Vecina de al lado", "texto": "Mi marido lo vio también, me lo contó.", "hora": None},
            {"quien": "Grupo «Barrio al día»", "texto": "Reenviado: pásalo a tus contactos.", "hora": "ayer 15:30"},
            {"quien": "Pariente de Ana", "texto": "Mira lo que me llegó. ¿Será cierto?", "hora": "ayer 20:00"},
            {"quien": "Cadena", "texto": "Reenviado muchas veces. Ya lo vieron cientos de personas.", "hora": "hoy 07:00"},
        ],
        "cierre": {"v": "Había un testigo con nombre al inicio.", "f": "Al inicio no había nadie con nombre: se fue repitiendo."},
    },
]

# =====================================================================================================================
# 4. CHAT DEL BARRIO. `turnos`: mensaje de un amigo/grupo y 3 respuestas con `valor` (2 = protege y ayuda, 1 = a medias, 0 =
# regala un dato de otra persona). `segundos`: tiempo para responder (si se acaba, «te quedas en visto» vale 1). `reaccion`:
# lo que contesta el chat. El dilema: ceder a la presión del grupo o proteger a un amigo.
# =====================================================================================================================
CHAT = [
    {
        "id": "h_mutirao", "temas": ["datos"], "misiones": ["generica_mutirao"],
        "titulo": "Chat «Mutirão da calle»", "amigo": "Dani",
        "intro": "Los organizadores del mutirão piden datos a cada vecino. Dani te cuenta que le pidieron su número de cuenta.",
        "turnos": [
            {"de": "Marcela (organizadora)", "texto": "Para anotarlos necesito el número de cuenta de cada vecino. ¿Me das el tuyo?", "segundos": 20, "opciones": [
                {"texto": "Primero dime para qué lo necesitas y dónde está escrito.", "valor": 2, "reaccion": "Marcela: «Eh... era solo para el registro»."},
                {"texto": "Te lo paso en privado.", "valor": 0, "reaccion": "Marcela: «¡Gracias! Pásamelo ya»."},
                {"texto": "Luego te contesto.", "valor": 1, "reaccion": "Marcela: «No tardes, se cierra hoy»."}]},
            {"de": "Marcela (organizadora)", "texto": "Y el de Dani, que no me contesta. ¿Me pasas su número de cuenta, que lo conoces?", "segundos": 15, "opciones": [
                {"texto": "Eso se lo tienes que pedir a Dani, no a mí.", "valor": 2, "reaccion": "Marcela: «Está bien, qué difícil».", },
                {"texto": "Es 4455-0021, pero no lo repitas.", "valor": 0, "reaccion": "Marcela: «Ya lo tengo, gracias»."},
                {"texto": "No sé, creo que lo tiene su hijo.", "valor": 1, "reaccion": "Marcela: «¿Y su hijo cuál es?»."}]},
            {"de": "Vecina Gloria", "texto": "Si no dan los datos, los tachan de la lista. ¿Todos de acuerdo?", "segundos": 20, "opciones": [
                {"texto": "En las planillas solo piden nombre y calle. Para eso no hace falta cuenta.", "valor": 2, "reaccion": "Gloria: «Cierto, no lo había pensado»."},
                {"texto": "Que cada uno decida qué datos da.", "valor": 1, "reaccion": "Gloria: «Hmm, bueno»."},
                {"texto": "Sí, que todos los den para evitar problemas.", "valor": 0, "reaccion": "Gloria: «Perfecto, lo anoto»."}]},
        ],
    },
    {
        "id": "h_lanhouse", "temas": ["datos", "estafa"], "misiones": ["generica_lanhouse"],
        "titulo": "Chat «Los de la lan house»", "amigo": "Nico",
        "intro": "Dicen que la lan house exige documento y teléfono para el wifi. Tu amigo Nico ya se los dio.",
        "turnos": [
            {"de": "Lucas", "texto": "Mándame la foto de tu documento y tu teléfono y te doy la clave del wifi.", "segundos": 18, "opciones": [
                {"texto": "No mando documentos por el chat. ¿Hay algún cartel que lo pida?", "valor": 2, "reaccion": "Lucas: «Bueno... no».", },
                {"texto": "Te mando solo el teléfono.", "valor": 1, "reaccion": "Lucas: «Y el documento también»."},
                {"texto": "Ahí va la foto del documento.", "valor": 0, "reaccion": "Lucas: «Gracias, ya te tengo»."}]},
            {"de": "Lucas", "texto": "Mejor dame el teléfono de Nico, que ya dijo que sí. Así lo confirmo.", "segundos": 15, "opciones": [
                {"texto": "Pregúntale a él directamente. Yo no paso datos de otros.", "valor": 2, "reaccion": "Lucas: «Ya, ya»."},
                {"texto": "Es 11 9876-5432.", "valor": 0, "reaccion": "Lucas: «Anotado»."},
                {"texto": "Se lo pregunto yo y te aviso.", "valor": 1, "reaccion": "Lucas: «Dale, rapidito»."}]},
            {"de": "Chat del barrio", "texto": "Si no dan los datos, no hay wifi. Es solo un trámite, no sean aguafiestas.", "segundos": 20, "opciones": [
                {"texto": "Vi que nadie anota nada: la clave se pide al mostrador.", "valor": 2, "reaccion": "Chat: «¿En serio? Voy a ver»."},
                {"texto": "Voy a ver qué hacer.", "valor": 1, "reaccion": "Chat: «Bueno, avísanos»."},
                {"texto": "Tienen razón, lo doy.", "valor": 0, "reaccion": "Chat: «¡Así se habla!»."}]},
        ],
    },
    {
        "id": "h_bar", "temas": ["datos", "dinero", "seguridad"], "misiones": ["generica_bar", "influencer_bar"],
        "titulo": "Chat «Amigos del bar»", "amigo": "Tito",
        "intro": "Dicen que el bar cobra una cuota por «seguridad». Tito te pide que lo cubras en el chat.",
        "turnos": [
            {"de": "Tito", "texto": "Si alguien pregunta, di que ya pagué la cuota. No quiero problemas.", "segundos": 18, "opciones": [
                {"texto": "No voy a decir eso si no es verdad; mejor lo aclaramos.", "valor": 2, "reaccion": "Tito: «Uf, bueno»."},
                {"texto": "Por esta vez lo hago.", "valor": 0, "reaccion": "Tito: «Gracias, eres mi mejor amigo»."},
                {"texto": "No sé nada, que pregunten.", "valor": 1, "reaccion": "Tito: «Gracias»."}]},
            {"de": "Beatriz (grupo)", "texto": "¿Alguien tiene el teléfono del dueño o el de Tito para preguntar de la cuota?", "segundos": 15, "opciones": [
                {"texto": "Pregunten en la barra; yo no doy teléfonos de otros.", "valor": 2, "reaccion": "Beatriz: «Tiene sentido»."},
                {"texto": "Tengo el de Tito, ahí va.", "valor": 0, "reaccion": "Beatriz: «Gracias, lo llamo»."},
                {"texto": "Preguntaré yo y les cuento.", "valor": 1, "reaccion": "Beatriz: «Bueno»."}]},
            {"de": "Beatriz (grupo)", "texto": "Estaba el guardia. Dijo que es un «aporte voluntario». ¿Alguien lo vio escrito?", "segundos": 20, "opciones": [
                {"texto": "Sí: había una alcancía rotulada «aporte voluntario para el torneo».", "valor": 2, "reaccion": "Beatriz: «Entonces nadie está obligado»."},
                {"texto": "No sé, creo que sí.", "valor": 1, "reaccion": "Beatriz: «¿Creo? Hmm»."},
                {"texto": "Es una cuota obligatoria, seguro.", "valor": 0, "reaccion": "Beatriz: «Ay, qué abuso»."}]},
        ],
    },
    {
        "id": "h_parroquia", "temas": ["datos", "dinero"], "misiones": ["generica_igreja"],
        "titulo": "Chat «Comunidad parroquial»", "amigo": "Padre Julián",
        "intro": "La parroquia publicó una cuenta para reparar el techo. Hay gente que te pide más datos de los necesarios.",
        "turnos": [
            {"de": {"v": "Comisión del techo", "f": "Cuenta @ayuda_techo"},
             "texto": {"v": "Pueden aportar a la cuenta a nombre de la parroquia, la del cartel.", "f": "Pásame tu documento para darte el número de cuenta a donde aportar."},
             "segundos": 20, "opciones": [
                {"texto": {"v": "Compruebo el nombre de la cuenta en el cartel de la iglesia y aporto.", "f": "El número de cuenta debe estar en el cartel, no por privado."}, "valor": 2, "reaccion": "Chat: «Bien visto»."},
                {"texto": "Aporto sin mirar nada más.", "valor": 1, "reaccion": "Chat: «Gracias por apoyar»."},
                {"texto": "Les mando mi documento sin más.", "valor": 0, "reaccion": "Chat: «Perfecto, registrado»."}]},
            {"de": "Chat de la comunidad", "texto": "Pásame el teléfono de Julián, el tesorero, para mandarle comprobantes.", "segundos": 15, "opciones": [
                {"texto": "Que me lo pida él y se lo doy; o mejor, pregunten en la sacristía.", "valor": 2, "reaccion": "Chat: «Mejor así»."},
                {"texto": "Aquí lo tienes: 11 9123-4567.", "valor": 0, "reaccion": "Chat: «Gracias»."},
                {"texto": "Ahorita se lo pregunto.", "valor": 1, "reaccion": "Chat: «Avísame»."}]},
            {"de": "Chat de la comunidad", "texto": "¿Compartimos el cartel con el número a todos los grupos?", "segundos": 20, "opciones": [
                {"texto": "Sí, pero solo la foto del cartel con el nombre de la parroquia.", "valor": 2, "reaccion": "Chat: «Hecho»."},
                {"texto": "Mejor esperen a confirmarlo.", "valor": 1, "reaccion": "Chat: «Ok»."},
                {"texto": "Sí, con los teléfonos de los tesoreros.", "valor": 0, "reaccion": "Chat: «Eso ya está mandado»."}]},
        ],
    },
    {
        "id": "h_general", "temas": ["general", "dinero", "evento", "salud", "seguridad", "politica", "estafa", "imagen"], "misiones": [],
        "titulo": "Chat «Barrio unido»", "amigo": "Pablo",
        "intro": "Circula: «{rumor}». Tu amigo Pablo está en el grupo y la gente te presiona.",
        "turnos": [
            {"de": "Mauro (grupo)", "texto": "¡Reenvíalo ya a todos tus contactos! Cuanto antes mejor.", "segundos": 15, "opciones": [
                {"texto": "Antes de reenviar, ¿quién lo dijo primero?", "valor": 2, "reaccion": "Mauro: «Ay, pero se enfría»."},
                {"texto": "Lo reenvío a un par de grupos.", "valor": 1, "reaccion": "Mauro: «Mejor que nada»."},
                {"texto": "Listo, ya lo mandé a todos.", "valor": 0, "reaccion": "Mauro: «¡Genial!»."}]},
            {"de": "Mauro (grupo)", "texto": "Pásame el teléfono de Pablo, que sabe más de esto.", "segundos": 15, "opciones": [
                {"texto": "Pregúntale a él por aquí; yo no paso su teléfono.", "valor": 2, "reaccion": "Mauro: «Mmm. Bueno»."},
                {"texto": "Es 11 9555-1234.", "valor": 0, "reaccion": "Mauro: «Lo llamo»."},
                {"texto": "Se lo digo yo.", "valor": 1, "reaccion": "Mauro: «Apúrate»."}]},
            {"de": "Chat del barrio", "texto": "Si no lo compartes eres cómplice. ¿De qué lado estás?", "segundos": 20, "opciones": [
                {"texto": "Del lado de comprobarlo en {lugar} antes de decir nada.", "valor": 2, "reaccion": "Chat: «Tiene razón»."},
                {"texto": "Prefiero no meterme.", "valor": 1, "reaccion": "Chat: «Cobarde»."},
                {"texto": "Del suyo, claro. Lo comparto.", "valor": 0, "reaccion": "Chat: «¡Eso!»."}]},
        ],
    },
]

# =====================================================================================================================
# 5. SEÑALES DE EDICIÓN EN UNA CAPTURA. `zonas`: cada fila de la captura. `falla: True` = señal de edición o engaño (solo cuenta si el
# rumor es falso); `texto_ok`: cómo se ve la fila si la captura es auténtica (rumor verdadero). `lupa`: lo que se ve al pasar el
# cursor (describe la zona sin delatar); `explica`: lo que se aprende al terminar.
# =====================================================================================================================
SENALES = [
    {
        "id": "s_cadena", "temas": ["estafa"], "misiones": ["generica_corrente"],
        "titulo": "Una cadena de «premios»", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "@premios_plaza_oficial", "lupa": "Nombre de la cuenta que lo envía", "falla": True,
             "explica": "Cuenta creada hace dos días, con el nombre «oficial» pero sin ningún dato de la parroquia."},
            {"id": "z2", "texto": "Reenvía a 10 contactos y ganas un premio", "lupa": "Pide algo a cambio", "falla": True,
             "explica": "Un premio a cambio de reenviar es el mecanismo clásico de una cadena."},
            {"id": "z3", "texto": "Hoy 25:70", "lupa": "La hora del mensaje", "falla": True,
             "explica": "La hora no existe: no hay 25:70. Alguien editó la captura."},
            {"id": "z4", "texto": "Retira tu premio en la plaza este sábado", "lupa": "El lugar y el día del premio", "falla": False,
             "explica": "Un dato concreto, pero por sí solo no dice nada."},
            {"id": "z5", "texto": "Foto de perfil: logo con globos", "lupa": "La foto de la cuenta", "falla": False,
             "explica": "Un logo cualquiera no prueba nada."},
            {"id": "z6", "texto": "Escribiendo...", "lupa": "El indicador de escritura", "falla": False,
             "explica": "Aparece en capturas reales."},
        ],
    },
    {
        "id": "s_cupon", "temas": ["estafa", "dinero"], "misiones": ["generica_supermercado"],
        "titulo": "Un cupón de descuento", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "CUPON 80 % DE DESCUENTO EN TODA LA COMPRA", "lupa": "El titular del cupón", "falla": True,
             "explica": "Un 80 % en toda la compra no lo ofrece ningún supermercado; los carteles del local hablan de 10 y 20 %."},
            {"id": "z2", "texto": "Super Dois Irmaos (la «a» no está)", "lupa": "El nombre del comercio", "falla": True,
             "explica": "El nombre está mal escrito: el comercio es «Dois Irmãos»."},
            {"id": "z3", "texto": "Válido hasta: ayer", "lupa": "La fecha de vencimiento", "falla": True,
             "explica": "Dice «ayer»: el cupón no podría usarse el fin de semana."},
            {"id": "z4", "texto": "Código de barras", "lupa": "Código impreso en el cupón", "falla": False,
             "explica": "Un código no dice si es real."},
            {"id": "z5", "texto": "Sin límite de uso", "lupa": "Condiciones al pie", "falla": False,
             "explica": "Es raro, pero no es prueba por sí mismo."},
            {"id": "z6", "texto": "Compártelo con 5 amigos", "lupa": "Pide algo más", "falla": False,
             "explica": "Sospechoso, aunque no es la señal más clara."},
        ],
    },
    {
        "id": "s_tarifa", "temas": ["dinero"], "misiones": ["generica_mototaxi"],
        "titulo": "Una captura de recibos", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Recibo de carrera: R$ 36", "lupa": "El monto del recibo", "falla": True,
             "explica": "El precio es el triple del cartel de tarifas, que no cambió."},
            {"id": "z2", "texto": "Fecha: 31/02", "lupa": "La fecha del recibo", "falla": True,
             "explica": "El 31 de febrero no existe."},
            {"id": "z3", "texto": "Letras de dos tamaños distintos en la misma línea", "lupa": "La tipografía del encabezado", "falla": True,
             "explica": "Dos tipos de letra en una línea delatan un texto pegado encima."},
            {"id": "z4", "texto": "Ruta: entrada del barrio", "lupa": "Origen de la carrera", "falla": False,
             "explica": "Un dato normal."},
            {"id": "z5", "texto": "Firma del conductor", "lupa": "La firma al pie", "falla": False,
             "explica": "Una firma suelta no prueba nada."},
            {"id": "z6", "texto": "Número de placa", "lupa": "Placa del vehículo", "falla": False,
             "explica": "Un dato normal."},
        ],
    },
    {
        "id": "s_encuesta", "temas": ["politica", "estafa"], "misiones": ["candidato_salao"],
        "titulo": "Una encuesta «cerrada»", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Ganó el candidato X: ya no hace falta votar", "lupa": "El titular", "falla": True,
             "explica": "Ninguna encuesta decide una elección, y siempre hay que votar."},
            {"id": "z2", "texto": "Encuesta de 12 personas", "lupa": "A cuánta gente preguntaron", "falla": True,
             "explica": "Doce personas no representan a un barrio entero."},
            {"id": "z3", "texto": "Gráfico con una barra que pasa del 100 %", "lupa": "El gráfico de resultados", "falla": True,
             "explica": "Un gráfico con más del 100 % es falso."},
            {"id": "z4", "texto": "Logo del instituto de encuestas", "lupa": "El logo", "falla": False,
             "explica": "Un logo se copia fácilmente."},
            {"id": "z5", "texto": "Fecha de votación en el pie", "lupa": "El pie de la imagen", "falla": False,
             "explica": "Coincide con la fecha real."},
            {"id": "z6", "texto": "Compártelo antes de que lo borren", "lupa": "Pide algo más", "falla": False,
             "explica": "Sospechoso, aunque no es la señal más clara."},
        ],
    },
    {
        "id": "s_luces", "temas": ["seguridad", "imagen"], "misiones": ["generica_mirante", "generica_salao"],
        "titulo": "Una foto de luces extrañas", "max_marcas": 3,
        "zonas": [
            {"id": "z1", "texto": "Luces sobre la ciudad", "lupa": "El cielo de la foto", "falla": True,
             "explica": "Las luces son de fuegos artificiales; el afiche de la comparsa lo decía."},
            {"id": "z2", "texto": "Fecha de la foto: anoche, 22:00", "lupa": "El dato de la foto", "falla": False,
             "explica": "Coincide con el horario de los fuegos."},
            {"id": "z3", "texto": "Pie: «NO eran aviones»", "lupa": "El texto añadido", "falla": True,
             "explica": "Un pie escrito encima de la foto no es una prueba."},
            {"id": "z4", "texto": "Marca de agua de una cuenta de «misterios»", "lupa": "La esquina de la imagen", "falla": True,
             "explica": "Esa cuenta vive de repetir misterios sin comprobarlos."},
            {"id": "z5", "texto": "Cuenta: @misterios_vivos", "lupa": "Quién la publica", "falla": False,
             "explica": "Un nombre no prueba nada."},
            {"id": "z6", "texto": "3.241 «me gusta»", "lupa": "Los «me gusta»", "falla": False,
             "explica": "Tener muchos «me gusta» no hace verdadera una foto."},
        ],
    },
]

# =====================================================================================================================
# 6. CONTRARRELOJ. La carta de la misión (su rumor real) se mezcla con estas `cartas`: «veraz» True = verdadera (dejarla pasar),
# False = falsa (hay que frenarla). `ritmo`: segundos en los que la carta se propaga por completo desde que aparece.
# =====================================================================================================================
CONTRARRELOJ = [
    {
        "id": "t_salud", "temas": ["salud"], "misiones": ["generica_santa_casa", "generica_posto"],
        "titulo": "Hora pico del chat: lo que se dice de la salud",
        "cartas": [
            {"texto": "Hay vacunas del calendario oficial gratis en el puesto de salud hasta las 5.", "veraz": True, "ritmo": 12},
            {"texto": "Un té de ajo cura la gripe en una hora: los médicos lo esconden.", "veraz": False, "ritmo": 9},
            {"texto": "Si recibes un mensaje con un enlace de «turno de vacuna», no lo abras.", "veraz": True, "ritmo": 14},
            {"texto": "Se agotaron las vacunas para toda la ciudad y no habrá más este año.", "veraz": False, "ritmo": 10},
        ],
    },
    {
        "id": "t_seguridad", "temas": ["seguridad"], "misiones": ["influencer_parque", "generica_varzea", "influencer_mirante"],
        "titulo": "Hora pico del chat: lo que pasa en la calle",
        "cartas": [
            {"texto": "La guardia cierra el paso al puente por obras, mañana de 9 a 12.", "veraz": True, "ritmo": 12},
            {"texto": "Un grupo armado recorre el barrio buscando casas con la puerta abierta.", "veraz": False, "ritmo": 8},
            {"texto": "Hubo un apagón en dos calles; la compañía ya lo reparó.", "veraz": True, "ritmo": 14},
            {"texto": "Los semáforos se apagan a las 20:00 por una orden secreta.", "veraz": False, "ritmo": 10},
        ],
    },
    {
        "id": "t_servicios", "temas": ["servicios", "evento", "general"], "misiones": ["generica_estacao_alto", "ciudadano_posto"],
        "titulo": "Hora pico del chat: lo que pasa con los servicios",
        "cartas": [
            {"texto": "El agua se corta mañana de 8 a 12 por mantenimiento (aviso oficial).", "veraz": True, "ritmo": 13},
            {"texto": "El teleférico cobrará el triple a partir de mañana, sin aviso.", "veraz": False, "ritmo": 9},
            {"texto": "Los buses de la línea 5 cambian de parada esta semana (cartel en la parada).", "veraz": True, "ritmo": 14},
            {"texto": "Todos los colegios cierran por un mes por una enfermedad que nadie nombra.", "veraz": False, "ritmo": 8},
        ],
    },
    {
        "id": "t_comercio", "temas": ["dinero", "estafa", "comercio", "datos"], "misiones": ["generica_padaria"],
        "titulo": "Hora pico del chat: lo que se compra y se vende",
        "cartas": [
            {"texto": "La feria del domingo abre a las 8 en la plaza (cartel de la organización).", "veraz": True, "ritmo": 13},
            {"texto": "Un código te da 90 % de descuento en todo si lo reenvías a 20 contactos.", "veraz": False, "ritmo": 8},
            {"texto": "El mercado cambia el horario de la tarde a partir de la semana próxima.", "veraz": True, "ritmo": 14},
            {"texto": "Todos los panaderos del barrio usan un aditivo prohibido. Pásalo.", "veraz": False, "ritmo": 9},
        ],
    },
    {
        "id": "t_general", "temas": ["general", "politica", "imagen"], "misiones": [],
        "titulo": "Hora pico del chat",
        "cartas": [
            {"texto": "El sábado habrá un mutirão de limpieza, trae guantes (aviso de la asociación).", "veraz": True, "ritmo": 13},
            {"texto": "Quien no comparta esto en 10 minutos perderá su cuenta.", "veraz": False, "ritmo": 8},
            {"texto": "El ensayo de la escola de samba es abierto, el sábado a las 8 de la noche.", "veraz": True, "ritmo": 14},
            {"texto": "Una foto muestra a la alcaldesa regalando casas; nadie sabe de dónde salió.", "veraz": False, "ritmo": 9},
        ],
    },
]

CASOS = {
    "rastrear": RASTREAR,
    "comparar": COMPARAR,
    "cronologia": CRONOLOGIA,
    "chat": CHAT,
    "senales": SENALES,
    "contrarreloj": CONTRARRELOJ,
}
