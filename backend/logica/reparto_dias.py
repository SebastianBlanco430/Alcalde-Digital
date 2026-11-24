# Reparto de misiones por días (modelo puro, sin ursina). Contrato: sesiones-24nov/misiones/contrato-dias.md.
#
# POR QUÉ. El fondo tiene 35 misiones de verificar (5 por día) y una partida de 7 días no da para todas: cada partida
# SORTEA su semana (4 por día, 28) y cada día ofrece solo lo suyo. Así la semana tiene ritmo (lo cotidiano primero, la
# elección al final), los arcos se cuentan en orden y dos partidas no son iguales.
#
#   sortear(fondo, semilla, por_dia=4)  -> Semana: qué ids se juegan, el día de cada una y la RESERVA de cada día (la que
#                                          quedó fuera, si es suelta). Determinista entre equipos y versiones de Python:
#                                          random.Random sembrado con TEXTO y elecciones sobre listas en orden del fondo
#                                          (nunca sobre un set). Un arco entra entero o no entra; un día deja fuera como
#                                          máximo una; las misiones que no son de verificar (Fiscalía, parkour) siempre entran.
#                                          Ningún día queda con un solo veredicto (todas verdaderas o todas falsas): el
#                                          candidato que lo provocaría no se sortea (si no queda otro, se ignora la regla).
#   elegir(candidatas, rol)             -> cuál asignar: Fiscalía primero; la que va al lugar de inicio del rol, la última.
#   RepartoDias(fondo, semilla)         -> el estado de la semana en una partida: día, completadas, caducadas, arrastradas
#                                          y reservas abiertas; ofrecibles(ocupadas) dice qué se puede asignar AHORA.
#
# DOS MODOS (atributo `con_reloj`):
#   - con reloj (partida local con FlujoConTiempo): el día lo fija quien tiene el reloj (avanzar_a). Al pasar de día se
#     arrastran hasta TOPE_ARRASTRE misiones de verificar (primero pasos de arco, luego orden del fondo) y el resto
#     CADUCA; una arrastrada vive un día más; la activa nunca caduca (cuenta en el tope); la de Fiscalía no caduca ni
#     ocupa cupo. Si todo lo del día está cerrado y son menos de las HORA_LIMITE_RESERVA, se abre la reserva del día.
#     Si al pasar de día la activa es una Fiscalía sin cerrar, queda APLAZADA (se suelta, no caduca) y desde entonces
#     sale la última; mientras haya una aplazada abierta, las Fiscalías nuevas entran aplazadas (aplazadas()).
#   - por progreso (sin reloj y en línea): el día d se abre cuando todo lo sorteado de verificar de los días anteriores
#     está completado o en curso. Sin arrastre, sin caducidad y sin reserva.
# En los dos: el paso n de un arco no se ofrece mientras el paso n-1 siga abierto (se ofrece si se completó o caducó), y
# la misión de Fiscalía (cualquiera que no sea de verificar) se ofrece como SEGUNDA del día: cuando ya se cerró una de
# verificar ese día, o cuando no queda ninguna de verificar que ofrecer.
#
# `mision` se usa por duck typing (id, tipo, dia, arco, paso, rol): este módulo NO importa misiones.py (misiones.py lo
# importa a él). El día de una misión de Fiscalía sin `dia` propio se pide a misiones_digitales.dia_de si existe.
#
# BANDERA. MISIONES_DIAS = False (o ALCALDE_MISIONES_DIAS=0) lo apaga: el catálogo vuelve a ser el de 14 misiones y se
# reparte en orden de catálogo, como en 0b7e148.

import os
import random
import sys
from dataclasses import dataclass

MISIONES_DIAS = True

DIAS = 7
POR_DIA = 4                     # misiones de verificar por día que entran en la semana
TOPE_ARRASTRE = 2               # misiones de verificar que pasan al día siguiente
HORA_LIMITE_RESERVA = 20.0      # la reserva del día solo se abre antes de esta hora
SEMILLA_EN_LINEA = 2026         # semilla por defecto de ReservaMisiones (determinista si nadie pasa la del mundo)
_VERSION = 1

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Hay reparto por días? ALCALDE_MISIONES_DIAS=1/0 manda sobre la constante (se lee en cada llamada)."""
    valor = os.environ.get("ALCALDE_MISIONES_DIAS", "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(MISIONES_DIAS)


def es_verificar(mision):
    return getattr(mision, "tipo", "verificar") == "verificar"


def tiene_dias(catalogo):
    """¿El catálogo es un fondo por días? (alguna misión de verificar declara su día). Los catálogos de las pruebas de
    siempre no lo son y se reparten como antes aunque la bandera esté encendida."""
    return any(es_verificar(m) and (getattr(m, "dia", 0) or 0) > 0 for m in catalogo)


def semilla_local():
    """Semilla de una partida local nueva: ALCALDE_SEMILLA_MISIONES (entero) si está; si no, una al azar (rejugabilidad)."""
    crudo = os.environ.get("ALCALDE_SEMILLA_MISIONES", "").strip()
    if crudo:
        try:
            return int(crudo)
        except ValueError:
            print(f"[misiones] ALCALDE_SEMILLA_MISIONES={crudo!r} no es un entero; se sortea una semilla", file=sys.stderr)
    return random.SystemRandom().randrange(1, 2 ** 31)


def _dia_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= DIAS


def _dia_de_fiscalia(id_mision):
    """El día que declara el JSON del caso (misiones_digitales.dia_de, de la sesión A), o None si no existe o falla."""
    try:
        from backend.logica import misiones_digitales
        leer = getattr(misiones_digitales, "dia_de", None)
        dia = leer(id_mision) if callable(leer) else None
    except Exception:           # un caso roto no puede impedir repartir: se coloca como si no tuviera día
        return None
    return dia if _dia_valido(dia) else None


def dias_de(fondo):
    """{id: día 1-7} de todo el fondo. Verificar: su `dia` (0 = día 1, entra siempre). Las demás (Fiscalía, parkour):
    su `dia` si es > 0; si no, misiones_digitales.dia_de(id); si tampoco, los días 1, 2, 3... en orden del fondo."""
    dias, siguiente = {}, 1
    for mision in fondo:
        dia = getattr(mision, "dia", 0) or 0
        if es_verificar(mision):
            dias[mision.id] = dia if dia > 0 else 1
            continue
        if dia <= 0:
            dia = _dia_de_fiscalia(mision.id) or 0
        if dia <= 0:
            dia, siguiente = min(siguiente, DIAS), siguiente + 1
        dias[mision.id] = dia
    return dias


# La semana sorteada. `ids`: las que se juegan, en el orden del fondo. `reservas`: {día: id de la reserva o None} (solo
# días con sorteo; la reserva es la que quedó fuera si es SUELTA). `dias`: {id: día} de todo el fondo.
@dataclass(frozen=True)
class Semana:
    ids: tuple
    reservas: dict
    dias: dict

    def del_dia(self, dia):
        return [i for i in self.ids if self.dias[i] == dia]


def sortear(fondo, semilla, por_dia=POR_DIA):
    """Semana de la partida (ver Semana). Día a día, en orden: si el día tiene más de `por_dia` misiones de verificar con
    día, deja fuera UNA, elegida al azar entre sus sueltas y los arcos que EMPIEZAN ese día y caben (cada paso en un día
    distinto que aún pueda dejar una fuera). Elegir un arco lo deja fuera entero y gasta el cupo de todos sus días."""
    fondo = list(fondo)
    azar = random.Random(f"misiones-dias:{semilla}")
    sorteables, arcos = {}, {}
    for mision in fondo:
        if es_verificar(mision) and (getattr(mision, "dia", 0) or 0) > 0:
            sorteables.setdefault(mision.dia, []).append(mision)
            if mision.arco:
                arcos.setdefault(mision.arco, []).append(mision)
    cupo = {dia: len(lista) > por_dia for dia, lista in sorteables.items()}
    fuera, reservas = set(), {dia: None for dia in sorteables}
    for dia in sorted(sorteables):
        if not cupo[dia]:
            continue
        candidatos, vistos = [], set()
        for mision in sorteables[dia]:
            if not mision.arco:
                candidatos.append([mision])
            elif mision.arco not in vistos and min(p.dia for p in arcos[mision.arco]) == dia:
                vistos.add(mision.arco)
                dias_arco = [p.dia for p in arcos[mision.arco]]
                if len(set(dias_arco)) == len(dias_arco) and all(cupo.get(d) for d in dias_arco):
                    candidatos.append(sorted(arcos[mision.arco], key=lambda p: p.paso))
        if not candidatos:
            continue
        # Ningún día con un solo veredicto: se descarta el candidato que dejaría alguno de sus días con todas verdaderas
        # o todas falsas. Si así no queda ninguno, se ignora la regla en ese día (el sorteo nunca falla).
        candidatos = [c for c in candidatos if _mezcla_veredictos(c, sorteables, fuera)] or candidatos
        elegido = azar.choice(candidatos)
        for mision in elegido:
            fuera.add(mision.id)
            cupo[mision.dia] = False
        if len(elegido) == 1 and not elegido[0].arco:
            reservas[dia] = elegido[0].id
    return Semana(tuple(m.id for m in fondo if m.id not in fuera), reservas, dias_de(fondo))


def lugar_inicio(rol):
    """Lugar donde nace el rol (backend.logica.roles), o None si el rol no existe (pruebas) o no se puede leer."""
    try:
        from backend.logica.roles import ROLES
        return ROLES[rol].lugar_inicio
    except Exception:
        return None


def elegir(candidatas, rol):
    """La misión a asignar de entre `candidatas` (ofrecibles, ya en el orden de prioridad del rol), o None. Primero la de
    Fiscalía (el reparto solo la ofrece cuando ya es la segunda del día); y, como desempate pedido por el verificador,
    la que va al LUGAR DE INICIO del rol queda la última (aparecía ya «llegada»): si es la única, se ofrece igual.
    Lo usan SistemaMisiones (local) y ReservaMisiones (en línea), así los dos eligen igual."""
    casa = lugar_inicio(rol)
    ordenadas = sorted(candidatas, key=lambda m: (casa is not None and m.destino == casa, es_verificar(m)))
    return ordenadas[0] if ordenadas else None


def _mezcla_veredictos(candidato, sorteables, fuera):
    """¿Quitar `candidato` deja en cada día afectado misiones verdaderas Y falsas? (petición del verificador: un día de un
    solo veredicto se «acierta» sin mirar)."""
    quitar = {m.id for m in candidato} | fuera
    for dia in {m.dia for m in candidato}:
        quedan = {getattr(m, "es_verdadera", None) for m in sorteables[dia] if m.id not in quitar}
        if not {True, False} <= quedan:
            return False
    return True


class RepartoDias:

    # `fondo`: el catálogo completo (Mision por duck typing). `semilla`: entero o texto (se guarda tal cual).
    def __init__(self, fondo, semilla, por_dia=POR_DIA, con_reloj=False):
        self._fondo = list(fondo)
        self._por_id = {m.id: m for m in self._fondo}
        self._orden = {m.id: i for i, m in enumerate(self._fondo)}
        self.semilla = semilla
        self.por_dia = por_dia
        self.semana = sortear(self._fondo, semilla, por_dia)
        self.con_reloj = bool(con_reloj)
        self._dia = 1                   # día del reloj (solo con reloj)
        self._hora = None               # hora del día (None = desconocida: la reserva se permite)
        self._hechas = {}               # id -> día en que se cerró (0 = desconocido), en orden de cierre
        self._caducadas = []
        self._arrastradas = []          # ids que pasaron al día actual (en el orden en que se arrastraron)
        self._reservas_abiertas = []    # días cuya reserva ya se abrió
        self._aplazadas = []            # Fiscalías aplazadas (ver _pasar_dia): salen las últimas, nunca caducan
        self._pasos = {}                # arco -> {paso: id}
        for mision in self._fondo:
            if es_verificar(mision) and mision.arco:
                self._pasos.setdefault(mision.arco, {})[mision.paso] = mision.id

    # -- Lectura --

    @property
    def dia(self):
        return self._dia if self.con_reloj else self.dia_abierto()

    @property
    def hora(self):
        return self._hora

    def completadas(self):
        return list(self._hechas)

    def caducadas(self):
        return list(self._caducadas)

    def arrastradas(self):
        return list(self._arrastradas)

    def reservas_abiertas(self):
        return list(self._reservas_abiertas)

    # Fiscalías aplazadas (en el orden en que se aplazaron). Incluye las ya cerradas: el estado viaja con el guardado.
    def aplazadas(self):
        return list(self._aplazadas)

    def _hay_aplazada_abierta(self):
        return any(not self._cerrada(i) for i in self._aplazadas)

    # Ids jugables de la semana: las sorteadas y las reservas que se abrieron, en el orden del fondo.
    def ids_semana(self):
        extra = {self.semana.reservas.get(d) for d in self._reservas_abiertas} - {None}
        return [m.id for m in self._fondo if m.id in set(self.semana.ids) | extra]

    def _cerrada(self, id_mision):
        return id_mision in self._hechas or id_mision in self._caducadas

    def _verificar(self, id_mision):
        return es_verificar(self._por_id[id_mision])

    # El paso n de un arco espera a que el n-1 esté completado o caducado.
    def _bloqueada(self, id_mision):
        mision = self._por_id[id_mision]
        if not mision.arco or mision.paso <= 1:
            return False
        anterior = self._pasos.get(mision.arco, {}).get(mision.paso - 1)
        return anterior is not None and not self._cerrada(anterior)

    # Por progreso: el primer día con alguna de verificar sorteada que no esté completada ni en curso (el último día
    # si no queda ninguna). Los días posteriores siguen cerrados.
    def dia_abierto(self, ocupadas=()):
        ocupadas = set(ocupadas)
        dias = self.semana.dias
        pendientes = [dias[i] for i in self.semana.ids
                      if self._verificar(i) and not self._cerrada(i) and i not in ocupadas]
        return min(pendientes) if pendientes else max([dias[i] for i in self.semana.ids] or [1])

    # -- Qué se ofrece --

    # Ids que se pueden asignar ahora (en el orden del fondo). `ocupadas`: las que alguien tiene en curso (la activa en
    # la partida local; las reservadas en línea): no se ofrecen y cuentan como abiertas. Puede ABRIR la reserva del día
    # (con reloj, si todo lo demás está cerrado y es antes de las 20:00): desde entonces queda ofrecida hasta cerrarse.
    def ofrecibles(self, ocupadas=()):
        ocupadas = set(ocupadas)
        if self.con_reloj:
            dia, verificar = self._dia, self._verificar_con_reloj(ocupadas)
        else:
            dia = self.dia_abierto(ocupadas)
            verificar = [i for i in self.semana.ids if self._verificar(i) and self.semana.dias[i] <= dia
                         and not self._cerrada(i) and i not in ocupadas and not self._bloqueada(i)]
        digitales = [i for i in self.semana.ids if not self._verificar(i) and self.semana.dias[i] <= dia
                     and not self._cerrada(i) and i not in ocupadas and self._fiscalia_libre(i, dia, verificar)]
        return sorted(set(verificar) | set(digitales), key=self._orden.__getitem__)

    def _grupo_del_dia(self):
        dia = self._dia
        grupo = [i for i in self.semana.del_dia(dia) if self._verificar(i)]
        grupo += [i for i in self._arrastradas if i not in grupo]
        reserva = self.semana.reservas.get(dia)
        if reserva is not None and dia in self._reservas_abiertas and reserva not in grupo:
            grupo.append(reserva)
        return grupo

    def _verificar_con_reloj(self, ocupadas):
        abiertas = [i for i in self._grupo_del_dia() if not self._cerrada(i)]
        libres = [i for i in abiertas if i not in ocupadas and not self._bloqueada(i)]
        reserva = self.semana.reservas.get(self._dia)
        if (not abiertas and reserva is not None and self._dia not in self._reservas_abiertas
                and not self._cerrada(reserva) and (self._hora is None or self._hora < HORA_LIMITE_RESERVA)):
            self._reservas_abiertas.append(self._dia)
            if reserva not in ocupadas:
                libres.append(reserva)
        return libres

    # Fiscalía como SEGUNDA misión del día: ya se cerró una de verificar «hoy» (con reloj: el día del reloj; por
    # progreso: un día igual o posterior al de la misión) o no queda ninguna de verificar que ofrecer.
    # Una Fiscalía APLAZADA (o cualquiera mientras haya una aplazada abierta: «entran ya aplazadas») sale la ÚLTIMA:
    # solo cuando no queda nada de verificar ofrecible, reserva incluida.
    def _fiscalia_libre(self, id_mision, dia, verificar_libres):
        if not verificar_libres:
            return True
        if self.con_reloj and (id_mision in self._aplazadas or self._hay_aplazada_abierta()):
            return False
        if self.con_reloj:
            return any(d == dia and self._verificar(i) for i, d in self._hechas.items())
        propio = self.semana.dias[id_mision]
        return any(self._verificar(i) and self.semana.dias[i] >= propio for i in self._hechas)

    # -- Cambios --

    def registrar_completada(self, id_mision, dia=None):
        if id_mision not in self._por_id or id_mision in self._hechas:
            return
        if dia is None:
            dia = self._dia if self.con_reloj else self.dia_abierto()
        self._hechas[id_mision] = dia
        if id_mision in self._caducadas:        # no debería pasar (la activa no caduca), pero nunca las dos cosas
            self._caducadas.remove(id_mision)

    def fijar_hora(self, hora):
        self._hora = None if hora is None else float(hora)

    # Pasa al día `dia` (1-7), de uno en uno: arrastra y caduca lo de cada día. `activa`: la misión en curso (nunca
    # caduca). True si el día cambió. Nunca vuelve atrás.
    def avanzar_a(self, dia, activa=None):
        if not _dia_valido(dia):
            raise ValueError(f"Día inválido para el reparto: {dia!r}; debe ser 1-{DIAS}.")
        if dia <= self._dia:
            return False
        while self._dia < dia:
            self._pasar_dia(activa)
        return True

    # Al pasar de día, además del arrastre: si la activa es una Fiscalía sin cerrar queda APLAZADA (quien la tiene la
    # suelta: SistemaMisiones.fijar_dia) y, mientras haya una aplazada abierta, las Fiscalías del día nuevo entran
    # aplazadas. Motivo (partida real, semilla 101): una Fiscalía ignorada como segunda del día 1 bloqueó la semana
    # entera; así ignorarla cuesta como mucho el resto de un día.
    def _pasar_dia(self, activa):
        dia = self._dia
        if activa in self._por_id and not self._verificar(activa) and not self._cerrada(activa) \
                and activa not in self._aplazadas:
            self._aplazadas.append(activa)
        en_curso = activa if (activa in self._por_id and self._verificar(activa) and not self._cerrada(activa)) else None
        nuevas = [en_curso] if en_curso is not None else []
        viejas = [i for i in self._arrastradas if not self._cerrada(i) and i != en_curso]
        candidatos = [i for i in self.semana.del_dia(dia)
                      if self._verificar(i) and not self._cerrada(i) and i != en_curso]
        reserva = self.semana.reservas.get(dia)
        if (reserva is not None and dia in self._reservas_abiertas and not self._cerrada(reserva)
                and reserva != en_curso):
            candidatos.append(reserva)
        candidatos.sort(key=lambda i: (0 if self._por_id[i].arco else 1, self._orden[i]))
        for id_mision in candidatos:
            if len(nuevas) < TOPE_ARRASTRE:
                nuevas.append(id_mision)
            else:
                self._caducadas.append(id_mision)
        self._caducadas.extend(viejas)
        self._arrastradas = nuevas
        self._dia = dia + 1
        if self._hay_aplazada_abierta():
            self._aplazadas += [i for i in self.semana.ids if not self._verificar(i) and not self._cerrada(i)
                                and self.semana.dias[i] <= self._dia and i not in self._aplazadas]

    # -- La semana --

    # ¿Queda algo por hacer en la semana? `puede(mision)` filtra quién puede hacerla (rol); por defecto, cualquiera.
    def queda_algo_en_la_semana(self, ocupadas=(), puede=None):
        puede = puede if puede is not None else (lambda _m: True)
        if any(puede(self._por_id[i]) for i in self.ids_semana() if not self._cerrada(i)):
            return True
        return any(puede(self._por_id[i]) for i in self.ofrecibles(ocupadas))

    # {"dia", "ofrecidas", "hechas", "pendientes", "arrastradas", "caducadas", "semana"} (contrato §5): ofrecidas,
    # hechas y pendientes son del día en curso; caducadas y semana, de toda la partida.
    def resumen(self):
        dia = self.dia
        if self.con_reloj:
            ofrecidas = self._grupo_del_dia()
        else:
            ofrecidas = [i for i in self.semana.del_dia(dia) if self._verificar(i)]
        ofrecidas += [i for i in self.semana.ids if not self._verificar(i) and self.semana.dias[i] <= dia
                      and self._hechas.get(i, dia) == dia]
        hechas = sum(1 for i in ofrecidas if i in self._hechas)
        pendientes = sum(1 for i in ofrecidas if not self._cerrada(i))
        return {"dia": dia, "ofrecidas": len(ofrecidas), "hechas": hechas, "pendientes": pendientes,
                "arrastradas": len(self._arrastradas), "caducadas": len(self._caducadas),
                "semana": len(self.ids_semana())}

    # -- Guardado (JSON) --

    def a_dict(self):
        semilla = self.semilla if isinstance(self.semilla, (int, str)) else str(self.semilla)
        return {"version": _VERSION, "semilla": semilla, "por_dia": self.por_dia, "con_reloj": self.con_reloj,
                "dia": self._dia, "hora": self._hora,
                "completadas": [[i, d] for i, d in self._hechas.items()],
                "caducadas": list(self._caducadas), "arrastradas": list(self._arrastradas),
                "reservas_abiertas": list(self._reservas_abiertas), "aplazadas": list(self._aplazadas)}

    # TOLERANTE con lo que se puede ignorar (ids que ya no están en el fondo, claves ausentes de un guardado viejo) y
    # ValueError si la forma es basura (quien restaura decide: SistemaMisiones vuelve a un reparto nuevo).
    @classmethod
    def desde_dict(cls, datos, fondo):
        if not isinstance(datos, dict):
            raise ValueError("Reparto por días guardado con formato desconocido.")
        semilla = datos.get("semilla")
        if isinstance(semilla, bool) or not isinstance(semilla, (int, str)):
            raise ValueError(f"Semilla del reparto inválida: {semilla!r}.")
        por_dia = datos.get("por_dia", POR_DIA)
        if isinstance(por_dia, bool) or not isinstance(por_dia, int) or por_dia < 1:
            raise ValueError(f"por_dia del reparto inválido: {por_dia!r}.")
        reparto = cls(fondo, semilla, por_dia, con_reloj=bool(datos.get("con_reloj", False)))
        dia = datos.get("dia", 1)
        if not _dia_valido(dia):
            raise ValueError(f"Día del reparto inválido: {dia!r}.")
        reparto._dia = dia
        hora = datos.get("hora")
        if hora is not None and (isinstance(hora, bool) or not isinstance(hora, (int, float))):
            raise ValueError(f"Hora del reparto inválida: {hora!r}.")
        reparto.fijar_hora(hora)
        conocido = reparto._por_id.__contains__
        for entrada in _lista(datos, "completadas"):
            id_mision, dia_hecha = (entrada[0], entrada[1]) if isinstance(entrada, (list, tuple)) and len(entrada) == 2 \
                else (entrada, 0)
            if isinstance(id_mision, str) and conocido(id_mision):
                reparto._hechas[id_mision] = dia_hecha if _dia_valido(dia_hecha) else 0
        reparto._caducadas = [i for i in _lista(datos, "caducadas")
                              if isinstance(i, str) and conocido(i) and i not in reparto._hechas]
        reparto._arrastradas = [i for i in _lista(datos, "arrastradas") if isinstance(i, str) and conocido(i)]
        reparto._reservas_abiertas = [d for d in _lista(datos, "reservas_abiertas") if _dia_valido(d)]
        reparto._aplazadas = [i for i in _lista(datos, "aplazadas")       # guardados anteriores: sin clave, ninguna
                              if isinstance(i, str) and conocido(i) and not reparto._verificar(i)]
        return reparto


def _lista(datos, clave):
    valor = datos.get(clave)
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ValueError(f"«{clave}» del reparto no es una lista: {valor!r}.")
    return valor
