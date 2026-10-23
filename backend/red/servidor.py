# Arranque del anfitrión SIN gráficos: construye el mundo real y la partida cooperativa y
# deja el servidor escuchando. Sirve para jugar con un equipo dedicado y para probar a mano.
#
#   venv/bin/python -m backend.red.servidor --puerto 7777 --ambito lan
#   venv/bin/python -m backend.red.servidor --ambito local            # solo este equipo
#   venv/bin/python -m backend.red.servidor --ambito abierto           # 0.0.0.0 (pide escribir ABRIR)
#
# Imprime «IP:puerto» y el código de sala (se necesita para entrar). No escribe IPs de pares en
# ningún registro. Órdenes por la entrada estándar: iniciar | estado | salir.
# NUNCA importa ursina ni panda3d.
import argparse
import sys
import threading

from backend.datos.ciudad_3d import ESCALA_MUNDO, SEMILLA_CASAS, construir_mundo_3d
from backend.datos.misiones_semilla import CATALOGO_MISIONES
from backend.datos.noticias_semilla import construir_arboles
from backend.grafos.grafo_social import construir_grafo_social_ejemplo
from backend.logica.estado_partida import EstadoPartida
from backend.red import huellas
from backend.red.anfitrion import AMBITOS, Anfitrion, calcular_huellas
from backend.red.partida_coop import MazoSembrado, PartidaCooperativa

RADIO_INTERACCION = 2.0     # m: igual que main.py (distancia a la puerta para «llegué»)


def construir_anfitrion(puerto=0, ambito="lan", semilla=SEMILLA_CASAS, abierto=False, mundo=None,
                        partida_opciones=None, **opciones):
    """Arma mundo + partida + anfitrión (sin arrancarlo). `opciones` pasan a Anfitrion;
    `mundo` reutiliza uno ya construido (pruebas); `partida_opciones` pasa a PartidaCooperativa."""
    codigo = opciones.pop("codigo", None) or huellas.generar_codigo_sala(
        huellas.LARGO_CODIGO_ABIERTO if ambito == "abierto" else huellas.LARGO_CODIGO)
    mundo = mundo if mundo is not None else construir_mundo_3d(semilla=semilla)
    arbol_noticias, arbol_stats = construir_arboles()
    estado = EstadoPartida(arbol_noticias, arbol_stats, mazo=MazoSembrado(arbol_noticias, semilla))
    partida = PartidaCooperativa(
        estado, mundo, CATALOGO_MISIONES, grafo_social=construir_grafo_social_ejemplo(),
        escala_mundo=ESCALA_MUNDO, punto_interaccion=mundo.punto_interaccion,
        radio_interaccion=RADIO_INTERACCION, **(partida_opciones or {}))
    h_mundo, h_contenido = calcular_huellas(mundo, semilla, CATALOGO_MISIONES)
    return Anfitrion(partida, mundo, semilla, codigo, h_mundo, h_contenido, ambito=ambito,
                     puerto=puerto, abierto=abierto, **opciones)


def _leer_argumentos(argv):
    ap = argparse.ArgumentParser(prog="python -m backend.red.servidor",
                                 description="Anfitrión de Alcalde Digital (modo online cooperativo).")
    ap.add_argument("--puerto", type=int, default=0, help="puerto TCP (0 = uno libre)")
    ap.add_argument("--ambito", choices=AMBITOS, default="lan",
                    help="local: solo este equipo; lan: red local (por defecto); abierto: 0.0.0.0")
    ap.add_argument("--semilla", type=int, default=SEMILLA_CASAS, help="semilla de la favela")
    ap.add_argument("--primero-cualquiera", action="store_true",
                    help="el primero en entrar puede venir de otro equipo (por defecto debe ser local)")
    ap.add_argument("--sin-auto-iniciar", action="store_true",
                    help="no empezar sola al estar todos listos (usa la orden «iniciar»)")
    ap.add_argument("--max-por-ip", type=int, default=None,
                    help="conexiones simultáneas por IP (por defecto el valor del protocolo; sube para jugar de a 4 en un equipo)")
    ap.add_argument("--sin-vehiculos", action="store_true",
                    help="sin bicis ni motos online (por defecto las hay si VEHICULOS_ONLINE está activo)")
    return ap.parse_args(argv)


def _vehiculos_online():
    # La bandera vive en frontend/online_config.py (módulo mínimo, sin ursina): clientes y anfitrión la comparten.
    try:
        from frontend import online_config
        return bool(online_config.VEHICULOS_ONLINE)
    except Exception:
        return False


def _confirmar_abierto():
    print("AVISO: el ámbito «abierto» escucha en TODAS las interfaces (0.0.0.0) y el tráfico va SIN "
          "CIFRAR. Recomendado: una VPN (Tailscale, ZeroTier, WireGuard) en lugar de abrir el puerto.")
    try:
        return input("Escribe ABRIR para continuar: ").strip() == "ABRIR"
    except EOFError:
        return False


def main(argv=None):
    args = _leer_argumentos(argv)
    abierto = args.ambito == "abierto"
    if abierto and not _confirmar_abierto():
        print("Cancelado: no se abrió el servidor.")
        return 1
    try:
        anfitrion = construir_anfitrion(
            puerto=args.puerto, ambito=args.ambito, semilla=args.semilla, abierto=abierto,
            exigir_anfitrion_local=not args.primero_cualquiera, auto_iniciar=not args.sin_auto_iniciar,
            vehiculos=_vehiculos_online() and not args.sin_vehiculos,
            **({"max_por_ip": args.max_por_ip} if args.max_por_ip else {}))
        host, puerto = anfitrion.iniciar()
    except (OSError, ValueError) as error:
        print(f"No se pudo abrir el servidor: {error}")
        return 1
    print(f"Anfitrión listo en {host}:{puerto}   código de sala: {anfitrion.codigo}")
    print("El tráfico va SIN CIFRAR. Comparte la dirección y el código solo con quien quieras que juegue.")
    print("Órdenes: iniciar | estado | salir   (Ctrl+C también apaga)")
    terminar = threading.Event()

    def leer_ordenes():
        for linea in sys.stdin:
            orden = linea.strip().lower()
            try:
                if orden == "iniciar":
                    anfitrion.iniciar_partida(forzar=True)
                    print("Partida iniciada.")
                elif orden == "estado":
                    print(anfitrion.estado())
                elif orden == "salir":
                    terminar.set()
                    return
            except (ValueError, RuntimeError, TimeoutError) as error:
                print(f"No se pudo: {error}")
        # Fin de la entrada (sin terminal): el servidor sigue hasta Ctrl+C o hasta cerrarse la sala.

    threading.Thread(target=leer_ordenes, name="alcalde-servidor-ordenes", daemon=True).start()
    try:
        while anfitrion.activo() and not terminar.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        anfitrion.detener()
    print("Servidor apagado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
