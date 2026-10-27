# Pago y cansancio de un turno de trabajo (modelo puro, sin ursina): ingresa el pago en la billetera del perfil,
# suma la fatiga del puesto y anota el movimiento en el libro. Lo llama ConexionFlujo.terminar_trabajo con el
# perfil del jugador que EMPEZÓ el turno (no con el jugador activo de después).

from backend.logica.inventario import SALDO_MAX, _entero_valido
from backend.logica.perfil_economia import FATIGA_MAX


# resultado = TurnoTrabajo.resultado() ({aciertos, errores, rendimiento, pago, fatiga}). Devuelve un dict
# {pago, fatiga, mensaje}: `pago` es lo que de verdad entró (0 si no hay billetera o está llena) y `mensaje`
# es el aviso para el jugador. Nunca lanza por un resultado raro: lo inválido cuenta como 0.
def aplicar_resultado(perfil, trabajo, resultado):
    datos = resultado if isinstance(resultado, dict) else {}
    pago = datos.get("pago", 0)
    fatiga = datos.get("fatiga", 0)
    pago = pago if _entero_valido(pago, 0, SALDO_MAX) else 0
    tope = getattr(trabajo, "pago_max", None)
    if _entero_valido(tope, 0, SALDO_MAX):
        pago = min(pago, tope)           # nunca más que lo que paga el puesto, venga lo que venga en `resultado`
    fatiga = fatiga if _entero_valido(fatiga, 0, FATIGA_MAX) else 0
    nombre = getattr(trabajo, "nombre", "turno")
    cobrado, mensaje = 0, ""
    if pago > 0:
        ingreso = perfil.inventario.ingresar(pago)
        if ingreso.ok:
            cobrado = pago
            perfil.ganado += pago
            perfil.registrar(f"Trabajo: {nombre}", pago)
            mensaje = f"+R$ {pago}"
        else:
            mensaje = f"No pudiste cobrar el turno: {ingreso.mensaje}"
    else:
        mensaje = "Turno sin paga: no acertaste lo suficiente"
    perfil.turnos += 1
    perfil.fatiga = min(FATIGA_MAX, perfil.fatiga + fatiga)
    return {"pago": cobrado, "fatiga": fatiga, "mensaje": mensaje}
