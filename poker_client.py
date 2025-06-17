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
        self.root.title("Texas Hold'em Poker")
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
        self.card_back_image = None
        self.original_bg_image = None
        self._resize_job = None

        self.initialize_audio()
        self.load_card_images()
        
        self.player_widgets = {}
        
        self.setup_ui()
        self.setup_connection_dialog()
        
        self.root.bind('<Configure>', self.on_window_resize)

    def initialize_audio(self):
        """Mempersiapkan pygame mixer dan memuat file audio."""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load("assets/background_music.mp3")
            pygame.mixer.music.set_volume(0.3)
            
            # Memuat semua sound effects
            self.button_sound = pygame.mixer.Sound("assets/button_click.mp3")
            self.chip_sound = pygame.mixer.Sound("assets/chip_sound.mp3")
            self.check_sound = pygame.mixer.Sound("assets/check_sound.mp3")
            self.win_sound = pygame.mixer.Sound("assets/win_sound.mp3")
            
            print("Audio berhasil diinisialisasi.")
        except Exception as e:
            print(f"Loading audio {e} failed. Audio will not be available.")
            self.button_sound = self.chip_sound = self.check_sound = self.win_sound = None

    def play_sfx(self, sound_object):
        """Memainkan sound effect jika ada."""
        if sound_object:
            sound_object.play()

    def on_window_resize(self, event):
        """Secara dinamis mengubah ukuran gambar latar belakang saat ukuran jendela berubah."""
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

    def load_card_images(self):
        """Memuat semua gambar kartu dari folder cards."""
        cards_folder = "assets/cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", "Folder 'assets/cards' tidak ditemukan!")
            return
        
        try:
            new_size = (80, 112)
            back_path = os.path.join(cards_folder, "card_back.jpg")
            if os.path.exists(back_path):
                img = Image.open(back_path).resize(new_size, Image.Resampling.LANCZOS)
                self.card_back_image = ImageTk.PhotoImage(img)
                self.card_images['back_design.jpg'] = self.card_back_image
            
            suits = ['club', 'diamond', 'heart', 'spade']
            ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
            
            for suit in suits:
                for rank in ranks:
                    filename = f"{suit}_{rank}.jpg"
                    filepath = os.path.join(cards_folder, filename)
                    if os.path.exists(filepath):
                        img = Image.open(filepath).resize(new_size, Image.Resampling.LANCZOS)
                        self.card_images[filename] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading card images: {e}")

    def setup_connection_dialog(self):
        """Menampilkan dialog koneksi dengan background kustom."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Poker Game")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.root.quit())

        try:
            bg_path = os.path.join("assets", "dialog_background.png")
            img = Image.open(bg_path).resize((400, 250), Image.Resampling.LANCZOS)
            dialog.bg_image = ImageTk.PhotoImage(img)
            tk.Label(dialog, image=dialog.bg_image, borderwidth=0).place(x=0, y=0)
        except Exception as e:
            print(f"Gagal memuat background dialog: {e}")
            dialog.configure(bg='#C70300')

        tk.Label(dialog, text="Server IP:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(20, 2))
        ip_entry = tk.Entry(dialog, font=('Arial', 12), justify='center')
        ip_entry.insert(0, "localhost")
        ip_entry.pack(pady=5)
        
        tk.Label(dialog, text="Your Name:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        name_entry = tk.Entry(dialog, font=('Arial', 12), justify='center')
        name_entry.pack(pady=5)
        
        def connect():
            server_ip = ip_entry.get().strip()
            name = name_entry.get().strip()
            if not server_ip or not name:
                messagebox.showerror("Error", "Please fill in all fields", parent=dialog)
                return
            
            self.player_name = name
            if self.connect_to_server(server_ip):
                try:
                    pygame.mixer.music.play(loops=-1)
                except Exception as e:
                    print(f"Gagal memainkan musik latar: {e}")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to connect to server.", parent=dialog)
        
        tk.Button(dialog, text="Connect", command=connect, bg='#2C2C2C', fg='white', font=('Arial', 12), padx=20, pady=5).pack(pady=20)

    def show_custom_winner_dialog(self, message):
        """Menampilkan dialog pemenang dengan background kustom."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Game Result")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.transient(self.root)

        try:
            bg_path = os.path.join("assets", "dialog_background.png")
            img = Image.open(bg_path).resize((500, 300), Image.Resampling.LANCZOS)
            dialog.bg_image = ImageTk.PhotoImage(img)
            tk.Label(dialog, image=dialog.bg_image, borderwidth=0).place(x=0, y=0)
        except Exception:
            dialog.configure(bg='black')
        
        tk.Label(dialog, text=message, font=('Arial', 14, 'bold'), fg='white', bg='#333333', justify='center', wraplength=450).pack(expand=True, pady=20, padx=20)
        tk.Button(dialog, text="OK", command=dialog.destroy, font=('Arial', 12, 'bold'), width=10).pack(pady=(0, 20))

    def setup_ui(self):
        """Mempersiapkan UI utama game."""
        try:
            bg_image_path = os.path.join("assets", "background.png")
            self.original_bg_image = Image.open(bg_image_path)
            resized_img = self.original_bg_image.resize((1200, 800), Image.Resampling.LANCZOS)
            self.background_photo = ImageTk.PhotoImage(resized_img)
            self.bg_label = tk.Label(self.root, image=self.background_photo, borderwidth=0)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except FileNotFoundError:
            self.root.configure(bg='black')

        self.pot_label = tk.Label(self.root, text="Pot: $0", bg='#1C1C1C', fg='white', font=('Arial', 16, 'bold'))
        self.pot_label.place(relx=0.5, rely=0.05, anchor='center')
        self.game_state_label = tk.Label(self.root, text="Waiting...", bg='#1C1C1C', fg='white', font=('Arial', 12))
        self.game_state_label.place(relx=0.5, rely=0.1, anchor='center')
        
        community_bg_frame = tk.Frame(self.root, bg='black', bd=2, relief=tk.SOLID)
        community_bg_frame.place(relx=0.5, rely=0.45, anchor='center')
        self.community_cards_frame = tk.Frame(community_bg_frame, bg='black')
        self.community_cards_frame.pack(expand=True, padx=5, pady=5)
        
        actions_frame = tk.Frame(self.root, bg='black', bd=0)
        actions_frame.place(relx=0.02, rely=0.98, anchor='sw')
        btn_style = {'font': ('Arial', 10, 'bold'), 'bg': '#D3D3D3', 'fg': 'black', 'width': 8}
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, **btn_style, state=tk.DISABLED)
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, **btn_style, state=tk.DISABLED)
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, **btn_style, state=tk.DISABLED)
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, **btn_style, state=tk.DISABLED)
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, **btn_style, state=tk.DISABLED)
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        my_player_area_frame = tk.Frame(self.root, bg='#111111', bd=1, relief=tk.SOLID)
        my_player_area_frame.place(relx=0.98, rely=0.98, anchor='se')
        my_info_frame = tk.Frame(my_player_area_frame, bg='#111111')
        my_info_frame.pack(pady=5, padx=10, anchor='w')
        self.my_name_label = tk.Label(my_info_frame, text="Player:", bg='#111111', fg='white', font=('Arial', 12, 'bold'))
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", bg='#111111', fg='white', font=('Arial', 11))
        self.my_bet_label = tk.Label(my_info_frame, text="Bet: $0", bg='#111111', fg='yellow', font=('Arial', 11))
        for label in [self.my_name_label, self.my_chips_label, self.my_bet_label]: label.pack(anchor='w')
        self.my_cards_display_frame = tk.Frame(my_player_area_frame, bg='#111111')
        self.my_cards_display_frame.pack(pady=5, padx=10, anchor='w')

        self.opponents_display_frame = tk.Frame(self.root, bg="black")
        self.opponents_display_frame.place(relx=0.02, rely=0.02, anchor='nw')
        
        self.start_btn = tk.Button(self.root, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 14, 'bold'))

    def connect_to_server(self, server_ip, port=8888):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            threading.Thread(target=self.listen_to_server, daemon=True).start()
            join_message = {'type': 'join', 'player_id': self.player_id, 'name': self.player_name}
            self.socket.send(json.dumps(join_message).encode('utf-8') + b'\n')
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
            self.my_name_label.config(text=f"Player: {self.player_name}")
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
        elif msg_type == 'game_result':
            winners = message.get('winners', [])
            if self.player_id in winners:
                self.play_sfx(self.win_sound)
            
            winner_names = [self.game_data['players'][pid]['name'] for pid in winners if pid in self.game_data.get('players', {})]
            display_message = message.get('message', 'Game Over')
            if winner_names:
                display_message += f"\nHand: {message.get('winning_hand_type')}"
            
            self.show_custom_winner_dialog(display_message)
        elif msg_type == 'action_failed':
             messagebox.showwarning("Action Failed", message.get('message'))
        elif msg_type == 'error':
            messagebox.showerror("Server Error", message.get('message'))


    def update_game_state(self, game_data):
        if not game_data: return
        self.game_data = game_data
        
        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        state_text = game_data.get('game_state', 'waiting').replace('_', ' ').title()
        if game_data.get('current_player_id') == self.player_id:
            state_text += " - Your Turn!"
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
            
    def update_community_cards(self, cards):
        for widget in self.community_cards_frame.winfo_children(): widget.destroy()
        for card_data in cards:
            img = self.card_images.get(card_data['image'])
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
                img = self.card_images.get(card_data['image'])
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
                img = self.card_images.get(card_data.get('image'))
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
        if current_bet > my_bet:
            self.call_btn.config(state=tk.NORMAL)
        else:
            self.check_btn.config(state=tk.NORMAL)
        if my_chips > (current_bet - my_bet):
            self.raise_btn.config(state=tk.NORMAL)

    def send_action(self, action, amount=0):
        if not self.connected: return
        try:
            self.socket.send(json.dumps({'type': 'action', 'player_id': self.player_id, 'action': action, 'amount': amount}).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Send action error: {e}")

    def fold_action(self): 
        self.play_sfx(self.button_sound)
        self.send_action('fold')

    def check_action(self):
        self.play_sfx(self.check_sound)
        self.send_action('check')

    def all_in_action(self):
        self.play_sfx(self.chip_sound)
        self.send_action('all_in')

    def call_action(self): 
        self.play_sfx(self.chip_sound)
        self.send_action('call')
    
    def raise_action(self): 
        self.play_sfx(self.chip_sound)
        amount = simpledialog.askinteger("Raise", "Raise to:", parent=self.root)
        if amount: self.send_action('raise', amount)
    
    def start_game(self):
        self.play_sfx(self.button_sound)
        if not self.connected: return
        try:
            self.socket.send(json.dumps({'type': 'start_game', 'player_id': self.player_id}).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Start game error: {e}")

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            if self.connected: self.socket.close()
            pygame.quit()

if __name__ == '__main__':
    client = PokerClient()
    client.run()