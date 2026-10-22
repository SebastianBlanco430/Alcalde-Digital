# Portátiles con dos GPU (integrada + dedicada, p. ej. AMD Radeon + NVIDIA RTX): Windows abre Python en la
# integrada salvo que se le diga otra cosa, y el juego corría ahí (medido: 12.9 FPS en la AMD integrada contra
# 22.6 en la RTX 2050 con el mismo recorrido, antes de las demás optimizaciones).
#
# asegurar() escribe la preferencia «Alto rendimiento» de Configuración > Pantalla > Gráficos
# (HKCU\Software\Microsoft\DirectX\UserGpuPreferences, valor "GpuPreference=2;") para el python.exe que
# ejecuta el juego: el del venv Y el python.exe real de la instalación, porque el del venv solo lanza a ese
# otro proceso, que es el que dibuja (medido: con solo el del venv el juego sigue en la integrada). Efecto
# secundario conocido: otros programas que se ejecuten con ESE python.exe también usarán la GPU dedicada.
# Es una preferencia del USUARIO (no del sistema). Si el usuario ya eligió algo para ese ejecutable, no se
# toca. Se llama antes de abrir la ventana: el controlador lee la preferencia al crear el contexto OpenGL.
#
# Para deshacerlo: ALCALDE_GPU_INTEGRADA=1 al lanzar main.py borra las entradas que valgan exactamente
# "GpuPreference=2;" para esos ejecutables y no escribe nada (o quitarlas a mano en esa pantalla de Windows).
# Fuera de Windows no hace nada. Nunca lanza: si falla, se avisa y sigue.

import os
import sys

GPU_DEDICADA = True          # False: no escribe ni borra nada (el juego usa la GPU que elija Windows)
CLAVE = r"Software\Microsoft\DirectX\UserGpuPreferences"
ALTO_RENDIMIENTO = "GpuPreference=2;"


def ejecutables():
    rutas = {sys.executable, getattr(sys, "_base_executable", sys.executable), os.path.realpath(sys.executable)}
    return sorted(r for r in rutas if r and os.path.isfile(r))


# Devuelve la lista de ejecutables a los que se les escribió la preferencia (vacía si no hizo falta).
def asegurar():
    if sys.platform != "win32" or not GPU_DEDICADA:
        return []
    if os.environ.get("ALCALDE_GPU_INTEGRADA", "").strip() == "1":
        revertir()
        return []
    try:
        import winreg
        escritos = []
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLAVE, 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as clave:
            for ruta in ejecutables():
                try:
                    winreg.QueryValueEx(clave, ruta)
                    continue                      # ya hay una elección (del usuario o nuestra): se respeta
                except FileNotFoundError:
                    pass
                winreg.SetValueEx(clave, ruta, 0, winreg.REG_SZ, ALTO_RENDIMIENTO)
                escritos.append(ruta)
        if escritos:
            print(f"[GPU] preferencia de alto rendimiento guardada para: {', '.join(escritos)}", flush=True)
        return escritos
    except Exception as error:      # noqa: BLE001 — sin permisos o sin registro: el juego sigue igual
        print(f"[GPU] no se pudo fijar la GPU dedicada ({error})", file=sys.stderr)
        return []


# Borra las preferencias que puso asegurar() (las que valen exactamente ALTO_RENDIMIENTO). Devuelve las rutas borradas.
def revertir():
    if sys.platform != "win32":
        return []
    try:
        import winreg
        borrados = []
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as clave:
            for ruta in ejecutables():
                try:
                    valor, _ = winreg.QueryValueEx(clave, ruta)
                except FileNotFoundError:
                    continue
                if valor == ALTO_RENDIMIENTO:
                    winreg.DeleteValue(clave, ruta)
                    borrados.append(ruta)
        if borrados:
            print(f"[GPU] preferencia de alto rendimiento quitada para: {', '.join(borrados)}", flush=True)
        return borrados
    except Exception as error:      # noqa: BLE001 — sin permisos: no se toca nada
        print(f"[GPU] no se pudo quitar la preferencia ({error})", file=sys.stderr)
        return []
