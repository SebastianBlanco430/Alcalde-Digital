# Catálogo semilla de misiones (datos puros). Tono: notificación de Civitas, con el sabor de Ciudad Nova (una favela
# de nombres brasileños) pero comprensible para quien habla español.
# Cada rol tiene al menos una misión cuyo destino NO es su lugar de inicio
# (si no, el jugador ya estaría "llegado" al aparecer). rol=None = genérica.
# Las misiones de roles que nadie juega las reparte SistemaMisiones entre los presentes,
# por eso los textos son neutros (no hablan en segunda persona del rol).
# 14 misiones: 2 por rol y 6 genéricas, entre los 11 lugares (las 7 últimas se añadieron en 2026-10; el orden importa
# porque SistemaMisiones y la reserva del online reparten en orden de catálogo).

from backend.logica.misiones import Mision

CATALOGO_MISIONES = (
    Mision(
        "ciudadano_praca", "ciudadano", "Tendencia en la Praça",
        "Civitas: algo es tendencia en la Praça da Sé. Ve y revísalo.", "Praça da Sé",
        pago=20,
    ),
    Mision(
        "periodista_prefeitura", "periodista", "Rumor en la Prefeitura",
        "Civitas: rumor sin verificar en la Prefeitura. Contrástalo.", "Prefeitura",
        pago=35,
    ),
    Mision(
        "influencer_parque", "influencer", "Publicación viral",
        "Civitas: una publicación se mueve en el Parque do Povo. Pásate.", "Parque do Povo",
        pago=30,
    ),
    Mision(
        "candidato_morro", "candidato", "Voces del morro",
        "Civitas: los vecinos del Morro da Esperança quieren ser escuchados.", "Morro da Esperança",
        pago=40,
    ),
    Mision(
        "generica_santa_casa", None, "Alerta sanitaria",
        "Civitas: circula una alerta en el Hospital Santa Casa. Verifícala.", "Hospital Santa Casa",
        pago=25,
    ),
    Mision(
        "generica_rodoviaria", None, "Cadena de mensajes",
        "Civitas: cadena sospechosa en la Rodoviária. Revísala.", "Rodoviária",
        pago=25,
    ),
    Mision(
        "generica_universidade", None, "Debate estudiantil",
        "Civitas: debate encendido en la Universidade de Ciudad Nova.", "Universidade de Ciudad Nova",
        pago=25,
    ),
    Mision(
        "periodista_radio", "periodista", "Micrófono abierto",
        "Civitas: en la Rádio Comunitária leyeron al aire un audio sin fuente. Investígalo.", "Rádio Comunitária",
        pago=30,
    ),
    Mision(
        "influencer_samba", "influencer", "Ensaio viral",
        "Civitas: un video del ensayo de la Escola de Samba se hace viral. ¿Es de este año?", "Escola de Samba",
        pago=30,
    ),
    Mision(
        "candidato_mercado", "candidato", "Precio de la feria",
        "Civitas: corre que los precios del Mercado Municipal se duplican mañana. Escucha a los comerciantes.",
        "Mercado Municipal",
        pago=35,
    ),
    Mision(
        "ciudadano_teleferico", "ciudadano", "Teleférico parado",
        "Civitas: dicen que el teleférico cierra para siempre. Pasa por la estación y averigua.",
        "Estação do Teleférico",
        pago=20,
    ),
    Mision(
        "generica_mutirao", None, "Mutirão sospechoso",
        "Civitas: piden voluntarios para un mutirão en el Morro, pero el mensaje pide datos bancarios.",
        "Morro da Esperança",
        pago=25,
    ),
    Mision(
        "generica_corrente", None, "Corrente do zap",
        "Civitas: una cadena del grupo de vecinos promete premios en la Praça da Sé. Revísala.", "Praça da Sé",
        pago=20,
    ),
    Mision(
        "generica_feira", None, "Feria de trueque",
        "Civitas: anuncian una feria de trueque con «regalos gratis» en el Parque do Povo. ¿Es real?",
        "Parque do Povo",
        pago=20,
    ),
)


# Misiones de los 13 lugares nuevos del mapa grande (backend/datos/ciudad_grande.py), una por lugar y todas genéricas
# (rol None). Verificación de rumores y desinformación en tono Civitas; el pago crece con la distancia a la Praça da Sé
# (R$20-60). NO están en CATALOGO_MISIONES: SistemaMisiones exige que cada destino exista en el mapa, y el mundo chico
# no tiene estos lugares. El mapa grande usa CATALOGO_MISIONES_GRANDE (= el catálogo de siempre + estas, al final: el
# orden importa porque SistemaMisiones y la reserva del online reparten en orden de catálogo).
MISIONES_MAPA_GRANDE = (
    Mision(
        "generica_posto", None, "Vacuna milagrosa",
        "Civitas: un audio dice que en el Posto de Saúde Vila Nova reparten una vacuna «que cura todo». Pregunta allí.",
        "Posto de Saúde Vila Nova",
        pago=30,
    ),
    Mision(
        "generica_mototaxi", None, "Tarifa fantasma",
        "Civitas: circula una captura con tarifas triples en el Ponto de Mototáxi da Entrada. ¿La hizo alguien de verdad?",
        "Ponto de Mototáxi da Entrada",
        pago=55,
    ),
    Mision(
        "generica_padaria", None, "Pan envenenado",
        "Civitas: una cadena asegura que la Padaria Pão Quente vende pan «adulterado». Habla con quien lo hornea.",
        "Padaria Pão Quente",
        pago=40,
    ),
    Mision(
        "generica_supermercado", None, "Oferta que no existe",
        "Civitas: un cupón de 80 % en el Supermercado Dois Irmãos se comparte sin parar. Comprueba si es real.",
        "Supermercado Dois Irmãos",
        pago=40,
    ),
    Mision(
        "generica_oficina", None, "Foto trucada",
        "Civitas: una foto de la Oficina do Seu Zé muestra un «robo» que nadie vio. Revisa qué pasó.",
        "Oficina do Seu Zé",
        pago=40,
    ),
    Mision(
        "generica_bar", None, "Rumor de la sinuca",
        "Civitas: en el Bar do Cabo dicen que habrá cobros por «seguridad» desde el lunes. Averigua la fuente.",
        "Bar do Cabo",
        pago=45,
    ),
    Mision(
        "generica_igreja", None, "Colecta dudosa",
        "Civitas: un mensaje pide transferencias para la Igreja Nossa Senhora da Esperança. Confirma con el padre.",
        "Igreja Nossa Senhora da Esperança",
        pago=30,
    ),
    Mision(
        "generica_escola", None, "Clases suspendidas",
        "Civitas: un grupo de padres cree que la Escola Municipal Paulo Freire cierra mañana. Verifica el aviso.",
        "Escola Municipal Paulo Freire",
        pago=40,
    ),
    Mision(
        "generica_salao", None, "Tinte prohibido",
        "Civitas: en el Salão da Dona Lu repiten que un producto causa daños. ¿Hay un estudio detrás?",
        "Salão da Dona Lu",
        pago=50,
    ),
    Mision(
        "generica_varzea", None, "Final cancelada",
        "Civitas: dicen que la final del Campo de Várzea se canceló por una pelea. Pregunta a los jugadores.",
        "Campo de Várzea",
        pago=50,
    ),
    Mision(
        "generica_feira_ladeira", None, "Frutas «orgánicas»",
        "Civitas: un video de la Feira da Ladeira promete frutas «orgánicas» al triple de precio. Contrástalo.",
        "Feira da Ladeira",
        pago=55,
    ),
    Mision(
        "generica_mirante", None, "Luces en el cielo",
        "Civitas: una publicación asegura que desde el Mirante do Alto se vio algo extraño anoche. Sube y comprueba.",
        "Mirante do Alto",
        pago=60,
    ),
    Mision(
        "generica_estacao_alto", None, "Cabina detenida",
        "Civitas: corre que una cabina quedó colgada en la Estação Alto do Morro. Ve a ver qué hay de cierto.",
        "Estação Alto do Morro",
        pago=60,
    ),
)


# Misiones EXTRA del mapa grande (F9): 4 por rol y 4 genéricas, repartidas por todo el mapa (R$20-60, el pago crece con la
# distancia al spawn del rol). Van AL FINAL del catálogo: SistemaMisiones asigna primero las del rol en orden de catálogo,
# así que dentro de cada rol están ordenadas de la más cercana a su spawn a la más lejana (ciudadano 56,-20; periodista
# 24,-32; influencer 24,24; candidato -32,-4) y nadie recibe un destino a 600 m recién empezada la partida. Varias son en
# lugares con trabajo (supermercado, padaria, oficina, bar, mototáxi, feria, lan house). Textos neutros (ver arriba).
MISIONES_EXTRA_GRANDE = (
    # -- Ciudadano --
    Mision(
        "ciudadano_posto", "ciudadano", "Turnos pagados",
        "Civitas: dicen que en el Posto de Saúde Vila Nova se «compran» turnos con transferencia. Pregunta en la fila.",
        "Posto de Saúde Vila Nova",
        pago=30,
    ),
    Mision(
        "ciudadano_supermercado", "ciudadano", "Empleo con depósito",
        "Civitas: un mensaje ofrece trabajo en el Supermercado Dois Irmãos, pero pide un «depósito». Verifícalo con el encargado.",
        "Supermercado Dois Irmãos",
        pago=35,
    ),
    Mision(
        "ciudadano_padaria", "ciudadano", "Harina a mitad de precio",
        "Civitas: circula que la Padaria Pão Quente vende harina a mitad de precio solo hoy. Averigua si es cierto.",
        "Padaria Pão Quente",
        pago=40,
    ),
    Mision(
        "ciudadano_feira", "ciudadano", "Cierre de la feria",
        "Civitas: un audio en cadena dice que la Feira da Ladeira cierra el sábado por «orden municipal». Busca el aviso oficial.",
        "Feira da Ladeira",
        pago=55,
    ),
    # -- Periodista --
    Mision(
        "periodista_igreja", "periodista", "Milagro en video",
        "Civitas: un video de la Igreja Nossa Senhora da Esperança promete un «milagro». Contrasta con quienes estuvieron.",
        "Igreja Nossa Senhora da Esperança",
        pago=35,
    ),
    Mision(
        "periodista_oficina", "periodista", "Taller clausurado",
        "Civitas: una cuenta anónima asegura que clausuraron la Oficina do Seu Zé. Habla con el dueño antes de publicar.",
        "Oficina do Seu Zé",
        pago=40,
    ),
    Mision(
        "periodista_escola", "periodista", "Notas filtradas",
        "Civitas: se filtró una «lista de reprobados» de la Escola Municipal Paulo Freire. Comprueba si es auténtica.",
        "Escola Municipal Paulo Freire",
        pago=45,
    ),
    Mision(
        "periodista_estacao", "periodista", "Falla del teleférico",
        "Civitas: dicen que la Estação Alto do Morro suspende el servicio por una falla grave. Ve a la fuente.",
        "Estação Alto do Morro",
        pago=55,
    ),
    # -- Influencer --
    Mision(
        "influencer_posto", "influencer", "Reto del suero",
        "Civitas: un reto viral pide beber «suero casero» frente al Posto de Saúde Vila Nova. Mira qué tan peligroso es.",
        "Posto de Saúde Vila Nova",
        pago=30,
    ),
    Mision(
        "influencer_padaria", "influencer", "Pan gigante",
        "Civitas: un video muestra un «pan gigante» de la Padaria Pão Quente. ¿Es real o está editado?",
        "Padaria Pão Quente",
        pago=40,
    ),
    Mision(
        "influencer_bar", "influencer", "Directo en el bar",
        "Civitas: una transmisión en vivo desde el Bar do Cabo regala «premios» a quien comparta. Revisa las condiciones.",
        "Bar do Cabo",
        pago=50,
    ),
    Mision(
        "influencer_mirante", "influencer", "Amanecer prohibido",
        "Civitas: una foto del Mirante do Alto dice que el acceso se cierra al público. Sube y comprueba.",
        "Mirante do Alto",
        pago=60,
    ),
    # -- Candidato --
    Mision(
        "candidato_igreja", "candidato", "Promesa en el atrio",
        "Civitas: circula un volante con «promesas» firmadas frente a la Igreja Nossa Senhora da Esperança. Escucha a los fieles.",
        "Igreja Nossa Senhora da Esperança",
        pago=30,
    ),
    Mision(
        "candidato_oficina", "candidato", "Obra sin permiso",
        "Civitas: acusan a la Oficina do Seu Zé de ampliarse sin permiso. Oye a los vecinos y al taller.",
        "Oficina do Seu Zé",
        pago=40,
    ),
    Mision(
        "candidato_varzea", "candidato", "Cancha prometida",
        "Civitas: dicen que cubrirán el Campo de Várzea con un techo «financiado». Pregunta quién lo pagará.",
        "Campo de Várzea",
        pago=45,
    ),
    Mision(
        "candidato_salao", "candidato", "Voto en la peluquería",
        "Civitas: en el Salão da Dona Lu repiten que «ya hay ganador» de la elección. Averigua de dónde sale.",
        "Salão da Dona Lu",
        pago=50,
    ),
    # -- Genéricas en lugares de trabajo --
    Mision(
        "generica_lanhouse", None, "Wifi gratis",
        "Civitas: un cartel de la Lan House da Praça promete wifi gratis «para siempre» si das tus datos. Revísalo.",
        "Praça da Sé",
        pago=20,
    ),
    Mision(
        "generica_taller_turno", None, "Turnos de taller",
        "Civitas: la Oficina do Seu Zé anunciaría turnos pagados al doble, según un mensaje reenviado. Confírmalo.",
        "Oficina do Seu Zé",
        pago=40,
    ),
    Mision(
        "generica_entregas", None, "Entrega que no llega",
        "Civitas: acusan al Ponto de Mototáxi da Entrada de cobrar entregas que nunca salieron. Pregunta a los clientes.",
        "Ponto de Mototáxi da Entrada",
        pago=55,
    ),
    Mision(
        "generica_feira_turno", None, "Puestos de la feria",
        "Civitas: ofrecen puestos en la Feira da Ladeira «solo hoy» contra un anticipo. Comprueba si es una estafa.",
        "Feira da Ladeira",
        pago=60,
    ),
)

CATALOGO_MISIONES_GRANDE = CATALOGO_MISIONES + MISIONES_MAPA_GRANDE + MISIONES_EXTRA_GRANDE


def catalogo_de_mundo(mundo):
    """El catálogo de misiones que corresponde al mundo: un MundoGrande (con chunks) usa CATALOGO_MISIONES_GRANDE; cualquier otro
    (el chico de siempre, o los falsos de las pruebas), CATALOGO_MISIONES. Lo usan main.py, el anfitrión y los clientes online
    para que todos hablen del mismo catálogo."""
    if hasattr(mundo, "contenido_de_chunk") and hasattr(mundo, "muros_de_chunk"):
        return CATALOGO_MISIONES_GRANDE
    return CATALOGO_MISIONES
