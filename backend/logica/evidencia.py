# Convención de evidencia sobre GameState (modelo puro): una evidencia es un flag permanente «evidencia:<id>».
# Es el único contrato entre quien la otorga (parkour, mundo digital) y quien la consume (motor de casos), así
# ninguno toca el código del otro. Otorgar es idempotente: la segunda vez no registra otro impacto.

PREFIJO = "evidencia:"


def nombre_flag(id_evidencia):
    if not isinstance(id_evidencia, str) or not id_evidencia.strip():
        raise ValueError("id de evidencia inválido: se esperaba un texto no vacío.")
    return PREFIJO + id_evidencia.strip()


# Casos v2 (backend/logica/casos_v2.py): las pruebas de un caso llevan su id delante, «<id_caso>.<id_prueba>», para que
# dos casos puedan usar el mismo id de prueba sin mezclarse (flag «evidencia:<id_caso>.<id_prueba>»).
SEPARADOR_CASO = "."


def id_de_caso(id_caso, id_prueba):
    for valor in (id_caso, id_prueba):
        if not isinstance(valor, str) or not valor.strip() or SEPARADOR_CASO in valor:
            raise ValueError(f"id de caso o de prueba inválido: {valor!r} (texto no vacío y sin '.').")
    return id_caso.strip() + SEPARADOR_CASO + id_prueba.strip()


# Ids (sin prefijo) de las pruebas del caso `id_caso` que tiene el jugador, ordenados.
def de_caso(game_state, id_caso):
    prefijo = id_caso + SEPARADOR_CASO
    return [i[len(prefijo):] for i in listar(game_state) if i.startswith(prefijo)]


def tiene(game_state, id_evidencia):
    return game_state.flag(nombre_flag(id_evidencia))


# Ids de las evidencias que tiene el jugador, ordenados.
def listar(game_state):
    return sorted(n[len(PREFIJO):] for n in game_state.flags() if n.startswith(PREFIJO))


# Otorga la evidencia y registra un impacto «evidencia» (origen = quién la dio: p. ej. «parkour:nivel1»).
# Retorna True si es nueva, False si ya se tenía (sin efecto). `efectos` opcional como en aplicar_evento.
def otorgar(game_state, id_evidencia, origen, efectos=None, datos=None):
    flag = nombre_flag(id_evidencia)
    if game_state.flag(flag):
        return False
    game_state.aplicar_evento(
        "evidencia", efectos=efectos, flags=[(flag, True)], origen=origen,
        datos=dict(datos or {}, evidencia=id_evidencia.strip()),
    )
    return True
