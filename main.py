import shutil
import threading
import random
import os
import json
import itertools
from functools import partial
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.metrics import sp, dp
from kivy.animation import Animation
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.properties import StringProperty, BooleanProperty, ListProperty, NumericProperty
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.scrollview import ScrollView

# --- CONFIG & ANDROID STORAGE PATH FIX ---
Window.clearcolor = (0.05, 0.08, 0.15, 1)

def get_save_path(filename):
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            return os.path.join(app_storage_path(), filename)
        except Exception:
            pass
    try:
        app = App.get_running_app()
        if app and app.user_data_dir:
            return os.path.join(app.user_data_dir, filename)
    except Exception:
        pass
    return filename

TOURNAMENT_FILE = get_save_path("league_plat_v9.json")
STATS_FILE = get_save_path("stats_plat_v9.json")

DEFAULT_TEAMS = {
    "IND": { "batters": ["Rohit", "Jaiswal", "Kohli", "Sky", "Pant", "Hardik", "Jadeja", "Axar", "Kuldeep", "Bumrah", "Siraj"], "bowlers": ["Bumrah", "Siraj", "Kuldeep", "Axar", "Hardik", "Jadeja"] },
    "AUS": { "batters": ["Warner", "Head", "Marsh", "Smith", "Maxwell", "Green", "Carey", "Starc", "Cummins", "Zampa", "Hazlewood"], "bowlers": ["Starc", "Cummins", "Hazlewood", "Zampa", "Green", "Maxwell"] },
    "ENG": { "batters": ["Bairstow", "Malan", "Root", "Stokes", "Buttler", "Livingstone", "Ali", "Woakes", "Rashid", "Wood", "Anderson"], "bowlers": ["Wood", "Woakes", "Rashid", "Ali", "Stokes", "Anderson"] },
    "PAK": { "batters": ["Fakhar", "Saim", "Babar", "Rizwan", "Shakeel", "Iftikhar", "Shadab", "Nawaz", "Shaheen", "Rauf", "Naseem"], "bowlers": ["Shaheen", "Naseem", "Rauf", "Shadab", "Nawaz", "Iftikhar"] },
    "SA":  { "batters": ["de Kock", "Bavuma", "Markram", "Klaasen", "Miller", "Stubbs", "Jansen", "Coetzee", "Maharaj", "Rabada", "Ngidi"], "bowlers": ["Rabada", "Ngidi", "Jansen", "Coetzee", "Maharaj", "Markram"] },
    "NZ":  { "batters": ["Conway", "Allen", "Williamson", "Mitchell", "Phillips", "Chapman", "Santner", "Sodhi", "Southee", "Ferguson", "Boult"], "bowlers": ["Boult", "Southee", "Ferguson", "Santner", "Sodhi", "Mitchell"] },
    "WI":  { "batters": ["King", "Mayers", "Hope", "Pooran", "Powell", "Russell", "Holder", "Hosein", "Joseph", "Motie", "McCoy"], "bowlers": ["Joseph", "McCoy", "Holder", "Russell", "Hosein", "Motie"] },
    "SL":  { "batters": ["Nissanka", "K.Mendis", "Samara", "Asalanka", "Shanaka", "Dhana", "Hasaranga", "Theekshana", "Chameera", "Madushanka", "Pathirana"], "bowlers": ["Chameera", "Madushanka", "Pathirana", "Theekshana", "Hasaranga", "Dhana"] }
}

COMMENTARY_db = {
    "0": ["Defended.", "Straight to fielder.", "No run.", "Good line."],
    "1": ["Quick single.", "Pushed to gap.", "Single."],
    "2": ["Driven for two.", "Good running.", "Couple of runs."],
    "4": ["CRACKED! Four.", "Elegant drive!", "One bounce boundary."],
    "6": ["MAXIMUM!", "Huge hit!", "Into the stands!"],
    "W": ["BOWLED!", "Edged and Gone!", "Caught in deep!", "LBW!"],
    "NB": ["No Ball! Free hit."]
}


# --- UI CLASSES ---
class PlayerSelectPopup(Popup):
    def __init__(self, title, players, callback, **kwargs):
        super().__init__(title=title, size_hint=(0.85, 0.7), **kwargs)
        self.callback = callback
        self.auto_dismiss = False
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=8, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        
        for p in players:
            btn_txt = f"{p['name']} (Skill: {p.get('skill', 50)})"
            btn = Button(text=btn_txt, size_hint_y=None, height=dp(50), 
                         background_color=(0.2, 0.6, 0.8, 1), font_size='16sp')
            btn.bind(on_release=lambda x, player=p: self.select_player(player))
            grid.add_widget(btn)
            
        scroll.add_widget(grid)
        layout.add_widget(scroll)
        self.content = layout

    def select_player(self, player):
        self.dismiss()
        self.callback(player)


class BowlerSelectPopup(Popup):
    def __init__(self, bowlers, current_bowler, current_strat, callback, **kwargs):
        super().__init__(title="Select Next Bowler", size_hint=(0.95, 0.85), auto_dismiss=False, **kwargs)
        self.callback = callback
        self.current_strat = current_strat if current_strat else "NORMAL"
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text=f"STRATEGY (Current: {self.current_strat})", size_hint_y=None, height=dp(25), bold=True, color=(1,0.8,0,1)))
        
        strat_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=5)
        self.btn_att = Button(text="ATTACK", on_release=lambda x: self.set_strat("ATTACK"))
        self.btn_nor = Button(text="NORMAL", on_release=lambda x: self.set_strat("NORMAL")) 
        self.btn_def = Button(text="DEFEND", on_release=lambda x: self.set_strat("DEFEND"))
        
        strat_box.add_widget(self.btn_att); strat_box.add_widget(self.btn_nor); strat_box.add_widget(self.btn_def)
        layout.add_widget(strat_box)
        self.set_strat(self.current_strat)
        
        layout.add_widget(Label(text="TAP BOWLER TO START OVER:", size_hint_y=None, height=dp(25), bold=True))
        
        scroll = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=8, padding=5)
        grid.bind(minimum_height=grid.setter('height'))
        
        for b in bowlers:
            is_tired = (b['name'] == current_bowler['name'])
            ov_done = f"{b['b']//6}.{b['b']%6}"
            econ = round(b['r'] / (b['b']/6), 1) if b['b'] > 0 else 0.0
            txt = f"[b]{b['name']}[/b]\n[size=14sp]Ov: {ov_done}  |  Figs: {b['w']}-{b['r']}  |  Econ: {econ}[/size]"
            
            bg_color = (0.2, 0.2, 0.25, 1)
            if is_tired: 
                txt += "\n[color=ff5555](Just Bowled)[/color]"
                bg_color = (0.15, 0.15, 0.15, 1)

            btn = Button(text=txt, size_hint_y=None, height=dp(70), markup=True,
                         background_color=bg_color, disabled=is_tired)
            
            if not is_tired:
                btn.bind(on_release=lambda x, bowl=b: self.select_and_dismiss(bowl))
                
            grid.add_widget(btn)
            
        scroll.add_widget(grid)
        layout.add_widget(scroll)
        self.content = layout

    def set_strat(self, strat):
        self.current_strat = strat
        self.btn_att.background_color = (0.9, 0.2, 0.2, 1) if strat == "ATTACK" else (0.3, 0.3, 0.3, 1)
        self.btn_nor.background_color = (0, 0.7, 0, 1) if strat == "NORMAL" else (0.3, 0.3, 0.3, 1)
        self.btn_def.background_color = (0.2, 0.5, 0.9, 1) if strat == "DEFEND" else (0.3, 0.3, 0.3, 1)

    def select_and_dismiss(self, bowler):
        self.dismiss()
        self.callback(bowler, self.current_strat)


class ClickableRow(ButtonBehavior, BoxLayout):
    pass


class DataManager:
    def __init__(self):
        self.stats = self.get_empty_stats()
        self.batch_mode = False
        self.load()

    def get_empty_stats(self):
        return { 
            "t20": {"batting": {}, "bowling": {}, "teams": {}, 
                    "records": {"f50": None, "f100": None, "best_over": {"r":0}, 
                                "most_4s": {"n":"", "v":0}, "most_6s": {"n":"", "v":0}, 
                                "highest_score": {"n":"", "v":0}, "highest_partnership": {"n":"", "v":0}}}, 
            "odi": {"batting": {}, "bowling": {}, "teams": {}, 
                    "records": {"f50": None, "f100": None, "best_over": {"r":0},
                                "most_4s": {"n":"", "v":0}, "most_6s": {"n":"", "v":0}, 
                                "highest_score": {"n":"", "v":0}, "highest_partnership": {"n":"", "v":0}}} 
        }

    def load(self):
        sf = get_save_path("stats_plat_v9.json")
        if os.path.exists(sf):
            try:
                with open(sf, 'r') as f: 
                    loaded = json.load(f)
                    if "t20" in loaded: self.stats = loaded
            except: pass
        
        backup = sf + ".bak"
        if os.path.exists(backup) and not self.stats.get('t20'):
            try:
                with open(backup, 'r') as f: self.stats = json.load(f)
            except: pass

    def save(self):
        if self.batch_mode: return
        sf = get_save_path("stats_plat_v9.json")
        temp = sf + ".tmp"
        try:
            with open(temp, 'w') as f: 
                json.dump(self.stats, f)
                f.flush(); os.fsync(f.fileno())
            if os.path.exists(sf): shutil.copy2(sf, sf + ".bak")
            os.replace(temp, sf)
        except: pass

    def update_team_stats(self, fmt, team_name, result, score, is_final=False):
        if team_name not in self.stats[fmt]["teams"]:
            self.stats[fmt]["teams"][team_name] = {"m":0, "w":0, "l":0, "t":0, "hs":0, "ls":999, "wc": 0}
        t = self.stats[fmt]["teams"][team_name]
        t['m'] += 1
        if result == 'W': 
            t['w'] += 1
            if is_final: t['wc'] = t.get('wc', 0) + 1
        elif result == 'L': t['l'] += 1
        else: t['t'] += 1
        if score > t.get('hs', 0): t['hs'] = score
        if score < t.get('ls', 999) and score > 0: t['ls'] = score
        self.save()

    def check_records(self, fmt, player_name, runs, balls):
        recs = self.stats[fmt]["records"]
        if runs >= 50 and runs < 56:
            if recs["f50"] is None or balls < recs["f50"]["b"]: recs["f50"] = {"name": player_name, "b": balls}
        if runs >= 100 and runs < 106:
            if recs["f100"] is None or balls < recs["f100"]["b"]: recs["f100"] = {"name": player_name, "b": balls}
        if runs > recs.get("highest_score", {"v":0})["v"]:
            recs["highest_score"] = {"n": player_name, "v": runs}
        self.save()
        
    def check_partnership(self, fmt, runs, batter1, batter2):
        recs = self.stats[fmt]["records"]
        curr_rec = recs.get("highest_partnership", {"v": 0})
        if runs > curr_rec["v"]:
            names = f"{batter1} & {batter2}"
            recs["highest_partnership"] = {"n": names, "v": runs}
            self.save()

    def update_over_record(self, fmt, runs, batter, bowler):
        recs = self.stats[fmt]["records"]
        if runs > recs.get("best_over", {}).get("r", 0):
            recs["best_over"] = {"r": runs, "bat": batter, "bowl": bowler}
            self.save()
            
    def check_boundary_records(self, fmt, name, fours, sixes):
        recs = self.stats[fmt]["records"]
        if fours > recs.get("most_4s", {"v":0})["v"]: recs["most_4s"] = {"n": name, "v": fours}
        if sixes > recs.get("most_6s", {"v":0})["v"]: recs["most_6s"] = {"n": name, "v": sixes}
        self.save()

    def get_rank_snapshot(self, fmt, mode):
        data = self.stats[fmt]['batting' if mode=='bat' else 'bowling']
        sorted_list = sorted(data.keys(), key=lambda k: data[k].get('pts', 0), reverse=True)
        return {name: i for i, name in enumerate(sorted_list)}

    def commit_match_stats(self, fmt, bat_stats, bowl_stats, mom_name=None):
        prev_bat = self.get_rank_snapshot(fmt, 'bat')
        prev_bowl = self.get_rank_snapshot(fmt, 'bowl')

        for p in bat_stats:
            name = p['name']
            if name not in self.stats[fmt]["batting"]:
                self.stats[fmt]["batting"][name] = {"m":0,"r":0,"b":0,"hs":0,"outs":0,"4s":0,"6s":0,"50":0,"100":0, "pts":0, "change": 0, "mom":0, "history": []}
            s = self.stats[fmt]["batting"][name]
            s['m'] = s.get('m', 0) + 1; s['r'] = s.get('r', 0) + p['r']; s['b'] = s.get('b', 0) + p['b']
            s['4s'] = s.get('4s', 0) + p.get('4s', 0); s['6s'] = s.get('6s', 0) + p.get('6s', 0)
            if p.get('is_out'): s['outs'] = s.get('outs', 0) + 1
            if p['r'] > s.get('hs', 0): s['hs'] = p['r']
            if p['r'] >= 100: s['100'] = s.get('100', 0) + 1
            elif p['r'] >= 50: s['50'] = s.get('50', 0) + 1
            if name == mom_name: s['mom'] = s.get('mom', 0) + 1
            
            hist = s.get("history", []); hist.append(p['r']) 
            if len(hist) > 5: hist.pop(0) 
            s['history'] = hist
            
            self.check_records(fmt, name, p['r'], p['b'])
            self.check_boundary_records(fmt, name, p.get('4s',0), p.get('6s',0))
            
            outs = s.get('outs', 1); runs = s.get('r', 0); balls = s.get('b', 1); matches = s.get('m', 1)
            avg = runs / outs if outs > 0 else runs; sr = (runs / balls) * 100 if balls > 0 else 0; rpm = runs / matches
            s['pts'] = min(999, int((avg * 8) + (sr * 1.5) + (rpm * 5)))

        for b in bowl_stats:
            if b['b'] > 0:
                name = b['name']
                if name not in self.stats[fmt]["bowling"]:
                    self.stats[fmt]["bowling"][name] = {"m":0,"b":0,"r":0,"w":0,"bi_w":0,"bi_r":999, "pts":0, "change": 0, "mom": 0, "history": []}
                s = self.stats[fmt]["bowling"][name]
                s['m'] = s.get('m', 0) + 1; s['b'] = s.get('b', 0) + b['b']
                s['r'] = s.get('r', 0) + b['r']; s['w'] = s.get('w', 0) + b['w']
                if name == mom_name: s['mom'] = s.get('mom', 0) + 1
                curr_w = s.get("bi_w", 0); curr_r = s.get("bi_r", 999)
                if b['w'] > curr_w or (b['w'] == curr_w and b['r'] < curr_r):
                    s["bi_w"] = b['w']; s["bi_r"] = b['r']
                
                hist = s.get("history", []); fig = f"{b['w']}-{b['r']}"; hist.append(fig)
                if len(hist) > 5: hist.pop(0)
                s['history'] = hist
                
                matches = s.get('m', 1); wkts = s.get('w', 0); balls = s.get('b', 1); runs_conc = s.get('r', 0)
                wpm = wkts / matches; eco = runs_conc / (balls/6) if balls > 0 else 0; eco_score = (10 - eco) * 40 if eco < 10 else 0  
                s['pts'] = min(999, int((wpm * 200) + eco_score + (wkts * 5)))

        self.calculate_rank_changes(fmt, 'bat', prev_bat)
        self.calculate_rank_changes(fmt, 'bowl', prev_bowl)
        self.save()

    def calculate_rank_changes(self, fmt, mode, prev_ranks):
        data = self.stats[fmt]['batting' if mode=='bat' else 'bowling']
        current_sorted = sorted(data.keys(), key=lambda k: data[k].get('pts', 0), reverse=True)
        for i, name in enumerate(current_sorted):
            if name in prev_ranks: data[name]['change'] = prev_ranks[name] - i
            else: data[name]['change'] = 0 
                
    def reset_stats(self):
        self.stats = self.get_empty_stats()
        sf = get_save_path("stats_plat_v9.json")
        tf = get_save_path("league_plat_v9.json")
        for f in [sf, sf + ".bak", tf, tf + ".bak"]:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass
        self.save()
        App.get_running_app().tournament_data = {}


kv_string = """
<Button>:
    on_press: app.play_click()
<RoundedButton@Button>:
    on_press: app.play_click()
<ClickableRow>:
    on_press: app.play_click()
    canvas.before:
        Color:
            rgba: (0.3, 0.3, 0.4, 1) if self.state == 'normal' else (0.5, 0.5, 0.6, 1)
        Rectangle:
            pos: self.pos
            size: self.size

<MenuScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 30
        spacing: 10
        Label:
            text: "CRICKET PLATINUM"
            font_size: '30sp'
            bold: True
            color: (1, 0.8, 0, 1)
            size_hint_y: 0.15
        BoxLayout:
            size_hint_y: 0.15
            spacing: 20
            Button:
                text: "T20 CUP"
                background_color: (0, 0.6, 1, 1)
                on_release: root.start_setup('t20')
            Button:
                text: "ODI CUP"
                background_color: (1, 0.5, 0, 1)
                on_release: root.start_setup('odi')
        Button:
            text: " CONTINUE LEAGUE"
            size_hint_y: 0.12
            disabled: not root.has_save
            background_color: (0.2, 0.8, 0.2, 1) if root.has_save else (0.3, 0.3, 0.3, 1)
            on_release: root.continue_game()
        GridLayout:
            cols: 2
            size_hint_y: 0.25
            spacing: 10
            Button:
                text: " Players"
                on_release: app.root.current = 'stats'
            Button:
                text: " Teams"
                on_release: app.root.current = 'team_stats'
            Button:
                text: " Records"
                background_color: (1, 0.84, 0, 1)
                color: (0,0,0,1)
                on_release: app.root.current = 'records'
            Button:
                text: " Rankings"
                on_release: app.root.current = 'rankings'
        
        BoxLayout:
            size_hint_y: 0.1
            spacing: 10
            Button:
                text: " Reset Data"
                background_color: (0.8, 0, 0, 1)
                on_release: root.confirm_reset()
            Button:
                text: " EXIT GAME"
                background_color: (0.2, 0.2, 0.2, 1)
                on_release: app.stop()
        Button:
            text: app.music_label
            size_hint_y: 0.1
            background_color: (0.4, 0, 0.6, 1)
            on_release: app.toggle_music()

<RecordsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 5
        
        BoxLayout:
            size_hint_y: 0.1
            spacing: 20
            Button:
                text: "T20 Records"
                on_release: root.show_records('t20')
            Button:
                text: "ODI Records"
                on_release: root.show_records('odi')
        
        Label:
            text: root.header_text
            size_hint_y: 0.08
            font_size: '22sp'
            bold: True
            color: (1, 0.84, 0, 1)

        ScrollView:
            BoxLayout:
                id: content_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: 10
                spacing: 15
        
        Button:
            text: "VIEW RECENT FORM"
            size_hint_y: 0.1
            background_color: (0.2, 0.6, 0.8, 1)
            on_release: root.show_player_form('bat')
            
        Button:
            text: "Back"
            size_hint_y: 0.1
            on_release: app.root.current = 'menu'

<TeamSelectScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        Label:
            text: "SELECT YOUR TEAM"
            size_hint_y: 0.1
            font_size: '24sp'
            bold: True
        GridLayout:
            id: grid
            cols: 2
            spacing: 15
            size_hint_y: 0.8
        Button:
            text: "Back"
            size_hint_y: 0.1
            on_release: app.root.current = 'menu'

<LeagueScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        BoxLayout:
            size_hint_y: 0.08
            Label:
                text: "Team"
                size_hint_x: 0.35
                bold: True
            Label:
                text: "P"
                size_hint_x: 0.1
            Label:
                text: "W"
                size_hint_x: 0.1
            Label:
                text: "L"
                size_hint_x: 0.1
            Label:
                text: "NRR"
                size_hint_x: 0.2
                color: (0.6, 0.8, 1, 1)
            Label:
                text: "Pts"
                size_hint_x: 0.15
                bold: True
                color: (1, 1, 0, 1)
        ScrollView:
            size_hint_y: 0.4
            BoxLayout:
                id: points_table
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
        Label:
            text: "FIXTURES & TOURNAMENT BRACKET"
            size_hint_y: 0.05
            bold: True
            color: (0.6, 0.8, 1, 1)
        ScrollView:
            BoxLayout:
                id: fixture_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 5
        BoxLayout:
            size_hint_y: 0.1
            spacing: 10
            Button:
                text: "EXIT TO MENU"
                background_color: (0.8, 0.2, 0.2, 1)
                on_release: app.root.current = 'menu'
            Button:
                id: sim_all_btn
                text: "SIM ALL LEAGUE"
                background_color: (1, 0.5, 0, 1)
                on_release: root.sim_all_league_matches()

<TeamStatsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 5
        BoxLayout:
            size_hint_y: 0.1
            spacing: 20
            Button:
                text: "T20 Teams"
                on_release: root.show_teams('t20')
            Button:
                text: "ODI Teams"
                on_release: root.show_teams('odi')
        Label:
            text: root.header_text
            size_hint_y: 0.08
            bold: True
            font_size: '22sp'
            color: (1, 0.84, 0, 1)
        
        BoxLayout:
            size_hint_y: None
            height: dp(35)
            canvas.before:
                Color:
                    rgba: 0.2, 0.2, 0.2, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label: 
                text: "Team"
                size_hint_x: 0.24
                bold: True
            Label: 
                text: "M"
                size_hint_x: 0.08
            Label: 
                text: "W"
                size_hint_x: 0.08
            Label: 
                text: "L"
                size_hint_x: 0.08
            Label: 
                text: "T"
                size_hint_x: 0.08
            Label: 
                text: "HS"
                size_hint_x: 0.13
            Label: 
                text: "LS"
                size_hint_x: 0.13
            Label:
                text: "WC"
                size_hint_x: 0.18
                color: (1, 0.84, 0, 1)
        
        ScrollView:
            BoxLayout:
                id: table_layout
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(2)
        Button:
            text: "Back"
            size_hint_y: 0.1
            on_release: app.root.current = 'menu'

<TeamPlayersScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 5
        Label:
            text: root.team_name + " SQUAD STATS"
            size_hint_y: 0.1
            font_size: '22sp'
            bold: True
            color: (1, 0.8, 0, 1)
        BoxLayout:
            size_hint_y: 0.1
            Button:
                text: "Batting Stats"
                on_release: root.show_batting()
            Button:
                text: "Bowling Stats"
                on_release: root.show_bowling()
        ScrollView:
            do_scroll_x: True
            BoxLayout:
                id: player_list
                orientation: 'vertical'
                size_hint_y: None
                size_hint_x: None
                height: self.minimum_height
                width: dp(1200)
                spacing: dp(2)
        Button:
            text: "Back"
            size_hint_y: 0.1
            on_release: app.root.current = 'team_stats'

<StatsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 5
        BoxLayout:
            size_hint_y: 0.1
            spacing: 5
            Button:
                text: "T20 Bat"
                on_release: root.show_stats('t20', 'bat')
            Button:
                text: "T20 Bowl"
                on_release: root.show_stats('t20', 'bowl')
            Button:
                text: "ODI Bat"
                on_release: root.show_stats('odi', 'bat')
            Button:
                text: "ODI Bowl"
                on_release: root.show_stats('odi', 'bowl')
        Label:
            text: root.header_text
            size_hint_y: 0.05
            bold: True
            color: (1, 0.84, 0, 1)
        
        ScrollView:
            id: header_scroll
            size_hint_y: None
            height: dp(40)
            do_scroll_y: False
            do_scroll_x: False
            bar_width: 0
            scroll_x: data_scroll.scroll_x
            
            BoxLayout:
                id: header_box
                size_hint_x: None
                height: dp(40)
                canvas.before:
                    Color:
                        rgba: 0.2, 0.2, 0.2, 1
                    Rectangle:
                        pos: self.pos
                        size: self.size

        ScrollView:
            id: data_scroll
            do_scroll_x: True
            BoxLayout:
                id: table_layout
                orientation: 'vertical'
                size_hint_y: None
                size_hint_x: None
                height: self.minimum_height
                spacing: dp(2)

        BoxLayout:
            size_hint_y: 0.08
            spacing: 20
            padding: 5
            canvas.before:
                Color:
                    rgba: 0.1, 0.1, 0.1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                id: prev_btn
                text: "<< Prev"
                on_release: root.change_page(-1)
            Label:
                id: page_lbl
                text: "Page 1"
                bold: True
            Button:
                id: next_btn
                text: "Next >>"
                on_release: root.change_page(1)

        Button:
            text: "Back"
            size_hint_y: 0.08
            background_color: (0.8, 0.2, 0.2, 1)
            on_release: app.root.current = 'menu'

<RankingsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        Label:
            text: "ICC RANKINGS"
            size_hint_y: 0.1
            bold: True
            font_size: '22sp'
        GridLayout:
            cols: 2
            size_hint_y: 0.15
            spacing: 5
            Button:
                text: "T20 Batting"
                on_release: root.show_ranks('t20', 'bat')
            Button:
                text: "T20 Bowling"
                on_release: root.show_ranks('t20', 'bowl')
            Button:
                text: "ODI Batting"
                on_release: root.show_ranks('odi', 'bat')
            Button:
                text: "ODI Bowling"
                on_release: root.show_ranks('odi', 'bowl')
        ScrollView:
            BoxLayout:
                id: rank_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
        Button:
            text: "Back"
            size_hint_y: 0.1
            on_release: app.root.current = 'menu'

<RoundedButton@Button>:
    background_color: 0,0,0,0
    bg_color: (0.2, 0.6, 1, 1)
    canvas.before:
        Color:
            rgba: self.bg_color if self.state == 'normal' else (self.bg_color[0]*0.8, self.bg_color[1]*0.8, self.bg_color[2]*0.8, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10),]

<GameCard@BoxLayout>:
    padding: dp(10)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 0.05
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10),]
        Color:
            rgba: 1, 1, 1, 0.1
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(10))
            width: 1

<GameScreen>:
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.22
            padding: dp(10)
            canvas.before:
                Color:
                    rgba: 0, 0, 0, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
                Color:
                    rgba: 0.2, 0.3, 0.6, 0.2
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [0, 0, dp(25), dp(25)]
            
            BoxLayout:
                size_hint_y: 0.25
                Label:
                    text: root.match_header
                    size_hint_x: 0.85
                    font_size: '16sp'
                    color: 1, 1, 1, 1
                    bold: True
                    markup: True
                    halign: 'left'
                    text_size: self.size
                
                Button:
                    text: "EXIT"
                    size_hint_x: 0.15
                    background_color: 0.8, 0, 0, 1
                    bold: True
                    font_size: '10sp'
                    on_release: app.root.current = 'menu'

            BoxLayout:
                size_hint_y: 0.45
                Label:
                    text: root.score_display
                    markup: True
                    font_size: '48sp'
                    bold: True
                    color: 1, 1, 1, 1
                    halign: 'center'
            
            BoxLayout:
                size_hint_y: 0.3
                Label:
                    text: root.rr_display + "   |   " + root.req_display
                    font_size: '13sp'
                    color: 1, 0.8, 0.4, 1
                    halign: 'center'

        FloatLayout:
            size_hint_y: 0.35
            canvas.before:
                Color:
                    rgba: 0.15, 0.35, 0.15, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
                Color:
                    rgba: 0.75, 0.65, 0.45, 1
                RoundedRectangle:
                    pos: (self.center_x - dp(50), self.y + dp(10))
                    size: (dp(100), self.height - dp(20))
                    radius: [dp(5),]

            Label:
                text: "BOWLING: " + root.bowler_text
                size_hint: None, None
                size: dp(220), dp(30)
                pos_hint: {'center_x': 0.5, 'top': 0.96}
                bold: True
                color: 1, 1, 1, 1
                canvas.before:
                    Color:
                        rgba: 0, 0, 0, 0.6
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(10),]

            Label:
                text: root.partnership_text
                font_size: '12sp'
                pos_hint: {'right': 0.98, 'top': 0.98}
                size_hint: None, None
                size: dp(150), dp(20)
                halign: 'right'
                bold: True
                color: 1, 1, 0, 1

            Label:
                id: event_lbl
                text: root.event_main
                font_size: '90sp'
                bold: True
                color: root.event_color
                pos_hint: {'center_x': 0.5, 'center_y': 0.55}
                outline_width: 3
                outline_color: 0,0,0,0.5
            
            Label:
                text: root.commentary
                font_size: '16sp'
                pos_hint: {'center_x': 0.5, 'y': 0.1}
                outline_width: 2
                color: 1,1,1,1

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.43
            padding: dp(10)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: 0.05, 0.05, 0.08, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            BoxLayout:
                size_hint_y: 0.12
                padding: [dp(10), 0]
                canvas.before:
                    Color:
                        rgba: 0.15, 0.15, 0.2, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [dp(5),]
                Label:
                    text: "THIS OVER:"
                    size_hint_x: 0.25
                    font_size: '11sp'
                    color: 0.6, 0.6, 0.6, 1
                    bold: True
                Label:
                    text: root.over_history
                    markup: True
                    size_hint_x: 0.75
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'
                    font_size: '16sp'
                    bold: True

            BoxLayout:
                spacing: dp(15)
                size_hint_y: 0.58
                
                BoxLayout:
                    orientation: 'vertical'
                    padding: dp(5)
                    spacing: dp(2)
                    canvas.before:
                        Color:
                            rgba: (0.1, 0.2, 0.3, 1) if not root.striker_active else (0.05, 0.25, 0.4, 1)
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(10),]
                        Color:
                            rgba: (0, 1, 0, 1) if root.striker_active else (0,0,0,0)
                        Line:
                            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(10))
                            width: 1.5
                    
                    Label:
                        text: "BATTER *" if root.striker_active else "BATTER"
                        font_size: '10sp'
                        color: 0.6, 0.6, 0.6, 1
                        size_hint_y: 0.15
                    
                    Label:
                        text: root.striker_text
                        markup: True
                        halign: 'center'
                        valign: 'middle'
                        size_hint_y: 0.35

                    BoxLayout:
                        size_hint_y: 0.2
                        orientation: 'vertical'
                        spacing: 1
                        BoxLayout:
                            Label: 
                                text: "PRS"
                                font_size: '8sp'
                                size_hint_x: 0.2
                                color: 1, 0.5, 0.5, 1
                            ProgressBar:
                                max: 100
                                value: root.striker_pressure
                                size_hint_x: 0.8
                        BoxLayout:
                            Label: 
                                text: "SET"
                                font_size: '8sp'
                                size_hint_x: 0.2
                                color: 1, 0.8, 0, 1
                            ProgressBar:
                                max: 100
                                value: root.striker_set_val
                                size_hint_x: 0.8

                    RoundedButton:
                        text: root.btn_text_striker
                        size_hint_y: 0.3
                        font_size: '11sp'
                        bg_color: root.get_strat_color_rgb(root.btn_text_striker)
                        on_release: root.toggle_strategy(True)

                BoxLayout:
                    orientation: 'vertical'
                    padding: dp(5)
                    spacing: dp(2)
                    canvas.before:
                        Color:
                            rgba: (0.1, 0.2, 0.3, 1) if root.striker_active else (0.05, 0.25, 0.4, 1)
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(10),]
                    
                    Label:
                        text: "RUNNER"
                        font_size: '10sp'
                        color: 0.6, 0.6, 0.6, 1
                        size_hint_y: 0.15
                    
                    Label:
                        text: root.non_striker_text
                        markup: True
                        halign: 'center'
                        valign: 'middle'
                        size_hint_y: 0.35

                    BoxLayout:
                        size_hint_y: 0.2
                        orientation: 'vertical'
                        spacing: 1
                        BoxLayout:
                            Label: 
                                text: "PRS"
                                font_size: '8sp'
                                size_hint_x: 0.2
                                color: 1, 0.5, 0.5, 1
                            ProgressBar:
                                max: 100
                                value: root.non_striker_pressure
                                size_hint_x: 0.8
                        BoxLayout:
                            Label: 
                                text: "SET"
                                font_size: '8sp'
                                size_hint_x: 0.2
                                color: 1, 0.8, 0, 1
                            ProgressBar:
                                max: 100
                                value: root.non_striker_set_val
                                size_hint_x: 0.8

                    RoundedButton:
                        text: root.btn_text_nonstriker
                        size_hint_y: 0.3
                        font_size: '11sp'
                        bg_color: root.get_strat_color_rgb(root.btn_text_nonstriker)
                        on_release: root.toggle_strategy(False)

            BoxLayout:
                size_hint_y: 0.3
                spacing: dp(10)
                Button:
                    text: "Stats"
                    size_hint_x: 0.25
                    background_color: 0.2, 0.2, 0.25, 1
                    on_release: root.open_scorecard()
                Button:
                    text: "STOP" if root.auto_active else root.btn_text
                    background_color: 0,0,0,0
                    bold: True
                    font_size: '22sp'
                    canvas.before:
                        Color:
                            rgba: (0.9, 0.2, 0.2, 1) if root.auto_active else ((0, 0.8, 0.3, 1) if root.is_user_batting else (0.9, 0.5, 0, 1))
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(15),]
                    on_press: root.on_control_press()
                    on_release: root.on_control_release()


<TossScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 40
        spacing: 20
        Label:
            text: " TOSS"
            font_size: '30sp'
            bold: True
        Label:
            id: status_lbl
            text: "Call it!"
            font_size: '18sp'
        BoxLayout:
            id: coin_box
            size_hint_y: 0.3
            spacing: 20
            Button:
                text: "HEADS"
                on_release: root.do_toss('Heads')
            Button:
                text: "TAILS"
                on_release: root.do_toss('Tails')
        BoxLayout:
            id: decision_box
            size_hint_y: 0.3
            spacing: 20
            opacity: 0
            disabled: True
            Button:
                text: "BAT"
                background_color: (0, 0.8, 0, 1)
                on_release: root.start_match(True)
            Button:
                text: "BOWL"
                background_color: (0.8, 0, 0, 1)
                on_release: root.start_match(False)
        BoxLayout:
            id: cpu_start_box
            size_hint_y: 0.2
            opacity: 0
            disabled: True
            Button:
                text: "START MATCH >>"
                background_color: (1, 0.8, 0, 1)
                color: (0,0,0,1)
                bold: True
                on_release: root.proceed_cpu_choice()

<ResultScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        Label:
            text: "MATCH SUMMARY"
            size_hint_y: 0.1
            font_size: '24sp'
            bold: True
            color: (1, 0.8, 0, 1)
        BoxLayout:
            size_hint_y: 0.15
            Label:
                id: score1_lbl
                text: ""
                font_size: '20sp'
                halign: 'right'
                text_size: self.size
                padding_x: 20
            Label:
                text: "vs"
                size_hint_x: 0.2
            Label:
                id: score2_lbl
                text: ""
                font_size: '20sp'
                halign: 'left'
                text_size: self.size
                padding_x: 20
        Label:
            text: root.res_text
            size_hint_y: 0.08
            font_size: '18sp'
            bold: True
            color: (0, 1, 0, 1)
        Label:
            id: margin_lbl
            text: ""
            size_hint_y: 0.06
            bold: True
            color: (1, 1, 1, 1)
        Label:
            id: mom_lbl
            text: "MOM: ..."
            size_hint_y: 0.1
            color: (1, 1, 0, 1)
            bold: True
        BoxLayout:
            size_hint_y: 0.15
            spacing: 10
            Button:
                text: " Scorecard"
                background_color: (0.2, 0.5, 0.8, 1)
                on_release: root.open_scorecard()
            Button:
                text: "Continue >>"
                background_color: (0, 0.8, 0, 1)
                on_release: root.on_continue()

<KnockoutWindow>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 10
        Label:
            text: " TOURNAMENT CHAMPIONS "
            font_size: '28sp'
            bold: True
            color: (1, 0.84, 0, 1)
            size_hint_y: 0.2
        Label:
            text: root.champions
            font_size: '40sp'
            bold: True
            size_hint_y: 0.2
        GridLayout:
            cols: 2
            size_hint_y: 0.4
            spacing: 10
            Label:
                text: "Most Runs:"
                halign: 'right'
                text_size: self.size
            Label:
                text: root.most_runs
                bold: True
                color: (0.2, 1, 0.2, 1)
                halign: 'left'
                text_size: self.size
            Label:
                text: "Most Wickets:"
                halign: 'right'
                text_size: self.size
            Label:
                text: root.most_wickets
                bold: True
                color: (0.2, 0.8, 1, 1)
                halign: 'left'
                text_size: self.size
            Label:
                text: "Player of Tournament (MOS):"
                halign: 'right'
                text_size: self.size
            Label:
                text: root.mos
                bold: True
                color: (1, 1, 0, 1)
                halign: 'left'
                text_size: self.size
                markup: True
        Button:
            text: "FINISH"
            size_hint_y: 0.2
            background_color: (0.2, 0.8, 0.2, 1)
            on_release: app.root.current = 'menu'
"""

class MenuScreen(Screen):
    has_save = BooleanProperty(False)
    def on_enter(self): 
        self.has_save = os.path.exists(get_save_path("league_plat_v9.json"))

    def start_setup(self, fmt):
        app = App.get_running_app(); app.match_format = fmt; app.overs = 20 if fmt == 't20' else 50
        app.root.current = 'team_select'

    def continue_game(self):
        App.get_running_app().load_tournament()
        App.get_running_app().root.current = 'league'

    def confirm_reset(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text="Are you sure you want to delete ALL data?"))
        btns = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
        btn_y = Button(text="YES", background_color=(0.8, 0, 0, 1))
        btn_n = Button(text="NO")
        btns.add_widget(btn_y); btns.add_widget(btn_n)
        content.add_widget(btns)
        popup = Popup(title="Confirm Reset", content=content, size_hint=(0.8, 0.4))
        btn_y.bind(on_release=lambda x: [App.get_running_app().data_mgr.reset_stats(), popup.dismiss(), setattr(self, 'has_save', False)])
        btn_n.bind(on_release=popup.dismiss)
        popup.open()

class TeamSelectScreen(Screen):
    def on_enter(self):
        grid = self.ids.grid; grid.clear_widgets()
        for team in sorted(DEFAULT_TEAMS.keys()):
            grid.add_widget(Button(text=team, font_size='20sp', bold=True, on_release=partial(self.select_team, team)))
    def select_team(self, team, instance):
        App.get_running_app().start_new_league(team); App.get_running_app().root.current = 'league'

class LeagueScreen(Screen):
    def on_enter(self): 
        self.load_table()

    def load_table(self):
        app = App.get_running_app(); data = app.tournament_data
        box = self.ids.points_table; box.clear_widgets()
        teams = data['points']
        teams.sort(key=lambda x: (x['pts'], x.get('nrr', 0)), reverse=True)
        for t in teams:
            row = BoxLayout(size_hint_y=None, height=dp(40))
            color = (0,1,0,1) if t['name'] == app.user_team else (1,1,1,1)
            row.add_widget(Label(text=t['name'], size_hint_x=0.35, color=color, bold=True))
            row.add_widget(Label(text=str(t['p']), size_hint_x=0.1))
            row.add_widget(Label(text=str(t['w']), size_hint_x=0.1))
            row.add_widget(Label(text=str(t['l']), size_hint_x=0.1))
            nrr = round(t.get('nrr', 0), 3)
            row.add_widget(Label(text=f"{nrr:+}", size_hint_x=0.2, color=(0.6,0.8,1,1)))
            row.add_widget(Label(text=str(t['pts']), size_hint_x=0.15, bold=True, color=(1,1,0,1)))
            box.add_widget(row)

        fbox = self.ids.fixture_list; fbox.clear_widgets()
        fixtures = data['fixtures']
        
        league_matches = [f for f in fixtures if "Play" in str(f[3])]
        matches_played = sum(1 for f in league_matches if f[2] is not None)
        
        if matches_played >= len(league_matches) and len(league_matches) > 0:
            self.ids.sim_all_btn.disabled = True
            if not data.get('sf_generated', False):
                top4 = teams[:4]
                fixtures.append([top4[0]['name'], top4[3]['name'], None, "SEMI FINAL 1"])
                fixtures.append([top4[1]['name'], top4[2]['name'], None, "SEMI FINAL 2"])
                data['sf_generated'] = True
                app.save_tournament()
            
            sf_matches = [f for f in fixtures if "SEMI" in str(f[3])]
            if len(sf_matches) == 2 and all(f[2] is not None for f in sf_matches):
                if not data.get('final_generated', False):
                    fixtures.append([sf_matches[0][2], sf_matches[1][2], None, "FINAL"])
                    data['final_generated'] = True
                    app.save_tournament()
        else:
            self.ids.sim_all_btn.disabled = False

        for idx, match in enumerate(fixtures):
            t1, t2, winner, status = match
            row = BoxLayout(size_hint_y=None, height=dp(60))
            is_user_match = (t1 == app.user_team or t2 == app.user_team)
            
            if "FINAL" in str(status) or "SEMI" in str(status):
                bg_color = (0.5, 0.4, 0, 1) if not winner else (0.1, 0.2, 0.1, 1)
            else:
                bg_color = (0, 0.4, 0.4, 1) if is_user_match else (0.2, 0.2, 0.2, 1)

            with row.canvas.before:
                Color(*bg_color); Rectangle(pos=row.pos, size=row.size)
            
            lbl_text = f"{t1} vs {t2}" if "Play" in str(status) else f"{status}: {t1} vs {t2}"
            if winner:
                row.add_widget(Label(text=lbl_text, size_hint_x=0.4))
                res_color = (0,1,0,1) if winner == app.user_team else (1,1,1,1)
                row.add_widget(Label(text=f"{winner} Won", color=res_color, size_hint_x=0.4))
            else:
                row.add_widget(Label(text=lbl_text, size_hint_x=0.4, bold=True))
                btn_box = BoxLayout(size_hint_x=0.5, spacing=5, padding=5)
                if is_user_match:
                    pbtn = Button(text="PLAY", background_color=(0, 0.8, 0, 1), bold=True)
                    pbtn.bind(on_release=partial(self.play_match, idx, t1, t2))
                    btn_box.add_widget(pbtn)
                sbtn = Button(text="SIM", background_color=(0.2, 0.6, 1, 1))
                sbtn.bind(on_release=partial(self.sim_match, idx, t1, t2, status))
                btn_box.add_widget(sbtn)
                row.add_widget(btn_box)
            fbox.add_widget(row)

    def sim_all_league_matches(self):
        content = BoxLayout(orientation='vertical', padding=20)
        content.add_widget(Label(text="Simulating Season...\nPlease Wait.", halign='center'))
        self.sim_popup = Popup(title="Processing", content=content, size_hint=(0.6, 0.3), auto_dismiss=False)
        self.sim_popup.open()
        threading.Thread(target=self._run_sim_thread).start()

    def _run_sim_thread(self):
        app = App.get_running_app()
        fixtures = app.tournament_data['fixtures']
        app.data_mgr.batch_mode = True
        
        for idx, match in enumerate(fixtures):
            if "Play" in str(match[3]) and match[2] is None:
                self.sim_match(idx, match[0], match[1], match[3], None, refresh_ui=False, do_save=False)
        
        app.data_mgr.batch_mode = False
        app.data_mgr.save()
        app.save_tournament()
        Clock.schedule_once(self._sim_complete)

    def _sim_complete(self, dt):
        self.sim_popup.dismiss()
        self.load_table()

    def play_match(self, idx, t1, t2, instance):
        app = App.get_running_app()
        app.current_match_idx = idx
        app.ai_team = t2 if t1 == app.user_team else t1
        app.root.current = 'toss'
    
    def sim_match(self, idx, t1, t2, status, instance, refresh_ui=True, do_save=True):
        app = App.get_running_app()
        was_in_batch = app.data_mgr.batch_mode
        app.data_mgr.batch_mode = True 

        bat_first = random.choice([t1, t2])
        bat_second = t2 if bat_first == t1 else t1
        winner = random.choice([t1, t2])
        loser = t2 if winner == t1 else t1
        
        is_t20 = (app.match_format == 't20')
        overs = 20 if is_t20 else 50
        base_runs = 160 if is_t20 else 280
        
        if winner == bat_first:
            s1 = random.randint(base_runs, base_runs + 50) 
            s2 = s1 - random.randint(5, 30)                
            w1 = random.randint(3, 8); w2 = random.randint(6, 10)
        else:
            s1 = random.randint(base_runs - 20, base_runs + 20)
            s2 = s1 + random.randint(2, 6)                      
            w1 = random.randint(5, 9); w2 = random.randint(2, 6)

        i1 = app.generate_simulated_innings(bat_first, s1, w1, overs, bat_second)
        i2 = app.generate_simulated_innings(bat_second, s2, w2, overs, bat_first)
        mom_name = app.calculate_mom(i1['bat'] + i2['bat'], i1['bowl'] + i2['bowl'])
        
        is_f = ("FINAL" in str(status) and "SEMI" not in str(status))
        win_score = s1 if winner == bat_first else s2
        lose_score = s2 if winner == bat_first else s1
        
        app.data_mgr.update_team_stats(app.match_format, winner, 'W', win_score, is_final=is_f)
        app.data_mgr.update_team_stats(app.match_format, loser, 'L', lose_score)
        
        app.data_mgr.commit_match_stats(app.match_format, i1['bat'], i2['bowl'], mom_name)
        app.data_mgr.commit_match_stats(app.match_format, i2['bat'], i1['bowl'], mom_name)
        
        all_bat = i1['bat'] + i2['bat']
        all_bowl = i1['bowl'] + i2['bowl']
        app.update_tournament_stats(all_bat, all_bowl)
        
        if hasattr(app, 'apply_xp_gains'):
            app.apply_xp_gains(all_bat, all_bowl)
        
        if "Play" in str(status):
            app.update_points_and_nrr(winner, loser, win_score, overs, lose_score, overs)

        app.tournament_data['fixtures'][idx][2] = winner
        if "SEMI" not in status and "FINAL" not in status:
            app.tournament_data['fixtures'][idx][3] = "Played"
        
        app.data_mgr.batch_mode = was_in_batch
        
        if do_save:
            app.data_mgr.save()
            app.save_tournament()
        
        if refresh_ui:
            app.innings_history = {1: i1, 2: i2}
            app.current_match_idx = idx
            app.game_over = True
            app.root.get_screen('result').res_text = f"{winner} WON!"
            app.root.current = 'result'


class RecordsScreen(Screen):
    header_text = StringProperty("Records")
    current_fmt = StringProperty("t20")

    def on_enter(self): 
        self.show_records('t20')

    def show_records(self, fmt):
        self.current_fmt = fmt
        self.header_text = f"{fmt.upper()} RECORDS"
        box = self.ids.content_box; box.clear_widgets()
        recs = App.get_running_app().data_mgr.stats[fmt].get('records', {})
        
        def add_rec_label(title, val, subtext=""):
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70), padding=5)
            with card.canvas.before:
                Color(0.2, 0.2, 0.25, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[10,])
            card.add_widget(Label(text=title, bold=True, color=(0.6, 0.8, 1, 1), font_size='13sp'))
            card.add_widget(Label(text=val, font_size='20sp', bold=True, color=(1, 0.84, 0, 1)))
            if subtext: card.add_widget(Label(text=subtext, font_size='12sp', color=(0.8, 0.8, 0.8, 1)))
            box.add_widget(card)

        hs = recs.get('highest_score', {})
        add_rec_label("HIGHEST INDIVIDUAL SCORE", f"{hs.get('v', 0)} Runs", hs.get('n', '-'))

        f50 = recs.get('f50')
        add_rec_label("FASTEST 50", f"{f50['b']} Balls" if f50 else "N/A", f50['name'] if f50 else "-")
        
        f100 = recs.get('f100')
        add_rec_label("FASTEST 100", f"{f100['b']} Balls" if f100 else "N/A", f100['name'] if f100 else "-")

        m4 = recs.get('most_4s', {})
        add_rec_label("MOST 4s IN INNINGS", str(m4.get('v', 0)), m4.get('n', '-'))
        
        m6 = recs.get('most_6s', {})
        add_rec_label("MOST 6s IN INNINGS", str(m6.get('v', 0)), m6.get('n', '-'))

        hps = recs.get('highest_partnership', {})
        add_rec_label("HIGHEST PARTNERSHIP", f"{hps.get('v', 0)} Runs", hps.get('n', '-'))

        bo = recs.get('best_over', {})
        val = f"{bo.get('r', 0)} Runs" if bo.get('r',0)>0 else "N/A"
        dt = f"{bo.get('bat','')} vs {bo.get('bowl','')}" if bo.get('r',0)>0 else ""
        add_rec_label("MOST EXPENSIVE OVER", val, dt)

    def show_player_form(self, mode):
        self.header_text = f"RECENT FORM ({self.current_fmt.upper()})"
        box = self.ids.content_box; box.clear_widgets()

        toggle_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        btn_bat = Button(text="Batting Form", background_color=(0, 0.6, 0, 1) if mode=='bat' else (0.3,0.3,0.3,1))
        btn_bat.bind(on_release=lambda x: self.show_player_form('bat'))
        btn_bowl = Button(text="Bowling Form", background_color=(0, 0.6, 0, 1) if mode=='bowl' else (0.3,0.3,0.3,1))
        btn_bowl.bind(on_release=lambda x: self.show_player_form('bowl'))
        toggle_box.add_widget(btn_bat); toggle_box.add_widget(btn_bowl)
        box.add_widget(toggle_box)
        
        data = App.get_running_app().data_mgr.stats[self.current_fmt].get('batting' if mode=='bat' else 'bowling', {})
        
        h = BoxLayout(size_hint_y=None, height=dp(30))
        h.add_widget(Label(text="Player", size_hint_x=0.4, bold=True, color=(1,1,0,1)))
        h.add_widget(Label(text="Last 5 Matches", size_hint_x=0.6, bold=True, color=(1,1,0,1)))
        box.add_widget(h)

        sorted_players = sorted(data.items(), key=lambda x: x[1].get('m', 0), reverse=True)

        for name, stats in sorted_players:
            hist = stats.get('history', [])
            if not hist: continue
            
            row = BoxLayout(size_hint_y=None, height=dp(40))
            row.add_widget(Label(text=name, size_hint_x=0.4, halign='left', padding_x=10, text_size=(None, None)))
            
            if mode == 'bat':
                form_str = ", ".join(map(str, reversed(hist)))
                col = (0.5, 1, 0.5, 1)
            else:
                form_str = "  ".join(reversed(hist))
                col = (0.5, 0.8, 1, 1)
                
            row.add_widget(Label(text=form_str, size_hint_x=0.6, color=col))
            with row.canvas.before:
                Color(1, 1, 1, 0.1)
                Line(points=[row.x, row.y, row.right, row.y], width=1)
            box.add_widget(row)


class TeamStatsScreen(Screen):
    header_text = StringProperty("Team Stats")
    
    def show_teams(self, fmt):
        self.current_fmt = fmt
        self.header_text = f"{fmt.upper()} Team Records"
        box = self.ids.table_layout; box.clear_widgets()
        data = App.get_running_app().data_mgr.stats[fmt].get('teams', {})
        
        sorted_teams = sorted(data.items(), key=lambda x: (x[1].get('wc',0), x[1].get('w',0)), reverse=True)
        weights = [0.24, 0.08, 0.08, 0.08, 0.08, 0.13, 0.13, 0.18]
        
        for name, s in sorted_teams:
            row = ClickableRow(orientation='horizontal', size_hint_y=None, height=dp(50))
            vals = [
                name, 
                str(s.get('m',0)),
                str(s.get('w',0)),
                str(s.get('l',0)),
                str(s.get('t',0)),
                str(s.get('hs',0)),
                str(s.get('ls',0)),
                str(s.get('wc', 0))
            ]
            for i, val in enumerate(vals):
                lbl = Label(text=val, size_hint_x=weights[i])
                if i==0: lbl.bold = True
                if i==7: lbl.color = (1, 0.84, 0, 1)
                row.add_widget(lbl)
                
            row.bind(on_release=partial(self.open_team_players, name))
            box.add_widget(row)

    def open_team_players(self, team_name, instance):
        app = App.get_running_app()
        app.selected_team_stat = team_name
        app.root.current = 'team_players'


class TeamPlayersScreen(Screen):
    team_name = StringProperty("")
    def on_enter(self):
        app = App.get_running_app(); self.team_name = app.selected_team_stat; self.show_batting()
    def show_batting(self):
        app = App.get_running_app(); self.populate_list(app.match_format, 'bat')
    def show_bowling(self):
        app = App.get_running_app(); self.populate_list(app.match_format, 'bowl')
    def populate_list(self, fmt, mode):
        box = self.ids.player_list; box.clear_widgets()
        roster = DEFAULT_TEAMS[self.team_name]['batters' if mode=='bat' else 'bowlers']
        stats_db = App.get_running_app().data_mgr.stats[fmt].get('batting' if mode=='bat' else 'bowling', {})
        h = BoxLayout(size_hint_y=None, height=dp(40))
        if mode == 'bat':
            cols = ["Name", "M", "R", "Ave", "SR", "50", "100", "4s", "6s", "HS", "MOM"]
            weights = [0.15, 0.05, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08]
        else:
            cols = ["Name", "M", "O", "W", "Econ", "Best", "MOM"]
            weights = [0.25, 0.1, 0.1, 0.1, 0.15, 0.15, 0.15]
        for i, c in enumerate(cols): h.add_widget(Label(text=c, bold=True, size_hint_x=weights[i]))
        box.add_widget(h)
        for p_name in roster:
            s = stats_db.get(p_name, {})
            row = BoxLayout(size_hint_y=None, height=dp(50))
            row.add_widget(Label(text=p_name, size_hint_x=weights[0]))
            row.add_widget(Label(text=str(s.get('m', 0)), size_hint_x=weights[1]))
            if mode == 'bat':
                row.add_widget(Label(text=str(s.get('r', 0)), size_hint_x=weights[2]))
                outs = s.get('outs', 0); runs = s.get('r', 0)
                avg = round(runs / outs, 1) if outs > 0 else runs
                row.add_widget(Label(text=str(avg), size_hint_x=weights[3]))
                balls = s.get('b', 0); sr = int((runs / balls) * 100) if balls > 0 else 0
                row.add_widget(Label(text=str(sr), size_hint_x=weights[4]))
                row.add_widget(Label(text=str(s.get('50', 0)), size_hint_x=weights[5]))
                row.add_widget(Label(text=str(s.get('100', 0)), size_hint_x=weights[6]))
                row.add_widget(Label(text=str(s.get('4s',0)), size_hint_x=weights[7]))
                row.add_widget(Label(text=str(s.get('6s',0)), size_hint_x=weights[8]))
                row.add_widget(Label(text=str(s.get('hs',0)), size_hint_x=weights[9]))
                row.add_widget(Label(text=str(s.get('mom',0)), size_hint_x=weights[10], color=(1,1,0,1)))
            else:
                balls = s.get('b', 0); ov_display = f"{balls//6}.{balls%6}"
                row.add_widget(Label(text=ov_display, size_hint_x=weights[2]))
                row.add_widget(Label(text=str(s.get('w', 0)), size_hint_x=weights[3]))
                runs_conceded = s.get('r', 0); econ = round(runs_conceded / (balls / 6), 1) if balls > 0 else 0.0
                row.add_widget(Label(text=str(econ), size_hint_x=weights[4]))
                best = f"{s.get('bi_w',0)}/{s.get('bi_r',0)}"
                row.add_widget(Label(text=best, size_hint_x=weights[5]))
                row.add_widget(Label(text=str(s.get('mom',0)), size_hint_x=weights[6], color=(1,1,0,1)))
            box.add_widget(row)

class StatsScreen(Screen):
    current_fmt = StringProperty('t20')
    header_text = StringProperty("Stats")
    sort_key = StringProperty("Runs")
    sort_reverse = BooleanProperty(True)
    current_page = NumericProperty(0)
    items_per_page = 25
    
    def on_enter(self):
        self.show_stats('t20', 'bat')

    def show_stats(self, fmt, mode):
        self.current_fmt = fmt
        self.current_mode = mode
        self.header_text = f"{fmt.upper()} {'Batting' if mode=='bat' else 'Bowling'} Records"
        self.sort_key = "Runs" if mode == 'bat' else "Wkts"
        self.current_page = 0
        self.build_table()

    def update_sort(self, key):
        if self.sort_key == key: 
            self.sort_reverse = not self.sort_reverse
        else: 
            self.sort_key = key
            self.sort_reverse = True
        self.current_page = 0
        self.build_table()

    def change_page(self, direction):
        self.current_page += direction
        self.build_table()

    def build_table(self):
        mode = getattr(self, 'current_mode', 'bat')
        layout = self.ids.table_layout; layout.clear_widgets()
        header_box = self.ids.header_box; header_box.clear_widgets()
        
        data_map = App.get_running_app().data_mgr.stats[self.current_fmt].get('batting' if mode=='bat' else 'bowling', {})
        data_list = []
        
        if mode == 'bat': 
            for name, s in data_map.items():
                outs = s.get('outs',0); runs = s.get('r',0); balls = s.get('b',0)
                avg = round(runs/outs, 1) if outs>0 else runs
                sr = int((runs/balls)*100) if balls>0 else 0
                data_list.append({'Name':name, 'Mat':s.get('m',0), 'Runs':runs, 'Ave':avg, 'SR':sr, 'HS':s.get('hs',0), '50':s.get('50', 0), '100':s.get('100',0), '4s':s.get('4s',0), '6s':s.get('6s',0), 'MOM': s.get('mom',0)})
            headers = ["Name", "Mat", "Runs", "Ave", "SR", "50", "100", "HS", "4s", "6s", "MOM"]
            widths = [150, 50, 70, 70, 60, 50, 50, 60, 50, 50, 60]
        else:
            for name, s in data_map.items():
                balls = s.get('b',0); runs = s.get('r',0); ov_display = f"{balls//6}.{balls%6}"
                econ = round(runs/(balls/6), 2) if balls>0 else 0
                best = f"{s.get('bi_w',0)}/{s.get('bi_r',0)}"
                data_list.append({'Name':name, 'Mat':s.get('m',0), 'Ov':ov_display, 'Econ':econ, 'Wkts':s.get('w',0), 'Best':best, 'MOM': s.get('mom',0)})
            headers = ["Name", "Mat", "Ov", "Econ", "Wkts", "Best", "MOM"]
            widths = [150, 50, 60, 60, 60, 80, 60]
        
        total_width = sum(widths)
        self.ids.header_box.width = dp(total_width)
        self.ids.table_layout.width = dp(total_width)

        data_list.sort(key=lambda x: x.get(self.sort_key, 0), reverse=self.sort_reverse)
        
        total_items = len(data_list)
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        paged_data = data_list[start_idx:end_idx]
        
        self.ids.page_lbl.text = f"Page {self.current_page + 1}"
        self.ids.prev_btn.disabled = (self.current_page == 0)
        self.ids.next_btn.disabled = (end_idx >= total_items)

        for i, h in enumerate(headers):
            btn = Button(text=h, size_hint_x=None, width=dp(widths[i]), bold=True, background_color=(0.3, 0.3, 0.3, 1))
            btn.bind(on_release=lambda x, val=h: self.update_sort(val))
            header_box.add_widget(btn)
        
        for item in paged_data:
            row = BoxLayout(size_hint_y=None, height=dp(40))
            for i, h in enumerate(headers): 
                lbl = Label(text=str(item[h]), size_hint_x=None, width=dp(widths[i]))
                if h == "MOM": lbl.color = (1,1,0,1)
                row.add_widget(lbl)
            layout.add_widget(row)

class RankingsScreen(Screen):
    def on_enter(self):
        self.show_ranks('t20', 'bat')

    def show_ranks(self, fmt, mode):
        box = self.ids.rank_box; box.clear_widgets()
        data = App.get_running_app().data_mgr.stats[fmt].get('batting' if mode=='bat' else 'bowling', {})
        
        ranked = []
        for name, s in data.items(): 
            ranked.append((name, s.get('pts', 0), s.get('change', 0)))
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(Label(text="Pos", size_hint_x=0.15, bold=True, color=(0.7,0.7,0.7,1)))
        header.add_widget(Label(text="Player", size_hint_x=0.5, bold=True, color=(0.7,0.7,0.7,1)))
        header.add_widget(Label(text="Rating", size_hint_x=0.2, bold=True, color=(0.7,0.7,0.7,1)))
        header.add_widget(Label(text="Change", size_hint_x=0.15, bold=True, color=(0.7,0.7,0.7,1)))
        box.add_widget(header)

        for idx, (n, p, change) in enumerate(ranked):
            row = BoxLayout(size_hint_y=None, height=dp(40))
            row.add_widget(Label(text=f"{idx+1}", size_hint_x=0.15))
            row.add_widget(Label(text=n, size_hint_x=0.5, halign='center'))
            row.add_widget(Label(text=str(int(p)), size_hint_x=0.2, bold=True, color=(1, 0.84, 0, 1)))
            
            change_text = "-"
            change_color = "888888"
            if change > 0:
                change_text = f"^ {change}"
                change_color = "00ff00"
            elif change < 0:
                change_text = f"v {abs(change)}"
                change_color = "ff0000"
                
            lbl_change = Label(text=f"[color={change_color}]{change_text}[/color]", 
                               size_hint_x=0.15, markup=True, bold=True)
            row.add_widget(lbl_change)
            box.add_widget(row)


class GameScreen(Screen):
    match_header = StringProperty("Loading Match...")
    score_display = StringProperty("0/0")
    rr_display = StringProperty("")
    req_display = StringProperty("")
    over_history = StringProperty("")
    partnership_text = StringProperty("")
    
    striker_set_val = NumericProperty(0)
    non_striker_set_val = NumericProperty(0)
    striker_pressure = NumericProperty(0)
    non_striker_pressure = NumericProperty(0)
    
    event_main = StringProperty("PLAY")
    event_color = ListProperty([1, 1, 1, 1])
    commentary = StringProperty("Match Started")
    
    btn_text = StringProperty("HIT")
    striker_text = StringProperty("")
    non_striker_text = StringProperty("")
    bowler_text = StringProperty("")
    
    strat_mode_striker = StringProperty("NOR")
    strat_mode_nonstriker = StringProperty("NOR")
    btn_text_striker = StringProperty("NOR")
    btn_text_nonstriker = StringProperty("NOR")
    
    is_user_batting = BooleanProperty(True)
    striker_active = BooleanProperty(True)
    auto_active = BooleanProperty(False)
    long_press_timer = None
    game_loop = None
    was_active_on_press = False
    
    player_strategies = {}
    last_strat_choice = "NOR" 
    current_partnership = {'r': 0, 'b': 0}
    ui_player_slots = ListProperty([None, None])

    def on_enter(self):
        self.update_ui()
        self.auto_active = False

    def open_batsman_selection(self):
        app = App.get_running_app()
        if self.auto_active:
            for p in app.match_bat_stats:
                if not p['is_out'] and p['b'] == 0 and p != app.non_striker:
                    self.on_batsman_selected(p)
                    return
            return

        available = [p for p in app.match_bat_stats if not p['is_out'] and p['b'] == 0 and p != app.non_striker]
        if not available:
            if app.innings == 1: app.swap_innings()
            else: app.end_game(False)
            return

        popup = PlayerSelectPopup(title="Select Next Batsman", players=available, callback=self.on_batsman_selected)
        popup.open()

    def on_batsman_selected(self, player_obj, *args):
        app = App.get_running_app()
        if app.striker.get('is_out'): app.striker = player_obj
        elif app.non_striker.get('is_out'): app.non_striker = player_obj
        else: app.striker = player_obj
        
        try:
            curr = app.match_bat_stats.index(player_obj)
            if curr >= app.next_bat_idx: app.next_bat_idx = curr + 1
        except: pass
        
        self.update_ui()
        if self.auto_active and not self.game_loop: 
            self.activate_auto_play(0)

    def open_bowler_selection(self):
        app = App.get_running_app()
        if self.auto_active:
            app.rotate_bowler()
            self.update_ui()
            return

        self.stop_auto_play() 
        valid = []
        max_balls = 24 if app.match_format == 't20' else 60
        for b_name in app.bowl_roster:
            b = app.match_bowlers[b_name]
            if b['b'] < max_balls:
                valid.append(b)
                
        popup = BowlerSelectPopup(
            bowlers=valid, 
            current_bowler=app.current_bowler, 
            current_strat=app.user_bowling_strategy,
            callback=self.on_bowler_selected
        )
        popup.open()

    def on_bowler_selected(self, bowler_obj, strategy):
        app = App.get_running_app()
        app.current_bowler = bowler_obj
        app.user_bowling_strategy = strategy
        self.update_ui()

    def animate_event(self):
        lbl = self.ids.event_lbl 
        lbl.font_size = dp(20)
        lbl.opacity = 0
        anim = Animation(font_size=dp(90), opacity=1, duration=0.1, t='out_back')
        anim += Animation(opacity=0, duration=1.0, t='in_quad')
        anim.start(lbl)

    def toggle_strategy(self, is_top_card):
        if not self.is_user_batting: return
        idx = 0 if is_top_card else 1
        p_name = self.ui_player_slots[idx]
        if not p_name: return
        curr = self.player_strategies.get(p_name, self.last_strat_choice)
        if curr == 'NOR': new_s = 'AGG'
        elif curr == 'AGG': new_s = 'DEF'
        else: new_s = 'NOR'
        self.player_strategies[p_name] = new_s
        self.last_strat_choice = new_s 
        self.update_ui()

    def get_strat_color_rgb(self, mode):
        if mode == 'DEF': return (0.2, 0.4, 0.8, 1)
        if mode == 'AGG': return (0.9, 0.1, 0.1, 1)
        return (1, 0.6, 0, 1)

    def on_control_press(self, instance=None):
        self.was_active_on_press = self.auto_active
        if not self.auto_active: 
            self.long_press_timer = Clock.schedule_once(self.activate_auto_play, 0.8)

    def on_control_release(self, instance=None):
        if self.long_press_timer: self.long_press_timer.cancel()
        if self.was_active_on_press: self.stop_auto_play()
        elif self.auto_active: pass
        else: self.play_ball()

    def activate_auto_play(self, dt):
        self.auto_active = True
        self.commentary = ">>> AUTO SIMULATION <<<"
        self.game_loop = Clock.schedule_interval(self.auto_play_step, 0.15)

    def stop_auto_play(self):
        self.auto_active = False
        if self.game_loop: self.game_loop.cancel()
        self.commentary = "Paused"

    def auto_play_step(self, dt):
        app = App.get_running_app()
        if app.game_over or (self.is_user_batting and self.btn_text == "BOWL"): 
            self.stop_auto_play()
        else: 
            self.play_ball()

    def trigger_milestone(self, name, runs):
        content = BoxLayout(orientation='vertical', padding=20)
        t_txt = "50 UP!" if runs == 50 else "CENTURY!"
        col = (0.5, 0.8, 1, 1) if runs == 50 else (1, 0.8, 0, 1)
        content.add_widget(Label(text=t_txt, font_size='30sp', bold=True, color=col, halign='center'))
        content.add_widget(Label(text=f"{name}", font_size='22sp', halign='center'))
        popup = Popup(title="MILESTONE", content=content, size_hint=(0.6, 0.3), separator_color=col)
        popup.open()
        Clock.schedule_once(popup.dismiss, 1.2)

    def open_scorecard(self):
        app = App.get_running_app()
        try:
            if hasattr(app, 'innings') and app.innings is not None:
                self.show_scorecard_popup(app.innings)
        except Exception as e:
            print(f"Scorecard Error: {e}")

    def update_ai_tactics(self):
        app = App.get_running_app()
        is_t20 = (app.match_format == 't20')
        overs_gone = app.balls // 6
        wickets_left = 10 - app.wickets
        
        pp_end = 6 if is_t20 else 10
        death_start = 16 if is_t20 else 40
        
        if self.is_user_batting:
            if app.runs_this_over > 10 or (app.score / (app.balls/6 + 0.1)) > 10:
                app.ai_tactic = "DEFENSIVE"
            elif app.runs_this_over < 4 and wickets_left < 5:
                app.ai_tactic = "ATTACK"
            else:
                app.ai_tactic = "NORMAL"
        else:
            if (overs_gone < pp_end and wickets_left < 7) or (wickets_left < 6 and overs_gone < death_start):
                app.ai_tactic = "DEFENSIVE"
                return

            if overs_gone >= death_start:
                if wickets_left > 3: app.ai_tactic = "AGGRESSIVE"
                elif wickets_left > 1: app.ai_tactic = "NORMAL"
                else: app.ai_tactic = "DEFENSIVE"
                return

            if app.is_chasing:
                rem_balls = (app.overs * 6) - app.balls
                if rem_balls > 0:
                    req = (app.target + 1) - app.score
                    rrr = (req / rem_balls) * 6
                    if rrr > 11.0: app.ai_tactic = "AGGRESSIVE"
                    elif rrr > 8.5: app.ai_tactic = "NORMAL"
                    elif rrr < 5.0: app.ai_tactic = "DEFENSIVE"
                    else: app.ai_tactic = "NORMAL"
                return

            if overs_gone < pp_end:
                if wickets_left > 8: app.ai_tactic = "AGGRESSIVE"
                else: app.ai_tactic = "NORMAL"
            else:
                if wickets_left > 7 and overs_gone > (death_start - 4): 
                    app.ai_tactic = "AGGRESSIVE"
                else:
                    app.ai_tactic = "NORMAL"

    def play_ball(self):
        app = App.get_running_app()
        if app.game_over: return
        
        old_innings = app.innings
        
        if app.balls % 6 == 0: 
            app.over_balls = []
            self.update_ai_tactics()

        striker = app.striker
        bowler = app.current_bowler
        
        if self.is_user_batting:
            raw_mode = self.player_strategies.get(striker['name'], 'NOR')
        else:
            raw_mode = app.ai_tactic

        if "DEF" in raw_mode: mode = 'DEF'
        elif "AGG" in raw_mode: mode = 'AGG'
        else: mode = 'NOR'

        if mode == 'DEF':
            weights = [60, 35, 4, 0, 0, 1] 
        elif mode == 'AGG':
            weights = [10, 20, 20, 30, 10, 10] 
            if striker.get('b', 0) > 15:
                weights[0] = 5
                weights[3] += 10
                weights[4] += 10
                weights[5] -= 2
            is_death = (app.match_format == 't20' and app.balls > 108) or (app.match_format == 'odi' and app.balls > 288)
            if is_death:
                weights[4] += 25
                weights[3] += 10
                weights[1] = 0   
                weights[5] += 5  
        else:
            weights = [30, 40, 15, 12, 1, 2]

        bat_skill = striker.get('skill', 50)
        bowl_skill = bowler.get('skill', 50)
        diff = (bat_skill - bowl_skill) / 10.0
        
        if diff > 0: 
            weights[0] -= diff
            weights[3] += diff
        else:
            weights[0] += abs(diff)
            weights[5] += abs(diff)

        pt = app.pitch_type
        if "GREEN" in pt and app.balls < 30: 
            weights[0] += 10; weights[5] += 2
        elif "FLAT" in pt:
            weights[3] += 5; weights[5] -= 1

        weights = [max(0, w) for w in weights]
        
        if app.is_free_hit:
            weights = [0, 5, 15, 40, 40, 0]
            app.is_free_hit = False

        outcomes = ["0", "1", "2", "4", "6", "W"]
        result = random.choices(outcomes, weights=weights, k=1)[0]
        
        comm_text = ""
        comm_color = [1,1,1,1] 
        
        if result == "W":
            if random.random() < 0.03:
                result = "1"
                comm_text = "DROPPED! A huge let off."
                comm_color = [1, 1, 0, 1]
            else:
                self.event_main = "OUT"; self.event_color = [1, 0, 0, 1]
                if mode == 'AGG': comm_text = "Caught! Mistimed the big shot."
                elif mode == 'DEF': comm_text = "Beauty! Through the gate."
                else: comm_text = "Edged and taken!"
                self.commentary = comm_text
                app.handle_wicket()

        if result != "W":
            runs = int(result)
            if runs == 1 and random.random() < 0.01:
                runs = 4
                comm_text = "Misfield allows the boundary!"
                comm_color = [0, 1, 0, 1]
            else:
                if runs == 6: 
                    comm_text = "MAXIMUM! Into the stands."
                    comm_color = [1, 0.8, 0, 1]
                elif runs == 4: 
                    comm_text = "FOUR! Cracking shot."
                    comm_color = [0, 1, 0, 1]
                elif runs == 2: 
                    comm_text = "Running hard for two."
                elif runs == 1: 
                    comm_text = "Single taken."
                else: 
                    comm_text = "Solid defense." if mode == 'DEF' else "Straight to fielder."

            app.handle_runs(runs)
            self.event_main = str(runs)
            self.event_color = comm_color
            self.commentary = f"{comm_text} ({mode})"

        if app.innings != old_innings or app.game_over: self.update_ui(); return

        app.over_balls.append(self.event_main if len(self.event_main)<3 else "W")
        app.balls += 1
        
        if result != "W" and int(result) % 2 != 0: 
            app.swap_strikers()
        
        self.animate_event()
        app.check_state()
        
        if app.innings != old_innings or app.game_over: self.update_ui(); return
        self.update_ui() 
        
        if app.balls % 6 == 0:
            app.data_mgr.update_over_record(app.match_format, app.runs_this_over, app.striker['name'], app.current_bowler['name'])
            app.runs_this_over = 0
            app.swap_strikers()
            
            if not self.is_user_batting and not app.game_over: self.open_bowler_selection()
            else: app.rotate_bowler()
        
        if self.auto_active: 
             if (app.balls % 6 == 0 and not self.is_user_batting) or result == "W":
                 if result == "W" and self.is_user_batting: self.open_batsman_selection()
                 elif app.balls % 6 == 0 and not self.is_user_batting: self.open_bowler_selection()

    def get_ai_strategy_mode(self, app):
        balls_left = (app.overs * 6) - app.balls
        wickets_left = 10 - app.wickets
        overs_gone = app.balls // 6
        
        if wickets_left < 3 and balls_left > 40:
            return 'DEF'

        if app.is_chasing:
            if balls_left <= 0: return 'AGG'
            rem = (app.target + 1) - app.score
            rrr = (rem / balls_left) * 6
            if rrr > 8.5: return 'AGG'
            if rrr < 4.0 and wickets_left > 2: return 'NOR'
            if rrr < 6.0 and wickets_left < 4: return 'DEF'
            return 'NOR'
        else:
            if overs_gone < 6:
                if wickets_left > 8: return 'AGG'
                return 'NOR'
            if balls_left < 30:
                if wickets_left > 2: return 'AGG'
                return 'NOR'
            if wickets_left > 7: return 'AGG'
            if wickets_left < 4: return 'DEF'
            return 'NOR'

    def update_ui(self):
        app = App.get_running_app()
        ov = f"{app.balls//6}.{app.balls%6}"
        
        self.partnership_text = f"Part: {app.partnership_runs} ({app.partnership_balls})"
        
        bt = app.batting_team
        bw = app.bowling_team
        
        pitch_color = "ffff00" 
        if "GREEN" in app.pitch_type: pitch_color = "88ff88"
        elif "FLAT" in app.pitch_type: pitch_color = "00ffff"
        elif "DRY" in app.pitch_type: pitch_color = "ffaa88"
        
        ai_c = "ffffff"
        if app.ai_tactic in ["ATTACK", "SLOG", "AGGRESSIVE"]: ai_c = "ff5555"
        elif app.ai_tactic in ["DEFENSIVE", "STEADY"]: ai_c = "55aaff"
        
        header_info = f"[color={pitch_color}]PITCH: {app.pitch_type}[/color]  |  [color={ai_c}]AI: {app.ai_tactic}[/color]"
        self.match_header = f"[color=#00ff00]{bt}[/color] vs {bw}\n[size=12sp]{header_info}[/size]"
        self.score_display = f"{app.score}/{app.wickets}   [size=18sp]({ov})[/size]"
        
        match_pressure = 0
        crr = round(app.score/(app.balls/6), 2) if app.balls>0 else 0
        
        if app.is_chasing:
            rem_runs = (app.target+1)-app.score
            rem_balls = (app.overs*6)-app.balls
            rrr = round((rem_runs/rem_balls)*6, 2) if rem_balls>0 else 0.0
            self.rr_display = f"CRR: {crr}  |  RRR: {rrr}"
            self.req_display = f"Need {rem_runs} off {rem_balls}"
            match_pressure = 30
            if rrr > 8: match_pressure += 20
            if rrr > 10: match_pressure += 20
            if rrr > 12: match_pressure += 30
            if app.wickets > 0: match_pressure += (app.wickets * 5)
        else:
            self.rr_display = f"CRR: {crr}"
            self.req_display = "Setting Target"
            match_pressure = 20 + (app.wickets * 10)
            if crr < 6.0 and app.balls > 30: match_pressure += 20
            
        final_pressure = min(100, max(0, match_pressure))

        s = app.striker; ns = app.non_striker
        p0 = self.ui_player_slots[0]; p1 = self.ui_player_slots[1]
        
        current_names = [s['name'], ns['name']]
        new_slots = [None, None]
        if p0 not in current_names and p1 not in current_names: new_slots = [s['name'], ns['name']]
        elif p0 in current_names and p1 in current_names: new_slots = [p0, p1]
        elif p0 not in current_names: new_slots = [(s['name'] if s['name'] != p1 else ns['name']), p1]
        else: new_slots = [p0, (s['name'] if s['name'] != p0 else ns['name'])]
        
        self.ui_player_slots = new_slots
        player_top = s if s['name'] == new_slots[0] else ns
        player_bot = s if s['name'] == new_slots[1] else ns
        top_is_active = (player_top['name'] == s['name'])
        self.striker_active = top_is_active
        
        mark_top = " [color=00ff00]*[/color]" if top_is_active else ""
        stats_top = f"[color=88ff88]4s:{player_top.get('4s',0)}[/color]  [color=ffcc00]6s:{player_top.get('6s',0)}[/color]"
        self.striker_text = f"[b]{player_top['name']}[/b]{mark_top}\n[size=14sp]{player_top['r']} ({player_top['b']})[/size]\n[size=10sp]{stats_top}[/size]"
        self.striker_set_val = min(100, (player_top.get('b',0)/20)*100)
        self.striker_pressure = final_pressure
        
        mark_bot = " [color=00ff00]*[/color]" if not top_is_active else ""
        stats_bot = f"[color=88ff88]4s:{player_bot.get('4s',0)}[/color]  [color=ffcc00]6s:{player_bot.get('6s',0)}[/color]"
        self.non_striker_text = f"[b]{player_bot['name']}[/b]{mark_bot}\n[size=14sp]{player_bot['r']} ({player_bot['b']})[/size]\n[size=10sp]{stats_bot}[/size]"
        self.non_striker_set_val = min(100, (player_bot.get('b',0)/20)*100)
        self.non_striker_pressure = final_pressure

        if self.is_user_batting:
            fallback = self.last_strat_choice
            self.btn_text_striker = self.player_strategies.get(player_top['name'], fallback)
            self.btn_text_nonstriker = self.player_strategies.get(player_bot['name'], fallback)
        else:
            ai_mode = self.get_ai_strategy_mode(app)
            self.btn_text_striker = ai_mode
            self.btn_text_nonstriker = ai_mode
        
        self.bowler_text = f"{app.current_bowler['name']} | {app.current_bowler['w']}-{app.current_bowler['r']}"
        
        hist = []
        for e in app.over_balls:
            c = "ff3333" if e=="W" else ("33ff33" if e=="4" else ("ffcc00" if e=="6" else "ffffff"))
            hist.append(f"[color={c}]{e}[/color]")
        self.over_history = " ".join(hist)
        
        self.is_user_batting = (app.batting_team == app.user_team)
        self.btn_text = "HIT" if self.is_user_batting else "BOWL"

    def show_scorecard_popup(self, inning_to_show=None):
        app = App.get_running_app()
        if inning_to_show is None:
            inning_to_show = app.innings

        content = BoxLayout(orientation='vertical', padding=0, spacing=0)
        tab_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=2)
        with tab_box.canvas.before:
            Color(0.08, 0.08, 0.1, 1)
            Rectangle(pos=tab_box.pos, size=tab_box.size)

        btn_inn1 = Button(text="1st INNINGS", background_color=(0,0,0,0), font_size='14sp', bold=True)
        btn_inn2 = Button(text="2nd INNINGS", background_color=(0,0,0,0), font_size='14sp', bold=True)
        
        def set_active_tab(active, inactive):
            active.color = (1, 0.8, 0, 1)
            active.canvas.before.clear()
            with active.canvas.before:
                Color(0.2, 0.25, 0.35, 1)
                RoundedRectangle(pos=active.pos, size=active.size, radius=[5,5,0,0])
            inactive.color = (0.5, 0.5, 0.5, 1)
            inactive.canvas.before.clear()

        btn_inn1.bind(on_release=lambda x: [set_active_tab(btn_inn1, btn_inn2), self.load_scorecard_data(scroll, 1)])
        btn_inn2.bind(on_release=lambda x: [set_active_tab(btn_inn2, btn_inn1), self.load_scorecard_data(scroll, 2)])

        if inning_to_show == 1: set_active_tab(btn_inn1, btn_inn2)
        else: set_active_tab(btn_inn2, btn_inn1)

        tab_box.add_widget(btn_inn1)
        tab_box.add_widget(btn_inn2)
        content.add_widget(tab_box)

        scroll = ScrollView(bar_width=dp(4), bar_color=(1, 0.8, 0, 1), effect_cls='ScrollEffect')
        self.load_scorecard_data(scroll, inning_to_show)
        content.add_widget(scroll)

        close_btn = Button(text="CLOSE", size_hint_y=None, height=dp(45),
                           background_color=(0.8, 0.1, 0.1, 1), bold=True)
        
        popup = Popup(title="", separator_height=0, content=content, size_hint=(0.95, 0.92))
        close_btn.bind(on_release=popup.dismiss)
        content.add_widget(close_btn)
        popup.open()

    def load_scorecard_data(self, scroll_view, inning):
        app = App.get_running_app()
        scroll_view.clear_widgets()
        
        data = None
        if inning == app.innings and not app.game_over:
            total_balls = sum(b['b'] for b in app.match_bowlers.values())
            data = {
                'team': app.batting_team, 'score': app.score, 'w': app.wickets,
                'bat': app.match_bat_stats, 'bowl': list(app.match_bowlers.values()),
                'fow': app.fow_list, 'ov_str': f"{total_balls//6}.{total_balls%6}"
            }
        elif inning in app.innings_history:
            h = app.innings_history[inning]
            if 'ov_str' not in h:
                tb = sum(b['b'] for b in h['bowl'])
                h['ov_str'] = f"{tb//6}.{tb%6}"
            data = h
        else:
            box = BoxLayout(orientation='vertical', padding=50)
            box.add_widget(Label(text="Innings Not Started", font_size='22sp', color=(0.4,0.4,0.4,1)))
            scroll_view.add_widget(box)
            return

        layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(5), 0, dp(5), dp(20)])
        layout.bind(minimum_height=layout.setter('height'))

        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(80), padding=10)
        with header.canvas.before:
            Color(0.12, 0.15, 0.18, 1)
            RoundedRectangle(pos=header.pos, size=header.size, radius=[0,0,10,10])
        
        team_lbl = Label(text=data['team'], font_size='20sp', bold=True, color=(0.5, 0.7, 1, 1), size_hint_y=0.4)
        score_txt = f"{data['score']}/{data['w']}  [size=18sp][color=aaaaaa]({data['ov_str']} ov)[/color][/size]"
        score_lbl = Label(text=score_txt, font_size='36sp', bold=True, markup=True, size_hint_y=0.6)
        
        header.add_widget(team_lbl)
        header.add_widget(score_lbl)
        layout.add_widget(header)

        layout.add_widget(self.create_row(["BATTER", "R", "B", "4s", "6s", "SR"], [0.4, 0.12, 0.12, 0.12, 0.12, 0.12], True))
        
        curr_s = app.striker.get('name', '') if app.striker else ''
        curr_ns = app.non_striker.get('name', '') if app.non_striker else ''

        for p in data['bat']:
            is_active = (p['name'] == curr_s or p['name'] == curr_ns)
            has_played = (p['b'] > 0 or p.get('is_out') or is_active)
            
            if has_played:
                name_txt = p['name']
                if is_active and inning == app.innings and not app.game_over:
                    name_txt = f"[color=00ff00]>[/color] {name_txt}"
                    sub_txt = "Batting"
                elif p.get('is_out'):
                    sub_txt = p.get('dismissal', 'out')
                else:
                    sub_txt = "not out"
                
                display_name = f"[b]{name_txt}[/b]\n[size=11sp][color=888888]{sub_txt}[/color][/size]"
                sr = int((p['r']/p['b'])*100) if p['b'] > 0 else 0
                vals = [display_name, str(p['r']), str(p['b']), str(p.get('4s',0)), str(p.get('6s',0)), str(sr)]
                layout.add_widget(self.create_row(vals, [0.4, 0.12, 0.12, 0.12, 0.12, 0.12], False, highlight=1))

        if data['fow']:
            fow_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(55), padding=[10,5])
            with fow_box.canvas.before:
                Color(0.15, 0.1, 0.1, 1)
                RoundedRectangle(pos=fow_box.pos, size=fow_box.size, radius=[6,])
            
            fow_box.add_widget(Label(text="FALL OF WICKETS", font_size='10sp', bold=True, color=(1,0.4,0.4,1)))
            fow_str = "  |  ".join([f"[b]{f['r']}-{f['w']}[/b] [size=11sp]({f.get('p','?')})[/size]" for f in data['fow']])
            fow_box.add_widget(Label(text=fow_str, markup=True, font_size='13sp', color=(1,1,1,1)))
            layout.add_widget(fow_box)

        layout.add_widget(BoxLayout(size_hint_y=None, height=dp(10)))
        layout.add_widget(self.create_row(["BOWLER", "O", "R", "W", "Econ", "Best"], [0.4, 0.12, 0.12, 0.12, 0.12, 0.12], True))
        
        curr_b_name = app.current_bowler.get('name', '') if app.current_bowler else ''
        
        for b in data['bowl']:
            if b['b'] > 0:
                is_bowling = (b['name'] == curr_b_name and inning == app.innings and not app.game_over)
                name_txt = f"[color=00ff00]>[/color] {b['name']}" if is_bowling else b['name']
                
                ov = f"{b['b']//6}.{b['b']%6}"
                econ = round(b['r'] / (b['b']/6), 1) if b['b'] > 0 else 0.0
                best = f"{b.get('w',0)}/{b.get('r',0)}"
                
                vals = [name_txt, ov, str(b['r']), str(b['w']), str(econ), best]
                layout.add_widget(self.create_row(vals, [0.4, 0.12, 0.12, 0.12, 0.12, 0.12], False, highlight=3))

        scroll_view.add_widget(layout)

    def create_row(self, values, widths, is_header=False, highlight=-1):
        h = dp(32) if is_header else dp(48)
        row = BoxLayout(size_hint_y=None, height=h, padding=[5,0])
        
        with row.canvas.before:
            if is_header:
                Color(0.2, 0.25, 0.3, 1)
            else:
                Color(0.12, 0.14, 0.18, 1)
            RoundedRectangle(pos=row.pos, size=row.size, radius=[4,4,4,4])
            Color(1, 1, 1, 0.05)
            Line(points=[row.x, row.y, row.right, row.y], width=1)

        for i, (txt, w) in enumerate(zip(values, widths)):
            c = (1,1,1,1)
            if is_header: c = (0.7, 0.8, 0.9, 1)
            elif i == highlight: c = (1, 0.84, 0, 1)
            elif i == 0: c = (1,1,1,1)
            else: c = (0.9, 0.9, 0.9, 1)

            lbl = Label(text=txt, size_hint_x=w, markup=True, color=c,
                        font_size='11sp' if is_header else '13sp',
                        bold=(is_header or i==0),
                        halign='left' if i==0 else 'center',
                        valign='middle')
            if i == 0: lbl.bind(size=lbl.setter('text_size'))
            row.add_widget(lbl)
            
        return row


class TossScreen(Screen):
    cpu_choice_bat = BooleanProperty(False)
    def on_enter(self):
        self.ids.status_lbl.text = "Call it!"
        self.ids.decision_box.opacity = 0; self.ids.decision_box.disabled = True
        self.ids.cpu_start_box.opacity = 0; self.ids.cpu_start_box.disabled = True

    def do_toss(self, call):
        res = random.choice(['Heads', 'Tails'])
        if call == res:
            self.ids.status_lbl.text = f"{res}! You Won Toss."
            self.ids.decision_box.opacity = 1; self.ids.decision_box.disabled = False
        else:
            self.cpu_choice_bat = random.choice([True, False])
            self.ids.status_lbl.text = f"{res}! CPU Chose to {'Bat' if self.cpu_choice_bat else 'Bowl'}"
            self.ids.cpu_start_box.opacity = 1; self.ids.cpu_start_box.disabled = False
    def proceed_cpu_choice(self): self.start_match(not self.cpu_choice_bat)
    def start_match(self, user_bat_first):
        App.get_running_app().setup_teams_for_game(user_bat_first)
        App.get_running_app().root.current = 'game'

class ResultScreen(Screen):
    res_text = StringProperty("")
    def on_enter(self):
        app = App.get_running_app()
        s1 = app.innings_history.get(1, {'score':0, 'w':0, 'team': '?'})
        s2 = app.innings_history.get(2, {'score':0, 'w':0, 'team': '?'})
        self.ids.score1_lbl.text = f"{s1['team']}: {s1['score']}/{s1['w']}"
        self.ids.score2_lbl.text = f"{s2['team']}: {s2['score']}/{s2['w']}"
        
        if s2['score'] > s1['score']:
            margin = 10 - s2['w']
            self.ids.margin_lbl.text = f"Won by {margin} wickets"
        else:
            margin = s1['score'] - s2['score']
            self.ids.margin_lbl.text = f"Won by {margin} runs"
            
        mom_name = app.calculate_mom(s1.get('bat', []) + s2.get('bat', []), s1.get('bowl', []) + s2.get('bowl', []))
        self.ids.mom_lbl.text = f"Man of the Match: {mom_name}"

    def open_scorecard(self):
        app = App.get_running_app()
        app.root.get_screen('game').show_scorecard_popup(2)

    def on_continue(self):
        app = App.get_running_app()
        status = app.tournament_data['fixtures'][app.current_match_idx][3]
        if "FINAL" in str(status) and "SEMI" not in str(status): app.root.current = 'knockout'
        else: app.root.current = 'league'

class KnockoutWindow(Screen):
    champions = StringProperty("")
    most_runs = StringProperty("")
    most_wickets = StringProperty("")
    mos = StringProperty("")

    def on_enter(self):
        app = App.get_running_app()
        t_stats = app.tournament_data.get('stats', {'batting': {}, 'bowling': {}})
        
        final_match = [f for f in app.tournament_data['fixtures'] if "FINAL" in str(f[3]) and "SEMI" not in str(f[3])]
        if final_match and final_match[0][2]: 
            self.champions = final_match[0][2]
        else: 
            self.champions = "TBD"
        
        b_data = t_stats['batting']
        if b_data:
            top_bat = max(b_data.items(), key=lambda x: x[1]['r'])
            self.most_runs = f"{top_bat[0]} ({top_bat[1]['r']} runs)"
        else:
            self.most_runs = "N/A"
            
        w_data = t_stats['bowling']
        if w_data:
            top_bowl = max(w_data.items(), key=lambda x: x[1]['w'])
            self.most_wickets = f"{top_bowl[0]} ({top_bowl[1]['w']} wkts)"
        else:
            self.most_wickets = "N/A"

        all_players = set(list(b_data.keys()) + list(w_data.keys()))
        best_mos_name = "N/A"
        best_mos_pts = -1
        
        for p in all_players:
            pts = b_data.get(p, {}).get('pts', 0) + w_data.get(p, {}).get('pts', 0)
            if pts > best_mos_pts:
                best_mos_pts = pts
                best_mos_name = p
                
        if best_mos_pts > -1:
            runs = b_data.get(best_mos_name, {}).get('r', 0)
            wkts = w_data.get(best_mos_name, {}).get('w', 0)
            perf_parts = []
            if runs > 0: perf_parts.append(f"{runs} Runs")
            if wkts > 0: perf_parts.append(f"{wkts} Wkts")
            perf_str = ", ".join(perf_parts)
            self.mos = f"{best_mos_name} ({int(best_mos_pts)} pts)\n[size=16sp]{perf_str}[/size]"
        else:
            self.mos = "N/A"


class SoundManager:
    def __init__(self):
        self.music = SoundLoader.load("bg_music.mp3") if os.path.exists("bg_music.mp3") else None
        self.click = SoundLoader.load("click.wav") if os.path.exists("click.wav") else None
        self.is_muted = False
        
        if self.music:
            self.music.loop = True
            self.music.volume = 0.3
            
        if self.click:
            self.click.volume = 1.0

    def start_music(self):
        if self.music and not self.is_muted: self.music.play()

    def toggle(self):
        self.is_muted = not self.is_muted
        if self.music:
            if self.is_muted: self.music.stop()
            else: self.music.play()
        return self.is_muted

    def play_click(self):
        if self.click and not self.is_muted:
            if self.click.state == 'play': self.click.stop()
            self.click.play()


class CricketApp(App):
    pitch_type = StringProperty("STANDARD")
    ai_tactic = StringProperty("NORMAL")
    user_bowling_strategy = StringProperty("NORMAL")
    data_mgr = DataManager()
    user_team = StringProperty("")
    ai_team = StringProperty("")
    match_format = StringProperty("t20")
    overs = 20
    tournament_data = {}
    current_match_idx = -1
    selected_team_stat = StringProperty("")
    batting_team = ""
    bowling_team = ""
    score = 0; wickets = 0; balls = 0; target = 0; innings = 1; is_chasing = False; game_over = False
    striker = {}; non_striker = {}; current_bowler = {}; bat_roster = []; bowl_roster = []
    match_bowlers = {}; match_bat_stats = []; over_balls = []; is_free_hit = False; innings_history = {}
    fow_list = ListProperty([])
    next_bat_idx = 2; bowler_idx = 0; runs_this_over = 0
    partnership_runs = 0; partnership_balls = 0
    
    music_label = StringProperty("Music: ON")

    def toggle_music(self):
        if hasattr(self, 'sound_mgr'):
            muted = self.sound_mgr.toggle()
            self.music_label = "Music: OFF" if muted else "Music: ON"

    def play_click(self):
        if hasattr(self, 'sound_mgr'):
            self.sound_mgr.play_click()

    def build(self):
        self.data_mgr.load()
        self.sound_mgr = SoundManager()
        self.sound_mgr.start_music()
        Builder.load_string(kv_string)
        sm = ScreenManager()
        sm.add_widget(MenuScreen(name='menu'))
        sm.add_widget(TeamSelectScreen(name='team_select'))
        sm.add_widget(LeagueScreen(name='league'))
        sm.add_widget(StatsScreen(name='stats'))
        sm.add_widget(TeamStatsScreen(name='team_stats'))
        sm.add_widget(TeamPlayersScreen(name='team_players'))
        sm.add_widget(RecordsScreen(name='records'))
        sm.add_widget(RankingsScreen(name='rankings'))
        sm.add_widget(TossScreen(name='toss'))
        sm.add_widget(GameScreen(name='game'))
        sm.add_widget(ResultScreen(name='result'))
        sm.add_widget(KnockoutWindow(name='knockout'))
        return sm

    def start_new_league(self, user_team_choice):
        self.user_team = user_team_choice; teams = list(DEFAULT_TEAMS.keys()); fixtures = []
        pairs = list(itertools.combinations(teams, 2)); random.shuffle(pairs) 
        for p in pairs: fixtures.append([p[0], p[1], None, "Play"])
        points_init = [{'name': t, 'p': 0, 'w': 0, 'l': 0, 'pts': 0, 'rf':0, 'of':0, 'ra':0, 'oa':0, 'nrr':0.0} for t in teams]
        self.tournament_data = {
            'user_team': self.user_team, 
            'fixtures': fixtures, 
            'points': points_init, 
            'format': self.match_format, 
            'final_generated': False, 
            'sf_generated': False,
            'stats': {'batting': {}, 'bowling': {}} 
        }
        self.save_tournament()

    def update_tournament_stats(self, bat_stats, bowl_stats):
        if 'stats' not in self.tournament_data:
             self.tournament_data['stats'] = {'batting': {}, 'bowling': {}}
        
        t_bat = self.tournament_data['stats']['batting']
        t_bowl = self.tournament_data['stats']['bowling']
        
        for p in bat_stats:
            name = p['name']
            if name not in t_bat: t_bat[name] = {'r': 0, 'pts': 0}
            t_bat[name]['r'] += p['r']
            t_bat[name]['pts'] += p['r'] + (p.get('4s',0)*2) + (p.get('6s',0)*4)

        for b in bowl_stats:
            if b['b'] > 0:
                name = b['name']
                if name not in t_bowl: t_bowl[name] = {'w': 0, 'pts': 0}
                t_bowl[name]['w'] += b['w']
                t_bowl[name]['pts'] += b['w'] * 25

        self.save_tournament()

    def load_tournament(self):
        def try_load(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)

        tf = get_save_path("league_plat_v9.json")
        if os.path.exists(tf):
            try:
                self.tournament_data = try_load(tf)
            except (json.JSONDecodeError, ValueError):
                backup = tf + ".bak"
                if os.path.exists(backup):
                    try:
                        self.tournament_data = try_load(backup)
                        shutil.copy2(backup, tf)
                    except:
                        return
                else:
                    return
        
        if self.tournament_data:
            self.user_team = self.tournament_data.get('user_team', "")
            self.match_format = self.tournament_data.get('format', 't20')
            self.overs = 20 if self.match_format == 't20' else 50

    def save_tournament(self):
        if not self.tournament_data: return
        tf = get_save_path("league_plat_v9.json")
        temp_file = tf + ".tmp"
        backup_file = tf + ".bak"
        
        try:
            with open(temp_file, 'w') as f: 
                json.dump(self.tournament_data, f)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(tf):
                shutil.copy2(tf, backup_file)
            os.replace(temp_file, tf)
        except Exception as e:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass

    def update_points_and_nrr(self, winner, loser, w_score, w_ov, l_score, l_ov):
        for t in self.tournament_data['points']:
            if t['name'] == winner:
                t['p'] += 1; t['w'] += 1; t['pts'] += 2
                t['rf'] += w_score; t['of'] += w_ov; t['ra'] += l_score; t['oa'] += l_ov
            elif t['name'] == loser:
                t['p'] += 1; t['l'] += 1
                t['rf'] += l_score; t['of'] += l_ov; t['ra'] += w_score; t['oa'] += w_ov
            if t['of'] > 0 and t['oa'] > 0:
                nrr = (t['rf'] / t['of']) - (t['ra'] / t['oa']); t['nrr'] = nrr

    def setup_teams_for_game(self, user_bat_first):
        self.pitch_type = random.choice([
            "FLAT (Batting Paradise)", 
            "GREEN (Bowler Friendly)", 
            "DRY (Slow/Turn)", 
            "STANDARD (Balanced)"
        ])
        if user_bat_first: self.batting_team, self.bowling_team = self.user_team, self.ai_team
        else: self.batting_team, self.bowling_team = self.ai_team, self.user_team
        self.init_match(); self.setup_rosters()

    def init_match(self):
        self.score=0; self.wickets=0; self.balls=0; self.innings=1; self.is_chasing=False; self.game_over=False
        self.over_balls = []; self.innings_history = {}; self.runs_this_over = 0; self.fow_list = []
        self.partnership_runs = 0
        self.partnership_balls = 0

    def get_skill(self, name, role, idx=0):
        if role == 'bat':
            if idx < 3: return random.randint(85, 95)
            elif idx < 6: return random.randint(75, 85)
            elif idx < 8: return random.randint(60, 75)
            else: return random.randint(15, 40)
        elif role == 'bowl':
            return random.randint(80, 95)

    def setup_rosters(self):
        self.bat_roster = DEFAULT_TEAMS[self.batting_team]["batters"]
        self.bowl_roster = DEFAULT_TEAMS[self.bowling_team]["bowlers"]
        
        self.match_bat_stats = []
        for i, p in enumerate(self.bat_roster):
            skill = self.get_skill(p, 'bat', i)
            self.match_bat_stats.append({'name':p, 'r':0, 'b':0, '4s':0, '6s':0, 'is_out':False, 'skill': skill, 'dismissal': "not out"})
            
        self.striker = self.match_bat_stats[0]
        self.non_striker = self.match_bat_stats[1]
        self.next_bat_idx = 2
        
        self.match_bowlers = {}
        for p in self.bowl_roster:
            skill = self.get_skill(p, 'bowl')
            self.match_bowlers[p] = {'name':p, 'r':0, 'w':0, 'b':0, 'skill': skill}
            
        self.bowler_idx = 0
        self.current_bowler = self.match_bowlers[self.bowl_roster[0]]

    def handle_wicket(self):
        self.striker['b'] += 1; self.striker['is_out'] = True; self.wickets += 1
        self.current_bowler['w'] += 1; self.current_bowler['b'] += 1
        self.fow_list.append({'w': self.wickets, 'r': self.score, 'p': self.striker['name']})
        
        self.data_mgr.check_partnership(self.match_format, self.partnership_runs, self.striker['name'], self.non_striker['name'])
        self.partnership_runs = 0; self.partnership_balls = 0
        
        gs = self.root.get_screen('game')
        if gs.auto_active and self.batting_team == self.user_team: gs.stop_auto_play()

        if self.batting_team == self.user_team and self.wickets < 10:
            gs.open_batsman_selection()
            return

        if self.next_bat_idx < len(self.match_bat_stats):
            self.striker = self.match_bat_stats[self.next_bat_idx]; self.next_bat_idx += 1
        else:
            if self.innings == 1: self.swap_innings()
            else: self.end_game(False)

    def generate_simulated_innings(self, team, total_score, wickets, overs_limit, opp_team):
        roster = DEFAULT_TEAMS[team]['batters']
        bowl_roster = DEFAULT_TEAMS[opp_team]['bowlers']
        
        bat_stats = []
        remaining_runs = total_score

        for i, p_name in enumerate(roster):
            if i >= wickets + 2: 
                bat_stats.append({'name':p_name, 'r':0, 'b':0, '4s':0, '6s':0, 'is_out':False})
                continue
            share = random.uniform(0.1, 0.3) if i < 3 else random.uniform(0.0, 0.15)
            runs = int(total_score * share)
            runs = min(remaining_runs, max(0, runs + random.randint(-5, 10)))
            sr = random.randint(110, 160) if overs_limit == 20 else random.randint(75, 120)
            balls = int((runs / sr) * 100) if runs > 0 else random.randint(1,4)
            bat_stats.append({'name':p_name, 'r':runs, 'b':balls, '4s':runs//7, '6s':runs//18, 'is_out':(i < wickets)})
            remaining_runs -= runs

        active_bowlers = bowl_roster[:6]
        balls_bowled = {b: 0 for b in active_bowlers}
        
        overs_to_assign = overs_limit
        max_quota = overs_limit // 5
        
        while overs_to_assign > 0:
            candidates = [b for b in active_bowlers if balls_bowled[b] < (max_quota * 6)]
            if not candidates: break
            chosen = random.choice(candidates)
            balls_bowled[chosen] += 6
            overs_to_assign -= 1

        eco_factors = {b: random.uniform(0.75, 1.25) for b in active_bowlers}
        run_shares = {}
        total_share_weight = 0
        
        for b in active_bowlers:
            w = balls_bowled[b] * eco_factors[b]
            run_shares[b] = w
            total_share_weight += w
            
        wicket_counts = {b: 0 for b in active_bowlers}
        if wickets > 0:
            candidates = [b for b in active_bowlers if balls_bowled[b] > 0]
            if candidates:
                weights = [balls_bowled[b] for b in candidates]
                for _ in range(wickets):
                    chosen = random.choices(candidates, weights=weights, k=1)[0]
                    wicket_counts[chosen] += 1

        bowl_stats = []
        for b in active_bowlers:
            my_runs = int(total_score * (run_shares[b] / total_share_weight)) if total_share_weight > 0 else 0
            bowl_stats.append({'name': b, 'b': balls_bowled[b], 'r': my_runs, 'w': wicket_counts[b]})
            
        return {'team': team, 'score': total_score, 'w': wickets, 'bat': bat_stats, 'bowl': bowl_stats, 'fow': []}

    def calculate_mom(self, bat_stats, bowl_stats):
        best_name, best_pts = "N/A", -1
        for p in bat_stats:
            pts = p.get('r', 0) + (p.get('4s', 0)*2) + (p.get('6s', 0)*4)
            if pts > best_pts: best_pts = pts; best_name = p['name']
        for b in bowl_stats:
            pts = b.get('w', 0) * 25
            if pts > best_pts: best_pts = pts; best_name = b['name']
        return best_name

    def handle_runs(self, r):
        self.score += r; self.striker['r'] += r; self.striker['b'] += 1
        self.partnership_runs += r
        self.partnership_balls += 1
        self.runs_this_over += r
        
        if r==4: self.striker['4s']+=1
        elif r==6: self.striker['6s']+=1
        self.current_bowler['r'] += r; self.current_bowler['b'] += 1
        self.data_mgr.check_records(self.match_format, self.striker['name'], self.striker['r'], self.striker['b'])

    def swap_strikers(self): self.striker, self.non_striker = self.non_striker, self.striker

    def rotate_bowler(self):
        max_balls = 24 if self.match_format == 't20' else 60
        start = self.bowler_idx
        for i in range(1, len(self.bowl_roster)+1):
            idx = (start + i) % len(self.bowl_roster); b = self.match_bowlers[self.bowl_roster[idx]]
            if b['b'] < max_balls: self.bowler_idx = idx; self.current_bowler = b; break

    def check_state(self):
        if self.is_chasing and self.score > self.target: self.end_game(True)
        elif self.balls >= self.overs*6:
            if self.innings == 1: self.swap_innings()
            else: self.end_game(False if self.score < self.target else "TIE")
    
    def swap_innings(self):
        if self.root:
            game_screen = self.root.get_screen('game')
            if game_screen: 
                game_screen.stop_auto_play()

        self.data_mgr.check_partnership(self.match_format, self.partnership_runs, self.striker['name'], self.non_striker['name'])
        self.partnership_runs = 0
        self.partnership_balls = 0

        self.innings_history[1] = {'team': self.batting_team, 'score': self.score, 'w': self.wickets, 'bat': self.match_bat_stats[:], 'bowl': list(self.match_bowlers.values()), 'fow': list(self.fow_list)}
        self.target = self.score; self.score=0; self.wickets=0; self.balls=0; self.innings=2; self.is_chasing=True; self.over_balls = []; self.fow_list = []
        self.batting_team, self.bowling_team = self.bowling_team, self.batting_team; self.setup_rosters()

    def end_game(self, won):
        self.data_mgr.check_partnership(self.match_format, self.partnership_runs, self.striker['name'], self.non_striker['name'])
        self.partnership_runs = 0
        self.partnership_balls = 0
        self.game_over = True
        
        self.innings_history[2] = {
            'team': self.batting_team, 
            'score': self.score, 
            'w': self.wickets, 
            'bat': self.match_bat_stats[:], 
            'bowl': list(self.match_bowlers.values()), 
            'fow': list(self.fow_list)
        }
        
        all_bats = self.innings_history[1]['bat'] + self.innings_history[2]['bat']
        all_bowls = self.innings_history[1]['bowl'] + self.innings_history[2]['bowl']
        mom_name = self.calculate_mom(all_bats, all_bowls)
        
        self.data_mgr.commit_match_stats(self.match_format, all_bats, all_bowls, mom_name)
        self.update_tournament_stats(all_bats, all_bowls)
        
        if hasattr(self, 'apply_xp_gains'):
            self.apply_xp_gains(all_bats, all_bowls)
        
        final_winner = self.batting_team if won == True else self.bowling_team
        loser = self.bowling_team if won == True else self.batting_team
        
        i1 = self.innings_history[1]
        i2 = self.innings_history[2]
        w_score = i2['score'] if i2['team'] == final_winner else i1['score']
        l_score = i1['score'] if i2['team'] == final_winner else i2['score']
        
        is_f = False
        if self.current_match_idx != -1:
            status = self.tournament_data['fixtures'][self.current_match_idx][3]
            is_f = ("FINAL" in str(status) and "SEMI" not in str(status))
            
        self.data_mgr.update_team_stats(self.match_format, final_winner, 'W', w_score, is_final=is_f)
        self.data_mgr.update_team_stats(self.match_format, loser, 'L', l_score)
        
        if self.current_match_idx != -1:
            if "Play" in str(self.tournament_data['fixtures'][self.current_match_idx][3]):
                self.update_points_and_nrr(final_winner, loser, w_score, self.overs, l_score, self.overs)
            
            self.tournament_data['fixtures'][self.current_match_idx][2] = final_winner
            curr_status = self.tournament_data['fixtures'][self.current_match_idx][3]
            
            if "SEMI" not in curr_status and "FINAL" not in curr_status:
                self.tournament_data['fixtures'][self.current_match_idx][3] = "Played"

            self.save_tournament()

        res = self.root.get_screen('result')
        res.res_text = f"{final_winner} WON!" if won != "TIE" else "MATCH TIED!"
        self.root.current = 'result'


if __name__ == '__main__':
    CricketApp().run()
