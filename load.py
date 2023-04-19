# -*- coding: utf-8 -*-

# Pioneer (System Value) plugin for EDMC
# Source: https://github.com/Silarn/EDMC-Pioneer
# Inspired by Economical Cartographics: https://github.com/n-st/EDMC-EconomicalCartographics
# Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.

import sys
import tkinter as tk
from tkinter import ttk, Widget as tkWidget
import myNotebook as nb
from config import config
from theme import theme
import locale
from EDMCLogging import get_main_logger
import semantic_version

from body_data import BodyData

logger = get_main_logger()

VERSION = '0.9'

this = sys.modules[__name__]  # For holding module globals
this.frame = None
this.scroll_canvas = None
this.scrollbar = None
this.scrollable_frame = None
this.label = None
this.values_label = None
this.total_label = None
this.bodies = {} # type: dict[str, BodyData]
this.odyssey = False
this.game_version = semantic_version.Version.coerce('0.0.0.0')
this.min_value = None
this.shorten_values = None
this.show_details = None
this.show_biological = None
this.planet_count = 0
this.body_count = 0
this.non_body_count = 0
this.scans = set()
this.map_count = 0
this.main_star_id = None
this.main_star = 0
this.main_star_name = "Star"
this.exo_earnings = 0
this.honked = False
this.fully_scanned = False
this.was_scanned = False
this.was_mapped = False
this.starsystem = ''

# Used during preferences
this.settings = None
this.edsm_setting = None


def plugin_start3(plugin_dir):
    return plugin_start()


def plugin_start():
    # App isn't initialised at this point so can't do anything interesting
    return 'Pioneer'


def plugin_app(parent: tk.Frame):
    parse_config()
    this.frame = tk.Frame(parent)
    this.label = tk.Label(this.frame)
    this.label.grid(row=0, column=0, columnspan=2, sticky=tk.N)
    this.scroll_canvas = tk.Canvas(this.frame, height=100, highlightthickness=0)
    this.scrollbar = ttk.Scrollbar(this.frame, orient="vertical", command=this.scroll_canvas.yview)
    this.scrollable_frame = ttk.Frame(this.scroll_canvas)
    this.scrollable_frame.bind(
        "<Configure>",
        lambda e: this.scroll_canvas.configure(
            scrollregion=this.scroll_canvas.bbox("all")
        )
    )
    this.scroll_canvas.bind("<Enter>", bind_mousewheel)
    this.scroll_canvas.bind("<Leave>", unbind_mousewheel)
    this.scroll_canvas.create_window((0, 0), window=this.scrollable_frame, anchor="nw")
    this.scroll_canvas.configure(yscrollcommand=this.scrollbar.set)
    this.values_label = ttk.Label(this.scrollable_frame)
    this.values_label.pack(fill="both", side="left")
    this.scroll_canvas.grid(row=1, column=0, sticky=tk.EW)
    this.scroll_canvas.grid_rowconfigure(1, weight=0)
    this.frame.grid_columnconfigure(0, weight=1)
    this.scrollbar.grid(row=1, column=1, sticky=tk.NSEW)
    this.total_label = tk.Label(this.frame)
    this.total_label.grid(row=2, column=0, columnspan=2, sticky=tk.N)
    update_display()
    theme.register(this.values_label)
    return this.frame


def plugin_prefs(parent, cmdr, is_beta):
    frame = nb.Frame(parent)
    nb.Label(frame, text='Valuable Body Minimum:').grid(row=0, column=0, sticky=tk.W)
    nb.Entry(frame, textvariable=this.min_value).grid(row=0, column=1, columnspan=2, sticky=tk.W)
    nb.Label(frame, text='Cr').grid(row=0, column=3, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Shorten credit values (thousands, millions)',
        variable=this.shorten_values
    ).grid(row=1, columnspan=3, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show detailed body values (scrollbox)',
        variable=this.show_details
    ).grid(row=2, columnspan=3, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show unmapped bodies with biological signals',
        variable=this.show_biological
    ).grid(row=3, columnspan=3, sticky=tk.W)
    return frame


def prefs_changed(cmdr, is_beta):
    config.set('pioneer_min_value', this.min_value.get())
    config.set('pioneer_shorten', this.shorten_values.get())
    config.set('pioneer_details', this.show_details.get())
    config.set('pioneer_biological', this.show_biological.get())
    update_display()


def parse_config():
    locale.setlocale(locale.LC_ALL, '')
    if config.get_int(key='ec_min_value', default=None) is not None:
        this.min_value = tk.IntVar(value=config.get_int(key='ec_min_value'))
        config.delete(key='ec_min_value')
    else:
        this.min_value = tk.IntVar(value=config.get_int(key='pioneer_min_value', default=400000))
    this.shorten_values = tk.BooleanVar(value=config.get_bool(key='pioneer_shorten', default=True))
    this.show_details = tk.BooleanVar(value=config.get_bool(key='pioneer_details', default=True))
    this.show_biological = tk.BooleanVar(value=config.get_bool(key='pioneer_biological', default=True))


def get_starclass_k(starclass):
    if starclass == 'N' or starclass == 'H':
        return 22628
    elif starclass in ['D', 'DA', 'DAB', 'DAO', 'DAZ', 'DAV', 'DB', 'DBZ', 'DBV', 'DO', 'DOV', 'DQ', 'DC', 'DCV', 'DX']:
        return 14057
    else:
        return 1200


# def get_planetclass_k(planetclass: str, terraformable: bool):
def get_planetclass_k(planetclass, terraformable):
    """
        Adapted from MattG's table at https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/
        Thank you, MattG! :)
    """
    terraform = 0
    mult = 1.0  # Multiplier to calculate rough terraform bonus range
    if planetclass == 'Metal rich body':
        base = 21790
    elif planetclass == 'Ammonia world':
        base = 96932
    elif planetclass == 'Sudarsky class I gas giant':
        base = 1656
    elif planetclass == 'Sudarsky class II gas giant' or planetclass == 'High metal content body':
        base = 9654
        if terraformable:
            terraform = 100677
            mult = .9
    elif planetclass == 'Water world':
        base = 64831
        if terraformable:
            terraform = 116295
            mult = .75
    elif planetclass == 'Earthlike body':
        base = 64831 + 116295  # Terraform is assumed as maximum value
        terraform = 0
    else:
        base = 300
        if terraformable:
            terraform = 93328
            mult = .9

    return base, terraform, mult


def get_star_value(k, mass, isFirstDiscoverer):
    value = k + (mass * k / 66.25)
    honk_value = value / 3
    if isFirstDiscoverer:
        value *= 2.6
        honk_value *= 2.6
    return int(value), int(honk_value)


# def get_body_value(k: int, kt: int, tm: int, mass: float, isFirstDicoverer: bool, isFirstMapper: bool):
def get_body_value(k, kt, tm, mass, isFirstDicoverer, isFirstMapper):
    """
        Adapted from MattG's example code at https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/
        Thank you, MattG! :)
    """
    q = 0.56591828
    k_final = k + kt
    k_final_min = k + (kt * tm)

    # deviation from original: we want to know what the body would yield *if*
    # we would map it, so we skip the "isMapped" check
    if isFirstDicoverer and isFirstMapper:
        # note the additional multiplier later (hence the lower multiplier here)
        mappingMultiplier = 3.699622554
    elif isFirstMapper:
        mappingMultiplier = 8.0956
    else:
        mappingMultiplier = 3.3333333333

    value = (k_final + k_final * q * (mass ** 0.2))
    min_value = (k_final_min + k_final_min * q * (mass ** 0.2))
    mapped_value = value * mappingMultiplier
    min_mapped_value = min_value * mappingMultiplier
    honk_value = value / 3
    min_honk_value = min_value / 3

    if this.odyssey or this.game_version.major >= 4:
        mapped_value += (mapped_value * 0.3) if ((mapped_value * 0.3) > 555) else 555
        min_mapped_value += (min_mapped_value * 0.3) if ((min_mapped_value * 0.3) > 555) else 555

    value = max(500, value)
    min_value = max(500, min_value)
    mapped_value = max(500, mapped_value)
    min_mapped_value = max(500, min_mapped_value)
    honk_value = max(500, honk_value)
    min_honk_value = max(500, min_honk_value)
    if isFirstDicoverer:
        value *= 2.6
        min_value *= 2.6
        mapped_value *= 2.6
        min_mapped_value *= 2.6
        honk_value *= 2.6
        min_honk_value *= 2.6

    return int(value), int(mapped_value), int(honk_value), int(min_value), int(min_mapped_value), int(min_honk_value)


def calc_system_value():
    if this.main_star == 0:
        this.values_label["text"] = "Main star not scanned.\nSystem already visited?"
        return 0, 0, 0, 0
    max_value = 0
    min_max_value = 0
    value_sum = 0
    min_value_sum = 0
    honk_sum = 0
    min_honk_sum = 0
    efficiency_bonus = 1.25
    value_sum += this.main_star
    min_value_sum += this.main_star
    max_value += this.main_star
    min_max_value += this.main_star
    bodies_text = ""
    for body_name, body_data in sorted(this.bodies.items(), key=lambda item: item[1].get_distance()):
        bodies_text += "{} - {}{}:".format(body_name,
                                            body_data.get_type() if not body_data.is_star() else
                                            get_star_label(body_data.get_type(),
                                                           body_data.get_subclass(),
                                                           body_data.get_luminosity()),
                                            " (T)" if body_data.is_terraformable() else "") + "\n"
        if body_data.is_mapped() is True:
            val_text = "{} - {}".format(format_credits(body_data.get_mapped_values()[1]),
                                        format_credits(body_data.get_mapped_values()[0])) \
                if body_data.get_mapped_values()[1] != body_data.get_mapped_values()[0] \
                else "{}".format(format_credits(body_data.get_mapped_values()[0]))
            bodies_text += "Current Value (Max): {}".format(val_text) + "\n"
            max_value += body_data.get_mapped_values()[0]
            min_max_value += body_data.get_mapped_values()[1]
            value_sum += body_data.get_mapped_values()[0]
            min_value_sum += body_data.get_mapped_values()[1]
        else:
            val_text = "{} - {}".format(format_credits(body_data.get_base_values()[1]),
                                        format_credits(body_data.get_base_values()[0])) \
                if body_data.get_base_values()[1] != body_data.get_base_values()[0] \
                else "{}".format(format_credits(body_data.get_base_values()[0]))
            max_val_text = "{} - {}".format(
                format_credits(int(body_data.get_mapped_values()[1] * efficiency_bonus)),
                format_credits(int(body_data.get_mapped_values()[0] * efficiency_bonus))
            ) if body_data.get_mapped_values()[1] != body_data.get_mapped_values()[0] \
                else "{}".format(format_credits(int(body_data.get_mapped_values()[0] * efficiency_bonus)))
            bodies_text += "Current Value: {}\nMax Value: {}".format(val_text, max_val_text) + "\n"
            max_value += int(body_data.get_mapped_values()[0] * efficiency_bonus)
            min_max_value += int(body_data.get_mapped_values()[1] * efficiency_bonus)
            value_sum += body_data.get_base_values()[0]
            min_value_sum += body_data.get_base_values()[1]
        if this.honked:
            if body_data.get_honk_values()[0] != body_data.get_honk_values()[1]:
                bodies_text += "Honk Value: {} - {}".format(
                    format_credits(body_data.get_honk_values()[1]),
                    format_credits(body_data.get_honk_values()[0])) + "\n"
            else:
                bodies_text += "Honk Value: {}".format(format_credits(body_data.get_honk_values()[0])) + "\n"
            value_sum += body_data.get_honk_values()[0]
            min_value_sum += body_data.get_honk_values()[1]
            honk_sum += body_data.get_honk_values()[0]
            min_honk_sum += body_data.get_honk_values()[1]
        max_value += body_data.get_honk_values()[0]
        min_max_value += body_data.get_honk_values()[1]
        bodies_text += "------------------" + "\n"
    this.values_label["text"] = "{} (Main star):\n   {}\n   {} + {} = {}".format(
        this.starsystem,
        this.main_star_name,
        format_credits(this.main_star),
        format_credits(honk_sum) if honk_sum == min_honk_sum else "{} to {}".format(
            format_credits(min_honk_sum),
            format_credits(honk_sum)
        ),
        (format_credits(this.main_star + honk_sum)) if honk_sum == min_honk_sum else "{} to {}".format(
            format_credits(this.main_star + min_honk_sum),
            format_credits(this.main_star + honk_sum)
        )) + "\n"
    this.values_label["text"] += "------------------" + "\n"
    this.values_label["text"] += bodies_text
    if not this.was_scanned:
        total_bodies = this.body_count + this.non_body_count
        if this.fully_scanned and total_bodies == len(this.scans):
            this.values_label["text"] += "Fully Scanned Bonus: {}".format(format_credits(total_bodies * 1000)) + "\n"
            value_sum += total_bodies * 1000
            min_value_sum += total_bodies * 1000
        max_value += total_bodies * 1000
        min_max_value += total_bodies * 1000
    if not this.was_mapped and this.planet_count > 0:
        if this.fully_scanned and this.planet_count == this.map_count:
            this.values_label["text"] += "Fully Mapped Bonus: {}".format(
                format_credits(this.planet_count * 10000)) + "\n"
            value_sum += this.planet_count * 10000
            min_value_sum += this.planet_count * 10000
        max_value += this.planet_count * 10000
        min_max_value += this.planet_count * 10000
    this.scroll_canvas.configure(width=100)
    tkWidget.nametowidget(this.frame, name=this.frame.winfo_parent()).update()
    label_width = this.values_label.winfo_width()
    full_width = this.label.winfo_width() - this.scrollbar.winfo_width()
    final_width = label_width if label_width > full_width else full_width
    this.scroll_canvas.configure(width=final_width)
    return value_sum, min_value_sum, max_value, min_max_value


def format_unit(num, unit, space=True):
    if num > 999999:
        # 1.3 Mu
        s = locale.format_string('%.1f M', num / 1000000.0, grouping=True, monetary=True)
    elif num > 999:
        # 456 ku
        s = locale.format_string('%.1f k', num / 1000.0, grouping=True, monetary=True)
    else:
        # 789 u
        s = locale.format_string('%.0f ', num, grouping=True, monetary=True)

    if not space:
        s = s.replace(' ', '')

    s += unit

    return s


def format_credits(credits, space=True):
    if this.shorten_values.get():
        return format_unit(credits, 'Cr', space)
    return locale.format_string('%d Cr', credits, grouping=True, monetary=True)


def format_ls(ls, space=True):
    return format_unit(ls, 'ls', space)


def get_bodyname(fullname: str = ""):
    if fullname.startswith(this.starsystem + ' '):
        bodyname = fullname[len(this.starsystem + ' '):]
    else:
        bodyname = fullname
    return bodyname


def get_star_label(star_class: str = "", subclass: str = "", luminosity: str = ""):
    name = "Star"
    star_type = "main-sequence"
    if luminosity == "Ia0":
        star_type = "hypergiant"
    elif luminosity.startswith("IV"):
        star_type = "subgiant"
    elif luminosity.startswith("III"):
        star_type = "giant"
    elif luminosity.startswith("II"):
        star_type = "bright giant"
    elif luminosity.startswith("I"):
        star_type = "supergiant"
    if star_class.startswith("D"):
        name = "White dwarf"
    elif star_class == "H":
        name = "Black hole"
    elif star_class == "SupermassiveBlackHole":
        star_class = "H"
        name = "Supermassive black hole"
    elif star_class == "N":
        name = "Neutron star"
    elif star_class == "O":
        name = "Luminous blue {} star"
    elif star_class in ["B", "B_BlueWhiteSuperGiant"]:
        star_class = "B"
        name = "Blue {} star"
    elif star_class in ["A", "A_BlueWhiteSuperGiant"]:
        star_class = "A"
        name = "White-blue {} star"
    elif star_class in ["F", "F_WhiteSuperGiant"]:
        star_class = "F"
        name = "White {} star"
    elif star_class in ["G", "G_WhiteSuperGiant"]:
        star_class = "G"
        name = "White-yellow {} star"
    elif star_class in ["K", "K_OrangeGiant"]:
        star_class = "K"
        name = "Yellow-orange {} star"
    elif star_class.startswith("W"):
        name = "Wolf-Rayet star"
    elif star_class.startswith("C"):
        name = "Carbon star"
    elif star_class in ["M", "M_RedSuperGiant", "M_RedGiant"]:
        star_class = "M"
        if star_type == "main-sequence":
            star_type = "dwarf"
        name = "Red {} star"
    elif star_class == "HeBe":
        name = "Herbig Ae/Be star"
    elif star_class == "TTS":
        name = "T Tauri star"
    elif star_class == "L":
        name = "Dark red dwarf star"
    elif star_class == "T":
        name = "Methane dwarf star"
    elif star_class == "Y":
        name = "Brown dwarf star"
    elif star_class == "MS":
        name = "Intermediate zirconium-monoxide star"
    elif star_class == "S":
        name = "Cool giant zirconium-monoxide star"

    final_name = name.format(star_type)
    return "{} ({}{} {})".format(final_name, star_class, subclass, luminosity)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    if entry['event'] == 'Fileheader' or entry['event'] == 'LoadGame':
        this.odyssey = entry.get('Odyssey', False)
        this.game_version = semantic_version.Version.coerce(entry.get('gameversion'))
    elif entry['event'] == 'Location':
        this.starsystem = entry['StarSystem']
    elif entry['event'] == 'Scan':
        bodyname_insystem = get_bodyname(entry['BodyName'])
        navbeacon = False
        if entry['ScanType'] == 'NavBeaconDetail':
            navbeacon = True
        if 'PlanetClass' not in entry:
            # That's no moon!
            if 'StarType' in entry:
                mass = entry['StellarMass']
                was_discovered = True if navbeacon else bool(entry['WasDiscovered'])
                distancels = float(entry['DistanceFromArrivalLS'])
                k = get_starclass_k(entry['StarType'])
                value, honk_value = get_star_value(k, mass, not was_discovered)
                if entry['BodyID'] == this.main_star_id:
                    this.main_star = value
                    this.main_star_name = get_star_label(entry['StarType'], entry['Subclass'], entry['Luminosity'])
                else:
                    body = BodyData(bodyname_insystem)
                    body.set_base_values(value, value)
                    body.set_mapped_values(value, value)
                    body.set_honk_values(honk_value, honk_value)
                    body.set_distance(distancels)
                    body.set_star(True)
                    body.set_type(entry['StarType'])
                    body.set_subclass(entry['Subclass'])
                    body.set_luminosity(entry['Luminosity'])
                    body.set_mapped(True)
                    this.bodies[bodyname_insystem] = body

                if not this.honked:
                    this.body_count += 1

            if bool(entry["WasDiscovered"]) or navbeacon:
                this.was_scanned = True
            this.scans.add(bodyname_insystem)
            update_display()
        else:
            try:
                efficiency_bonus = 1.25
                # If we get any key-not-in-dict errors, then this body probably
                # wasn't interesting in the first place
                if bodyname_insystem not in this.bodies or this.bodies[bodyname_insystem].get_base_values()[0] == 0:
                    if 'StarSystem' in entry:
                        this.starsystem = entry['StarSystem']
                    terraformable = bool(entry['TerraformState'])
                    distancels = float(entry['DistanceFromArrivalLS'])
                    planetclass = entry['PlanetClass']
                    mass = float(entry['MassEM'])
                    was_discovered = True if navbeacon else bool(entry['WasDiscovered'])
                    was_mapped = True if navbeacon else bool(entry['WasMapped'])
                    this.was_scanned = True if was_discovered else this.was_scanned
                    this.was_mapped = True if was_mapped else this.was_mapped

                    k, kt, tm = get_planetclass_k(planetclass, terraformable)
                    value, mapped_value, honk_value, \
                    min_value, min_mapped_value, min_honk_value = \
                        get_body_value(k, kt, tm, mass, not was_discovered, not was_mapped)

                    if bodyname_insystem not in this.bodies:
                        this.bodies[bodyname_insystem] = BodyData(bodyname_insystem)
                        this.planet_count += 1
                        this.scans.add(bodyname_insystem)
                        if not this.honked:
                            this.body_count += 1
                    this.bodies[bodyname_insystem].set_base_values(value, min_value)
                    this.bodies[bodyname_insystem].set_honk_values(honk_value, min_honk_value)
                    this.bodies[bodyname_insystem].set_distance(distancels)
                    this.bodies[bodyname_insystem].set_type(planetclass)
                    this.bodies[bodyname_insystem].set_terraformable(terraformable)
                    if this.bodies[bodyname_insystem].get_mapped_values()[1] == 0:
                        this.bodies[bodyname_insystem].set_mapped_values(int(mapped_value), int(min_mapped_value))
                    else:
                        this.bodies[bodyname_insystem].set_mapped_values(int(mapped_value * efficiency_bonus), int(min_mapped_value * efficiency_bonus))

                update_display()

            except Exception as e:
                logger.error(e)

    elif entry['event'] == 'FSSDiscoveryScan':
        this.honked = True
        this.body_count = entry["BodyCount"]
        this.non_body_count = entry['NonBodyCount']
        update_display()

    elif entry['event'] == 'FSSAllBodiesFound':
        this.fully_scanned = True
        update_display()

    elif entry['event'] == 'SAAScanComplete':
        efficiency_bonus = 1.25
        target = int(entry['EfficiencyTarget'])
        used = int(entry['ProbesUsed'])
        was_efficient = True if target >= used else False
        this.map_count += 1
        bodyname_insystem = get_bodyname(entry['BodyName'])
        if bodyname_insystem not in this.bodies:
            this.bodies[bodyname_insystem] = BodyData(bodyname_insystem)
            this.planet_count += 1
        else:
            # body exists, only replace its value with a "hidden" marker
            map_val, map_val_max = this.bodies[bodyname_insystem].get_mapped_values()
            final_val = (
                int(map_val * efficiency_bonus) if was_efficient else map_val,
                int(map_val_max * efficiency_bonus) if was_efficient else map_val_max
            )
            this.bodies[bodyname_insystem].set_mapped_values(final_val[0], final_val[1])
        this.bodies[bodyname_insystem].set_mapped(True)

        update_display()

    elif entry['event'] == 'FSDJump':
        if 'StarSystem' in entry:
            this.starsystem = entry['StarSystem']
        this.main_star_id = entry['BodyID'] if 'BodyID' in entry else 0
        this.main_star = 0
        this.main_star_name = "Star"
        this.bodies = {}
        this.honked = False
        this.fully_scanned = False
        this.was_scanned = False
        this.was_mapped = False
        this.planet_count = 0
        this.map_count = 0
        this.body_count = 0
        this.non_body_count = 0
        this.scans = set()
        update_display()
        this.scroll_canvas.yview_scroll(-1, "page")

    elif entry['event'] == 'FSSBodySignals':
        bodyname_insystem = get_bodyname(entry['BodyName'])
        for signal in entry['Signals']:
            if signal['Type'] == '$SAA_SignalType_Biological;':
                if bodyname_insystem not in this.bodies:
                    this.bodies[bodyname_insystem] = BodyData(bodyname_insystem)
                    this.planet_count += 1
                    this.scans.add(bodyname_insystem)
                    if not this.honked:
                        this.body_count += 1
                this.bodies[bodyname_insystem].set_bio_signals(signal['Count'])



def update_display():
    efficiency_bonus = 1.25
    valuable_body_names = [
        body_name
        for body_name, body_data
        in sorted(
            this.bodies.items(),
            key=lambda item: item[1].get_distance()
        )
        if body_data.get_mapped_values()[0] * efficiency_bonus >= this.min_value.get() and not body_data.is_mapped()
    ]
    exobio_body_names = [
        '%s (%d)' % (body_name, body_data.get_bio_signals())
        for body_name, body_data
        in sorted(
            this.bodies.items(),
            key=lambda item: item[1].get_distance()
        )
        if body_data.get_bio_signals() > 0 and not body_data.is_mapped()
    ]

    def format_body(body_name):
        # template: NAME (VALUE, DIST), …
        body_value = int(this.bodies[body_name].get_mapped_values()[0] * efficiency_bonus)
        body_distance = this.bodies[body_name].get_distance()
        if body_value >= this.min_value.get():
            return '%s (up to %s, %s)' % \
                   (body_name.upper(),
                    format_credits(body_value, False),
                    format_ls(body_distance, False))
        else:
            return '%s'

    if this.bodies or this.main_star > 0:
        if this.fully_scanned and len(this.scans) >= this.body_count:
            text = 'Pioneer:'
        else:
            text = 'Pioneer: Scanning'
        if this.honked:
            text += ' (H)'
        if this.fully_scanned and len(this.scans) >= this.body_count:
            if this.was_scanned:
                text += ' (S)'
            else:
                text += ' (S+)'
            if this.planet_count > 0 and this.planet_count == this.map_count:
                if this.was_mapped:
                    text += ' (M)'
                else:
                    text += ' (M+)'
        text += '\n'

        if valuable_body_names:
            text += 'Valuable Bodies (> {}):'.format(format_credits(this.min_value.get())) + '\n'
            text += '\n'.join([format_body(b) for b in valuable_body_names])
        if valuable_body_names and exobio_body_names and this.show_biological.get():
            text += '\n'
        if exobio_body_names and this.show_biological.get():
            text += 'Biological Signals (Unmapped):\n'
            while True:
                exo_list = exobio_body_names[:5]
                exobio_body_names = exobio_body_names[5:]
                text += ' ⬦ '.join([b for b in exo_list])
                if len(exobio_body_names) == 0:
                    break
                else:
                    text += '\n'

        text += '\n' + 'B#: {} NB#: {}'.format(this.body_count, this.non_body_count)
        this.label['text'] = text
    else:
        this.label['text'] = 'Pioneer: Nothing Scanned'

    total_value, min_total_value, max_value, min_max_value = calc_system_value()
    if total_value != min_total_value:
        this.total_label['text'] = 'Estimated System Value: {} to {}'.format(
            format_credits(min_total_value), format_credits(total_value))
        this.total_label['text'] += '\nMaximum System Value: {} to {}'.format(
            format_credits(min_max_value), format_credits(max_value))
    else:
        this.total_label['text'] = 'Estimated System Value: {}'.format(
            format_credits(total_value) if total_value > 0 else "N/A")
        this.total_label['text'] += '\nMaximum System Value: {}'.format(
            format_credits(max_value) if total_value > 0 else "N/A")

    if this.show_details.get():
        this.scroll_canvas.grid()
        this.scrollbar.grid()
    else:
        this.scroll_canvas.grid_remove()
        this.scrollbar.grid_remove()


def bind_mousewheel(event):
    if sys.platform in ("linux", "cygwin", "msys"):
        this.scroll_canvas.bind_all('<Button-4>', on_mousewheel)
        this.scroll_canvas.bind_all('<Button-5>', on_mousewheel)
    else:
        this.scroll_canvas.bind_all('<MouseWheel>', on_mousewheel)


def unbind_mousewheel(event):
    if sys.platform in ("linux", "cygwin", "msys"):
        this.scroll_canvas.unbind_all('<Button-4>')
        this.scroll_canvas.unbind_all('<Button-5>')
    else:
        this.scroll_canvas.unbind_all('<MouseWheel>')


def on_mousewheel(event):
    shift = (event.state & 0x1) != 0
    scroll = 0
    if event.num == 4 or event.delta == 120:
        scroll = -1
    if event.num == 5 or event.delta == -120:
        scroll = 1
    if shift:
        this.scroll_canvas.xview_scroll(scroll, "units")
    else:
        this.scroll_canvas.yview_scroll(scroll, "units")
