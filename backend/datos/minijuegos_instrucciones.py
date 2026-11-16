# Textos de la PANTALLA PREVIA de cada minijuego de verificar (datos puros, sin ursina). La escena de minijuegos
# (frontend/escenas/escena_minijuego.py) la enseña antes de empezar, para que el jugador sepa qué va a hacer y qué hábito de
# redes sociales practica. Se apaga con ALCALDE_MINIJUEGOS_INTRO=0 (backend/logica/minijuegos.pantalla_previa_activa).
#
# Cada entrada: «objetivo» (una o dos frases), «pasos» (tres frases cortas: cómo se juega) y «redes» (el hábito del uso
# adecuado de las redes sociales que se practica). Las teclas NO van aquí: las pone la vista con su propia AYUDA.
# Límites para que quepan en la pantalla sin encoger la letra: objetivo <= 170, cada paso <= 130, redes <= 200 caracteres.

from backend.logica import minijuegos as mj

INSTRUCCIONES = {
    mj.RASTREAR: {
        "objetivo": "Un mensaje te llegó reenviado muchas veces. Sigue la cadena hacia atrás hasta encontrar quién lo "
                    "publicó primero.",
        "pasos": (
            "En cada paso verás tres mensajes: quién lo mandó, a qué hora y qué dice.",
            "Elige el más ANTIGUO que no diga «reenviado»: ese es el eslabón anterior de la cadena.",
            "Cada error es un rodeo. Con demasiados rodeos pierdes el rastro.",
        ),
        "redes": "«Reenviado muchas veces» o «me lo pasó una amiga» no es una fuente. Antes de compartir, busca la cuenta "
                 "o el documento original.",
    },
    mj.COMPARAR: {
        "objetivo": "Tienes el original (lo que de verdad se dijo) y la copia que circula en el chat. Descubre qué le "
                    "cambiaron a la copia.",
        "pasos": (
            "Compara cada línea de la copia (derecha) con la misma línea del original (izquierda).",
            "Marca las líneas alteradas; puedes desmarcarlas si te equivocas.",
            "Pulsa «Confirmar marcas», o «No veo diferencias» si crees que la copia es fiel.",
        ),
        "redes": "Una captura o una transcripción se edita en segundos. Ve al original (la emisora, la cuenta oficial, "
                 "el cartel) antes de creerle a la copia.",
    },
    mj.CRONOLOGIA: {
        "objetivo": "Varios mensajes hablan del mismo rumor, pero llegaron desordenados. Ordénalos para ver cómo se fue "
                    "contando y de dónde salió.",
        "pasos": (
            "Arriba va lo que se dijo primero y abajo lo último: fíjate en el día y la hora.",
            "Agarra un mensaje (Enter o clic), súbelo o bájalo y vuelve a pulsar para soltarlo.",
            "Cuando creas que está en orden, pulsa «Comprobar el orden».",
        ),
        "redes": "Cada reenvío agrega detalles y pierde la fuente. Mirar la cadena completa evita quedarte con la última "
                 "versión, que suele ser la más exagerada.",
    },
    mj.CHAT: {
        "objetivo": "En el grupo del barrio te piden datos tuyos y de otras personas. Responde sin exponer a nadie, "
                    "aunque el grupo te presione.",
        "pasos": (
            "Lee el chat de la izquierda y elige una de las tres respuestas de la derecha.",
            "La presión del grupo sube con el tiempo: si tardas demasiado, te quedas en visto.",
            "Piensa qué datos entregas con cada respuesta, no cuál te saca más rápido del apuro.",
        ),
        "redes": "Tu número, tu cuenta o tu dirección (y los de tus amigos) no se comparten en un grupo porque alguien "
                 "insista. Si el pedido es legítimo, llega por un canal oficial.",
    },
    mj.SENALES: {
        "objetivo": "Te llegó una captura con un premio, un cupón o una cadena. Encuentra las pistas que delatan que está "
                    "editada o que es un engaño.",
        "pasos": (
            "Recorre las zonas de la captura: la lupa de la derecha te dice qué estás mirando.",
            "Marca hasta tres zonas sospechosas: cuenta rara, hora imposible, premio a cambio de reenviar...",
            "Confirma tus marcas, o pulsa «No veo nada raro» si crees que es auténtica.",
        ),
        "redes": "Las cadenas que prometen premios por reenviar son el engaño más viejo de las redes. Revisa la cuenta, "
                 "la fecha y si la promesa tiene sentido antes de reenviar.",
    },
    mj.CONTRARRELOJ: {
        "objetivo": "Las noticias llegan al chat una tras otra y se difunden solas. Decide rápido cuáles frenar y cuáles "
                    "dejar pasar.",
        "pasos": (
            "FRENA lo que creas falso y DEJA PASAR lo que creas cierto.",
            "La barra de cada noticia muestra cuánto se difundió: si se llena antes de que decidas, no cuenta.",
            "Con las flechas arriba y abajo eliges la noticia.",
        ),
        "redes": "Lo urgente se comparte sin pensar. Antes de reenviar una alerta de salud o seguridad, tómate unos "
                 "segundos: ¿quién la firma? ¿lo dice una fuente oficial?",
    },
}


def instrucciones_de(minijuego_id):
    """Textos de la pantalla previa del minijuego, o None si no tiene (entonces se empieza directo)."""
    return INSTRUCCIONES.get(minijuego_id)
