import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import json
import uuid
import os
from PIL import Image, ImageTk
import pygame

class PokerClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("The Good Poker")
        self.root.geometry("1200x800")
        
        # Network settings
        self.socket = None
        self.connected = False
        self.player_id = str(uuid.uuid4())
        self.player_name = ""
        
        # Game state
        self.game_data = {}
        
        # Image, Audio, and UI state
        self.card_images = {}
        self.backgrounds = {}
        self.card_back_image = None
        self.original_bg_image = None
        self._resize_job = None

        self.initialize_audio()
        self.load_assets() # Metode ini sekarang ada dan dipanggil dari sini
        
        self.player_widgets = {}
        
        self.setup_views()
        self.switch_view("login")
        
        self.root.bind('<Configure>', self.on_window_resize)

    def initialize_audio(self):
        """Mempersiapkan pygame mixer dan memuat file audio."""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load("assets/background_music.mp3")
            pygame.mixer.music.set_volume(0.3)
            self.button_sound = pygame.mixer.Sound("assets/button_click.mp3")
            self.chip_sound = pygame.mixer.Sound("assets/chip_sound.mp3")
            self.check_sound = pygame.mixer.Sound("assets/check_sound.mp3")
            self.win_sound = pygame.mixer.Sound("assets/win_sound.mp3")
        except Exception as e:
            print(f"Gagal memuat audio: {e}")
            self.button_sound = self.chip_sound = self.check_sound = self.win_sound = None

    def load_assets(self):
        """Memuat semua aset gambar (backgrounds dan kartu) secara sistematis."""
        try:
            self.backgrounds['login'] = Image.open("assets/login_background.png")
            self.backgrounds['gameplay'] = Image.open("assets/gameplay_background.png")
            self.backgrounds['winner'] = Image.open("assets/winner_background.png")
        except Exception as e:
            messagebox.showerror("Asset Error", f"Gagal memuat gambar background: {e}")
            self.root.quit()
            return

        cards_folder = "assets/cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", "Folder 'assets/cards' tidak ditemukan!")
            return

        suits = ['club', 'diamond', 'heart', 'spade']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
        new_size = (80, 112)

        for suit in suits:
            for rank in ranks:
                filename = f"{suit}_{rank}.jpg"
                filepath = os.path.join(cards_folder, filename)
                try:
                    if os.path.exists(filepath):
                        img = Image.open(filepath).resize(new_size, Image.Resampling.LANCZOS)
                        self.card_images[filename.lower()] = ImageTk.PhotoImage(img)
                    else:
                        print(f"Peringatan: File kartu tidak ditemukan - {filepath}")
                except Exception as e:
                    print(f"Error memuat file {filename}: {e}")

        card_back_filename = "card_back.jpg" 
        card_back_path = os.path.join(cards_folder, card_back_filename)
        try:
            if os.path.exists(card_back_path):
                img = Image.open(card_back_path).resize(new_size, Image.Resampling.LANCZOS)
                photo_img = ImageTk.PhotoImage(img)
                self.card_back_image = photo_img
                self.card_images[card_back_filename] = photo_img
            else:
                messagebox.showerror("Asset Error", f"File kartu belakang '{card_back_filename}' tidak ditemukan!")
        except Exception as e:
            messagebox.showerror("Asset Error", f"Gagal memuat kartu belakang '{card_back_filename}': {e}")


    def play_sfx(self, sound_object):
        """Memainkan sound effect jika ada."""
        if sound_object:
            sound_object.play()

    def on_window_resize(self, event):
        """Menerima event resize dan menjadwalkan ulang job resize (debouncing)."""
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self.perform_resize)

    def perform_resize(self):
        """Fungsi yang benar-benar melakukan resize gambar. Dipanggil setelah jeda."""
        if not self.original_bg_image:
            return
        new_width = self.root.winfo_width()
        new_height = self.root.winfo_height()
        resized_img = self.original_bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.background_photo = ImageTk.PhotoImage(resized_img)
        self.bg_label.configure(image=self.background_photo)

    def setup_views(self):
        """Mempersiapkan semua 'layar' atau 'view' untuk aplikasi."""
        self.main_bg_label = tk.Label(self.root, borderwidth=0)
        self.main_bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # --- View 1: Login ---
        self.login_frame = tk.Frame(self.root)
        tk.Label(self.login_frame, text="Server IP:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(20, 2))
        self.ip_entry = tk.Entry(self.login_frame, font=('Arial', 12), justify='center')
        self.ip_entry.insert(0, "localhost")
        self.ip_entry.pack(pady=5)
        tk.Label(self.login_frame, text="Your Name:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        self.name_entry = tk.Entry(self.login_frame, font=('Arial', 12), justify='center')
        self.name_entry.pack(pady=5)
        tk.Button(self.login_frame, text="Connect", command=self.connect_action, bg='#2C2C2C', fg='white', font=('Arial', 12), padx=20, pady=5).pack(pady=20)

        # --- View 2: Gameplay ---
        self.gameplay_frame = tk.Frame(self.root)
        self.pot_label = tk.Label(self.gameplay_frame, text="Pot: $0", bg='#1C1C1C', fg='white', font=('Arial', 16, 'bold'))
        self.pot_label.place(relx=0.5, rely=0.05, anchor='center')
        self.game_state_label = tk.Label(self.gameplay_frame, text="Waiting...", bg='#1C1C1C', fg='white', font=('Arial', 12))
        self.game_state_label.place(relx=0.5, rely=0.1, anchor='center')
        community_bg_frame = tk.Frame(self.gameplay_frame, bg='black', bd=2, relief=tk.SOLID)
        community_bg_frame.place(relx=0.5, rely=0.45, anchor='center')
        self.community_cards_frame = tk.Frame(community_bg_frame, bg='black')
        self.community_cards_frame.pack(expand=True, padx=5, pady=5)
        actions_frame = tk.Frame(self.gameplay_frame, bg='black', bd=0)
        actions_frame.place(relx=0.02, rely=0.98, anchor='sw')
        btn_style = {'font': ('Arial', 10, 'bold'), 'bg': '#D3D3D3', 'fg': 'black', 'width': 8}
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, **btn_style, state=tk.DISABLED)
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, **btn_style, state=tk.DISABLED)
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, **btn_style, state=tk.DISABLED)
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, **btn_style, state=tk.DISABLED)
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, **btn_style, state=tk.DISABLED)
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]: btn.pack(side=tk.LEFT, padx=5, pady=5)
        my_player_area_frame = tk.Frame(self.gameplay_frame, bg='#111111', bd=1, relief=tk.SOLID)
        my_player_area_frame.place(relx=0.98, rely=0.98, anchor='se')
        my_info_frame = tk.Frame(my_player_area_frame, bg='#111111')
        my_info_frame.pack(pady=5, padx=10, anchor='w')
        self.my_name_label = tk.Label(my_info_frame, text="Player:", bg='#111111', fg='white', font=('Arial', 12, 'bold'))
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", bg='#111111', fg='white', font=('Arial', 11))
        self.my_bet_label = tk.Label(my_info_frame, text="Bet: $0", bg='#111111', fg='yellow', font=('Arial', 11))
        for label in [self.my_name_label, self.my_chips_label, self.my_bet_label]: label.pack(anchor='w')
        self.my_cards_display_frame = tk.Frame(my_player_area_frame, bg='#111111')
        self.my_cards_display_frame.pack(pady=5, padx=10, anchor='w')
        self.opponents_display_frame = tk.Frame(self.gameplay_frame, bg="black")
        self.opponents_display_frame.place(relx=0.02, rely=0.02, anchor='nw')
        self.start_btn = tk.Button(self.gameplay_frame, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 14, 'bold'))
        self.showdown_button = tk.Button(self.gameplay_frame, text="SHOW YOUR CARDS", command=self.showdown_action, bg='gold', fg='black', font=('Arial', 16, 'bold'))

        # --- View 3: Winner ---
        self.winner_frame = tk.Frame(self.root)
        self.winner_info_label = tk.Label(self.winner_frame, text="", font=('Arial', 24, 'bold'), fg='white', bg='#111111', justify='center')
        self.winner_info_label.pack(expand=True)

    def switch_view(self, view_name):
        """Menyembunyikan semua view dan menampilkan yang dipilih."""
        self.login_frame.place_forget()
        self.gameplay_frame.place_forget()
        self.winner_frame.place_forget()

        if view_name in self.backgrounds:
            self.original_bg_image = self.backgrounds[view_name]
            self.perform_resize()
        
        target_frame = getattr(self, f"{view_name}_frame", None)
        if target_frame:
            # Set background transparan untuk frame utama agar background root terlihat
            target_frame.config(bg="") 
            for widget in target_frame.winfo_children():
                # Ini trik agar widget di dalam frame bisa transparan
                if isinstance(widget, tk.Frame):
                     widget.config(bg=target_frame.cget('bg'))
            
            if view_name == "login":
                 target_frame.place(relx=0.5, rely=0.5, anchor='center')
            else:
                 target_frame.place(x=0, y=0, relwidth=1, relheight=1)

    def connect_action(self):
        server_ip = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()
        if not server_ip or not name:
            messagebox.showerror("Error", "Please fill in all fields")
            return
        
        self.player_name = name
        self.my_name_label.config(text=f"Player: {self.player_name}")
        if self.connect_to_server(server_ip):
            try:
                pygame.mixer.music.play(loops=-1)
            except Exception as e:
                print(f"Gagal memainkan musik latar: {e}")
            self.switch_view("gameplay")
        else:
            messagebox.showerror("Error", "Failed to connect to server.")

    def connect_to_server(self, server_ip, port=8888):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            threading.Thread(target=self.listen_to_server, daemon=True).start()
            self.send_message({'type': 'join', 'player_id': self.player_id, 'name': self.player_name})
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def listen_to_server(self):
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data: break
                buffer += data
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    if message_str.strip():
                        self.root.after(0, self.handle_server_message, json.loads(message_str))
            except Exception: break
        self.connected = False
        self.root.after(0, self.root.quit)
        
    def handle_server_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'join_success':
            self.switch_view("gameplay")
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
        elif msg_type == 'game_result':
            winners = message.get('winners', [])
            winnings_map = message.get('winnings_map', {})
            if self.player_id in winners:
                self.play_sfx(self.win_sound)
            
            winner_names = [self.game_data['players'][pid]['name'] for pid in winners if pid in self.game_data['players']] if self.game_data else winners
            winnings_info = "\n".join([f"{self.game_data['players'][pid]['name']} wins ${amount}" for pid, amount in winnings_map.items()])
            display_message = f"Winner(s): {', '.join(winner_names)}\n{message.get('winning_hand_type')}\n\n{winnings_info}"
            self.winner_info_label.config(text=display_message)
            self.switch_view('winner')
        elif msg_type in ['join_failed', 'action_failed', 'error']:
            messagebox.showerror(msg_type.replace('_', ' ').title(), message.get('message'))

    def update_game_state(self, game_data):
        if not game_data: return
        self.game_data = game_data
        
        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        state_text = game_data.get('game_state', 'waiting').replace('_', ' ').title()
        if game_data.get('current_player_id') == self.player_id: state_text += " - Your Turn!"
        self.game_state_label.config(text=state_text)
        
        self.update_community_cards(game_data.get('community_cards', []))
        self.update_players(game_data.get('players', {}))
        
        is_my_turn = game_data.get('current_player_id') == self.player_id
        game_is_active = game_data.get('game_state') in ['pre_flop', 'flop', 'turn', 'river']
        self.update_action_buttons(is_my_turn and game_is_active)
        
        if game_data.get('game_state') in ['waiting', 'game_over']:
            self.start_btn.place(relx=0.5, rely=0.6, anchor='center')
        else:
            self.start_btn.place_forget()
        
        if game_data.get('game_state') == 'awaiting_showdown':
            my_data = game_data.get('players', {}).get(self.player_id, {})
            if not my_data.get('is_folded') and not my_data.get('has_revealed'):
                self.showdown_button.place(relx=0.5, rely=0.8, anchor='center')
            else:
                self.showdown_button.place_forget()
        else:
            self.showdown_button.place_forget()
            
    def update_community_cards(self, cards):
        for widget in self.community_cards_frame.winfo_children(): widget.destroy()
        for card_data in cards:
            img = self.card_images.get(card_data['image'].lower())
            if img: tk.Label(self.community_cards_frame, image=img, bg='black').pack(side=tk.LEFT, padx=3)
        for _ in range(len(cards), 5):
            if self.card_back_image: tk.Label(self.community_cards_frame, image=self.card_back_image, bg='black').pack(side=tk.LEFT, padx=3)
    
    def update_players(self, players_data):
        if self.player_id in players_data:
            my_data = players_data[self.player_id]
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Bet: ${my_data.get('current_bet', 0)}")
            for widget in self.my_cards_display_frame.winfo_children(): widget.destroy()
            for card_data in my_data.get('cards', []):
                img = self.card_images.get(card_data['image'].lower())
                if img: tk.Label(self.my_cards_display_frame, image=img, bg='#111111').pack(side=tk.LEFT, padx=2)
        
        for widget in self.opponents_display_frame.winfo_children(): widget.destroy()
        for pid, p_data in players_data.items():
            if pid == self.player_id: continue
            frame = tk.Frame(self.opponents_display_frame, bg='#111111', bd=1, relief=tk.SOLID)
            frame.pack(pady=4, padx=5, anchor='nw')
            name_text = p_data.get('name', '') + (" (D)" if pid == self.game_data.get('dealer_player_id') else "")
            tk.Label(frame, text=name_text, bg='#111111', fg='white', font=('Arial', 9, 'bold')).pack(anchor='w', padx=5)
            tk.Label(frame, text=f"Chips: ${p_data.get('chips',0)}", bg='#111111', fg='white', font=('Arial', 8)).pack(anchor='w', padx=5)
            cards_frame = tk.Frame(frame, bg='#111111')
            cards_frame.pack(anchor='w', padx=5, pady=(2,5))
            for card_data in p_data.get('cards', []):
                img = self.card_images.get(card_data.get('image').lower())
                if img: tk.Label(cards_frame, image=img, bg='#111111').pack(side=tk.LEFT)

    def update_action_buttons(self, can_act):
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.config(state=tk.DISABLED)
        if not can_act: return
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data or my_data.get('is_folded') or my_data.get('is_all_in'): return
        current_bet, my_bet, my_chips = self.game_data.get('current_bet', 0), my_data.get('current_bet', 0), my_data.get('chips', 0)
        self.fold_btn.config(state=tk.NORMAL)
        if my_chips > 0: self.all_in_btn.config(state=tk.NORMAL)
        if current_bet > my_bet: self.call_btn.config(state=tk.NORMAL)
        else: self.check_btn.config(state=tk.NORMAL)
        if my_chips > (current_bet - my_bet): self.raise_btn.config(state=tk.NORMAL)

    def send_message(self, message_data):
        if not self.connected: return
        try:
            self.socket.send((json.dumps(message_data) + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Send message error: {e}")

    def fold_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'player_id': self.player_id, 'action': 'fold'})
    def check_action(self): self.play_sfx(self.check_sound); self.send_message({'type': 'action', 'player_id': self.player_id, 'action': 'check'})
    def all_in_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'player_id': self.player_id, 'action': 'all_in'})
    def call_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'player_id': self.player_id, 'action': 'call'})
    def raise_action(self): 
        self.play_sfx(self.chip_sound)
        amount = simpledialog.askinteger("Raise", "Raise to:", parent=self.root)
        if amount: self.send_message({'type': 'action', 'player_id': self.player_id, 'action': 'raise', 'amount': amount})
    
    def showdown_action(self):
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'reveal_cards', 'player_id': self.player_id})
        self.showdown_button.place_forget()

    def start_game(self):
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'start_game', 'player_id': self.player_id})

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt: pass
        finally:
            if self.connected: self.socket.close()
            pygame.quit()

if __name__ == '__main__':
    client = PokerClient()
    client.run()