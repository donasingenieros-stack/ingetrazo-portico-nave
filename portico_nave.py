# SPDX-License-Identifier: GPL-3.0-or-later
# Pórtico de nave — extensión para IngeTrazo.
# (c) 2026 Donas Ingenieros (José María Martín García-Donas). Escrita con ayuda de IA (Claude).
"""Pórtico de nave — nave industrial paramétrica de pórticos a dos aguas.

Extensiones ▸ Pórtico de nave ▸ Nueva nave… genera, con un cuadro de
parámetros, una nave de pórticos metálicos a dos aguas:

* pilares y dinteles IPE / HEA / HEB, con cartelas de alero y de cumbrera
  (alma y ala inferior en chapa); dintel opcionalmente distinto en los
  pórticos extremos (primero y último);
* alturas de alero independientes en cada fachada (cumbrera desplazada,
  misma pendiente en ambos faldones);
* correas C o Z conformadas, o IPE, repartidas por faldón con una
  separación máxima;
* canalón en U apoyado sobre el dintel, junto al pilar;
* puente grúa opcional: ménsulas en los pilares y viga carril;
* cruces de San Andrés (redondo macizo) en cubierta y en fachadas
  laterales, en los vanos extremos o en todos.
* fachadas de paneles de hormigón en las cuatro fachadas, con altura de
  fachada y de placa propias en cada una: en los piñones (pórticos primero y
  último), perfil U (UPE o UPN) en las esquinas y perfiles H intermedios por
  delante del pórtico; en los laterales, paneles de pilar a pilar alojados en
  la H del pilar. El panel va siempre entre las alas, pegado al ala exterior.

Interfaz en español e inglés (selector en el cuadro de parámetros).

Organización del modelo (lo que muestra el Explorador):

* la nave es UN grupo contenedor; sus parámetros se guardan en
  ``group.ext["portico_nave"]``, viajan con las copias y con el .igz, y
  **Editar nave…** la vuelve a generar en el mismo sitio (aunque se haya
  movido o girado);
* cada pórtico es un COMPONENTE: los pórticos interiores comparten una
  definición y los extremos otra (una sola si el dintel es el mismo); dentro
  de ellas, pilares, dinteles, cartelas y ménsulas son a su vez componentes;
* correas, canalones, vigas carril y cruces van en grupos propios, cada pieza
  como instancia de un componente;
* etiquetas (capas) Estructura, Correas, Canalones, Puente grúa y
  Arriostramientos, y clases BIM IfcColumn / IfcBeam / IfcMember.

Coordenadas locales de la nave (metros): X a lo largo de la luz (0 = cara
exterior del pilar izquierdo), Y a lo largo de la nave (0 = primer pórtico),
Z vertical (0 = arranque de pilares).

Convenios geométricos:

* «Luz» es la distancia entre caras exteriores de pilares.
* «Altura de alero» es la cota de la cara superior del dintel en la cara
  exterior del pilar, en cada fachada.
* Con aleros distintos la pendiente es común y la cumbrera se desplaza hacia
  la fachada más alta.
* Unión pilar–dintel: el pilar sube por encima de la cara superior del
  dintel (5 cm por defecto) y el dintel arranca en la cara interior del pilar.
* La primera correa se sitúa a una distancia del extremo del dintel (cara
  interior del pilar) medida hasta el borde de la correa; la última, a una
  distancia de la cumbrera medida también hasta su borde.
* La cota de la ménsula es la de su cara superior (apoyo de la viga carril);
  el vuelo se mide desde la cara interior del pilar al eje de la viga carril.
* Cruces de fachada en el plano del eje de pilares; cruces de cubierta en un
  plano paralelo al faldón, a un cuarto del canto del dintel bajo su cara
  superior.
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

__version__ = "1.2"

KEY = Path(__file__).stem            # = ExtensionApp.key
STEEL = 7850.0                       # kg/m³

# ---------------------------------------------------------------------------
# Idioma
# ---------------------------------------------------------------------------

LANGS = (("es", "Español"), ("en", "English"))
_LANG: str | None = None

_S = {
    # Generales
    "title": ("Pórtico de nave", "Portal-frame shed"),
    "nave": ("Nave", "Shed"),
    "lang": ("Idioma / Language", "Idioma / Language"),
    # Menús y órdenes
    "m_new": ("Nueva nave…", "New shed…"),
    "m_edit": ("Editar nave…", "Edit shed…"),
    "m_meas": ("Medición de acero…", "Steel take-off…"),
    "t_new": ("Nueva nave", "New shed"),
    "t_edit": ("Editar — {name}", "Edit — {name}"),
    "t_meas": ("Medición de acero — {name}", "Steel take-off — {name}"),
    "ok_new": ("nave creada.", "shed created."),
    "ok_edit": ("«{name}» actualizada.", "“{name}” updated."),
    "w_close_group": ("Cierre el grupo que está editando y vuelva a ejecutar la orden.",
                      "Close the group you are editing and run the command again."),
    "w_select": ("Seleccione una nave creada con Pórtico de nave.",
                 "Select a shed created with Portal-frame shed."),
    "w_not_nave": ("«{name}» no es una nave de Pórtico de nave.",
                   "“{name}” is not a Portal-frame shed."),
    "w_anyway": ("¿Generar la nave de todos modos?", "Generate the shed anyway?"),
    # Errores
    "e_pos": ("La luz y las alturas de alero deben ser positivas.",
              "Span and eaves heights must be positive."),
    "e_n": ("Debe haber al menos un pórtico.", "There must be at least one frame."),
    "e_sep": ("La separación entre pórticos debe ser positiva.",
              "Frame spacing must be positive."),
    "e_slope": ("La pendiente debe estar entre 0 % y 100 %.",
                "Roof pitch must be between 0 % and 100 %."),
    "e_cols": ("Los pilares no caben en la luz indicada.",
               "The columns do not fit in the given span."),
    "e_low": ("La altura de alero es insuficiente para el dintel elegido ({side}).",
              "The eaves height is too low for the chosen rafter ({side})."),
    "e_flat": ("Con pendiente 0 % las dos alturas de alero deben ser iguales.",
               "With a 0 % pitch both eaves heights must be equal."),
    "e_ridge": ("Con aleros de {hl:.2f} y {hr:.2f} m la pendiente debe ser mayor que {tmin:.2f} %.",
                "With eaves at {hl:.2f} and {hr:.2f} m the pitch must exceed {tmin:.2f} %."),
    "e_purlin": ("Dimensiones de correa incoherentes.", "Inconsistent purlin dimensions."),
    "e_purlin_sep": ("La separación máxima de correas debe ser positiva.",
                     "Maximum purlin spacing must be positive."),
    "e_gutter": ("Dimensiones de canalón incoherentes.", "Inconsistent gutter dimensions."),
    "e_brace": ("El diámetro del redondo y el número de recuadros deben ser positivos.",
                "Rod diameter and number of panels must be positive."),
    # Avisos de puente grúa
    "c_clash": ("La viga carril (cara superior a {top:.3f} m) interfiere con el dintel o la "
                "cartela (cara inferior a {free:.3f} m en su vertical){where}.",
                "The runway beam (top at {top:.3f} m) clashes with the rafter or haunch "
                "(underside at {free:.3f} m above it){where}."),
    "c_low": ("La ménsula queda por debajo del arranque del pilar.",
              "The bracket lies below the column base."),
    "c_vuelo": ("El vuelo de la ménsula es menor que la semianchura de la viga carril.",
                "The bracket reach is less than half the runway beam width."),
    "c_ridge": ("La viga carril sobrepasa la cumbrera{where}.",
                "The runway beam goes past the ridge{where}."),
    "c_purlin": ("La primera correa (a {d:.2f} m del extremo del dintel) choca con el canalón "
                 "de {a:.2f} m de anchura.",
                 "The first purlin ({d:.2f} m from the rafter end) clashes with the "
                 "{a:.2f} m wide gutter."),
    "c_info_brace": ("Con un solo pórtico no se generan cruces de San Andrés.",
                     "No cross bracing is generated with a single frame."),
    # Fachadas
    "e_fach_h": ("La altura de fachada y de panel deben ser positivas ({f}).",
                 "Wall and panel heights must be positive ({f})."),
    "e_fach_holg": ("La holgura de la fachada al pilar no puede ser negativa.",
                    "The wall clearance to the columns cannot be negative."),
    "e_fach_sep": ("La separación máxima entre perfiles de fachada es demasiado pequeña.",
                   "The maximum spacing between wall posts is too small."),
    "e_panel_e": ("El espesor de panel debe ser positivo.", "Panel thickness must be positive."),
    "e_panel_fit": ("El panel de {e:.0f} mm no cabe entre las alas del {prof} "
                    "(hueco libre {free:.0f} mm).",
                    "The {e:.0f} mm panel does not fit between the flanges of the {prof} "
                    "(clear gap {free:.0f} mm)."),
    "c_fach_pinon": ("La {f} supera la altura de alero; el hastial por encima del alero no "
                     "se modela.",
                     "The {f} exceeds the eaves height; the gable above the eaves is not "
                     "modelled."),
    "c_fach_lat": ("Los paneles de la {f} ({h:.2f} m) superan la cabeza de los pilares "
                   "({head:.3f} m).",
                   "The {f} panels ({h:.2f} m) exceed the column head ({head:.3f} m)."),
    "c_fach_brace": ("Las cruces de la {f} no caben entre el panel y el ala interior del pilar.",
                     "The {f} bracing does not fit between the panel and the inner column "
                     "flange."),
    "fk_frontal": ("fachada piñón frontal", "front gable wall"),
    "fk_posterior": ("fachada piñón posterior", "rear gable wall"),
    "fk_izq": ("fachada lateral izquierda", "left side wall"),
    "fk_der": ("fachada lateral derecha", "right side wall"),
    "tab_fach": ("Fachadas", "Walls"),
    "f_paneles": ("Paneles de hormigón", "Concrete panels"),
    "f_panel_e": ("Espesor de panel", "Panel thickness"),
    "g_fach": ("Fachada", "Wall"),
    "g_on": ("Activa", "On"),
    "g_h": ("Altura de fachada", "Wall height"),
    "g_ph": ("Altura de placa", "Panel height"),
    "f_esquina": ("Piñón: perfil de esquina (U)", "Gable: corner post (channel)"),
    "f_intermedio": ("Piñón: perfil intermedio", "Gable: intermediate post"),
    "f_fsep": ("Piñón: separación máxima entre perfiles", "Gable: maximum post spacing"),
    "f_fholg": ("Piñón: holgura a los pilares del pórtico", "Gable: clearance to frame columns"),
    "f_fach_note": ("Piñones (pórticos primero y último): perfil U en las esquinas, con el alma "
                    "enrasada con la cara exterior del pilar, y perfiles intermedios por delante "
                    "del pórtico; los perfiles tienen la altura de su fachada. Laterales: paneles "
                    "de pilar a pilar, dentro de la H del pilar. El panel va entre las alas, "
                    "pegado al ala exterior.",
                    "Gables (first and last frames): channel posts at the corners, web flush "
                    "with the outer face of the column, and intermediate posts in front of the "
                    "frame; posts take the height of their wall. Side walls: panels from column "
                    "to column, inside the column H. Panels sit between the flanges, against "
                    "the outer flange."),
    "sum_pan": (" · {u} paneles ({m2} m²)", " · {u} panels ({m2} m²)"),
    "r_post_c": ("Perfiles de esquina — {f}", "Corner posts — {f}"),
    "r_post_h": ("Perfiles intermedios — {f}", "Intermediate posts — {f}"),
    "m_panels": ("Paneles de hormigón", "Concrete panels"),
    "ph": (("Fachada", "Ud.", "Superficie (m²)", "Volumen (m³)"),
           ("Wall", "No.", "Area (m²)", "Volume (m³)")),
    "o_paneles": ("Paneles", "Panels"),
    "n_fach_frontal": ("Fachada piñón frontal", "Front gable wall"),
    "n_fach_posterior": ("Fachada piñón posterior", "Rear gable wall"),
    "n_fach_izq": ("Fachada lateral izquierda", "Left side wall"),
    "n_fach_der": ("Fachada lateral derecha", "Right side wall"),
    "n_post_c": ("{prof} esquina {k}", "{prof} corner {k}"),
    "n_panel": ("Panel {i}.{j}", "Panel {i}.{j}"),
    "ly_fac": ("Fachada perfiles", "Wall posts"),
    "ly_pan": ("Fachada paneles", "Wall panels"),
    "mt_fac": ("Acero fachada", "Wall steel"),
    "mt_pan": ("Panel de hormigón", "Concrete panel"),
    # Lados y tipos de pórtico
    "side_l": ("fachada izquierda", "left side"),
    "side_r": ("fachada derecha", "right side"),
    "kind_ext": ("pórticos extremos", "end frames"),
    "kind_int": ("pórticos interiores", "interior frames"),
    # Resumen
    "sum": ("Nave {L:.2f} × {Ln:.2f} m · {n} pórticos · {cor} · acero ≈ {kg} kg",
            "Shed {L:.2f} × {Ln:.2f} m · {n} frames · {cor} · steel ≈ {kg} kg"),
    "sum_cor": ("{k} correas por faldón", "{k} purlins per slope"),
    "sum_cor2": ("correas por faldón {kl} / {kr}", "purlins per slope {kl} / {kr}"),
    # Pestañas y campos
    "tab_geo": ("Geometría", "Geometry"),
    "tab_frame": ("Pilares y dinteles", "Columns and rafters"),
    "tab_purlin": ("Correas", "Purlins"),
    "tab_gutter": ("Canalón", "Gutter"),
    "tab_crane": ("Puente grúa", "Crane runway"),
    "tab_brace": ("Arriostramiento", "Bracing"),
    "f_luz": ("Luz (caras exteriores de pilares)", "Span (outer faces of columns)"),
    "f_alero": ("Altura de alero, fachada izquierda", "Eaves height, left side"),
    "f_alero_der": ("Altura de alero, fachada derecha", "Eaves height, right side"),
    "f_alero_note": ("Cara superior del dintel en la cara exterior del pilar. Con aleros "
                     "distintos la cumbrera se desplaza; la pendiente es la misma en ambos faldones.",
                     "Top of rafter at the outer face of the column. With different eaves the "
                     "ridge shifts; both slopes keep the same pitch."),
    "f_pend": ("Pendiente", "Roof pitch"),
    "f_n": ("Número de pórticos", "Number of frames"),
    "f_sep": ("Separación entre pórticos", "Frame spacing"),
    "f_pilar": ("Perfil de pilares", "Column section"),
    "f_dintel": ("Perfil de dinteles", "Rafter section"),
    "f_sobre": ("Pilar: altura sobre la cara superior del dintel",
                "Column: height above the top of the rafter"),
    "f_dext_on": ("Dintel distinto en los pórticos extremos (primero y último)",
                  "Different rafter in the end frames (first and last)"),
    "f_dext": ("Perfil de dintel en pórticos extremos", "End-frame rafter section"),
    "f_ca_l": ("Cartela de alero: longitud", "Eaves haunch: length"),
    "f_ca_h": ("Cartela de alero: canto", "Eaves haunch: depth"),
    "f_ck_l": ("Cartela de cumbrera: semilongitud", "Ridge haunch: half-length"),
    "f_ck_h": ("Cartela de cumbrera: canto", "Ridge haunch: depth"),
    "f_cart_note": ("Longitud o canto 0 = sin cartela.", "Length or depth 0 = no haunch."),
    "f_ctipo": ("Tipo", "Type"),
    "f_ch": ("Canto", "Depth"),
    "f_cb": ("Ala", "Flange"),
    "f_ce": ("Espesor", "Thickness"),
    "f_cc": ("Labio", "Lip"),
    "f_cipe": ("Perfil IPE", "IPE section"),
    "f_csep": ("Separación máxima", "Maximum spacing"),
    "f_cda": ("Primera correa: del extremo del dintel al borde (sobre faldón)",
              "First purlin: rafter end to purlin edge (along slope)"),
    "f_cdc": ("Última correa: de la cumbrera al borde (sobre faldón)",
              "Last purlin: ridge to purlin edge (along slope)"),
    "f_cv": ("Vuelo sobre los pórticos extremos", "Overhang beyond end frames"),
    "p_C": ("C conformada", "Cold-formed C"),
    "p_Z": ("Z conformada", "Cold-formed Z"),
    "p_IPE": ("IPE laminado", "Hot-rolled IPE"),
    "f_can": ("Canalón en U apoyado sobre el dintel, junto al pilar",
              "U gutter resting on the rafter, next to the column"),
    "f_cana": ("Anchura", "Width"),
    "f_canh": ("Altura", "Height"),
    "f_cane": ("Espesor de chapa", "Sheet thickness"),
    "f_grua": ("Ménsulas y viga carril de puente grúa", "Crane brackets and runway beam"),
    "f_mens": ("Perfil de ménsula", "Bracket section"),
    "f_mz": ("Cota de apoyo (cara superior de ménsula)", "Bearing level (top of bracket)"),
    "f_mv": ("Vuelo (cara interior del pilar a eje de viga carril)",
             "Reach (inner face of column to runway beam axis)"),
    "f_vc": ("Perfil de viga carril", "Runway beam section"),
    "f_acub": ("Cruces de San Andrés en cubierta", "Roof cross bracing"),
    "f_afach": ("Cruces de San Andrés en fachadas laterales", "Side-wall cross bracing"),
    "f_avanos": ("Vanos arriostrados", "Braced bays"),
    "v_extremos": ("Vanos extremos", "End bays"),
    "v_todos": ("Todos los vanos", "All bays"),
    "f_arec": ("Recuadros por faldón (cubierta)", "Panels per slope (roof)"),
    "f_afn": ("Recuadros en altura (fachada)", "Panels in height (wall)"),
    "f_ad": ("Diámetro del redondo", "Rod diameter"),
    "f_brace_note": ("Redondo macizo. Cubierta: de cara interior de pilar a cumbrera. "
                     "Fachada: de arranque de pilar a cara inferior del dintel.",
                     "Solid round bar. Roof: inner face of column to ridge. "
                     "Wall: column base to rafter underside."),
    # Medición
    "mh": (("Elemento", "Perfil", "Ud.", "Long. unit. (m)", "kg/m", "Total (kg)"),
           ("Element", "Section", "No.", "Unit length (m)", "kg/m", "Total (kg)")),
    "m_total": ("TOTAL", "TOTAL"),
    "m_note": ("Pesos nominales de catálogo, sin uniones, placas ni rigidizadores.",
               "Nominal catalogue weights, without connections, plates or stiffeners."),
    "m_copy": ("Copiar (para Excel)", "Copy (for Excel)"),
    "r_pil": ("Pilares", "Columns"),
    "r_din": ("Dinteles", "Rafters"),
    "r_ca": ("Cartelas de alero", "Eaves haunches"),
    "r_ck": ("Cartelas de cumbrera", "Ridge haunches"),
    "r_cor": ("Correas", "Purlins"),
    "r_can": ("Canalones", "Gutters"),
    "r_mens": ("Ménsulas", "Brackets"),
    "r_vc": ("Vigas carril", "Runway beams"),
    "r_acub": ("Cruces de cubierta", "Roof bracing"),
    "r_afach": ("Cruces de fachada", "Wall bracing"),
    "r_plate": ("chapa e={tw:.1f}/{tf:.1f} mm", "plate t={tw:.1f}/{tf:.1f} mm"),
    # Explorador
    "o_luz": ("Luz", "Span"),
    "o_long": ("Longitud", "Length"),
    "o_alero": ("Alero", "Eaves"),
    "o_port": ("Pórticos", "Frames"),
    "o_acero": ("Acero", "Steel"),
    # Nombres del modelo
    "n_frame": ("Pórtico {i}", "Frame {i}"),
    "n_col_l": ("Pilar izquierdo", "Left column"),
    "n_col_r": ("Pilar derecho", "Right column"),
    "n_raf_l": ("Dintel izquierdo", "Left rafter"),
    "n_raf_r": ("Dintel derecho", "Right rafter"),
    "n_ca_l": ("Cartela de alero izquierda", "Left eaves haunch"),
    "n_ca_r": ("Cartela de alero derecha", "Right eaves haunch"),
    "n_ck": ("Cartela de cumbrera", "Ridge haunch"),
    "n_me_l": ("Ménsula izquierda", "Left bracket"),
    "n_me_r": ("Ménsula derecha", "Right bracket"),
    "n_cor": ("Correas", "Purlins"),
    "n_cor_l": ("Correa I-{k}", "Purlin L-{k}"),
    "n_cor_r": ("Correa D-{k}", "Purlin R-{k}"),
    "n_can": ("Canalones", "Gutters"),
    "n_can_l": ("Canalón izquierdo", "Left gutter"),
    "n_can_r": ("Canalón derecho", "Right gutter"),
    "n_pg": ("Puente grúa", "Crane runway"),
    "n_vc_l": ("Viga carril izquierda", "Left runway beam"),
    "n_vc_r": ("Viga carril derecha", "Right runway beam"),
    "n_arr": ("Arriostramientos", "Bracing"),
    "n_acub_l": ("Cruz de cubierta izquierda, vano {j}", "Left roof bracing, bay {j}"),
    "n_acub_r": ("Cruz de cubierta derecha, vano {j}", "Right roof bracing, bay {j}"),
    "n_afach_l": ("Cruz de fachada izquierda, vano {j}", "Left wall bracing, bay {j}"),
    "n_afach_r": ("Cruz de fachada derecha, vano {j}", "Right wall bracing, bay {j}"),
    # Etiquetas y materiales
    "ly_est": ("Estructura", "Structure"),
    "ly_cor": ("Correas", "Purlins"),
    "ly_can": ("Canalones", "Gutters"),
    "ly_pg": ("Puente grúa", "Crane runway"),
    "ly_arr": ("Arriostramientos", "Bracing"),
    "mt_est": ("Acero estructural", "Structural steel"),
    "mt_cor": ("Acero correas", "Purlin steel"),
    "mt_can": ("Chapa canalón", "Gutter sheet"),
    "mt_pg": ("Acero puente grúa", "Crane runway steel"),
    "mt_arr": ("Acero arriostramientos", "Bracing steel"),
}


def lang() -> str:
    """Idioma activo: preferencia guardada o, en su defecto, el de la configuración regional."""
    global _LANG
    if _LANG is None:
        _LANG = "es"
        try:
            from PySide6.QtCore import QLocale, QSettings
            saved = QSettings("IngeTrazo", KEY).value("lang")
            if saved in dict(LANGS):
                _LANG = saved
            elif QLocale().name().lower().startswith("en"):
                _LANG = "en"
        except Exception:  # noqa: BLE001
            pass
    return _LANG


def set_lang(code: str) -> None:
    global _LANG
    if code not in dict(LANGS):
        return
    _LANG = code
    try:
        from PySide6.QtCore import QSettings
        QSettings("IngeTrazo", KEY).setValue("lang", code)
    except Exception:  # noqa: BLE001
        pass


def tr(key: str, **kw):
    es, en = _S[key]
    s = en if lang() == "en" else es
    return s.format(**kw) if kw else s


def title() -> str:
    return tr("title")


def _num(v: float, d: int = 0) -> str:
    """Número con separador de miles según el idioma."""
    s = f"{v:,.{d}f}"
    if lang() == "en":
        return s
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


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

# Perfiles U (h, b, tw, tf en mm; peso kg/m). UPN con ala inclinada: se modela
# con alas paralelas del espesor nominal.
_UPE = {80: (80, 50, 4.0, 7.0, 7.9), 100: (100, 55, 4.5, 7.5, 9.8),
        120: (120, 60, 5.0, 8.0, 12.1), 140: (140, 65, 5.0, 9.0, 14.5),
        160: (160, 70, 5.5, 9.5, 17.0), 180: (180, 75, 5.5, 10.5, 19.7),
        200: (200, 80, 6.0, 11.0, 22.8), 220: (220, 85, 6.5, 12.0, 26.6),
        240: (240, 90, 7.0, 12.5, 30.2), 270: (270, 95, 7.5, 13.5, 35.2),
        300: (300, 100, 9.5, 15.0, 44.4)}
_UPN = {80: (80, 45, 6.0, 8.0, 8.64), 100: (100, 50, 6.0, 8.5, 10.6),
        120: (120, 55, 7.0, 9.0, 13.4), 140: (140, 60, 7.0, 10.0, 16.0),
        160: (160, 65, 7.5, 10.5, 18.8), 180: (180, 70, 8.0, 11.0, 22.0),
        200: (200, 75, 8.5, 11.5, 25.3), 220: (220, 80, 9.0, 12.5, 29.4),
        240: (240, 85, 9.5, 13.0, 33.2), 260: (260, 90, 10.0, 14.0, 37.9),
        280: (280, 95, 10.0, 15.0, 41.8), 300: (300, 100, 10.0, 16.0, 46.2)}

PROFILES: dict[str, tuple] = {}
for _serie, _tabla in (("IPE", _IPE), ("HEA", _HEA), ("HEB", _HEB), ("UPE", _UPE),
                       ("UPN", _UPN)):
    for _n, (_h, _b, _tw, _tf, _kg) in _tabla.items():
        PROFILES[f"{_serie} {_n}"] = (_h / 1000, _b / 1000, _tw / 1000, _tf / 1000, _kg)
PROFILE_NAMES = list(PROFILES)

PURLIN_TYPES = ["C", "Z", "IPE"]
BRACED_BAYS = ["extremos", "todos"]
# Fachadas: piñones (pórticos primero y último) y laterales.
FACADES = ["frontal", "posterior", "izq", "der"]
PINONES = ["frontal", "posterior"]
U_SERIES = ("UPE", "UPN")
POST_SERIES = ("HEA", "HEB", "IPE")
PANEL_GAP = 0.01      # holgura del panel al alma del perfil, m

DEFAULTS = {
    # Geometría
    "luz": 16.0, "alero": 8.0, "alero_der": 8.0, "pendiente": 10.0,   # pendiente en %
    "n_porticos": 5, "separacion": 5.0,
    # Pilares y dinteles
    "pilar": "HEA 300", "dintel": "IPE 360", "pilar_sobre": 0.05,
    "dintel_ext_on": False, "dintel_ext": "IPE 300",
    # Cartelas (0 = sin cartela)
    "cart_alero_l": 1.60, "cart_alero_h": 0.36,
    "cart_cumb_l": 0.80, "cart_cumb_h": 0.20,
    # Correas
    "correa_tipo": "C", "correa_h": 0.200, "correa_b": 0.070,
    "correa_e": 0.0025, "correa_c": 0.020, "correa_ipe": "IPE 140",
    "correa_sep": 1.50, "correa_d_alero": 0.35, "correa_d_cumbrera": 0.15,
    "correa_vuelo": 0.0,
    # Canalón
    "canalon": True, "canalon_a": 0.30, "canalon_h": 0.20, "canalon_e": 0.002,
    # Puente grúa
    "grua": True, "mensula": "HEA 200", "mensula_z": 6.60, "mensula_vuelo": 0.40,
    "viga_carril": "HEB 240",
    # Arriostramiento (cruces de San Andrés en redondo)
    "arr_cub": True, "arr_fach": True, "arr_vanos": "extremos",
    "arr_recuadros": 3, "arr_fach_n": 1, "arr_d": 0.020,
    # Fachadas de paneles de hormigón. Piñones: perfil U en las esquinas y
    # perfiles intermedios por delante del pórtico. Laterales: paneles de
    # pilar a pilar, dentro de la H del pilar. Altura de fachada y de panel
    # independientes en cada fachada.
    "fach_frontal": True, "fach_posterior": True, "fach_izq": True, "fach_der": True,
    "fach_h_frontal": 8.0, "fach_h_posterior": 8.0, "fach_h_izq": 8.0, "fach_h_der": 8.0,
    "panel_h_frontal": 2.0, "panel_h_posterior": 2.0, "panel_h_izq": 2.0, "panel_h_der": 2.0,
    "paneles": True, "panel_e": 0.16,
    "fach_esquina": "UPE 200", "fach_intermedio": "HEA 200", "fach_sep": 6.0,
    "fach_holgura": 0.0,
}

# Valores que se aplican a naves guardadas con versiones anteriores, para que
# al editarlas o medirlas no aparezcan piezas que no tenían.
LEGACY = {"arr_cub": False, "arr_fach": False,
          "fach_frontal": False, "fach_posterior": False, "fach_izq": False, "fach_der": False}

LAYER_KEYS = ("est", "cor", "can", "pg", "arr", "fac", "pan")
MAT_RGB = {"est": (0.36, 0.42, 0.50), "cor": (0.72, 0.62, 0.30),
           "can": (0.80, 0.80, 0.82), "pg": (0.80, 0.45, 0.15),
           "arr": (0.25, 0.55, 0.35), "fac": (0.45, 0.50, 0.56),
           "pan": (0.76, 0.76, 0.73)}


def layer_name(k: str) -> str:
    return tr("ly_" + k)


class NaveError(Exception):
    """Rechazo comprensible para el usuario (parámetros incoherentes)."""


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def normalize(params, legacy: bool = True) -> dict:
    """Parámetros completos y saneados. Con ``legacy`` (parámetros guardados
    en una nave), las claves ausentes toman los valores de ``LEGACY``."""
    src = dict(params or {})
    p = dict(DEFAULTS)
    if src:
        if legacy:
            p.update(LEGACY)
        # Versión 1.0: un único alero.
        p["alero_der"] = src.get("alero", DEFAULTS["alero"])
    p.update({k: v for k, v in src.items() if k in DEFAULTS})
    for k, v in DEFAULTS.items():
        if isinstance(v, bool):
            p[k] = bool(p[k])
        elif isinstance(v, int):
            p[k] = int(p[k])
        elif isinstance(v, float):
            p[k] = float(p[k])
    for k in ("pilar", "dintel", "dintel_ext", "correa_ipe", "mensula", "viga_carril"):
        if p[k] not in PROFILES:
            p[k] = DEFAULTS[k]
    if p["correa_tipo"] not in PURLIN_TYPES:
        p["correa_tipo"] = "C"
    if p["arr_vanos"] not in BRACED_BAYS:
        p["arr_vanos"] = DEFAULTS["arr_vanos"]
    if p["fach_esquina"] not in PROFILES or p["fach_esquina"].split()[0] not in U_SERIES:
        p["fach_esquina"] = DEFAULTS["fach_esquina"]
    if (p["fach_intermedio"] not in PROFILES
            or p["fach_intermedio"].split()[0] not in POST_SERIES):
        p["fach_intermedio"] = DEFAULTS["fach_intermedio"]
    return p


class Side:
    """Un faldón y su fachada, en coordenadas propias: x desde la cara
    exterior del pilar de esa fachada hacia la cumbrera."""

    def __init__(self, geo: "Geo", H: float, xs: float, rafter: str) -> None:
        self.p = geo.p
        self.t = geo.t
        self.hp = geo.hp
        self.H = H                       # altura de alero
        self.xs = xs                     # distancia horizontal a la cumbrera
        self.rafter = rafter
        self.hd, self.bd, self.twd, self.tfd, self.kgd = PROFILES[rafter]
        self.hv = self.hd / geo.ca       # canto del dintel en vertical
        # Unión pilar–dintel: el pilar sube por encima del dintel y el dintel
        # arranca en la cara interior del pilar.
        self.Hp = self.z_top(geo.hp) + geo.p["pilar_sobre"]   # longitud del pilar
        self.z_knee = self.z_under(geo.hp)   # cara inferior del dintel en el pilar
        self.Lslope = xs / geo.ca            # faldón, desde la cara exterior del pilar
        self.Lrafter = (xs - geo.hp) / geo.ca   # dintel, desde la cara interior

    def z_top(self, x: float) -> float:
        """Cota de la cara superior del dintel en la abscisa x."""
        return self.H + x * self.t

    def z_under(self, x: float) -> float:
        return self.H - self.hv + x * self.t

    def z_under_cartela(self, x: float) -> float:
        """Cota inferior del conjunto dintel + cartela de alero en x."""
        p = self.p
        z = self.z_under(x)
        Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
        x0 = self.hp
        if Lc > 0 and hc > 0 and x0 <= x <= x0 + Lc:
            z -= hc * (1 - (x - x0) / Lc)
        return z


class Geo:
    """Magnitudes derivadas de los parámetros (todas en metros)."""

    def __init__(self, p: dict) -> None:
        self.p = p
        if p["luz"] <= 0 or p["alero"] <= 0 or p["alero_der"] <= 0:
            raise NaveError(tr("e_pos"))
        if p["n_porticos"] < 1:
            raise NaveError(tr("e_n"))
        if p["n_porticos"] > 1 and p["separacion"] <= 0:
            raise NaveError(tr("e_sep"))
        if not 0.0 <= p["pendiente"] < 100.0:
            raise NaveError(tr("e_slope"))
        self.L = p["luz"]
        self.Hl, self.Hr = p["alero"], p["alero_der"]
        self.t = p["pendiente"] / 100.0
        self.a = math.atan(self.t)
        self.ca, self.sa = math.cos(self.a), math.sin(self.a)
        self.hp, self.bp, self.twp, self.tfp, self.kgp = PROFILES[p["pilar"]]
        self.n = p["n_porticos"]
        self.s = p["separacion"] if self.n > 1 else 0.0
        self.Ln = (self.n - 1) * self.s
        if 2 * self.hp >= self.L:
            raise NaveError(tr("e_cols"))
        # Cumbrera: misma pendiente en ambos faldones.
        dH = self.Hr - self.Hl
        if self.t == 0.0:
            if abs(dH) > 1e-9:
                raise NaveError(tr("e_flat"))
            self.xr = self.L / 2
        else:
            self.xr = (self.L + dH / self.t) / 2
        if not self.hp < self.xr < self.L - self.hp:
            tmin = abs(dH) / (self.L - 2 * self.hp) * 100
            raise NaveError(tr("e_ridge", hl=self.Hl, hr=self.Hr, tmin=tmin))
        self.zr = self.Hl + self.xr * self.t           # cota de cumbrera (cara superior)
        # Dinteles por tipo de pórtico.
        self.rafter = {"int": p["dintel"],
                       "ext": p["dintel_ext"] if p["dintel_ext_on"] else p["dintel"]}
        self.sides = {}
        for kind, raf in self.rafter.items():
            for sd, H, xs in (("l", self.Hl, self.xr), ("r", self.Hr, self.L - self.xr)):
                side = Side(self, H, xs, raf)
                if H - side.hv - self.hp * self.t <= 0.5:
                    raise NaveError(tr("e_low", side=tr("side_" + sd)))
                self.sides[kind, sd] = side
        if (p["arr_cub"] or p["arr_fach"]) and (
                p["arr_d"] <= 0 or p["arr_recuadros"] < 1 or p["arr_fach_n"] < 1):
            raise NaveError(tr("e_brace"))

    # --- Pórticos -------------------------------------------------------

    def kind(self, i: int) -> str:
        """Tipo de pórtico i (0 … n−1): «ext» para el primero y el último."""
        if self.p["dintel_ext_on"] and i in (0, self.n - 1):
            return "ext"
        return "int"

    def kinds_used(self) -> list[str]:
        return sorted({self.kind(i) for i in range(self.n)})

    def side(self, sd: str, kind: str = "int") -> Side:
        return self.sides[kind, sd]

    # --- Correas --------------------------------------------------------

    def purlin_section(self) -> tuple:
        """(polígono (u, w), peso kg/m, canto) de la correa; w = 0 apoyo."""
        p = self.p
        if p["correa_tipo"] == "IPE":
            h, b, tw, tf, kg = PROFILES[p["correa_ipe"]]
            poly = [(u, w + h / 2) for u, w in i_section(h, b, tw, tf)]
            return poly, kg, h
        h, b, e, c = p["correa_h"], p["correa_b"], p["correa_e"], p["correa_c"]
        if min(h, b, e) <= 0 or 2 * e >= min(h, b) or c < 0 or c >= h / 2:
            raise NaveError(tr("e_purlin"))
        poly = c_section(h, b, e, c) if p["correa_tipo"] == "C" else z_section(h, b, e, c)
        return poly, polygon_area(poly) * STEEL, h

    def purlin_positions(self, sd: str = "l") -> list[float]:
        """Distancias, medidas sobre el faldón desde la cara exterior del pilar,
        del origen de cada correa. La primera queda a «correa_d_alero» del
        extremo del dintel (cara interior del pilar) y la última a
        «correa_d_cumbrera» de la cumbrera, ambas medidas hasta el borde de la
        correa: con 0, la correa queda justo en el extremo del dintel."""
        p = self.p
        poly, _kg, _h = self.purlin_section()
        umin = min(u for u, _w in poly)
        umax = max(u for u, _w in poly)
        a0 = self.hp / self.ca + max(0.0, p["correa_d_alero"]) - umin
        a1 = self.side(sd).Lslope - max(0.0, p["correa_d_cumbrera"]) - umax
        if a1 <= a0:
            return [a0]
        smax = p["correa_sep"]
        if smax <= 0:
            raise NaveError(tr("e_purlin_sep"))
        k = max(1, math.ceil((a1 - a0) / smax - 1e-9))
        return [a0 + i * (a1 - a0) / k for i in range(k + 1)]

    # --- Puente grúa ----------------------------------------------------

    def purlin_check(self) -> list[str]:
        """Aviso si la primera correa choca con el canalón."""
        p = self.p
        if p["canalon"] and p["correa_d_alero"] < p["canalon_a"] - 1e-6:
            return [tr("c_purlin", d=p["correa_d_alero"], a=p["canalon_a"])]
        return []

    def crane_check(self) -> list[str]:
        """Avisos de interferencia: correas con la cabeza del pilar y puente
        grúa con dintel y cartela."""
        p = self.p
        out = self.purlin_check()
        if not p["grua"]:
            return out + self.facade_warnings()
        hm = PROFILES[p["mensula"]][0]
        hvc, bvc = PROFILES[p["viga_carril"]][:2]
        x = self.hp + p["mensula_vuelo"]
        top_vc = p["mensula_z"] + hvc
        asym = abs(self.Hl - self.Hr) > 1e-9
        kinds = self.kinds_used()

        def where(sd, kind=None):
            parts = ([tr("side_" + sd)] if asym else []) + (
                [tr("kind_" + kind)] if kind and len(kinds) > 1 else [])
            return f" ({', '.join(parts)})" if parts else ""
        for sd in ("l", "r"):
            for kind in kinds:
                side = self.side(sd, kind)
                free = min(side.z_under_cartela(x - bvc / 2), side.z_under_cartela(x + bvc / 2))
                if top_vc > free - 1e-6:
                    out.append(tr("c_clash", top=top_vc, free=free, where=where(sd, kind)))
            if x + bvc / 2 >= self.side(sd).xs:
                out.append(tr("c_ridge", where=where(sd)))
        if p["mensula_z"] - hm <= 0:
            out.append(tr("c_low"))
        if p["mensula_vuelo"] <= bvc / 2:
            out.append(tr("c_vuelo"))
        out += self.facade_warnings()
        seen, uniq = set(), []
        for m in out:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        return uniq

    # --- Fachadas ---------------------------------------------------------
    # Paneles de hormigón siempre entre las alas de los perfiles, pegados al ala
    # exterior. Piñones: perfil U en las esquinas (alma enrasada con la cara
    # exterior del pilar) y perfiles H intermedios, por delante del pórtico
    # extremo. Laterales: paneles de pilar a pilar, alojados en la H del pilar y
    # terminando en su alma.

    def facades_on(self) -> list[str]:
        return [fk for fk in FACADES if self.p["fach_" + fk]]

    def has_facade(self) -> bool:
        return bool(self.facades_on())

    def facade_check(self) -> None:
        """Errores de las fachadas (lanza NaveError)."""
        p = self.p
        on = self.facades_on()
        if not on:
            return
        for fk in on:
            if p["fach_h_" + fk] <= 0 or (p["paneles"] and p["panel_h_" + fk] <= 0):
                raise NaveError(tr("e_fach_h", f=tr("fk_" + fk)))
        if p["fach_holgura"] < 0:
            raise NaveError(tr("e_fach_holg"))
        pin = [fk for fk in on if fk in PINONES]
        if pin and p["fach_sep"] <= 0.5:
            raise NaveError(tr("e_fach_sep"))
        if not p["paneles"]:
            return
        e = p["panel_e"]
        if e <= 0:
            raise NaveError(tr("e_panel_e"))
        hosts = []
        if pin:
            hosts += [p["fach_esquina"], p["fach_intermedio"]]
        if any(fk not in PINONES for fk in on):
            hosts.append(p["pilar"])
        for name in hosts:
            h, _b, _tw, tf, _kg = PROFILES[name]
            if h - 2 * tf < e + 0.002:
                raise NaveError(tr("e_panel_fit", e=e * 1000, prof=name,
                                   free=(h - 2 * tf) * 1000))

    def facade_warnings(self) -> list[str]:
        p = self.p
        out = []
        for fk in self.facades_on():
            H = p["fach_h_" + fk]
            if fk in PINONES:
                if H > min(self.Hl, self.Hr) + 1e-6:
                    out.append(tr("c_fach_pinon", f=tr("fk_" + fk)))
            else:
                sd = "l" if fk == "izq" else "r"
                head = min(self.side(sd, k).Hp for k in self.kinds_used())
                if p["paneles"] and H > head + 1e-6:
                    out.append(tr("c_fach_lat", f=tr("fk_" + fk), h=H, head=head))
                if (p["paneles"] and p["arr_fach"] and self.braced_bays()
                        and self.hp - 2 * self.tfp - p["panel_e"] < p["arr_d"] + 0.004):
                    out.append(tr("c_fach_brace", f=tr("fk_" + fk)))
        return out

    def lateral_panels(self, sd: str) -> bool:
        return self.p["paneles"] and self.p["fach_" + ("izq" if sd == "l" else "der")]

    def pinon_depth(self) -> float:
        return max(PROFILES[self.p["fach_esquina"]][0], PROFILES[self.p["fach_intermedio"]][0])

    def pinon_lines(self) -> list[tuple]:
        """Piñones activos: (clave, origen, dirección). El origen está en el
        plano exterior de la fachada y en su extremo inicial; la normal izquierda
        de la dirección apunta al exterior. Longitud = luz."""
        off = self.bp / 2 + self.p["fach_holgura"] + self.pinon_depth()
        lines = {"frontal": ((self.L, -off), (-1.0, 0.0)),
                 "posterior": ((0.0, self.Ln + off), (1.0, 0.0))}
        return [(fk, *lines[fk]) for fk in PINONES if self.p["fach_" + fk]]

    def pinon_layout(self) -> tuple:
        """Posiciones de los perfiles del piñón (extremos con perfil U) y
        tramos de panel entre almas."""
        p = self.p
        length = self.L
        nv = max(1, math.ceil(length / p["fach_sep"] - 1e-9))
        posts = [length * k / nv for k in range(nv + 1)]
        twu = PROFILES[p["fach_esquina"]][2]
        twh = PROFILES[p["fach_intermedio"]][2]
        spans = []
        for i in range(nv):
            a = posts[i] + (twu if i == 0 else twh / 2) + PANEL_GAP
            b = posts[i + 1] - (twu if i == nv - 1 else twh / 2) - PANEL_GAP
            spans.append((a, b))
        return posts, spans

    def lateral_spans(self) -> list[tuple]:
        """Tramos de panel lateral en Y, de alma a alma de pilar."""
        if self.n < 2:
            return []
        return [(i * self.s + self.twp / 2 + PANEL_GAP,
                 (i + 1) * self.s - self.twp / 2 - PANEL_GAP) for i in range(self.n - 1)]

    def courses(self, fk: str) -> list[tuple]:
        """Hiladas de paneles (cota inferior, altura) de la fachada fk."""
        out = []
        H, hp = self.p["fach_h_" + fk], self.p["panel_h_" + fk]
        z = 0.0
        while z < H - 1e-6:
            hh = min(hp, H - z)
            out.append((z, hh))
            z += hh
        return out

    def panel_tf(self) -> float:
        """Ala exterior más gruesa de los perfiles del piñón: el panel la toca."""
        return max(PROFILES[self.p["fach_esquina"]][3], PROFILES[self.p["fach_intermedio"]][3])

    def wall_brace_x(self, sd: str) -> float:
        """Plano de las cruces de fachada (abscisa del faldón): eje del pilar, o
        centro del hueco entre panel y ala interior si hay paneles."""
        if self.lateral_panels(sd):
            return (self.tfp + self.p["panel_e"] + self.hp - self.tfp) / 2
        return self.hp / 2

    def panel_summary(self) -> dict:
        """Paneles por fachada: {clave: (unidades, m², m³)}."""
        p = self.p
        out = {}
        if not p["paneles"]:
            return out
        for fk in self.facades_on():
            nc = len(self.courses(fk))
            if fk in PINONES:
                spans = self.pinon_layout()[1]
            else:
                spans = self.lateral_spans()
            if not spans:
                continue
            area = sum(b - a for a, b in spans) * p["fach_h_" + fk]
            out[fk] = (len(spans) * nc, area, area * p["panel_e"])
        return out

    def notes(self) -> list[str]:
        """Avisos informativos (no bloquean)."""
        p = self.p
        if (p["arr_cub"] or p["arr_fach"]) and self.n < 2:
            return [tr("c_info_brace")]
        return []

    # --- Arriostramiento -------------------------------------------------

    def braced_bays(self) -> list[int]:
        """Índices de vano (0 … n−2) con cruces de San Andrés."""
        if self.n < 2 or not (self.p["arr_cub"] or self.p["arr_fach"]):
            return []
        if self.p["arr_vanos"] == "todos":
            return list(range(self.n - 1))
        return sorted({0, self.n - 2})

    def roof_brace_dz(self) -> float:
        """Distancia del plano de cruces de cubierta bajo la cara superior del dintel."""
        return min(PROFILES[r][0] for r in self.rafter.values()) / 4

    def roof_brace_nodes(self, sd: str) -> list[float]:
        """Abscisas (coordenadas del faldón) de los nudos de las cruces de cubierta."""
        side = self.side(sd)
        k = self.p["arr_recuadros"]
        x0 = self.hp
        return [x0 + j * (side.xs - x0) / k for j in range(k + 1)]

    def wall_brace_top(self, sd: str) -> float:
        """Cabeza de las cruces de fachada: cara inferior del dintel más bajo
        en el pilar de ese lado."""
        return min(self.side(sd, kind).z_knee for kind in self.kinds_used())


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


def u_profile(h, b, tw, tf):
    """Perfil U: alma en u ∈ [0, tw], alas hacia +u; w centrado."""
    hh = h / 2
    return [(0, -hh), (b, -hh), (b, -hh + tf), (tw, -hh + tf), (tw, hh - tf),
            (b, hh - tf), (b, hh), (0, hh)]


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


def rod_kgm(d: float) -> float:
    return math.pi * d * d / 4 * STEEL


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


def rod(mesh, p, q, d, attrs, sides=8) -> None:
    """Redondo de diámetro d entre los puntos p y q (prisma de ``sides`` caras)."""
    v = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
    ln = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if ln <= 1e-9:
        return
    e = (v[0] / ln, v[1] / ln, v[2] / ln)
    ref = (0.0, 0.0, 1.0) if abs(e[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = (e[1] * ref[2] - e[2] * ref[1], e[2] * ref[0] - e[0] * ref[2],
         e[0] * ref[1] - e[1] * ref[0])
    lu = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2)
    u = (u[0] / lu, u[1] / lu, u[2] / lu)
    w = (e[1] * u[2] - e[2] * u[1], e[2] * u[0] - e[0] * u[2], e[0] * u[1] - e[1] * u[0])
    r = d / 2
    cap = []
    for i in range(sides):
        c, s = math.cos(2 * math.pi * i / sides), math.sin(2 * math.pi * i / sides)
        cap.append(tuple(p[j] + r * (c * u[j] + s * w[j]) for j in range(3)))
    prism(mesh, cap, v, attrs)


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
    name = tr("mt_" + key)
    if name not in scene.materials:
        scene.materials[name] = Material(name, color=MAT_RGB[key])
    return scene.materials[name].face_attrs()


def _ensure_layers(scene, keys) -> None:
    from core.layers import Layer
    have = {ly.name for ly in scene.layers}
    for k in keys:
        if layer_name(k) not in have:
            scene.layers.append(Layer(layer_name(k)))


def _haunch(mesh, web_pts_xz, tw, b, tf, under_a, under_b, attrs):
    """Cartela soldada: alma (polígono en XZ, espesor tw) y ala inferior
    (chapa b × tf siguiendo el borde inferior under_a → under_b)."""
    prism(mesh, [(x, -tw / 2, z) for x, z in web_pts_xz], (0, tw, 0), attrs)
    (xa, za), (xb, zb) = under_a, under_b
    flange = [(xa, za), (xb, zb), (xb, zb - tf), (xa, za - tf)]
    prism(mesh, [(x, -b / 2, z) for x, z in flange], (0, b, 0), attrs)


class _Builder:
    """Construye las piezas reutilizando mallas iguales (componentes)."""

    def __init__(self, scene, p: dict) -> None:
        self.scene = scene
        self.p = p
        self.g = Geo(p)
        self.est = _paint(scene, "est")
        self.ly_est = layer_name("est")
        self.R = _rot_about_center(self.g.L / 2, self.g.Ln / 2)   # piezas longitudinales
        self.R0 = _rot_about_center(self.g.L / 2, 0.0)            # dentro del pórtico
        self._cache: dict = {}

    def cached(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    # --- Piezas del pórtico (coordenadas del faldón; derecha con R0) ----

    def column_mesh(self, Hp):
        g = self.g

        def make():
            m = _mesh()
            prism(m, [(w, u, 0.0) for u, w in i_section(g.hp, g.bp, g.twp, g.tfp)],
                  (0, 0, Hp), self.est)
            return m
        return self.cached(("col", round(Hp, 6)), make)

    def rafter_mesh(self, side: Side):
        def make():
            x0 = self.g.hp                      # cara interior del pilar
            zc = side.z_top(x0) - side.hv / 2
            run = side.xs - x0
            m = _mesh()
            prism(m, [(x0, u, zc + w / self.g.ca)
                      for u, w in i_section(side.hd, side.bd, side.twd, side.tfd)],
                  (run, 0, run * side.t), self.est)
            return m
        return self.cached(("raf", round(side.H, 6), round(side.xs, 6), side.rafter), make)

    def eaves_haunch_mesh(self, side: Side):
        p, g = self.p, self.g

        def make():
            Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
            x0, x1 = g.hp, g.hp + Lc
            A = (x0, side.z_under(x0) - hc)
            B = (x1, side.z_under(x1))
            m = _mesh()
            _haunch(m, [(x0, side.z_under(x0)), B, A], side.twd, side.bd, side.tfd, A, B,
                    self.est)
            return m
        return self.cached(("ca", round(side.H, 6), side.rafter), make)

    def ridge_haunch_mesh(self, kind):
        p, g = self.p, self.g
        side = g.side("l", kind)

        def make():
            Lk, hk = p["cart_cumb_l"], p["cart_cumb_h"]
            xm = g.xr
            zr = side.z_under(xm)
            zs = side.z_under(xm - Lk)
            P0, Pb, P1 = (xm - Lk, zs), (xm, zr - hk), (xm + Lk, zs)
            m = _mesh()
            prism(m, [(x, -side.twd / 2, z) for x, z in [P0, (xm, zr), P1, Pb]],
                  (0, side.twd, 0), self.est)
            for a, b in ((P0, Pb), (Pb, P1)):
                (xa, za), (xb, zb) = a, b
                prism(m, [(x, -side.bd / 2, z) for x, z in
                          [(xa, za), (xb, zb), (xb, zb - side.tfd), (xa, za - side.tfd)]],
                      (0, side.bd, 0), self.est)
            return m
        return self.cached(("ck", side.rafter), make)

    def bracket_mesh(self):
        p, g = self.p, self.g

        def make():
            hm, bm, twm, tfm, _kg = PROFILES[p["mensula"]]
            bvc = PROFILES[p["viga_carril"]][1]
            Lm = p["mensula_vuelo"] + bvc / 2
            zm = p["mensula_z"] - hm / 2
            m = _mesh()
            prism(m, [(g.hp, u, zm + w) for u, w in i_section(hm, bm, twm, tfm)], (Lm, 0, 0),
                  _paint(self.scene, "pg"))
            return m
        return self.cached("me", make)

    def frame_parts(self, kind) -> list:
        p, g = self.p, self.g
        L = g.L
        sl, sr = g.side("l", kind), g.side("r", kind)
        parts = [
            _group(self.column_mesh(sl.Hp), tr("n_col_l"), _T(g.hp / 2),
                   layer=self.ly_est, ifc="IfcColumn"),
            _group(self.column_mesh(sr.Hp), tr("n_col_r"), _T(L - g.hp / 2),
                   layer=self.ly_est, ifc="IfcColumn"),
            _group(self.rafter_mesh(sl), tr("n_raf_l"), None, layer=self.ly_est, ifc="IfcBeam"),
            _group(self.rafter_mesh(sr), tr("n_raf_r"), self.R0, layer=self.ly_est,
                   ifc="IfcBeam"),
        ]
        if p["cart_alero_l"] > 0 and p["cart_alero_h"] > 0:
            parts += [_group(self.eaves_haunch_mesh(sl), tr("n_ca_l"), None, layer=self.ly_est,
                             ifc="IfcMember"),
                      _group(self.eaves_haunch_mesh(sr), tr("n_ca_r"), self.R0,
                             layer=self.ly_est, ifc="IfcMember")]
        if p["cart_cumb_l"] > 0 and p["cart_cumb_h"] > 0:
            parts.append(_group(self.ridge_haunch_mesh(kind), tr("n_ck"), None,
                                layer=self.ly_est, ifc="IfcMember"))
        if p["grua"]:
            ly = layer_name("pg")
            parts += [_group(self.bracket_mesh(), tr("n_me_l"), None, layer=ly, ifc="IfcMember"),
                      _group(self.bracket_mesh(), tr("n_me_r"), self.R0, layer=ly,
                             ifc="IfcMember")]
        return parts

    # --- Pórticos --------------------------------------------------------

    def frames(self) -> list:
        """Pórticos 1 … n: una definición para los interiores y otra para los
        extremos (si su dintel es distinto); el resto son copias."""
        from core.group import Group, copy_group
        g = self.g
        defs: dict = {}
        out = []
        for i in range(g.n):
            kind = g.kind(i)
            if kind not in defs:
                first = Group(name=tr("n_frame", i=i + 1))
                first.adopt(self.frame_parts(kind))
                first.component = True
                first.layer = self.ly_est
                if i:
                    first.xform = _T(0, i * g.s, 0)
                defs[kind] = (first, i)
                out.append(first)
            else:
                src, i0 = defs[kind]
                c = copy_group(src, delta=QVector3D(0, (i - i0) * g.s, 0))
                c.name = tr("n_frame", i=i + 1)
                out.append(c)
        return out

    # --- Correas, canalones, vigas carril --------------------------------

    def purlins(self) -> list:
        p, g = self.p, self.g
        poly, _kg, _h = g.purlin_section()
        v = p["correa_vuelo"]
        Lco = g.Ln + 2 * v
        if Lco <= 0:
            return []
        m_co = _mesh()
        prism(m_co, [(u, -v, w) for u, w in poly], (0, Lco, 0), _paint(self.scene, "cor"))
        ly = layer_name("cor")
        inst = []
        for sd, name, R in (("l", "n_cor_l", None), ("r", "n_cor_r", self.R)):
            H = g.side(sd).H
            for k, a in enumerate(g.purlin_positions(sd), 1):
                M = _T(a * g.ca, 0, H + a * g.sa)
                M.rotate(-math.degrees(g.a), 0, 1, 0)
                inst.append(_group(m_co, tr(name, k=k), M if R is None else R * M,
                                   layer=ly, ifc="IfcMember"))
        return [_container(tr("n_cor"), inst, ly)]

    def gutters(self) -> list:
        p, g = self.p, self.g
        v = p["correa_vuelo"]
        Lco = g.Ln + 2 * v
        if not p["canalon"] or Lco <= 0:
            return []
        a, h, e = p["canalon_a"], p["canalon_h"], p["canalon_e"]
        if min(a, h, e) <= 0 or 2 * e >= min(a, h):
            raise NaveError(tr("e_gutter"))
        # Apoyado sobre el dintel, junto al ala interior del pilar: el fondo
        # descansa en el punto alto del dintel bajo él (x = hp + a).
        m_cn = _mesh()
        zb = (g.hp + a) * g.t
        prism(m_cn, [(g.hp + u, -v, zb + w) for u, w in u_section(a, h, e)], (0, Lco, 0),
              _paint(self.scene, "can"))
        ly = layer_name("can")
        return [_container(tr("n_can"), [
            _group(m_cn, tr("n_can_l"), _T(0, 0, g.Hl), layer=ly),
            _group(m_cn, tr("n_can_r"), self.R * _T(0, 0, g.Hr), layer=ly)], ly)]

    def runway(self) -> list:
        p, g = self.p, self.g
        if not p["grua"] or g.Ln <= 0:
            return []
        hvc, bvc, twv, tfv, _kg = PROFILES[p["viga_carril"]]
        xv = g.hp + p["mensula_vuelo"]
        m_vc = _mesh()
        prism(m_vc, [(xv + u, 0.0, p["mensula_z"] + hvc / 2 + w)
                     for u, w in i_section(hvc, bvc, twv, tfv)], (0, g.Ln, 0),
              _paint(self.scene, "pg"))
        ly = layer_name("pg")
        return [_container(tr("n_pg"), [
            _group(m_vc, tr("n_vc_l"), None, layer=ly, ifc="IfcBeam"),
            _group(m_vc, tr("n_vc_r"), self.R, layer=ly, ifc="IfcBeam")], ly)]

    # --- Cruces de San Andrés -------------------------------------------

    def bracing(self) -> list:
        p, g = self.p, self.g
        bays = g.braced_bays()
        if not bays:
            return []
        d = p["arr_d"]
        attrs = _paint(self.scene, "arr")
        ly = layer_name("arr")
        s, L = g.s, g.L

        def gx(sd, x):          # abscisa del faldón → abscisa de la nave
            return x if sd == "l" else L - x

        def cross(m, a, b):     # cruz entre los puntos (x, z) a y b, de y = 0 a y = s
            (xa, za), (xb, zb) = a, b
            rod(m, (xa, 0.0, za), (xb, s, zb), d, attrs)
            rod(m, (xb, 0.0, zb), (xa, s, za), d, attrs)

        inst = []
        for sd in ("l", "r"):
            side = g.side(sd)
            if p["arr_cub"]:
                m = _mesh()
                dz = g.roof_brace_dz()
                xs = g.roof_brace_nodes(sd)
                for x0, x1 in zip(xs, xs[1:]):
                    cross(m, (gx(sd, x0), side.z_top(x0) - dz), (gx(sd, x1), side.z_top(x1) - dz))
                for j in bays:
                    inst.append(_group(m, tr("n_acub_" + sd, j=j + 1), _T(0, j * s, 0),
                                       layer=ly, ifc="IfcMember"))
            if p["arr_fach"]:
                m = _mesh()
                x = gx(sd, g.wall_brace_x(sd))
                top = g.wall_brace_top(sd)
                k = p["arr_fach_n"]
                zs = [i * top / k for i in range(k + 1)]
                for z0, z1 in zip(zs, zs[1:]):
                    cross(m, (x, z0), (x, z1))
                for j in bays:
                    inst.append(_group(m, tr("n_afach_" + sd, j=j + 1), _T(0, j * s, 0),
                                       layer=ly, ifc="IfcMember"))
        return [_container(tr("n_arr"), inst, ly)]

    # --- Fachadas ----------------------------------------------------------

    def facades(self) -> list:
        p, g = self.p, self.g
        if not g.has_facade():
            return []
        g.facade_check()
        fac = _paint(self.scene, "fac")
        pan = _paint(self.scene, "pan") if p["paneles"] else None
        ly_f, ly_p = layer_name("fac"), layer_name("pan")
        e = p["panel_e"]

        def box(s0, s1, t0, t1, height):
            """Prisma rectangular (s, t, z) compartido entre paneles iguales."""
            def make():
                m = _mesh()
                prism(m, [(s0, t0, 0), (s1, t0, 0), (s1, t1, 0), (s0, t1, 0)],
                      (0, 0, height), pan)
                return m
            key = ("box",) + tuple(round(v, 5) for v in (s0, s1, t0, t1, height))
            return self.cached(key, make)

        def post(kind, H):
            """Perfil vertical de piñón: exterior en t = 0, canto hacia t < 0."""
            def make():
                m = _mesh()
                if kind == "h":
                    h, b, tw, tf, _k = PROFILES[p["fach_intermedio"]]
                    sec = i_section(h, b, tw, tf)
                else:
                    h, b, tw, tf, _k = PROFILES[p["fach_esquina"]]
                    sec = [(u if kind == "u0" else -u, w) for u, w in u_profile(h, b, tw, tf)]
                prism(m, [(u, w - h / 2, 0.0) for u, w in sec], (0, 0, H), fac)
                return m
            return self.cached(("post", kind, round(H, 6)), make)

        groups = []
        if any(fk in PINONES for fk in g.facades_on()):
            tf = g.panel_tf()
            posts, spans = g.pinon_layout()
            for fk, origin, d in g.pinon_lines():
                H = p["fach_h_" + fk]
                F = _frame_matrix(origin, d)

                def at(s_, z=0.0, F=F):
                    M = QMatrix4x4(F)
                    M.translate(QVector3D(s_, 0, z))
                    return M
                kids = [_group(post("u0", H), tr("n_post_c", prof=p["fach_esquina"], k=1),
                               at(0.0), layer=ly_f, ifc="IfcColumn"),
                        _group(post("u1", H), tr("n_post_c", prof=p["fach_esquina"], k=2),
                               at(g.L), layer=ly_f, ifc="IfcColumn")]
                for k, s_ in enumerate(posts[1:-1], 1):
                    kids.append(_group(post("h", H), f"{p['fach_intermedio']} {k}", at(s_),
                                       layer=ly_f, ifc="IfcColumn"))
                if p["paneles"]:
                    for i, (a, b) in enumerate(spans, 1):
                        for j, (z0, hz) in enumerate(g.courses(fk), 1):
                            kids.append(_group(box(0, b - a, -tf - e, -tf, hz),
                                               tr("n_panel", i=i, j=j), at(a, z0),
                                               layer=ly_p, ifc="IfcWall"))
                groups.append(_container(tr("n_fach_" + fk), kids, ly_f))
        spans = g.lateral_spans()
        if spans and p["paneles"]:
            x0, x1 = g.tfp, g.tfp + e
            for fk, sd in (("izq", "l"), ("der", "r")):
                if not p["fach_" + fk]:
                    continue
                kids = []
                for i, (y0, y1) in enumerate(spans, 1):
                    for j, (z0, hz) in enumerate(g.courses(fk), 1):
                        M = _T(0, y0, z0)
                        kids.append(_group(box(x0, x1, 0, y1 - y0, hz), tr("n_panel", i=i, j=j),
                                           M if sd == "l" else self.R * M,
                                           layer=ly_p, ifc="IfcWall"))
                groups.append(_container(tr("n_fach_" + fk), kids, ly_p))
        return groups


def _frame_matrix(origin, d) -> QMatrix4x4:
    """Sistema local de una fachada: s según d, t = normal izquierda
    (exterior), z vertical."""
    dx, dy = d
    return QMatrix4x4(dx, -dy, 0.0, origin[0],
                      dy, dx, 0.0, origin[1],
                      0.0, 0.0, 1.0, 0.0,
                      0.0, 0.0, 0.0, 1.0)


def build_nave(scene, params) -> list:
    """Hijos del contenedor de la nave, en coordenadas locales de la nave."""
    p = normalize(params)
    b = _Builder(scene, p)
    out = (b.frames() + b.purlins() + b.gutters() + b.runway() + b.bracing()
           + b.facades())
    keys = ["est", "cor"] + (["can"] if p["canalon"] else []) + (["pg"] if p["grua"] else [])
    if b.g.braced_bays():
        keys.append("arr")
    if b.g.has_facade():
        keys += ["fac"] + (["pan"] if p["paneles"] else [])
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
    asym = abs(g.Hl - g.Hr) > 1e-9
    ext_on = p["dintel_ext_on"] and g.rafter["ext"] != g.rafter["int"]
    count = {k: sum(1 for i in range(g.n) if g.kind(i) == k) for k in ("int", "ext")}
    rows: list = []

    def label(key, sd=None, kind=None):
        s = tr(key)
        extra = []
        if sd and asym:
            extra.append(tr("side_" + sd))
        if kind and ext_on:
            extra.append(tr("kind_" + kind))
        return s + (" — " + ", ".join(extra) if extra else "")

    def add(elem, prof, units, length, kgm):
        if units <= 0:
            return
        for i, r in enumerate(rows):
            if r[0] == elem and r[1] == prof and abs(r[3] - length) < 1e-6 and r[4] == kgm:
                rows[i] = (elem, prof, r[2] + units, length, kgm)
                return
        rows.append((elem, prof, units, length, kgm))

    kinds = g.kinds_used()
    for kind in kinds:
        for sd in ("l", "r"):
            side = g.side(sd, kind)
            add(label("r_pil", sd, kind), p["pilar"], count[kind], side.Hp, g.kgp)
    for kind in kinds:
        for sd in ("l", "r"):
            side = g.side(sd, kind)
            add(label("r_din", sd, kind), side.rafter, count[kind], side.Lrafter, side.kgd)
    Lc, hc = p["cart_alero_l"], p["cart_alero_h"]
    if Lc > 0 and hc > 0:
        for kind in kinds:
            sd = g.side("l", kind)
            kg = (Lc * hc / 2 * sd.twd + math.hypot(Lc, hc + Lc * g.t) * sd.bd * sd.tfd) * STEEL
            add(label("r_ca", None, kind), tr("r_plate", tw=sd.twd * 1000, tf=sd.tfd * 1000),
                2 * count[kind], Lc, kg / Lc)
    Lk, hk = p["cart_cumb_l"], p["cart_cumb_h"]
    if Lk > 0 and hk > 0:
        for kind in kinds:
            sd = g.side("l", kind)
            kg = (Lk * hk * sd.twd + 2 * math.hypot(Lk, hk - Lk * g.t) * sd.bd * sd.tfd) * STEEL
            add(label("r_ck", None, kind), tr("r_plate", tw=sd.twd * 1000, tf=sd.tfd * 1000),
                count[kind], 2 * Lk, kg / (2 * Lk))
    _poly, kgc, _h = g.purlin_section()
    Lco = g.Ln + 2 * p["correa_vuelo"]
    if Lco > 0:
        name = (p["correa_ipe"] if p["correa_tipo"] == "IPE" else
                f"{p['correa_tipo']} {p['correa_h']*1000:.0f}×{p['correa_b']*1000:.0f}×"
                f"{p['correa_e']*1000:.1f}")
        for sd in ("l", "r"):
            add(tr("r_cor"), name, len(g.purlin_positions(sd)), Lco, kgc)
    if p["canalon"] and Lco > 0:
        kg = polygon_area(u_section(p["canalon_a"], p["canalon_h"], p["canalon_e"])) * STEEL
        add(tr("r_can"), f"U {p['canalon_a']*1000:.0f}×{p['canalon_h']*1000:.0f}×"
            f"{p['canalon_e']*1000:.1f}", 2, Lco, kg)
    if p["grua"]:
        bvc = PROFILES[p["viga_carril"]][1]
        add(tr("r_mens"), p["mensula"], 2 * g.n, p["mensula_vuelo"] + bvc / 2,
            PROFILES[p["mensula"]][4])
        if g.Ln > 0:
            add(tr("r_vc"), p["viga_carril"], 2, g.Ln, PROFILES[p["viga_carril"]][4])
    bays = g.braced_bays()
    if bays:
        d = p["arr_d"]
        prof = f"Ø{d*1000:.0f}"
        kgm = rod_kgm(d)
        for sd in ("l", "r"):
            if p["arr_cub"]:
                xs = g.roof_brace_nodes(sd)
                dl = (xs[1] - xs[0]) / g.ca
                add(label("r_acub", sd), prof, 2 * p["arr_recuadros"] * len(bays),
                    math.hypot(g.s, dl), kgm)
            if p["arr_fach"]:
                k = p["arr_fach_n"]
                add(label("r_afach", sd), prof, 2 * k * len(bays),
                    math.hypot(g.s, g.wall_brace_top(sd) / k), kgm)
    if g.has_facade():
        g.facade_check()
        posts = g.pinon_layout()[0]
        for fk in PINONES:
            if not p["fach_" + fk]:
                continue
            H = p["fach_h_" + fk]
            add(tr("r_post_c", f=tr("fk_" + fk)), p["fach_esquina"], 2, H,
                PROFILES[p["fach_esquina"]][4])
            add(tr("r_post_h", f=tr("fk_" + fk)), p["fach_intermedio"], len(posts) - 2, H,
                PROFILES[p["fach_intermedio"]][4])
    return [(e, prof, u, l, kgm, u * l * kgm) for e, prof, u, l, kgm in rows]


def panel_rows(params) -> list[tuple]:
    """Paneles de hormigón por fachada: (fachada, unidades, m², m³)."""
    p = normalize(params)
    g = Geo(p)
    if not g.has_facade():
        return []
    g.facade_check()
    return [(tr("fk_" + fk), u, a, v) for fk, (u, a, v) in g.panel_summary().items()]


def summary(params) -> str:
    p = normalize(params)
    g = Geo(p)
    kg = sum(r[5] for r in measurement(p))
    kl, kr = len(g.purlin_positions("l")), len(g.purlin_positions("r"))
    cor = tr("sum_cor", k=kl) if kl == kr else tr("sum_cor2", kl=kl, kr=kr)
    txt = tr("sum", L=g.L, Ln=g.Ln, n=g.n, cor=cor, kg=_num(kg))
    pr = panel_rows(p)
    if pr:
        txt += tr("sum_pan", u=sum(r[1] for r in pr), m2=_num(sum(r[2] for r in pr), 1))
    return txt


# ---------------------------------------------------------------------------
# Operaciones sobre el documento
# ---------------------------------------------------------------------------

def nave_data(group):
    ext = getattr(group, "ext", None) or {}
    return ext.get(KEY)


def _next_name(scene) -> str:
    used = {gr.name for gr in scene.groups}
    i = 1
    while f"{tr('nave')} {i}" in used:
        i += 1
    return f"{tr('nave')} {i}"


def make_nave(scene, params, name=None, xform=None, index=None, layer=None, uid=None):
    """Crea el contenedor de la nave y lo añade al documento."""
    p = normalize(params)
    children = build_nave(scene, p)          # lanza NaveError antes de tocar el documento
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
    """Sustituye la nave por otra con nuevos parámetros, en el mismo lugar.
    La nave nueva se genera antes de retirar la existente."""
    if nave_data(group) is None:
        raise NaveError(tr("w_not_nave", name=group.name))
    p = normalize(params)
    children = build_nave(scene, p)
    idx = scene.groups.index(group)
    scene.groups.remove(group)
    scene.selection.discard(group)
    c = _container(group.name, children, group.layer)
    c.xform = QMatrix4x4(group.xform)
    if group.uid:
        c.uid = group.uid
    c.ext = {KEY: {"params": json.loads(json.dumps(p))}}
    scene.groups.insert(idx, c)
    return c


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
    last = (data.get(KEY) or {}).get("last")
    return normalize(last, legacy=False)


def _remember(scene, p) -> None:
    data = getattr(scene, "plugin_data", None)
    if data is not None:
        data.setdefault(KEY, {})["last"] = json.loads(json.dumps(p))


def nueva(viewport) -> None:
    scene = viewport.scene
    if getattr(scene, "edit_group", None) is not None:
        _warn(viewport, tr("w_close_group"))
        return
    p = NaveDialog.ask(viewport, _last_params(scene), lambda: tr("t_new"))
    if p is None:
        return

    def mutate(sc):
        _remember(sc, p)
        c = make_nave(sc, p)
        sc.selection.clear()
        sc.selection.add(c)
    _run(viewport, mutate, f"{title()}: {tr('ok_new')} " + summary(p))


def editar(viewport) -> None:
    scene = viewport.scene
    naves = _selected_naves(scene)
    if not naves:
        _warn(viewport, tr("w_select"))
        return
    nave = naves[0]
    p = NaveDialog.ask(viewport, normalize(nave_data(nave).get("params")),
                       lambda: tr("t_edit", name=nave.name))
    if p is None:
        return

    def mutate(sc):
        _remember(sc, p)
        c = rebuild_nave(sc, nave, p)
        sc.selection.clear()
        sc.selection.add(c)
    _run(viewport, mutate, f"{title()}: {tr('ok_edit', name=nave.name)} " + summary(p))


def medicion(viewport) -> None:
    scene = viewport.scene
    naves = _selected_naves(scene)
    if not naves:
        _warn(viewport, tr("w_select"))
        return
    MeasureDialog.show_for(viewport, naves[0])


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------

def _warn(viewport, text) -> None:
    from PySide6.QtWidgets import QMessageBox
    try:
        viewport.flash_status(f"{title()}: " + text.splitlines()[0], 6000)
    except Exception:  # noqa: BLE001
        pass
    QMessageBox.warning(viewport.window(), title(), text)


class NaveDialog:
    """Cuadro de parámetros, por pestañas, con avisos en vivo. Al cambiar de
    idioma se vuelve a abrir conservando los valores introducidos."""

    @classmethod
    def ask(cls, viewport, params, title_fn):
        p = normalize(params)
        while True:
            status, p = cls._ask_once(viewport, p, title_fn)
            if status != "relang":
                return p if status == "ok" else None

    @classmethod
    def _ask_once(cls, viewport, p0, title_fn):
        from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                       QDoubleSpinBox, QFormLayout, QGridLayout, QLabel,
                                       QMessageBox, QSpinBox, QTabWidget, QVBoxLayout,
                                       QWidget)
        dlg = QDialog(viewport.window())
        dlg.setWindowTitle(f"{title()} — {title_fn()}")
        dlg.setMinimumWidth(760)
        lay = QVBoxLayout(dlg)
        top = QFormLayout()
        lang_cb = QComboBox()
        for code, name in LANGS:
            lang_cb.addItem(name, code)
        lang_cb.setCurrentIndex([c for c, _ in LANGS].index(lang()))
        top.addRow(tr("lang"), lang_cb)
        lay.addLayout(top)
        tabs = QTabWidget()
        lay.addWidget(tabs)
        w: dict = {}

        def page(key):
            pg = QWidget()
            form = QFormLayout(pg)
            tabs.addTab(pg, tr(key))
            return form

        def note(form, key):
            lb = QLabel(tr(key))
            lb.setWordWrap(True)
            form.addRow(lb)

        def length(form, key, label, lo=0.0, hi=200.0, dec=3, step=0.05, suffix=" m"):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(dec)
            sb.setSingleStep(step)
            sb.setSuffix(suffix)
            sb.setValue(p0[key])
            form.addRow(tr(label), sb)
            w[key] = sb
            return sb

        def mm(form, key, label, hi=1000.0, dec=1):
            sb = QDoubleSpinBox()
            sb.setRange(0.0, hi)
            sb.setDecimals(dec)
            sb.setSuffix(" mm")
            sb.setValue(p0[key] * 1000)
            sb.setProperty("mm", True)
            form.addRow(tr(label), sb)
            w[key] = sb
            return sb

        def integer(form, key, label, lo, hi):
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(p0[key])
            form.addRow(tr(label), sb)
            w[key] = sb
            return sb

        def profile(form, key, label, series=("IPE", "HEA", "HEB")):
            cb = QComboBox()
            cb.addItems([n for n in PROFILE_NAMES if n.split()[0] in series])
            cb.setCurrentText(p0[key])
            form.addRow(tr(label), cb)
            w[key] = cb
            return cb

        def coded(form, key, label, codes, prefix):
            cb = QComboBox()
            for c in codes:
                cb.addItem(tr(prefix + c), c)
            cb.setCurrentIndex(codes.index(p0[key]))
            cb.setProperty("coded", True)
            form.addRow(tr(label), cb)
            w[key] = cb
            return cb

        def check(form, key, label):
            cb = QCheckBox(tr(label))
            cb.setChecked(p0[key])
            form.addRow(cb)
            w[key] = cb
            return cb

        def enable_with(ctrl, widgets, extra=None):
            def sync(*_a):
                on = ctrl.isChecked() if extra is None else extra()
                for x in widgets:
                    x.setEnabled(on)
            ctrl.toggled.connect(sync)
            sync()
            return sync

        f = page("tab_geo")
        length(f, "luz", "f_luz", 2.0, 100.0)
        length(f, "alero", "f_alero", 1.0, 50.0)
        length(f, "alero_der", "f_alero_der", 1.0, 50.0)
        note(f, "f_alero_note")
        length(f, "pendiente", "f_pend", 0.0, 99.0, 2, 1.0, " %")
        integer(f, "n_porticos", "f_n", 1, 200)
        length(f, "separacion", "f_sep", 0.5, 30.0)

        f = page("tab_frame")
        profile(f, "pilar", "f_pilar")
        profile(f, "dintel", "f_dintel")
        length(f, "pilar_sobre", "f_sobre", 0.0, 1.0, 3, 0.01)
        dext_on = check(f, "dintel_ext_on", "f_dext_on")
        dext = profile(f, "dintel_ext", "f_dext")
        enable_with(dext_on, [dext])
        length(f, "cart_alero_l", "f_ca_l", 0.0, 10.0)
        length(f, "cart_alero_h", "f_ca_h", 0.0, 3.0)
        length(f, "cart_cumb_l", "f_ck_l", 0.0, 10.0)
        length(f, "cart_cumb_h", "f_ck_h", 0.0, 3.0)
        note(f, "f_cart_note")

        f = page("tab_purlin")
        tipo = coded(f, "correa_tipo", "f_ctipo", PURLIN_TYPES, "p_")
        conf = [mm(f, "correa_h", "f_ch"), mm(f, "correa_b", "f_cb"),
                mm(f, "correa_e", "f_ce", 20.0, 2), mm(f, "correa_c", "f_cc")]
        ipe = profile(f, "correa_ipe", "f_cipe", ("IPE",))
        length(f, "correa_sep", "f_csep", 0.3, 5.0)
        length(f, "correa_d_alero", "f_cda", 0.0, 3.0)
        length(f, "correa_d_cumbrera", "f_cdc", 0.0, 3.0)
        length(f, "correa_vuelo", "f_cv", 0.0, 3.0)

        def sync_tipo():
            is_ipe = tipo.currentData() == "IPE"
            for sb in conf:
                sb.setEnabled(not is_ipe)
            ipe.setEnabled(is_ipe)
        tipo.currentIndexChanged.connect(lambda _i: sync_tipo())
        sync_tipo()

        f = page("tab_gutter")
        cn = check(f, "canalon", "f_can")
        enable_with(cn, [mm(f, "canalon_a", "f_cana"), mm(f, "canalon_h", "f_canh"),
                         mm(f, "canalon_e", "f_cane", 20.0, 2)])

        f = page("tab_crane")
        pg = check(f, "grua", "f_grua")
        enable_with(pg, [profile(f, "mensula", "f_mens"),
                         length(f, "mensula_z", "f_mz", 0.5, 50.0),
                         length(f, "mensula_vuelo", "f_mv", 0.05, 3.0),
                         profile(f, "viga_carril", "f_vc")])

        f = page("tab_brace")
        acub = check(f, "arr_cub", "f_acub")
        afach = check(f, "arr_fach", "f_afach")
        common = [coded(f, "arr_vanos", "f_avanos", BRACED_BAYS, "v_"),
                  mm(f, "arr_d", "f_ad", 60.0, 0)]
        arec = integer(f, "arr_recuadros", "f_arec", 1, 20)
        afn = integer(f, "arr_fach_n", "f_afn", 1, 10)
        note(f, "f_brace_note")
        enable_with(acub, [arec])
        enable_with(afach, [afn])
        both = lambda: acub.isChecked() or afach.isChecked()  # noqa: E731
        enable_with(acub, common, both)
        enable_with(afach, common, both)

        f = page("tab_fach")
        pnl = check(f, "paneles", "f_paneles")
        pnl_w = [mm(f, "panel_e", "f_panel_e", 600.0, 0)]
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 4, 0, 4)
        for c, key in enumerate(("g_fach", "g_on", "g_h", "g_ph")):
            hd = QLabel(f"<b>{tr(key)}</b>")
            grid.addWidget(hd, 0, c)
        fach_rows = {}
        for r, fk in enumerate(FACADES, 1):
            cb = QCheckBox()
            cb.setChecked(p0["fach_" + fk])
            w["fach_" + fk] = cb
            hs = QDoubleSpinBox()
            hs.setRange(0.0, 50.0)
            hs.setDecimals(3)
            hs.setSingleStep(0.1)
            hs.setSuffix(" m")
            hs.setValue(p0["fach_h_" + fk])
            w["fach_h_" + fk] = hs
            ps = QDoubleSpinBox()
            ps.setRange(0.0, 10.0)
            ps.setDecimals(2)
            ps.setSingleStep(0.1)
            ps.setSuffix(" m")
            ps.setValue(p0["panel_h_" + fk])
            w["panel_h_" + fk] = ps
            lab = tr("fk_" + fk)
            grid.addWidget(QLabel(lab[:1].upper() + lab[1:]), r, 0)
            grid.addWidget(cb, r, 1)
            grid.addWidget(hs, r, 2)
            grid.addWidget(ps, r, 3)
            fach_rows[fk] = (cb, hs, ps)
        f.addRow(grid_w)
        pin_w = [profile(f, "fach_esquina", "f_esquina", U_SERIES),
                 profile(f, "fach_intermedio", "f_intermedio", POST_SERIES),
                 length(f, "fach_sep", "f_fsep", 0.5, 30.0),
                 length(f, "fach_holgura", "f_fholg", 0.0, 1.0, 3, 0.01)]
        note(f, "f_fach_note")

        def sync_fach(*_a):
            for fk, (cb, hs, ps) in fach_rows.items():
                hs.setEnabled(cb.isChecked())
                ps.setEnabled(cb.isChecked() and pnl.isChecked())
            pin_on = any(fach_rows[fk][0].isChecked() for fk in PINONES)
            for x in pin_w:
                x.setEnabled(pin_on)
            for x in pnl_w:
                x.setEnabled(pnl.isChecked())
        for cb, _h, _p in fach_rows.values():
            cb.toggled.connect(sync_fach)
        pnl.toggled.connect(sync_fach)
        sync_fach()

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
                elif wd.property("coded"):
                    out[k] = wd.currentData()
                else:
                    out[k] = wd.currentText()
            return normalize(out)

        def refresh(*_a):
            try:
                p = read()
                g = Geo(p)
                msgs = g.crane_check()
                text = summary(p)
                if msgs:
                    text += "<br><span style='color:#c0392b'>⚠ " + "<br>⚠ ".join(msgs) + "</span>"
                for m in g.notes():
                    text += f"<br><span style='color:#7f8c8d'>ℹ {m}</span>"
                info.setText(text)
            except NaveError as exc:
                info.setText(f"<span style='color:#c0392b'>⚠ {exc}</span>")

        for wd in w.values():
            for sig in ("valueChanged", "currentIndexChanged", "toggled"):
                if hasattr(wd, sig):
                    getattr(wd, sig).connect(refresh)
                    break
        refresh()
        state = {"status": "cancel", "params": p0}

        def accept():
            try:
                p = read()
                g = Geo(p)
                g.purlin_section()
                msgs = g.crane_check()
            except NaveError as exc:
                QMessageBox.warning(dlg, title(), str(exc))
                return
            if msgs and QMessageBox.question(
                    dlg, title(), "\n".join(msgs) + "\n\n" + tr("w_anyway")
            ) != QMessageBox.Yes:
                return
            state.update(status="ok", params=p)
            dlg.accept()

        def relang(_i):
            code = lang_cb.currentData()
            if code == lang():
                return
            state.update(status="relang", params=read())
            set_lang(code)
            dlg.done(2)

        lang_cb.currentIndexChanged.connect(relang)
        buttons.accepted.connect(accept)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()
        return state["status"], state["params"]


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
        dlg.setWindowTitle(f"{title()} — {tr('t_meas', name=nave.name)}")
        lay = QVBoxLayout(dlg)
        heads = list(tr("mh"))
        tbl = QTableWidget(len(rows) + 1, len(heads))
        tbl.setHorizontalHeaderLabels(heads)
        lines = ["\t".join(heads)]
        for i, (e, prof, u, l, kgm, kg) in enumerate(rows):
            vals = [e, prof, str(u), _num(l, 3), _num(kgm, 2), _num(kg, 1)]
            lines.append("\t".join(vals))
            for j, v in enumerate(vals):
                tbl.setItem(i, j, QTableWidgetItem(v))
        total = sum(r[5] for r in rows)
        tbl.setItem(len(rows), 0, QTableWidgetItem(tr("m_total")))
        tbl.setItem(len(rows), 5, QTableWidgetItem(_num(total, 1)))
        lines.append("\t".join([tr("m_total"), "", "", "", "", _num(total, 1)]))
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(tbl)
        lay.addWidget(QLabel(tr("m_note")))
        prs = panel_rows(nave_data(nave).get("params"))
        if prs:
            ph = list(tr("ph"))
            ptbl = QTableWidget(len(prs) + 1, len(ph))
            ptbl.setHorizontalHeaderLabels(ph)
            lines += ["", "\t".join(ph)]
            for i, (fa, u, a, v) in enumerate(prs):
                vals = [fa, str(u), _num(a, 2), _num(v, 3)]
                lines.append("\t".join(vals))
                for j, val in enumerate(vals):
                    ptbl.setItem(i, j, QTableWidgetItem(val))
            tot = [tr("m_total"), str(sum(r[1] for r in prs)),
                   _num(sum(r[2] for r in prs), 2), _num(sum(r[3] for r in prs), 3)]
            lines.append("\t".join(tot))
            for j, val in enumerate(tot):
                ptbl.setItem(len(prs), j, QTableWidgetItem(val))
            ptbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            ptbl.setEditTriggers(QTableWidget.NoEditTriggers)
            lay.addWidget(QLabel(f"<b>{tr('m_panels')}</b>"))
            lay.addWidget(ptbl)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        copy_btn = bb.addButton(tr("m_copy"), QDialogButtonBox.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText("\n".join(lines)))
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(820, 600 if prs else 420)
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
        sub.addAction(tr("m_new"), run(nueva))
    if existing:
        sub.addAction(tr("m_edit"), run(editar))
        sub.addAction(tr("m_meas"), run(medicion))


def outliner_kind(group):
    data = nave_data(group)
    if data is None:
        return None
    try:
        p = normalize(data.get("params"))
        g = Geo(p)
        kg = sum(r[5] for r in measurement(p))
    except NaveError:
        return {"type": tr("nave"), "props": []}
    alero = (f"{g.Hl:.2f} m" if abs(g.Hl - g.Hr) < 1e-9 else f"{g.Hl:.2f} / {g.Hr:.2f} m")
    port = f"{g.n} × {p['pilar']} / {p['dintel']}"
    if p["dintel_ext_on"]:
        port += f" ({p['dintel_ext']})"
    return {"type": tr("nave"), "props": [
        (tr("o_luz"), f"{g.L:.2f} m"), (tr("o_long"), f"{g.Ln:.2f} m"),
        (tr("o_alero"), alero), (tr("o_port"), port),
        (tr("o_acero"), f"{_num(kg)} kg")] + (
        [(tr("o_paneles"), f"{sum(r[1] for r in panel_rows(p))} "
          f"({_num(sum(r[2] for r in panel_rows(p)), 1)} m²)")] if panel_rows(p) else [])}


def setup(app) -> None:
    viewport_of = lambda: app.viewport  # noqa: E731
    sub = app.add_menu(title())
    if sub is not None:
        _fill_menu(sub, viewport_of)

    def context(menu, selection) -> None:
        if not _selected_naves(app.viewport.scene):
            return
        menu.addSeparator()
        _fill_menu(menu.addMenu(title()), viewport_of, create=False, later=True)

    app.add_context_menu(context)
    add_kind = getattr(app, "add_outliner_kind", None)
    if add_kind is not None:
        add_kind(outliner_kind)
