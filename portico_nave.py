# SPDX-License-Identifier: GPL-3.0-or-later
# Pórtico de nave — extensión para IngeTrazo.
# (c) 2026 Donas Ingenieros (José María Martín García-Donas). Escrita con ayuda de IA (Claude).
"""Pórtico de nave — nave industrial paramétrica de pórticos a dos aguas.

Extensiones ▸ Pórtico de nave ▸ Nueva nave… genera, con un cuadro de
parámetros, una nave de pórticos metálicos a dos aguas:

* pilares y dinteles IPE / HEA / HEB, con cartelas de alero y de cumbrera
  (alma y ala inferior en chapa);
* correas C o Z conformadas, o IPE, repartidas por faldón con una
  separación máxima;
* canalón exterior en U;
* puente grúa opcional: ménsulas en los pilares y viga carril.

Organización del modelo (lo que muestra el Explorador):

* la nave es UN grupo contenedor; sus parámetros se guardan en
  ``group.ext["portico_nave"]``, viajan con las copias y con el .igz, y
  **Editar nave…** la vuelve a generar en el mismo sitio (aunque se haya
  movido o girado);
* cada pórtico es un COMPONENTE: los n pórticos comparten una única
  definición, y dentro de ella pilares, dinteles, cartelas y ménsulas son a
  su vez componentes (el pilar izquierdo y el derecho comparten geometría);
* correas, canalones y vigas carril van en grupos propios, cada pieza como
  instancia de un componente;
* etiquetas (capas) Estructura, Correas, Canalones y Puente grúa, y clases
  BIM IfcColumn / IfcBeam / IfcMember para la exportación IFC.

Coordenadas locales de la nave (metros): X a lo largo de la luz (0 = cara
exterior del pilar izquierdo), Y a lo largo de la nave (0 = primer pórtico),
Z vertical (0 = arranque de pilares).

Convenios geométricos:

* «Luz» es la distancia entre caras exteriores de pilares.
* «Altura de alero» es la cota de la cara superior del dintel en la cara
  exterior del pilar.
* La cota de la ménsula es la de su cara superior (apoyo de la viga carril);
  el vuelo se mide desde la cara interior del pilar al eje de la viga carril.
"""
from __future__ import annotations

import copy
import json
import logging
import math
from pathlib import Path

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.history import SnapshotImport

log = logging.getLogger("ingetrazo.plugins.portico_nave")

__version__ = "1.0"

KEY = Path(__file__).stem            # = ExtensionApp.key
TITLE = "Pórtico de nave"
STEEL = 7850.0                       # kg/m³

# ---------------------------------------------------------------------------
# Perfiles laminados (h, b, tw, tf en mm; peso en kg/m) — series europeas
# ---------------------------------------------------------------------------

_IPE = {80: (80, 46, 3.8, 5.2, 6.0), 100: (100, 55, 4.1, 5.7, 8.1),
        120: (120, 64, 4.4, 6.3, 10.4), 140: (140, 73, 4.7, 6.9, 12.9),
        160: (160, 82, 5.0, 7.4, 15.8), 180: (180, 91, 5.3, 8.0, 18.8),
        200: (200, 100, 5.6, 8.5, 22.4), 220: (220, 110, 5.9, 9.2, 26.2),
        240: (240, 120, 6.2, 9.8, 30.7), 270: (270, 135, 6.6, 10.2, 36.1),
        300: (300, 150, 7.1, 10.7, 42.2), 330: (330, 160, 7.5, 11.5, 49.1),
        360: (360, 170, 8.0, 12.7, 57.1), 400: (400, 180, 8.6, 13.5, 66.3),
        450: (450, 190, 9.4, 14.6, 77.6), 500: (500, 200, 10.2, 16.0, 90.7),
        550: (550, 210, 11.1, 17.2, 106.0), 600: (600, 220, 12.0, 19.0, 122.0)}
_HEA = {100: (96, 100, 5.0, 8.0, 16.7), 120: (114, 120, 5.0, 8.0, 19.9),
        140: (133, 140, 5.5, 8.5, 24.7), 160: (152, 160, 6.0, 9.0, 30.4),
        180: (171, 180, 6.0, 9.5, 35.5), 200: (190, 200, 6.5, 10.0, 42.3),
        220: (210, 220, 7.0, 11.0, 50.5), 240: (230, 240, 7.5, 12.0, 60.3),
        260: (250, 260, 7.5, 12.5, 68.2), 280: (270, 280, 8.0, 13.0, 76.4),
        300: (290, 300, 8.5, 14.0, 88.3), 320: (310, 300, 9.0, 15.5, 97.6),
        340: (330, 300, 9.5, 16.5, 105.0), 360: (350, 300, 10.0, 17.5, 112.0),
        400: (390, 300, 11.0, 19.0, 125.0), 450: (440, 300, 11.5, 21.0, 140.0),
        500: (490, 300, 12.0, 23.0, 155.0), 550: (540, 300, 12.5, 24.0, 166.0),
        600: (590, 300, 13.0, 25.0, 178.0)}
_HEB = {100: (100, 100, 6.0, 10.0, 20.4), 120: (120, 120, 6.5, 11.0, 26.7),
        140: (140, 140, 7.0, 12.0, 33.7), 160: (160, 160, 8.0, 13.0, 42.6),
        180: (180, 180, 8.5, 14.0, 51.2), 200: (200, 200, 9.0, 15.0, 61.3),
        220: (220, 220, 9.5, 16.0, 71.5), 240: (240, 240, 10.0, 17.0, 83.2),
        260: (260, 260, 10.0, 17.5, 93.0), 280: (280, 280, 10.5, 18.0, 103.0),
        300: (300, 300, 11.0, 19.0, 117.0), 320: (320, 300, 11.5, 20.5, 127.0),
        340: (340, 300, 12.0, 21.5, 134.0), 360: (360, 300, 12.5, 22.5, 142.0),
        400: (400, 300, 13.5, 24.0, 155.0), 450: (450, 300, 14.0, 26.0, 171.0),
        500: (500, 300, 14.5, 28.0, 187.0), 550: (550, 300, 15.0, 29.0, 199.0),
        600: (600, 300, 15.5, 30.0, 212.0)}

PROFILES: dict[str, tuple] = {}
for _serie, _tabla in (("IPE", _IPE), ("HEA", _HEA), ("HEB", _HEB)):
    for _n, (_h, _b, _tw, _tf, _kg) in _tabla.items():
        PROFILES[f"{_serie} {_n}"] = (_h / 1000, _b / 1000, _tw / 1000, _tf / 1000, _kg)
PROFILE_NAMES = list(PROFILES)

PURLIN_TYPES = [("C", "C conformada"), ("Z", "Z conformada"), ("IPE", "IPE laminado")]

DEFAULTS = {
    # Geometría
    "luz": 16.0, "alero": 8.0, "pendiente": 10.0,       # pendiente en %
    "n_porticos": 5, "separacion": 5.0,
    # Pilares y dinteles
    "pilar": "HEA 300", "dintel": "IPE 360",
    # Cartelas (0 = sin cartela)
    "cart_alero_l": 1.60, "cart_alero_h": 0.36,
    "cart_cumb_l": 0.80, "cart_cumb_h": 0.20,
    # Correas
    "correa_tipo": "C", "correa_h": 0.200, "correa_b": 0.070,
    "correa_e": 0.0025, "correa_c": 0.020, "correa_ipe": "IPE 140",
    "correa_sep": 1.50, "correa_d_alero": 0.15, "correa_d_cumbrera": 0.15,
    "correa_vuelo": 0.0,
    # Canalón
    "canalon": True, "canalon_a": 0.30, "canalon_h": 0.20, "canalon_e": 0.002,
    # Puente grúa
    "grua": True, "mensula": "HEA 200", "mensula_z": 6.60, "mensula_vuelo": 0.40,
    "viga_carril": "HEB 240",
}

LAYERS = {"est": "Estructura", "cor": "Correas", "can": "Canalones", "pg": "Puente grúa"}
MATS = {"est": ("Acero estructural", (0.36, 0.42, 0.50)),
        "cor": ("Acero correas", (0.72, 0.62, 0.30)),
        "can": ("Chapa canalón", (0.80, 0.80, 0.82)),
        "pg": ("Acero puente grúa", (0.80, 0.45, 0.15))}


class NaveError(Exception):
    """Rechazo comprensible para el usuario (parámetros incoherentes)."""


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def normalize(params) -> dict:
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (params or {}).items() if k in DEFAULTS})
    for k, v in DEFAULTS.items():
        if isinstance(v, bool):
            p[k] = bool(p[k])
        elif isinstance(v, int):
            p[k] = int(p[k])
        elif isinstance(v, float):
            p[k] = float(p[k])
    for k in ("pilar", "dintel", "correa_ipe", "mensula", "viga_carril"):
        if p[k] not in PROFILES:
            p[k] = DEFAULTS[k]
    if p["correa_tipo"] not in {c for c, _ in PURLIN_TYPES}:
        p["correa_tipo"] = "C"
    return p


class Geo:
    """Magnitudes derivadas de los parámetros (todas en metros)."""

    def __init__(self, p: dict) -> None:
        self.p = p
        if p["luz"] <= 0 or p["alero"] <= 0:
            raise NaveError("La luz y la altura de alero deben ser positivas.")
        if p["n_porticos"] < 1:
            raise NaveError("Debe haber al menos un pórtico.")
        if p["n_porticos"] > 1 and p["separacion"] <= 0:
            raise NaveError("La separación entre pórticos debe ser positiva.")
        if not 0.0 <= p["pendiente"] < 100.0:
            raise NaveError("La pendiente debe estar entre 0 % y 100 %.")
        self.L = p["luz"]
        self.H = p["alero"]
        self.t = p["pendiente"] / 100.0
        self.a = math.atan(self.t)
        self.ca, self.sa = math.cos(self.a), math.sin(self.a)
        self.hp, self.bp, self.twp, self.tfp, self.kgp = PROFILES[p["pilar"]]
        self.hd, self.bd, self.twd, self.tfd, self.kgd = PROFILES[p["dintel"]]
        self.n = p["n_porticos"]
        self.s = p["separacion"] if self.n > 1 else 0.0
        self.Ln = (self.n - 1) * self.s
        self.hv = self.hd / self.ca          # canto del dintel en vertical
        if 2 * self.hp >= self.L:
            raise NaveError("Los pilares no caben en la luz indicada.")
        if self.H - self.hv - self.hp * self.t <= 0.5:
            raise NaveError("La altura de alero es insuficiente para el dintel elegido.")
        # Cabeza de pilar: cara inferior del dintel en la cara interior del pilar.
        self.Hp = self.z_under(self.hp)
        self.Lslope = (self.L / 2) / self.ca

    def z_top(self, x: float) -> float:
        """Cota de la cara superior del dintel izquierdo en la abscisa x."""
        return self.H + x * self.t

    def z_under(self, x: float) -> float:
        return self.H - self.hv + x * self.t

    def z_under_cartela(self, x: float) -> float:
        """Cota inferior del conjunto dintel + cartela de alero en x (lado izq.)."""
        p = self.p
        z = self.z_under(x)
        Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
        x0 = self.hp
        if Lc > 0 and hc > 0 and x0 <= x <= x0 + Lc:
            z -= hc * (1 - (x - x0) / Lc)
        return z

    def purlin_section(self) -> tuple:
        """(polígono (u, w), peso kg/m, canto) de la correa; w = 0 apoyo."""
        p = self.p
        if p["correa_tipo"] == "IPE":
            h, b, tw, tf, kg = PROFILES[p["correa_ipe"]]
            poly = [(u, w + h / 2) for u, w in i_section(h, b, tw, tf)]
            return poly, kg, h
        h, b, e, c = p["correa_h"], p["correa_b"], p["correa_e"], p["correa_c"]
        if min(h, b, e) <= 0 or 2 * e >= min(h, b) or c < 0 or c >= h / 2:
            raise NaveError("Dimensiones de correa incoherentes.")
        poly = c_section(h, b, e, c) if p["correa_tipo"] == "C" else z_section(h, b, e, c)
        return poly, polygon_area(poly) * STEEL, h

    def purlin_positions(self) -> list[float]:
        """Distancias, medidas sobre el faldón desde el alero, de cada correa."""
        p = self.p
        a0 = max(0.0, p["correa_d_alero"])
        a1 = self.Lslope - max(0.0, p["correa_d_cumbrera"])
        if a1 <= a0:
            return [a0]
        smax = p["correa_sep"]
        if smax <= 0:
            raise NaveError("La separación máxima de correas debe ser positiva.")
        k = max(1, math.ceil((a1 - a0) / smax - 1e-9))
        return [a0 + i * (a1 - a0) / k for i in range(k + 1)]

    def crane_check(self) -> list[str]:
        """Avisos de interferencia del puente grúa con dintel y cartela."""
        p = self.p
        if not p["grua"]:
            return []
        out = []
        hm = PROFILES[p["mensula"]][0]
        hvc, bvc = PROFILES[p["viga_carril"]][:2]
        x = self.hp + p["mensula_vuelo"]
        top_vc = p["mensula_z"] + hvc
        free = min(self.z_under_cartela(x - bvc / 2), self.z_under_cartela(x + bvc / 2))
        if top_vc > free - 1e-6:
            out.append(f"La viga carril (cara superior a {top_vc:.3f} m) interfiere con el "
                       f"dintel o la cartela (cara inferior a {free:.3f} m en su vertical).")
        if p["mensula_z"] - hm <= 0:
            out.append("La ménsula queda por debajo del arranque del pilar.")
        if p["mensula_vuelo"] <= bvc / 2:
            out.append("El vuelo de la ménsula es menor que la semianchura de la viga carril.")
        if x + bvc / 2 >= self.L / 2:
            out.append("La viga carril sobrepasa el eje de la nave.")
        return out


# ---------------------------------------------------------------------------
# Secciones (polígonos 2D: u horizontal, w vertical)
# ---------------------------------------------------------------------------

def i_section(h, b, tw, tf):
    """Doble T centrada en el origen; w a lo largo del canto."""
    hb, hh, ht = b / 2, h / 2, tw / 2
    return [(-hb, -hh), (hb, -hh), (hb, -hh + tf), (ht, -hh + tf), (ht, hh - tf),
            (hb, hh - tf), (hb, hh), (-hb, hh), (-hb, hh - tf), (-ht, hh - tf),
            (-ht, -hh + tf), (-hb, -hh + tf)]


def c_section(h, b, e, c):
    """C con labios; alma centrada en u = 0 (el ala va hacia +u). w = 0 apoyo."""
    if c > e:
        pts = [(0, 0), (b, 0), (b, c), (b - e, c), (b - e, e), (e, e), (e, h - e),
               (b - e, h - e), (b - e, h - c), (b, h - c), (b, h), (0, h)]
    else:
        pts = [(0, 0), (b, 0), (b, e), (e, e), (e, h - e), (b, h - e), (b, h), (0, h)]
    return [(u - e / 2, w) for u, w in pts]


def z_section(h, b, e, c):
    """Z con labios; ala inferior hacia +u, superior hacia −u. w = 0 apoyo."""
    q = e / 2
    if c > e:
        return [(-q, 0), (b - q, 0), (b - q, c), (b - 3 * q, c), (b - 3 * q, e), (q, e),
                (q, h), (-(b - q), h), (-(b - q), h - c), (-(b - 3 * q), h - c),
                (-(b - 3 * q), h - e), (-q, h - e)]
    return [(-q, 0), (b - q, 0), (b - q, e), (q, e), (q, h), (-(b - q), h),
            (-(b - q), h - e), (-q, h - e)]


def u_section(a, h, e):
    """Canalón en U, boca arriba; u de 0 a a, w de 0 a h."""
    return [(0, 0), (a, 0), (a, h), (a - e, h), (a - e, e), (e, e), (e, h), (0, h)]


def polygon_area(poly) -> float:
    s = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


# ---------------------------------------------------------------------------
# Mallas
# ---------------------------------------------------------------------------

def _newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % len(pts)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _add_face(mesh, pts, attrs):
    f = mesh.add_face([QVector3D(*q) for q in pts])
    f.attrs = copy.deepcopy(attrs)
    return f


def prism(mesh, cap, ext, attrs) -> None:
    """Sólido cerrado: polígono plano ``cap`` (puntos 3D) barrido por el
    vector ``ext``. Todas las normales hacia fuera."""
    n = _newell(cap)
    if n[0] * ext[0] + n[1] * ext[1] + n[2] * ext[2] < 0:
        cap = list(reversed(cap))
    top = [(q[0] + ext[0], q[1] + ext[1], q[2] + ext[2]) for q in cap]
    _add_face(mesh, list(reversed(cap)), attrs)
    _add_face(mesh, top, attrs)
    k = len(cap)
    for i in range(k):
        a, b = cap[i], cap[(i + 1) % k]
        _add_face(mesh, [a, b, top[(i + 1) % k], top[i]], attrs)


def _mesh():
    from core.mesh import Mesh
    return Mesh()


def _group(mesh, name, xform=None, component=True, layer=None, ifc=None):
    from core.group import Group
    g = Group(mesh, name=name)
    g.xform = QMatrix4x4(xform) if xform is not None else QMatrix4x4()
    g.component = component
    g.layer = layer
    if ifc:
        g.ifc = {"class": ifc, "name": name}
    return g


def _container(name, children, layer=None):
    from core.group import Group
    g = Group(name=name)
    g.adopt(children)
    g.component = False
    g.layer = layer
    return g


def _T(x=0.0, y=0.0, z=0.0) -> QMatrix4x4:
    m = QMatrix4x4()
    m.translate(QVector3D(x, y, z))
    return m


def _rot_about_center(cx, cy) -> QMatrix4x4:
    """Giro de 180° alrededor del eje vertical que pasa por (cx, cy):
    lleva el lado izquierdo de la nave al derecho."""
    m = QMatrix4x4()
    m.translate(QVector3D(cx, cy, 0))
    m.rotate(180.0, 0, 0, 1)
    m.translate(QVector3D(-cx, -cy, 0))
    return m


# ---------------------------------------------------------------------------
# Construcción de la nave
# ---------------------------------------------------------------------------

def _paint(scene, key) -> dict:
    from core.materials import Material
    name, rgb = MATS[key]
    if name not in scene.materials:
        scene.materials[name] = Material(name, color=rgb)
    return scene.materials[name].face_attrs()


def _ensure_layers(scene, keys) -> None:
    from core.layers import Layer
    have = {ly.name for ly in scene.layers}
    for k in keys:
        if LAYERS[k] not in have:
            scene.layers.append(Layer(LAYERS[k]))


def _haunch(mesh, web_pts_xz, tw, b, tf, under_a, under_b, attrs):
    """Cartela soldada: alma (polígono en XZ, espesor tw) y ala inferior
    (chapa b × tf siguiendo el borde inferior under_a → under_b)."""
    prism(mesh, [(x, -tw / 2, z) for x, z in web_pts_xz], (0, tw, 0), attrs)
    (xa, za), (xb, zb) = under_a, under_b
    flange = [(xa, za), (xb, zb), (xb, zb - tf), (xa, za - tf)]
    prism(mesh, [(x, -b / 2, z) for x, z in flange], (0, b, 0), attrs)


def build_nave(scene, params) -> list:
    """Hijos del contenedor de la nave, en coordenadas locales de la nave."""
    p = normalize(params)
    g = Geo(p)
    est = _paint(scene, "est")
    lay_est = LAYERS["est"]
    L, t = g.L, g.t
    R = _rot_about_center(L / 2, g.Ln / 2)
    R0 = _rot_about_center(L / 2, 0.0)        # dentro de la definición del pórtico

    # --- Pilar: doble T, canto según X (plano del pórtico), de z = 0 a Hp
    m_pil = _mesh()
    prism(m_pil, [(w, u, 0.0) for u, w in i_section(g.hp, g.bp, g.twp, g.tfp)],
          (0, 0, g.Hp), est)
    pil_l = _group(m_pil, "Pilar izquierdo", _T(g.hp / 2), layer=lay_est, ifc="IfcColumn")
    pil_r = _group(m_pil, "Pilar derecho", _T(L - g.hp / 2), layer=lay_est, ifc="IfcColumn")

    # --- Dintel izquierdo: corte a plomo en x = 0 y en la cumbrera
    zc = g.H - g.hv / 2                    # eje del dintel en x = 0
    m_din = _mesh()
    prism(m_din, [(0.0, u, zc + w / g.ca) for u, w in i_section(g.hd, g.bd, g.twd, g.tfd)],
          (L / 2, 0, (L / 2) * t), est)
    din_l = _group(m_din, "Dintel izquierdo", None, layer=lay_est, ifc="IfcBeam")
    din_r = _group(m_din, "Dintel derecho", R0, layer=lay_est, ifc="IfcBeam")
    parts = [pil_l, pil_r, din_l, din_r]

    # --- Cartela de alero (bajo el dintel, junto a la cara interior del pilar)
    Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
    if Lc > 0 and hc > 0:
        x0, x1 = g.hp, g.hp + Lc
        A = (x0, g.z_under(x0) - hc)
        B = (x1, g.z_under(x1))
        m_ca = _mesh()
        _haunch(m_ca, [(x0, g.z_under(x0)), B, A], g.twd, g.bd, g.tfd, A, B, est)
        parts += [_group(m_ca, "Cartela de alero izquierda", None, layer=lay_est, ifc="IfcMember"),
                  _group(m_ca, "Cartela de alero derecha", R0, layer=lay_est, ifc="IfcMember")]

    # --- Cartela de cumbrera (una pieza bajo los dos dinteles)
    Lk, hk = p["cart_cumb_l"], p["cart_cumb_h"]
    if Lk > 0 and hk > 0:
        xm = L / 2
        zr = g.z_under(xm)
        P0 = (xm - Lk, g.z_under(xm - Lk))
        Pb = (xm, zr - hk)
        P1 = (xm + Lk, g.z_under(xm - Lk))
        m_ck = _mesh()
        prism(m_ck, [(x, -g.twd / 2, z) for x, z in [P0, (xm, zr), P1, Pb]], (0, g.twd, 0), est)
        for a, b in ((P0, Pb), (Pb, P1)):
            (xa, za), (xb, zb) = a, b
            prism(m_ck, [(x, -g.bd / 2, z) for x, z in
                         [(xa, za), (xb, zb), (xb, zb - g.tfd), (xa, za - g.tfd)]],
                  (0, g.bd, 0), est)
        parts.append(_group(m_ck, "Cartela de cumbrera", None, layer=lay_est, ifc="IfcMember"))

    # --- Ménsulas del puente grúa (forman parte del pórtico)
    if p["grua"]:
        hm, bm, twm, tfm, _kg = PROFILES[p["mensula"]]
        bvc = PROFILES[p["viga_carril"]][1]
        Lm = p["mensula_vuelo"] + bvc / 2
        zm = p["mensula_z"] - hm / 2
        m_me = _mesh()
        prism(m_me, [(g.hp, u, zm + w) for u, w in i_section(hm, bm, twm, tfm)], (Lm, 0, 0),
              _paint(scene, "pg"))
        parts += [_group(m_me, "Ménsula izquierda", None, layer=LAYERS["pg"], ifc="IfcMember"),
                  _group(m_me, "Ménsula derecha", R0, layer=LAYERS["pg"], ifc="IfcMember")]

    # --- Pórticos: una definición y n instancias
    from core.group import Group, copy_group
    porticos = []
    first = Group(name="Pórtico 1")
    first.adopt(parts)
    first.component = True
    first.layer = lay_est
    porticos.append(first)
    for i in range(1, g.n):
        c = copy_group(first, delta=QVector3D(0, i * g.s, 0))
        c.name = f"Pórtico {i + 1}"
        porticos.append(c)
    out = list(porticos)

    # --- Correas
    poly, _kg, _h = g.purlin_section()
    v = p["correa_vuelo"]
    Lco = g.Ln + 2 * v
    if Lco > 0:
        m_co = _mesh()
        prism(m_co, [(u, -v, w) for u, w in poly], (0, Lco, 0), _paint(scene, "cor"))
        inst = []
        for k, a in enumerate(g.purlin_positions(), 1):
            M = _T(a * g.ca, 0, g.H + a * g.sa)
            M.rotate(-math.degrees(g.a), 0, 1, 0)
            inst.append(_group(m_co, f"Correa I-{k}", M, layer=LAYERS["cor"], ifc="IfcMember"))
            inst.append(_group(m_co, f"Correa D-{k}", R * M, layer=LAYERS["cor"], ifc="IfcMember"))
        out.append(_container("Correas", inst, LAYERS["cor"]))

    # --- Canalones (exteriores, boca arriba, borde superior a cota de alero)
    if p["canalon"] and Lco > 0:
        a, h, e = p["canalon_a"], p["canalon_h"], p["canalon_e"]
        if min(a, h, e) <= 0 or 2 * e >= min(a, h):
            raise NaveError("Dimensiones de canalón incoherentes.")
        m_cn = _mesh()
        prism(m_cn, [(-a + u, -v, g.H - h + w) for u, w in u_section(a, h, e)], (0, Lco, 0),
              _paint(scene, "can"))
        out.append(_container("Canalones", [
            _group(m_cn, "Canalón izquierdo", None, layer=LAYERS["can"]),
            _group(m_cn, "Canalón derecho", R, layer=LAYERS["can"])], LAYERS["can"]))

    # --- Vigas carril
    if p["grua"] and g.Ln > 0:
        hvc, bvc, twv, tfv, _kg = PROFILES[p["viga_carril"]]
        xv = g.hp + p["mensula_vuelo"]
        m_vc = _mesh()
        prism(m_vc, [(xv + u, 0.0, p["mensula_z"] + hvc / 2 + w)
                     for u, w in i_section(hvc, bvc, twv, tfv)], (0, g.Ln, 0), _paint(scene, "pg"))
        out.append(_container("Puente grúa", [
            _group(m_vc, "Viga carril izquierda", None, layer=LAYERS["pg"], ifc="IfcBeam"),
            _group(m_vc, "Viga carril derecha", R, layer=LAYERS["pg"], ifc="IfcBeam")],
            LAYERS["pg"]))
    keys = ["est", "cor"] + (["can"] if p["canalon"] else []) + (["pg"] if p["grua"] else [])
    _ensure_layers(scene, keys)
    return out


# ---------------------------------------------------------------------------
# Medición de acero
# ---------------------------------------------------------------------------

def measurement(params) -> list[tuple]:
    """Filas (elemento, perfil, unidades, longitud unitaria m, kg/m, kg total).
    Pesos nominales de catálogo; cartelas como chapa (alma + ala)."""
    p = normalize(params)
    g = Geo(p)
    n = g.n
    rows = [("Pilares", p["pilar"], 2 * n, g.Hp, g.kgp),
            ("Dinteles", p["dintel"], 2 * n, g.Lslope, g.kgd)]
    Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
    if Lc > 0 and hc > 0:
        kg = (Lc * hc / 2 * g.twd + math.hypot(Lc, hc + Lc * g.t) * g.bd * g.tfd) * STEEL
        rows.append(("Cartelas de alero", f"chapa e={g.twd*1000:.1f}/{g.tfd*1000:.1f} mm",
                     2 * n, Lc, kg / Lc))
    Lk, hk = p["cart_cumb_l"], p["cart_cumb_h"]
    if Lk > 0 and hk > 0:
        kg = (Lk * hk * g.twd + 2 * math.hypot(Lk, hk - Lk * g.t) * g.bd * g.tfd) * STEEL
        rows.append(("Cartelas de cumbrera", f"chapa e={g.twd*1000:.1f}/{g.tfd*1000:.1f} mm",
                     n, 2 * Lk, kg / (2 * Lk)))
    _poly, kgc, _h = g.purlin_section()
    Lco = g.Ln + 2 * p["correa_vuelo"]
    if Lco > 0:
        name = (p["correa_ipe"] if p["correa_tipo"] == "IPE" else
                f"{p['correa_tipo']} {p['correa_h']*1000:.0f}×{p['correa_b']*1000:.0f}×"
                f"{p['correa_e']*1000:.1f}")
        rows.append(("Correas", name, 2 * len(g.purlin_positions()), Lco, kgc))
    if p["canalon"] and Lco > 0:
        kg = polygon_area(u_section(p["canalon_a"], p["canalon_h"], p["canalon_e"])) * STEEL
        rows.append(("Canalones", f"U {p['canalon_a']*1000:.0f}×{p['canalon_h']*1000:.0f}×"
                     f"{p['canalon_e']*1000:.1f}", 2, Lco, kg))
    if p["grua"]:
        bvc = PROFILES[p["viga_carril"]][1]
        rows.append(("Ménsulas", p["mensula"], 2 * n, p["mensula_vuelo"] + bvc / 2,
                     PROFILES[p["mensula"]][4]))
        if g.Ln > 0:
            rows.append(("Vigas carril", p["viga_carril"], 2, g.Ln, PROFILES[p["viga_carril"]][4]))
    return [(e, prof, u, l, kgm, u * l * kgm) for e, prof, u, l, kgm in rows]


def summary(params) -> str:
    p = normalize(params)
    g = Geo(p)
    kg = sum(r[5] for r in measurement(p))
    return (f"Nave {g.L:.2f} × {g.Ln:.2f} m · {g.n} pórticos · "
            f"{len(g.purlin_positions())} correas por faldón · acero ≈ {kg:,.0f} kg"
            ).replace(",", ".")


# ---------------------------------------------------------------------------
# Operaciones sobre el documento
# ---------------------------------------------------------------------------

def nave_data(group):
    ext = getattr(group, "ext", None) or {}
    return ext.get(KEY)


def _next_name(scene) -> str:
    used = {gr.name for gr in scene.groups}
    i = 1
    while f"Nave {i}" in used:
        i += 1
    return f"Nave {i}"


def make_nave(scene, params, name=None, xform=None, index=None, layer=None, uid=None):
    """Crea el contenedor de la nave y lo añade al documento."""
    p = normalize(params)
    children = build_nave(scene, p)          # lanza NaveError antes de tocar nada
    c = _container(name or _next_name(scene), children, layer)
    if xform is not None:
        c.xform = QMatrix4x4(xform)
    if uid:
        c.uid = uid
    c.ext = {KEY: {"params": json.loads(json.dumps(p))}}
    if index is None:
        scene.groups.append(c)
    else:
        scene.groups.insert(index, c)
    return c


def rebuild_nave(scene, group, params):
    """Sustituye la nave por otra con nuevos parámetros, en el mismo lugar."""
    if nave_data(group) is None:
        raise NaveError(f"«{group.name}» no es una nave de {TITLE}.")
    idx = scene.groups.index(group)
    scene.groups.remove(group)
    scene.selection.discard(group)
    return make_nave(scene, params, name=group.name, xform=group.xform, index=idx,
                     layer=group.layer, uid=group.uid)


def _run(viewport, mutate, ok) -> bool:
    hist = viewport.history
    hist.execute(SnapshotImport(mutate))
    err = getattr(hist, "last_error", None)
    if err:
        _warn(viewport, str(err).split(": ", 1)[-1])
        return False
    notify = getattr(viewport, "notify_scene_changed", None)
    if callable(notify):
        notify()
    viewport.update()
    viewport.flash_status(ok, 4000)
    return True


def _selected_naves(scene):
    out = []
    for e in scene.selection:
        gr = getattr(e, "owner", None) or e
        if gr in scene.groups and nave_data(gr) is not None and gr not in out:
            out.append(gr)
    return out


def _last_params(scene) -> dict:
    data = getattr(scene, "plugin_data", None) or {}
    return normalize((data.get(KEY) or {}).get("last"))


def _remember(scene, p) -> None:
    data = getattr(scene, "plugin_data", None)
    if data is not None:
        data.setdefault(KEY, {})["last"] = json.loads(json.dumps(p))


def nueva(viewport) -> None:
    scene = viewport.scene
    if getattr(scene, "edit_group", None) is not None:
        _warn(viewport, "Cierre el grupo que está editando y vuelva a ejecutar la orden.")
        return
    p = NaveDialog.ask(viewport, _last_params(scene), "Nueva nave")
    if p is None:
        return

    def mutate(sc):
        _remember(sc, p)
        c = make_nave(sc, p)
        sc.selection.clear()
        sc.selection.add(c)
    _run(viewport, mutate, f"{TITLE}: nave creada. " + summary(p))


def editar(viewport) -> None:
    scene = viewport.scene
    naves = _selected_naves(scene)
    if not naves:
        _warn(viewport, "Seleccione una nave creada con Pórtico de nave.")
        return
    nave = naves[0]
    p = NaveDialog.ask(viewport, normalize(nave_data(nave).get("params")),
                       f"Editar — {nave.name}")
    if p is None:
        return

    def mutate(sc):
        _remember(sc, p)
        c = rebuild_nave(sc, nave, p)
        sc.selection.clear()
        sc.selection.add(c)
    _run(viewport, mutate, f"{TITLE}: «{nave.name}» actualizada. " + summary(p))


def medicion(viewport) -> None:
    scene = viewport.scene
    naves = _selected_naves(scene)
    if not naves:
        _warn(viewport, "Seleccione una nave creada con Pórtico de nave.")
        return
    MeasureDialog.show_for(viewport, naves[0])


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------

def _warn(viewport, text) -> None:
    from PySide6.QtWidgets import QMessageBox
    try:
        viewport.flash_status(f"{TITLE}: " + text.splitlines()[0], 6000)
    except Exception:  # noqa: BLE001
        pass
    QMessageBox.warning(viewport.window(), TITLE, text)


class NaveDialog:
    """Cuadro de parámetros, por pestañas, con avisos en vivo."""

    @classmethod
    def ask(cls, viewport, params, title):
        from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                       QDoubleSpinBox, QFormLayout, QLabel, QSpinBox,
                                       QTabWidget, QVBoxLayout, QWidget)
        p0 = normalize(params)
        dlg = QDialog(viewport.window())
        dlg.setWindowTitle(f"{TITLE} — {title}")
        dlg.setMinimumWidth(620)
        lay = QVBoxLayout(dlg)
        tabs = QTabWidget()
        lay.addWidget(tabs)
        w: dict = {}

        def page(name):
            pg = QWidget()
            form = QFormLayout(pg)
            tabs.addTab(pg, name)
            return form

        def length(form, key, label, lo=0.0, hi=200.0, dec=3, step=0.05, suffix=" m"):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(dec)
            sb.setSingleStep(step)
            sb.setSuffix(suffix)
            sb.setValue(p0[key])
            form.addRow(label, sb)
            w[key] = sb
            return sb

        def mm(form, key, label, hi=1000.0, dec=1):
            sb = QDoubleSpinBox()
            sb.setRange(0.0, hi)
            sb.setDecimals(dec)
            sb.setSuffix(" mm")
            sb.setValue(p0[key] * 1000)
            sb.setProperty("mm", True)
            form.addRow(label, sb)
            w[key] = sb
            return sb

        def profile(form, key, label, series=("IPE", "HEA", "HEB")):
            cb = QComboBox()
            cb.addItems([n for n in PROFILE_NAMES if n.split()[0] in series])
            cb.setCurrentText(p0[key])
            form.addRow(label, cb)
            w[key] = cb
            return cb

        def check(form, key, label):
            cb = QCheckBox(label)
            cb.setChecked(p0[key])
            form.addRow(cb)
            w[key] = cb
            return cb

        f = page("Geometría")
        length(f, "luz", "Luz (caras exteriores de pilares)", 2.0, 100.0)
        length(f, "alero", "Altura de alero (cara superior del dintel)", 1.0, 50.0)
        length(f, "pendiente", "Pendiente", 0.0, 99.0, 2, 1.0, " %")
        sp = QSpinBox()
        sp.setRange(1, 200)
        sp.setValue(p0["n_porticos"])
        f.addRow("Número de pórticos", sp)
        w["n_porticos"] = sp
        length(f, "separacion", "Separación entre pórticos", 0.5, 30.0)

        f = page("Pilares y dinteles")
        profile(f, "pilar", "Perfil de pilares")
        profile(f, "dintel", "Perfil de dinteles")
        length(f, "cart_alero_l", "Cartela de alero: longitud", 0.0, 10.0)
        length(f, "cart_alero_h", "Cartela de alero: canto", 0.0, 3.0)
        length(f, "cart_cumb_l", "Cartela de cumbrera: semilongitud", 0.0, 10.0)
        length(f, "cart_cumb_h", "Cartela de cumbrera: canto", 0.0, 3.0)
        f.addRow(QLabel("Longitud o canto 0 = sin cartela."))

        f = page("Correas")
        tipo = QComboBox()
        for code, label in PURLIN_TYPES:
            tipo.addItem(label, code)
        tipo.setCurrentIndex([c for c, _ in PURLIN_TYPES].index(p0["correa_tipo"]))
        f.addRow("Tipo", tipo)
        w["correa_tipo"] = tipo
        conf = [mm(f, "correa_h", "Canto"), mm(f, "correa_b", "Ala"),
                mm(f, "correa_e", "Espesor", 20.0, 2), mm(f, "correa_c", "Labio")]
        ipe = profile(f, "correa_ipe", "Perfil IPE", ("IPE",))
        length(f, "correa_sep", "Separación máxima", 0.3, 5.0)
        length(f, "correa_d_alero", "Distancia al alero (sobre faldón)", 0.0, 3.0)
        length(f, "correa_d_cumbrera", "Distancia a la cumbrera (sobre faldón)", 0.0, 3.0)
        length(f, "correa_vuelo", "Vuelo sobre los pórticos extremos", 0.0, 3.0)

        def sync_tipo():
            is_ipe = tipo.currentData() == "IPE"
            for sb in conf:
                sb.setEnabled(not is_ipe)
            ipe.setEnabled(is_ipe)
        tipo.currentIndexChanged.connect(lambda _i: sync_tipo())
        sync_tipo()

        f = page("Canalón")
        cn = check(f, "canalon", "Canalón exterior en U")
        cn_w = [mm(f, "canalon_a", "Anchura"), mm(f, "canalon_h", "Altura"),
                mm(f, "canalon_e", "Espesor de chapa", 20.0, 2)]
        cn.toggled.connect(lambda on: [x.setEnabled(on) for x in cn_w])
        for x in cn_w:
            x.setEnabled(cn.isChecked())

        f = page("Puente grúa")
        pg = check(f, "grua", "Ménsulas y viga carril de puente grúa")
        pg_w = [profile(f, "mensula", "Perfil de ménsula"),
                length(f, "mensula_z", "Cota de apoyo (cara superior de ménsula)", 0.5, 50.0),
                length(f, "mensula_vuelo", "Vuelo (cara interior del pilar a eje de viga carril)",
                       0.05, 3.0),
                profile(f, "viga_carril", "Perfil de viga carril")]
        pg.toggled.connect(lambda on: [x.setEnabled(on) for x in pg_w])
        for x in pg_w:
            x.setEnabled(pg.isChecked())

        info = QLabel()
        info.setWordWrap(True)
        lay.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(buttons)

        def read() -> dict:
            out = {}
            for k, wd in w.items():
                if isinstance(wd, QCheckBox):
                    out[k] = wd.isChecked()
                elif isinstance(wd, QSpinBox):
                    out[k] = wd.value()
                elif isinstance(wd, QDoubleSpinBox):
                    out[k] = wd.value() / 1000 if wd.property("mm") else wd.value()
                elif k == "correa_tipo":
                    out[k] = wd.currentData()
                else:
                    out[k] = wd.currentText()
            return normalize(out)

        def refresh(*_a):
            try:
                p = read()
                msgs = Geo(p).crane_check()
                text = summary(p)
                if msgs:
                    text += "<br><span style='color:#c0392b'>⚠ " + "<br>⚠ ".join(msgs) + "</span>"
                info.setText(text)
            except NaveError as exc:
                info.setText(f"<span style='color:#c0392b'>⚠ {exc}</span>")

        for wd in w.values():
            for sig in ("valueChanged", "currentIndexChanged", "toggled"):
                if hasattr(wd, sig):
                    getattr(wd, sig).connect(refresh)
                    break
        refresh()
        result = {}

        def accept():
            from PySide6.QtWidgets import QMessageBox
            try:
                p = read()
                g = Geo(p)
                g.purlin_section()
                msgs = g.crane_check()
            except NaveError as exc:
                QMessageBox.warning(dlg, TITLE, str(exc))
                return
            if msgs and QMessageBox.question(
                    dlg, TITLE, "\n".join(msgs) + "\n\n¿Generar la nave de todos modos?"
            ) != QMessageBox.Yes:
                return
            result.update(p)
            dlg.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return None
        return result


class MeasureDialog:
    """Medición de acero de la nave, con copia al portapapeles (TSV)."""

    @classmethod
    def show_for(cls, viewport, nave):
        from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHeaderView,
                                       QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout)
        try:
            rows = measurement(nave_data(nave).get("params"))
        except NaveError as exc:
            _warn(viewport, str(exc))
            return
        dlg = QDialog(viewport.window())
        dlg.setWindowTitle(f"{TITLE} — Medición de acero — {nave.name}")
        lay = QVBoxLayout(dlg)
        heads = ["Elemento", "Perfil", "Ud.", "Long. unit. (m)", "kg/m", "Total (kg)"]
        tbl = QTableWidget(len(rows) + 1, len(heads))
        tbl.setHorizontalHeaderLabels(heads)
        fmt = lambda v, d: f"{v:,.{d}f}".replace(",", " ").replace(".", ",")  # noqa: E731
        lines = ["\t".join(heads)]
        for i, (e, prof, u, l, kgm, kg) in enumerate(rows):
            vals = [e, prof, str(u), fmt(l, 3), fmt(kgm, 2), fmt(kg, 1)]
            lines.append("\t".join(vals))
            for j, v in enumerate(vals):
                tbl.setItem(i, j, QTableWidgetItem(v))
        total = sum(r[5] for r in rows)
        tbl.setItem(len(rows), 0, QTableWidgetItem("TOTAL"))
        tbl.setItem(len(rows), 5, QTableWidgetItem(fmt(total, 1)))
        lines.append("\t".join(["TOTAL", "", "", "", "", fmt(total, 1)]))
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(tbl)
        lay.addWidget(QLabel("Pesos nominales de catálogo, sin uniones, placas ni rigidizadores."))
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        copy_btn = bb.addButton("Copiar (para Excel)", QDialogButtonBox.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText("\n".join(lines)))
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(720, 360)
        dlg.exec()


# ---------------------------------------------------------------------------
# Registro en IngeTrazo
# ---------------------------------------------------------------------------

def _fill_menu(sub, viewport_of, create=True, existing=True, later=False) -> None:
    from PySide6.QtCore import QTimer

    def run(fn):
        if not later:
            return lambda: fn(viewport_of())
        return lambda: QTimer.singleShot(0, lambda: fn(viewport_of()))

    if create:
        sub.addAction("Nueva nave…", run(nueva))
    if existing:
        sub.addAction("Editar nave…", run(editar))
        sub.addAction("Medición de acero…", run(medicion))


def outliner_kind(group):
    data = nave_data(group)
    if data is None:
        return None
    try:
        p = normalize(data.get("params"))
        g = Geo(p)
        kg = sum(r[5] for r in measurement(p))
    except NaveError:
        return {"type": "Nave", "props": []}
    return {"type": "Nave", "props": [
        ("Luz", f"{g.L:.2f} m"), ("Longitud", f"{g.Ln:.2f} m"),
        ("Alero", f"{g.H:.2f} m"), ("Pórticos", f"{g.n} × {p['pilar']} / {p['dintel']}"),
        ("Acero", f"{kg:,.0f} kg".replace(",", "."))]}


def setup(app) -> None:
    viewport_of = lambda: app.viewport  # noqa: E731
    sub = app.add_menu(TITLE)
    if sub is not None:
        _fill_menu(sub, viewport_of)

    def context(menu, selection) -> None:
        if not _selected_naves(app.viewport.scene):
            return
        menu.addSeparator()
        _fill_menu(menu.addMenu(TITLE), viewport_of, create=False, later=True)

    app.add_context_menu(context)
    add_kind = getattr(app, "add_outliner_kind", None)
    if add_kind is not None:
        add_kind(outliner_kind)
