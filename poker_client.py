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
        self.root.title("The Good Poker - Persona Style")
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
            # Main BGM
            pygame.mixer.music.set_volume(0.3)
            
            # Sound Effects
            self.button_sound = pygame.mixer.Sound("assets/button_click.mp3")
            self.chip_sound = pygame.mixer.Sound("assets/chip_sound.mp3")
            self.check_sound = pygame.mixer.Sound("assets/check_sound.mp3")
            self.win_sound = pygame.mixer.Sound("assets/win_sound.mp3")
            self.lose_sound = pygame.mixer.Sound("assets/lose_sound.mp3")
            # --- NEW FEATURE: FOLD SOUND ---
            self.fold_sound = pygame.mixer.Sound("assets/fold_sound.mp3")

        except Exception as e:
            print(f"Failed to load audio: {e}")
            self.button_sound = self.chip_sound = self.check_sound = self.win_sound = self.lose_sound = self.fold_sound = None

    def load_assets(self):
        """Loads all image assets (backgrounds and cards)."""
        try:
            self.raw_backgrounds['login'] = Image.open("assets/login_background.png")
            self.raw_backgrounds['gameplay'] = Image.open("assets/gameplay_background.png") 
            # --- NEW FEATURE: WIN/LOSS SCREENS ---
            self.raw_backgrounds['win_screen'] = Image.open("assets/win_screen.png")
            self.raw_backgrounds['lose_screen'] = Image.open("assets/lose_screen.png")
        except Exception as e:
            messagebox.showerror("Asset Error", f"Failed to load background images. Ensure win_screen.png and lose_screen.png exist. Error: {e}")
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
    
    # --- NEW FEATURE: BGM CONTROL ---
    def play_bgm(self, track_name):
        """Loads and plays a background music track."""
        if not pygame.mixer.get_init(): return
        try:
            pygame.mixer.music.load(f"assets/{track_name}")
            pygame.mixer.music.play(loops=-1)
        except Exception as e:
            print(f"Failed to play BGM '{track_name}': {e}")


    def on_window_resize(self, event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self.perform_resize)

    def perform_resize(self):
        """Resizes the background for the currently active view."""
        if not self.current_view_name or self.current_view_name not in self.raw_backgrounds:
            # Handle dynamic result screen backgrounds
            if self.current_view_name == 'result':
                # The background is set dynamically, just need the image object
                raw_bg_image = self.result_bg_image
            else:
                return
        else:
            raw_bg_image = self.raw_backgrounds[self.current_view_name]

        view_frame = self.view_frames[self.current_view_name]
        bg_label = view_frame.nametowidget("bg_label")
        
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
        # ... (rest of login view setup is unchanged)
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
        
        # ... (most of gameplay setup is unchanged, see below for Raise UI)
        info_frame = tk.Frame(gameplay_frame, bg='#1C1C1C')
        info_frame.place(relx=0.03, rely=0.97, anchor='sw')
        self.pot_label = tk.Label(info_frame, text="Pot: $0", bg='#1C1C1C', fg='white', font=('Arial', 16, 'bold'))
        self.pot_label.pack(pady=(5,0), padx=10, anchor='w')
        self.game_state_label = tk.Label(info_frame, text="Waiting...", bg='#1C1C1C', fg='white', font=('Arial', 10), wraplength=300, justify=tk.LEFT)
        self.game_state_label.pack(pady=(0,5), padx=10, anchor='w')
        community_bg_frame = tk.Frame(gameplay_frame, bg='black', bd=0)
        community_bg_frame.place(relx=0.5, rely=0.5, anchor='center')
        self.community_cards_frame = tk.Frame(community_bg_frame, bg='black')
        self.community_cards_frame.pack(expand=True, padx=5, pady=5)
        actions_frame = tk.Frame(gameplay_frame, bg='white', bd=2, relief=tk.SOLID)
        actions_frame.place(relx=0.97, rely=0.97, anchor='se')
        btn_style = {'font': ('Arial', 14, 'bold'), 'bg': '#2C2C2C', 'fg': 'white'}
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, state=tk.DISABLED, **btn_style)
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, state=tk.DISABLED, **btn_style)
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, state=tk.DISABLED, **btn_style)
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, state=tk.DISABLED, **btn_style)
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, state=tk.DISABLED, **btn_style)
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.pack(side=tk.TOP, fill='x', padx=10, pady=6)
        my_player_area_frame = tk.Frame(gameplay_frame, bg='white', bd=2, relief=tk.SOLID)
        my_player_area_frame.place(relx=0.5, rely=0.97, anchor='s')
        my_info_frame = tk.Frame(my_player_area_frame, bg='white')
        my_info_frame.pack(pady=5, padx=10, fill='x')
        self.my_name_label = tk.Label(my_info_frame, text="Player:", bg='white', fg='black', font=('Arial', 12, 'bold'))
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", bg='white', fg='black', font=('Arial', 11))
        self.my_bet_label = tk.Label(my_info_frame, text="Bet: $0", bg='white', fg='#A9A9A9', font=('Arial', 11, 'italic'))
        self.my_name_label.pack(anchor='center')
        self.my_chips_label.pack(anchor='center')
        self.my_bet_label.pack(anchor='center')
        self.my_cards_display_frame = tk.Frame(my_player_area_frame, bg='white')
        self.my_cards_display_frame.pack(pady=5, padx=10)
        self.opponents_container_frame = tk.Frame(gameplay_frame, bg=None)
        self.opponents_container_frame.place(relx=0.5, rely=0.02, anchor='n')
        self.start_btn = tk.Button(gameplay_frame, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 14, 'bold'))
        self.showdown_button = tk.Button(gameplay_frame, text="SHOW YOUR CARDS", command=self.showdown_action, bg='gold', fg='black', font=('Arial', 16, 'bold'))


        # --- NEW FEATURE: INLINE RAISE UI ---
        self.raise_ui_frame = tk.Frame(gameplay_frame, bg='black', bd=2, relief=tk.RAISED)
        tk.Label(self.raise_ui_frame, text="Select Raise Amount", bg='black', fg='white', font=('Arial', 14, 'bold')).pack(pady=10)
        self.raise_amount_label = tk.Label(self.raise_ui_frame, text="$0", bg='black', fg='yellow', font=('Arial', 16, 'bold'))
        self.raise_amount_label.pack(pady=5)
        self.raise_slider = tk.Scale(self.raise_ui_frame, from_=0, to=1000, orient=tk.HORIZONTAL, length=300,
                                     bg='black', fg='white', troughcolor='#555555', command=self.update_raise_label)
        self.raise_slider.pack(pady=10, padx=20)
        raise_buttons_subframe = tk.Frame(self.raise_ui_frame, bg='black')
        raise_buttons_subframe.pack(pady=10)
        tk.Button(raise_buttons_subframe, text="Confirm", command=self.confirm_raise_action, bg='green', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
        tk.Button(raise_buttons_subframe, text="Cancel", command=self.cancel_raise_action, bg='red', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)


        # --- Result View (formerly Winner View) ---
        result_frame = tk.Frame(self.root, name="result")
        self.view_frames['result'] = result_frame
        tk.Label(result_frame, name="bg_label").place(x=0, y=0, relwidth=1, relheight=1)
        self.result_info_label = tk.Label(result_frame, text="", font=('Arial', 24, 'bold'), fg='white', bg='#111111', justify='center', wraplength=600)
        self.result_info_label.place(relx=0.5, rely=0.4, anchor='center')
        self.back_to_table_btn = tk.Button(result_frame, text="Back to Table", command=self.back_to_gameplay_action, font=('Arial', 14))
        self.back_to_table_btn.place(relx=0.5, rely=0.8, anchor='center')

    def switch_view(self, view_name):
        """Hides the current view and shows the selected one."""
        if self.current_view_name:
            if old_frame := self.view_frames.get(self.current_view_name):
                old_frame.place_forget()

        if new_frame := self.view_frames.get(view_name):
            self.current_view_name = view_name
            new_frame.place(x=0, y=0, relwidth=1, relheight=1)
            new_frame.tkraise()
            if view_name != 'result': # Result screen background is handled dynamically
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
        self.my_name_label.config(text=f"{self.player_name}")
        if self.connect_to_server(server_ip):
            self.play_bgm("background_music.mp3")
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
            # --- NEW FEATURE: DYNAMIC WIN/LOSS SCREEN ---
            is_winner = self.player_id in message.get('winners', [])
            self.show_result_screen(is_winner, message)

        elif msg_type in ['join_failed', 'action_failed', 'error']:
            messagebox.showerror(msg_type.replace('_', ' ').title(), message.get('message'))

    def update_game_state(self, game_data):
        # ... (This function remains mostly the same)
        if not game_data: return
        self.game_data = game_data
        
        if game_data.get('game_state') in ['waiting', 'game_over'] and self.current_view_name != 'gameplay':
            self.switch_view('gameplay')

        state_text = game_data.get('game_state', 'waiting').replace('_', ' ').title()
        
        current_player_id = game_data.get('current_player_id')
        if current_player_id and game_data['players'].get(current_player_id):
            current_player_name = game_data['players'][current_player_id].get('name', '')
            state_text += f"\nTurn: {current_player_name}"
            if current_player_id == self.player_id:
                state_text += " (Your Turn!)"

        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
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
                self.showdown_button.place(relx=0.5, rely=0.75, anchor='center')

    def update_community_cards(self, cards):
        # ... (Unchanged)
        for widget in self.community_cards_frame.winfo_children(): widget.destroy()
        card_list = cards or []
        for card_data in card_list:
            if img := self.card_images.get(card_data.get('image', '').lower()): 
                tk.Label(self.community_cards_frame, image=img, bg='black').pack(side=tk.LEFT, padx=3)
        for _ in range(5 - len(card_list)):
            if self.card_back_image: 
                tk.Label(self.community_cards_frame, image=self.card_back_image, bg='black').pack(side=tk.LEFT, padx=3)
    
    def update_players(self, players_data):
        # ... (Unchanged)
        if my_data := players_data.get(self.player_id):
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Bet: ${my_data.get('current_bet', 0)}")
            for widget in self.my_cards_display_frame.winfo_children(): widget.destroy()
            for card_data in my_data.get('cards', []):
                if img := self.card_images.get(card_data['image'].lower()):
                    tk.Label(self.my_cards_display_frame, image=img, bg='white').pack(side=tk.LEFT, padx=2)
        for widget in self.opponents_container_frame.winfo_children(): widget.destroy()
        for pid, p_data in players_data.items():
            if pid == self.player_id: continue
            frame_bg = '#3D3D3D' if p_data.get('is_current_player') else '#111111'
            frame = tk.Frame(self.opponents_container_frame, bg=frame_bg, bd=1, relief=tk.SOLID)
            frame.pack(side=tk.LEFT, padx=10, pady=5)
            status_text = " (Folded)" if p_data.get('is_folded') else " (All-In)" if p_data.get('is_all_in') else ""
            name_text = p_data.get('name', '') + (" (D)" if pid == self.game_data.get('dealer_player_id') else "") + status_text
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
        # ... (Unchanged)
        all_buttons = [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]
        is_raise_ui_active = self.raise_ui_frame.winfo_viewable()
        
        for btn in all_buttons:
            btn.config(state=tk.DISABLED)
            
        if not can_act or is_raise_ui_active: return

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
        else: 
            self.check_btn.config(state=tk.NORMAL)
        
        if my_chips > (bet_to_match - my_bet): 
            self.raise_btn.config(state=tk.NORMAL)

    def send_message(self, message_data):
        # ... (Unchanged)
        if not self.connected or not self.socket: return
        try:
            self.socket.sendall((json.dumps(message_data) + '\n').encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"Could not send message, connection lost: {e}")
            self.connected = False
        except Exception as e:
            print(f"Send message error: {e}")

    # --- ACTION METHODS ---
    def fold_action(self): 
        # --- NEW FEATURE: FOLD SOUND ---
        self.play_sfx(self.fold_sound)
        self.send_message({'type': 'action', 'action': 'fold'})

    def check_action(self): self.play_sfx(self.check_sound); self.send_message({'type': 'action', 'action': 'check'})
    def all_in_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'action': 'all_in'})
    def call_action(self): self.play_sfx(self.chip_sound); self.send_message({'type': 'action', 'action': 'call'})
    
    # --- NEW FEATURE: INLINE RAISE UI (METHODS) ---
    def raise_action(self):
        """Shows the inline raise UI instead of a popup."""
        self.play_sfx(self.chip_sound)
        my_data = self.game_data.get('players', {}).get(self.player_id, {})
        my_chips = my_data.get('chips', 0)
        my_current_bet = my_data.get('current_bet', 0)
        current_bet = self.game_data.get('current_bet', 0)
        
        # A proper raise must be at least the size of the last bet/raise.
        # Simplified: must be at least one big blind more than the current bet to match.
        min_raise_val = current_bet + self.game_data.get('big_blind', 20)
        max_raise_val = my_chips + my_current_bet

        # Configure and show the slider
        self.raise_slider.config(from_=min_raise_val, to=max_raise_val)
        self.raise_slider.set(min_raise_val)
        self.update_raise_label(min_raise_val)
        self.raise_ui_frame.place(relx=0.5, rely=0.65, anchor='center')
        self.update_action_buttons(False) # Disable main buttons

    def update_raise_label(self, value):
        """Updates the label showing the slider's current value."""
        self.raise_amount_label.config(text=f"${int(float(value))}")

    def confirm_raise_action(self):
        """Confirms the raise and sends it to the server."""
        amount = self.raise_slider.get()
        self.send_message({'type': 'action', 'action': 'raise', 'amount': amount})
        self.raise_ui_frame.place_forget()
        # No need to re-enable buttons, server update will handle it

    def cancel_raise_action(self):
        """Hides the raise UI and restores button states."""
        self.raise_ui_frame.place_forget()
        self.update_action_buttons(True) # Re-enable main buttons
    
    def showdown_action(self): 
        # ... (Unchanged)
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'reveal_cards'})
        self.showdown_button.place_forget()

    def start_game(self): 
        # ... (Unchanged)
        self.play_sfx(self.button_sound)
        self.send_message({'type': 'start_game'})

    def on_closing(self):
        """Handles the window closing event."""
        if self.connected:
            self.socket.close()
        self.root.destroy()
        pygame.quit()

    # --- NEW FEATURE: DYNAMIC RESULT SCREEN & BGM CONTROL ---
    def show_result_screen(self, is_winner, message):
        """Displays the appropriate result screen (win or lose)."""
        if is_winner:
            self.play_bgm("win_music.mp3")
            self.result_bg_image = self.raw_backgrounds['win_screen']
            pygame.mixer.music.stop()
            self.play_sfx(self.win_sound)
        else:
            self.play_bgm("lose_music.mp3")
            self.result_bg_image = self.raw_backgrounds['lose_screen']
            pygame.mixer.music.stop()
            self.play_sfx(self.lose_sound)

        # Format the text
        winner_names = message.get('message', 'Winner!')
        winning_hand = message.get('winning_hand_type', '')
        winnings_map = message.get('winnings_map', {})
        winnings_info = "\n".join([f"{self.game_data.get('players', {}).get(pid, {}).get('name', 'Unknown')} wins ${amount}" for pid, amount in winnings_map.items()])
        display_message = f"{winner_names}\n({winning_hand})\n\n{winnings_info}"
        
        self.result_info_label.config(text=display_message)
        self.switch_view('result')
        self.perform_resize() # Manually trigger resize for the new dynamic bg

    def back_to_gameplay_action(self):
        """Returns to the gameplay screen and restores the main BGM."""
        self.play_bgm("background_music.mp3")
        self.switch_view('gameplay')

    def run(self):
        """Starts the main GUI loop."""
        self.root.mainloop()

if __name__ == '__main__':
    client = PokerClient()
    client.run()
