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
    ),
    Mision(
        "periodista_prefeitura", "periodista", "Rumor en la Prefeitura",
        "Civitas: rumor sin verificar en la Prefeitura. Contrástalo.", "Prefeitura",
    ),
    Mision(
        "influencer_parque", "influencer", "Publicación viral",
        "Civitas: una publicación se mueve en el Parque do Povo. Pásate.", "Parque do Povo",
    ),
    Mision(
        "candidato_morro", "candidato", "Voces del morro",
        "Civitas: los vecinos del Morro da Esperança quieren ser escuchados.", "Morro da Esperança",
    ),
    Mision(
        "generica_santa_casa", None, "Alerta sanitaria",
        "Civitas: circula una alerta en el Hospital Santa Casa. Verifícala.", "Hospital Santa Casa",
    ),
    Mision(
        "generica_rodoviaria", None, "Cadena de mensajes",
        "Civitas: cadena sospechosa en la Rodoviária. Revísala.", "Rodoviária",
    ),
    Mision(
        "generica_universidade", None, "Debate estudiantil",
        "Civitas: debate encendido en la Universidade de Ciudad Nova.", "Universidade de Ciudad Nova",
    ),
    Mision(
        "periodista_radio", "periodista", "Micrófono abierto",
        "Civitas: en la Rádio Comunitária leyeron al aire un audio sin fuente. Investígalo.", "Rádio Comunitária",
    ),
    Mision(
        "influencer_samba", "influencer", "Ensaio viral",
        "Civitas: un video del ensayo de la Escola de Samba se hace viral. ¿Es de este año?", "Escola de Samba",
    ),
    Mision(
        "candidato_mercado", "candidato", "Precio de la feria",
        "Civitas: corre que los precios del Mercado Municipal se duplican mañana. Escucha a los comerciantes.",
        "Mercado Municipal",
    ),
    Mision(
        "ciudadano_teleferico", "ciudadano", "Teleférico parado",
        "Civitas: dicen que el teleférico cierra para siempre. Pasa por la estación y averigua.",
        "Estação do Teleférico",
    ),
    Mision(
        "generica_mutirao", None, "Mutirão sospechoso",
        "Civitas: piden voluntarios para un mutirão en el Morro, pero el mensaje pide datos bancarios.",
        "Morro da Esperança",
    ),
    Mision(
        "generica_corrente", None, "Corrente do zap",
        "Civitas: una cadena del grupo de vecinos promete premios en la Praça da Sé. Revísala.", "Praça da Sé",
    ),
    Mision(
        "generica_feira", None, "Feria de trueque",
        "Civitas: anuncian una feria de trueque con «regalos gratis» en el Parque do Povo. ¿Es real?",
        "Parque do Povo",
    ),
)
