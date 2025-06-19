import tkinter as tk
from tkinter import messagebox, simpledialog
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
        
        # UI State
        self.card_images = {}
        self.raw_backgrounds = {}
        self.photo_backgrounds = {}
        self.card_back_image = None
        self.view_frames = {}
        self.current_view_name = None
        self._resize_job = None

        self.initialize_audio()
        self.load_assets()
        self.setup_views()
        self.switch_view("login")
        
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def initialize_audio(self):
        """Initializes the pygame mixer and loads audio files."""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load("assets/background_music.mp3")
            pygame.mixer.music.set_volume(0.3)
            self.button_sound = pygame.mixer.Sound("assets/button_click.mp3")
            self.chip_sound = pygame.mixer.Sound("assets/chip_sound.mp3")
            self.check_sound = pygame.mixer.Sound("assets/check_sound.mp3")
            self.win_sound = pygame.mixer.Sound("assets/win_sound.mp3")
        except Exception as e:
            print(f"Failed to load audio: {e}")
            self.button_sound = self.chip_sound = self.check_sound = self.win_sound = None

    def load_assets(self):
        """Loads all image assets (backgrounds and cards)."""
        try:
            self.raw_backgrounds['login'] = Image.open("assets/login_background.png")
            self.raw_backgrounds['gameplay'] = Image.open("assets/gameplay_background.png")
            self.raw_backgrounds['winner'] = Image.open("assets/winner_background.png")
        except Exception as e:
            messagebox.showerror("Asset Error", f"Failed to load background images: {e}")
            self.root.quit()
            return

        cards_folder = "assets/cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", f"Folder '{cards_folder}' not found!")
            return

        suits = ['club', 'diamond', 'heart', 'spade']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
        new_size = (80, 112)

        for suit in suits:
            for rank in ranks:
                filename = f"{suit}_{rank}.jpg"
                filepath = os.path.join(cards_folder, filename)
                try:
                    img = Image.open(filepath).resize(new_size, Image.Resampling.LANCZOS)
                    self.card_images[filename.lower()] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"Warning: Could not load card {filename}: {e}")

        try:
            card_back_path = os.path.join(cards_folder, "card_back.jpg")
            img = Image.open(card_back_path).resize(new_size, Image.Resampling.LANCZOS)
            self.card_back_image = ImageTk.PhotoImage(img)
            self.card_images["card_back.jpg"] = self.card_back_image
        except Exception as e:
            messagebox.showerror("Asset Error", f"Failed to load card_back.jpg: {e}")

    def play_sfx(self, sound_object):
        if sound_object:
            sound_object.play()

    def on_window_resize(self, event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self.perform_resize)

    def perform_resize(self):
        """Resizes the background for the currently active view."""
        if not self.current_view_name or self.current_view_name not in self.raw_backgrounds:
            return

        view_frame = self.view_frames[self.current_view_name]
        bg_label = view_frame.nametowidget("bg_label")
        raw_bg_image = self.raw_backgrounds[self.current_view_name]
        
        new_width = self.root.winfo_width()
        new_height = self.root.winfo_height()
        resized_img = raw_bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        self.photo_backgrounds[self.current_view_name] = ImageTk.PhotoImage(resized_img)
        bg_label.configure(image=self.photo_backgrounds[self.current_view_name])

    def setup_views(self):
        """Sets up all application 'views' as self-contained frames."""
        
        # --- Login View ---
        login_frame = tk.Frame(self.root, name="login_view")
        self.view_frames['login'] = login_frame
        tk.Label(login_frame, name="bg_label").place(x=0, y=0, relwidth=1, relheight=1)

        content_container = tk.Frame(login_frame, bg='#6A0B0A')
        content_container.place(relx=0.5, rely=0.5, anchor='center')
        
        tk.Label(content_container, text="Server IP:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(20, 2), padx=40)
        self.ip_entry = tk.Entry(content_container, font=('Arial', 12), justify='center')
        self.ip_entry.insert(0, "localhost")
        self.ip_entry.pack(pady=5, padx=10)
        tk.Label(content_container, text="Your Name:", bg='#6A0B0A', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        self.name_entry = tk.Entry(content_container, font=('Arial', 12), justify='center')
        self.name_entry.pack(pady=5, padx=10)
        tk.Button(content_container, text="Connect", command=self.connect_action, bg='#2C2C2C', fg='white', font=('Arial', 12), padx=20, pady=5).pack(pady=20)

        # --- Gameplay View ---
        gameplay_frame = tk.Frame(self.root, name="gameplay_view")
        self.view_frames['gameplay'] = gameplay_frame
        tk.Label(gameplay_frame, name="bg_label").place(x=0, y=0, relwidth=1, relheight=1)

        self.pot_label = tk.Label(gameplay_frame, text="Pot: $0", bg='#1C1C1C', fg='white', font=('Arial', 16, 'bold'))
        self.pot_label.place(relx=0.5, rely=0.05, anchor='center')
        self.game_state_label = tk.Label(gameplay_frame, text="Waiting...", bg='#1C1C1C', fg='white', font=('Arial', 12), wraplength=400)
        self.game_state_label.place(relx=0.5, rely=0.1, anchor='center')

        community_bg_frame = tk.Frame(gameplay_frame, bg='black', bd=2, relief=tk.SOLID)
        community_bg_frame.place(relx=0.5, rely=0.45, anchor='center')
        self.community_cards_frame = tk.Frame(community_bg_frame, bg='black')
        self.community_cards_frame.pack(expand=True, padx=5, pady=5)

        actions_frame = tk.Frame(gameplay_frame, bg='black', bd=0)
        actions_frame.place(relx=0.02, rely=0.98, anchor='sw')
        btn_style = {'font': ('Arial', 10, 'bold'), 'bg': '#D3D3D3', 'fg': 'black', 'width': 10}
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, state=tk.DISABLED, **btn_style)
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, state=tk.DISABLED, **btn_style)
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, state=tk.DISABLED, **btn_style)
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, state=tk.DISABLED, **btn_style)
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, state=tk.DISABLED, **btn_style)
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.pack(side=tk.LEFT, padx=5, pady=5)

        my_player_area_frame = tk.Frame(gameplay_frame, bg='#111111', bd=1, relief=tk.SOLID)
        my_player_area_frame.place(relx=0.98, rely=0.98, anchor='se')
        my_info_frame = tk.Frame(my_player_area_frame, bg='#111111')
        my_info_frame.pack(pady=5, padx=10, anchor='w')
        self.my_name_label = tk.Label(my_info_frame, text="Player:", bg='#111111', fg='white', font=('Arial', 12, 'bold'))
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", bg='#111111', fg='white', font=('Arial', 11))
        self.my_bet_label = tk.Label(my_info_frame, text="Bet: $0", bg='#111111', fg='yellow', font=('Arial', 11))
        self.my_name_label.pack(anchor='w')
        self.my_chips_label.pack(anchor='w')
        self.my_bet_label.pack(anchor='w')
        self.my_cards_display_frame = tk.Frame(my_player_area_frame, bg='#111111')
        self.my_cards_display_frame.pack(pady=5, padx=10, anchor='w')

        self.opponents_display_frame = tk.Frame(gameplay_frame, bg="black", highlightbackground="gold", highlightthickness=1)
        self.opponents_display_frame.place(relx=0.02, rely=0.02, anchor='nw')

        self.start_btn = tk.Button(gameplay_frame, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 14, 'bold'))
        self.showdown_button = tk.Button(gameplay_frame, text="SHOW YOUR CARDS", command=self.showdown_action, bg='gold', fg='black', font=('Arial', 16, 'bold'))

        # --- Winner View ---
        winner_frame = tk.Frame(self.root, name="winner_view")
        self.view_frames['winner'] = winner_frame
        tk.Label(winner_frame, name="bg_label").place(x=0, y=0, relwidth=1, relheight=1)

        self.winner_info_label = tk.Label(winner_frame, text="", font=('Arial', 24, 'bold'), fg='white', bg='#111111', justify='center', wraplength=600)
        self.winner_info_label.place(relx=0.5, rely=0.4, anchor='center')
        self.back_to_table_btn = tk.Button(winner_frame, text="Back to Table", command=lambda: self.switch_view('gameplay'), font=('Arial', 14))
        self.back_to_table_btn.place(relx=0.5, rely=0.8, anchor='center')

    def switch_view(self, view_name):
        """Hides the current view and shows the selected one."""
        if self.current_view_name:
            if old_frame := self.view_frames.get(self.current_view_name):
                old_frame.place_forget()

        if new_frame := self.view_frames.get(view_name):
            self.current_view_name = view_name
            new_frame.place(x=0, y=0, relwidth=1, relheight=1)
            new_frame.tkraise() # Bring the new frame to the top
            self.perform_resize()
        else:
            print(f"Error: View '{view_name}' not found.")

    def connect_action(self):
        """Handles the connect button action."""
        server_ip = self.ip_entry.get().strip()
        name = self.name_entry.get().strip()
        if not server_ip or not name:
            messagebox.showerror("Error", "Please fill in all fields.")
            return
        
        self.player_name = name
        self.my_name_label.config(text=f"Player: {self.player_name}")
        if self.connect_to_server(server_ip):
            if pygame.mixer.get_init():
                pygame.mixer.music.play(loops=-1)
        else:
            messagebox.showerror("Connection Error", "Failed to connect to the server.")

    def connect_to_server(self, server_ip, port=8888):
        """Establishes a connection to the server."""
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
        """Listens for messages from the server in a dedicated thread."""
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
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                print("Connection to the server was lost.")
                self.connected = False
                break
            except Exception as e:
                print(f"Error in listen_to_server: {e}")
                self.connected = False
                break
        
        if not self.connected:
            self.root.after(0, lambda: messagebox.showinfo("Disconnected", "Lost connection to the server."))
            self.root.after(0, self.on_closing)

    def handle_server_message(self, message):
        """Handles messages received from the server on the main GUI thread."""
        msg_type = message.get('type')
        
        if msg_type == 'join_success':
            self.switch_view("gameplay")
            
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
            
        elif msg_type == 'game_result':
            winnings_map = message.get('winnings_map', {})
            winners = message.get('winners', [])
            if self.player_id in winners:
                self.play_sfx(self.win_sound)
            
            winner_names = message.get('message', 'Winner!')
            winning_hand = message.get('winning_hand_type', '')
            winnings_info = "\n".join([f"{self.game_data.get('players', {}).get(pid, {}).get('name', 'Unknown')} wins ${amount}" for pid, amount in winnings_map.items()])
            
            display_message = f"{winner_names}\n({winning_hand})\n\n{winnings_info}"
            self.winner_info_label.config(text=display_message)
            self.switch_view('winner')

        elif msg_type in ['join_failed', 'action_failed', 'error']:
            messagebox.showerror(msg_type.replace('_', ' ').title(), message.get('message'))

    def update_game_state(self, game_data):
        """Updates the entire UI based on new game data from the server."""
        if not game_data: return
        self.game_data = game_data
        
        if game_data.get('game_state') in ['waiting', 'game_over'] and self.current_view_name != 'gameplay':
            self.switch_view('gameplay')

        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        state_text = game_data.get('game_state', 'waiting').replace('_', ' ').title()
        
        current_player_id = game_data.get('current_player_id')
        if current_player_id and game_data['players'].get(current_player_id):
            current_player_name = game_data['players'][current_player_id].get('name', '')
            state_text += f" - Turn: {current_player_name}"
            if current_player_id == self.player_id:
                state_text += " (Your Turn!)"

        self.game_state_label.config(text=state_text)
        
        self.update_community_cards(game_data.get('community_cards', []))
        self.update_players(game_data.get('players', {}))
        
        is_my_turn = game_data.get('current_player_id') == self.player_id
        game_is_active = game_data.get('game_state') in ['pre_flop', 'flop', 'turn', 'river']
        self.update_action_buttons(is_my_turn and game_is_active)
        
        self.start_btn.place_forget()
        if game_data.get('game_state') in ['waiting', 'game_over']:
            self.start_btn.place(relx=0.5, rely=0.6, anchor='center')
        
        self.showdown_button.place_forget()
        if game_data.get('game_state') == 'awaiting_showdown':
            my_data = game_data.get('players', {}).get(self.player_id, {})
            if my_data and not my_data.get('is_folded') and not my_data.get('has_revealed'):
                self.showdown_button.place(relx=0.5, rely=0.8, anchor='center')

    def update_community_cards(self, cards):
        """Updates the community card display."""
        for widget in self.community_cards_frame.winfo_children(): widget.destroy()
        
        card_list = cards or []
        for card_data in card_list:
            if img := self.card_images.get(card_data.get('image', '').lower()): 
                tk.Label(self.community_cards_frame, image=img, bg='black').pack(side=tk.LEFT, padx=3)
        
        for _ in range(5 - len(card_list)):
            if self.card_back_image: 
                tk.Label(self.community_cards_frame, image=self.card_back_image, bg='black').pack(side=tk.LEFT, padx=3)
    
    def update_players(self, players_data):
        """Updates the player info displays for self and opponents."""
        if my_data := players_data.get(self.player_id):
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Bet: ${my_data.get('current_bet', 0)}")
            for widget in self.my_cards_display_frame.winfo_children(): widget.destroy()
            for card_data in my_data.get('cards', []):
                if img := self.card_images.get(card_data['image'].lower()):
                    tk.Label(self.my_cards_display_frame, image=img, bg='#111111').pack(side=tk.LEFT, padx=2)
        
        for widget in self.opponents_display_frame.winfo_children(): widget.destroy()
        
        for pid, p_data in players_data.items():
            if pid == self.player_id: continue
            
            frame_bg = '#3D3D3D' if p_data.get('is_current_player') else '#111111'
            frame = tk.Frame(self.opponents_display_frame, bg=frame_bg, bd=1, relief=tk.SOLID)
            frame.pack(pady=4, padx=5, anchor='nw', fill='x')

            status_text = " (Folded)" if p_data.get('is_folded') else " (All-In)" if p_data.get('is_all_in') else ""
            name_text = p_data.get('name', '') + (" (Dealer)" if pid == self.game_data.get('dealer_player_id') else "") + status_text
            
            tk.Label(frame, text=name_text, bg=frame_bg, fg='white', font=('Arial', 9, 'bold')).pack(anchor='w', padx=5)
            tk.Label(frame, text=f"Chips: ${p_data.get('chips',0)}", bg=frame_bg, fg='white', font=('Arial', 8)).pack(anchor='w', padx=5)
            if p_data.get('current_bet', 0) > 0:
                 tk.Label(frame, text=f"Bet: ${p_data.get('current_bet',0)}", bg=frame_bg, fg='yellow', font=('Arial', 8)).pack(anchor='w', padx=5)

            cards_frame = tk.Frame(frame, bg=frame_bg)
            cards_frame.pack(anchor='w', padx=5, pady=(2,5))
            for card_data in p_data.get('cards', []):
                img_key = card_data.get('image', 'card_back.jpg').lower()
                if img := self.card_images.get(img_key):
                    tk.Label(cards_frame, image=img, bg=frame_bg).pack(side=tk.LEFT)

    def update_action_buttons(self, can_act):
        """Enables or disables player action buttons based on game state."""
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.config(state=tk.DISABLED)
            
        if not can_act: return
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data or my_data.get('is_folded') or my_data.get('is_all_in'): return
        
        bet_to_match = self.game_data.get('current_bet', 0)
        my_bet = my_data.get('current_bet', 0)
        my_chips = my_data.get('chips', 0)
        
        self.fold_btn.config(state=tk.NORMAL)
        if my_chips > 0: self.all_in_btn.config(state=tk.NORMAL)
        
        if bet_to_match > my_bet:
            call_amount = min(my_chips, bet_to_match - my_bet)
            self.call_btn.config(state=tk.NORMAL, text=f"Call ${call_amount}")
            self.check_btn.config(state=tk.DISABLED)
        else: 
            self.check_btn.config(state=tk.NORMAL)
            self.call_btn.config(state=tk.DISABLED, text="Call")
        
        if my_chips > (bet_to_match - my_bet): 
            self.raise_btn.config(state=tk.NORMAL)
        else:
            self.raise_btn.config(state=tk.DISABLED)

    def send_message(self, message_data):
        """Sends a JSON-formatted message to the server."""
        if not self.connected or not self.socket: return
        try:
            self.socket.sendall((json.dumps(message_data) + '\n').encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"Could not send message, connection lost: {e}")
            self.connected = False
        except Exception as e:
            print(f"Send message error: {e}")

    # --- Action Methods ---
    def fold_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'action': 'fold'})
    def check_action(self): self.play_sfx(self.check_sound); self.send_message({'type': 'action', 'action': 'check'})
    def all_in_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'action': 'all_in'})
    def call_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'action': 'call'})
    
    def raise_action(self): 
        self.play_sfx(self.chip_sound)
        my_data = self.game_data.get('players', {}).get(self.player_id, {})
        my_chips = my_data.get('chips', 0)
        my_current_bet = my_data.get('current_bet', 0)
        current_bet = self.game_data.get('current_bet', 0)
        
        # A raise must be at least the size of the previous bet/raise.
        # For now, we'll simplify and say it must be at least a big blind more.
        min_raise_val = current_bet + self.game_data.get('big_blind', 20)
        max_raise_val = my_chips + my_current_bet

        amount = simpledialog.askinteger("Raise", "Raise to amount:", parent=self.root, initialvalue=min_raise_val, minvalue=min_raise_val, maxvalue=max_raise_val)
        if amount:
            self.send_message({'type': 'action', 'action': 'raise', 'amount': amount})
    
    def showdown_action(self):
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'reveal_cards'})
        self.showdown_button.place_forget()

    def start_game(self):
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'start_game'})

    def on_closing(self):
        """Handles the window closing event."""
        if self.connected:
            self.socket.close()
        self.root.destroy()
        pygame.quit()

    def run(self):
        """Starts the main GUI loop."""
        self.root.mainloop()

if __name__ == '__main__':
    client = PokerClient()
    client.run()