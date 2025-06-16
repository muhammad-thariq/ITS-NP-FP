import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import json
import uuid
import os
from PIL import Image, ImageTk

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
        self.my_cards = []
        self.community_cards = []
        self.current_player_id = None
        self.dealer_player_id = None
        
        # Card images
        self.card_images = {}
        self.card_back_image = None
        self.load_card_images()
        
        self.player_widgets = {}
        
        self.setup_ui()
        self.setup_connection_dialog()
        
    def load_card_images(self):
        """Load all card images from the cards folder"""
        cards_folder = "assets/cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", "Folder 'assets/cards' tidak ditemukan!")
            return
        
        try:
            # POINT 1: Perbesar ukuran kartu
            new_size = (80, 112)

            back_path = os.path.join(cards_folder, "card_back.jpg")
            if os.path.exists(back_path):
                img = Image.open(back_path)
                img = img.resize(new_size, Image.Resampling.LANCZOS) # Ukuran baru
                self.card_back_image = ImageTk.PhotoImage(img)
                self.card_images['card_back.jpg'] = self.card_back_image
            else:
                print(f"Peringatan: {back_path} tidak ditemukan.")
            
            suits = ['club', 'diamond', 'heart', 'spade']
            ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
            
            for suit in suits:
                for rank in ranks:
                    filename = f"{suit}_{rank}.jpg"
                    filepath = os.path.join(cards_folder, filename)
                    if os.path.exists(filepath):
                        img = Image.open(filepath)
                        img = img.resize(new_size, Image.Resampling.LANCZOS) # Ukuran baru
                        self.card_images[filename] = ImageTk.PhotoImage(img)
                    else:
                        print(f"Peringatan: {filepath} tidak ditemukan.")
                        
        except Exception as e:
            print(f"Error loading card images: {e}")
            messagebox.showwarning("Warning", "Beberapa gambar kartu tidak dapat dimuat.")
    
    def setup_connection_dialog(self):
        """Show connection dialog at startup"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Poker Game")
        dialog.geometry("400x250")
        dialog.grab_set()
        dialog.configure(bg='#0D4F3C')
        
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.root.quit())
        
        tk.Label(dialog, text="Server IP:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        ip_entry = tk.Entry(dialog, font=('Arial', 12))
        ip_entry.insert(0, "localhost")
        ip_entry.pack(pady=5)
        
        tk.Label(dialog, text="Your Name:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        name_entry = tk.Entry(dialog, font=('Arial', 12))
        name_entry.pack(pady=5)
        
        def connect():
            server_ip = ip_entry.get().strip()
            name = name_entry.get().strip()
            
            if not server_ip or not name:
                messagebox.showerror("Error", "Please fill in all fields", parent=dialog)
                return
            
            self.player_name = name
            if self.connect_to_server(server_ip):
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to connect to server. Is the server running?", parent=dialog)
        
        tk.Button(dialog, text="Connect", command=connect, bg='#4CAF50', fg='white', font=('Arial', 12), padx=20, pady=5).pack(pady=20)
        
    def setup_ui(self):
        """Setup the main game UI with a Persona 5 theme"""
        # 1. Set Background Image
        try:
            bg_image_path = os.path.join("assets", "background.png")
            self.background_image = Image.open(bg_image_path).resize((1200, 800), Image.Resampling.LANCZOS)
            self.background_photo = ImageTk.PhotoImage(self.background_image)
            bg_label = tk.Label(self.root, image=self.background_photo)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except FileNotFoundError:
            print("Peringatan: 'assets/background.png' tidak ditemukan.")
            self.root.configure(bg='black')

        # 2. Area Utama
        self.pot_label = tk.Label(self.root, text="Pot: $0", bg='#1C1C1C', fg='white', font=('Arial', 16, 'bold'), padx=10, pady=5)
        self.pot_label.place(relx=0.5, rely=0.05, anchor='center')

        self.game_state_label = tk.Label(self.root, text="Waiting for players...", bg='#1C1C1C', fg='white', font=('Arial', 12))
        self.game_state_label.place(relx=0.5, rely=0.1, anchor='center')
        
        community_bg_frame = tk.Frame(self.root, bg='black', bd=2, relief=tk.SOLID)
        community_bg_frame.place(relx=0.5, rely=0.45, relwidth=0.5, relheight=0.25, anchor='center') # Sedikit lebih tinggi untuk kartu besar
        self.community_cards_frame = tk.Frame(community_bg_frame, bg='black')
        self.community_cards_frame.pack(expand=True)
        
        # 3. Area Tombol Aksi (Kiri Bawah)
        actions_frame = tk.Frame(self.root, bg='black', bd=0)
        actions_frame.place(relx=0.02, rely=0.98, anchor='sw')
        btn_style = {'font': ('Arial', 10, 'bold'), 'bg': '#D3D3D3', 'fg': 'black', 'width': 8}
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, **btn_style, state=tk.DISABLED)
        self.fold_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, **btn_style, state=tk.DISABLED)
        self.check_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, **btn_style, state=tk.DISABLED)
        self.call_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, **btn_style, state=tk.DISABLED)
        self.raise_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, **btn_style, state=tk.DISABLED)
        self.all_in_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 4. Area Pemain Sendiri (Kanan Bawah)
        my_player_area_frame = tk.Frame(self.root, bg='#111111', bd=1, relief=tk.SOLID)
        my_player_area_frame.place(relx=0.98, rely=0.98, anchor='se')
        
        my_info_frame = tk.Frame(my_player_area_frame, bg='#111111')
        my_info_frame.pack(pady=5, padx=10, anchor='w')
        
        self.my_name_label = tk.Label(my_info_frame, text="Player:", bg='#111111', fg='white', font=('Arial', 12, 'bold'))
        self.my_name_label.pack(anchor='w')
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", bg='#111111', fg='white', font=('Arial', 11))
        self.my_chips_label.pack(anchor='w')
        self.my_bet_label = tk.Label(my_info_frame, text="Current Bet: $0", bg='#111111', fg='yellow', font=('Arial', 11))
        self.my_bet_label.pack(anchor='w')

        self.my_cards_display_frame = tk.Frame(my_player_area_frame, bg='#111111')
        self.my_cards_display_frame.pack(pady=5, padx=10, anchor='w')

        # 5. Area Musuh (Kiri Atas) - POINT 2
        self.opponents_display_frame = tk.Frame(self.root, bg="black")
        self.opponents_display_frame.place(relx=0.02, rely=0.02, anchor='nw') # Pindah ke kiri atas

        # Tombol Start
        self.start_btn = tk.Button(self.root, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 14, 'bold'), padx=20, pady=10)
    
    def connect_to_server(self, server_ip, port=8888):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            join_message = {'type': 'join', 'player_id': self.player_id, 'name': self.player_name}
            self.socket.send(json.dumps(join_message).encode('utf-8') + b'\n')
            listen_thread = threading.Thread(target=self.listen_to_server)
            listen_thread.daemon = True
            listen_thread.start()
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
                        try:
                            message = json.loads(message_str)
                            self.root.after(0, lambda m=message: self.handle_server_message(m))
                        except json.JSONDecodeError:
                            print(f"Invalid JSON received: {message_str}")
            except Exception as e:
                print(f"Listen error: {e}")
                break
        self.connected = False
        self.root.after(0, lambda: messagebox.showinfo("Disconnected", "Lost connection to server."))
        self.root.after(0, self.root.quit)
        
    def handle_server_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'join_success':
            self.my_name_label.config(text=f"Player: {self.player_name}")
        elif msg_type == 'join_failed':
            messagebox.showerror("Error", message.get('message'))
            self.root.quit()
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
        elif msg_type == 'action_failed':
            messagebox.showwarning("Action Failed", message.get('message'))
        elif msg_type == 'game_result':
            winners = message.get('winners', [])
            winning_hand_type = message.get('winning_hand_type', 'Unknown Hand')
            if 'players' in self.game_data:
                winner_names = [self.game_data['players'][pid]['name'] for pid in winners if pid in self.game_data['players']]
                display_message = message.get('message')
                if self.player_id in winners:
                    display_message += f"\n\nYou won with a {winning_hand_type}!"
                elif winner_names:
                    display_message += f"\n\n{winner_names[0]} won with a {winning_hand_type}!"
                messagebox.showinfo("Game Result", display_message)
        elif msg_type == 'error':
            messagebox.showerror("Server Error", message.get('message'))
    
    def update_game_state(self, game_data):
        if not game_data: return
        self.game_data = game_data
        self.current_player_id = game_data.get('current_player_id')
        self.dealer_player_id = game_data.get('dealer_player_id')
        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        
        game_state = game_data.get('game_state', 'waiting')
        state_text = game_state.replace('_', ' ').title()
        if self.current_player_id == self.player_id:
            state_text += " - Your Turn!"
        elif self.current_player_id and self.current_player_id in self.game_data.get('players', {}):
            state_text += f" - {self.game_data['players'][self.current_player_id]['name']}'s Turn"
        self.game_state_label.config(text=state_text)
        
        self.update_community_cards(game_data.get('community_cards', []))
        self.update_players(game_data.get('players', {}))
        self.update_action_buttons(self.current_player_id == self.player_id and game_state in ['pre_flop', 'flop', 'turn', 'river'])
        
        if game_state == 'waiting' or game_state == 'game_over':
            self.start_btn.place(relx=0.5, rely=0.6, anchor='center')
        else:
            self.start_btn.place_forget()
            
    def update_community_cards(self, cards):
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        for card_data in cards:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                tk.Label(self.community_cards_frame, image=card_image, bg='black').pack(side=tk.LEFT, padx=2)
        for _ in range(len(cards), 5):
            if self.card_back_image:
                tk.Label(self.community_cards_frame, image=self.card_back_image, bg='black').pack(side=tk.LEFT, padx=2)
    
    def update_players(self, players_data):
        # Update info pemain sendiri
        if self.player_id in players_data:
            my_data = players_data[self.player_id]
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Current Bet: ${my_data.get('current_bet', 0)}")
            self.update_my_cards(my_data.get('cards', []))
        
        # Hapus widget musuh lama dan buat yang baru
        for widget in self.opponents_display_frame.winfo_children():
            widget.destroy()

        # Tampilkan musuh di kiri atas
        for pid, p_data in players_data.items():
            if pid == self.player_id:
                continue

            # Frame untuk setiap musuh
            opponent_frame = tk.Frame(self.opponents_display_frame, bg='#111111', bd=1, relief=tk.SOLID)
            opponent_frame.pack(pady=4, padx=5, anchor='nw') # Sesuaikan anchor ke nw

            # Info ringkas
            name_text = p_data.get('name', 'Unknown')
            if pid == self.dealer_player_id: name_text += " (D)"
            tk.Label(opponent_frame, text=name_text, bg='#111111', fg='white', font=('Arial', 9, 'bold')).pack(anchor='w', padx=5)
            tk.Label(opponent_frame, text=f"Chips: ${p_data.get('chips', 0)}", bg='#111111', fg='white', font=('Arial', 8)).pack(anchor='w', padx=5)
            tk.Label(opponent_frame, text=f"Bet: ${p_data.get('current_bet', 0)}", bg='#111111', fg='yellow', font=('Arial', 8)).pack(anchor='w', padx=5)
            
            # Kartu musuh
            cards_frame = tk.Frame(opponent_frame, bg='#111111')
            cards_frame.pack(anchor='w', padx=5, pady=(2,5))
            for card_data in p_data.get('cards', []):
                card_image = self.card_images.get(card_data['image'], self.card_back_image)
                tk.Label(cards_frame, image=card_image, bg='#111111').pack(side=tk.LEFT, padx=1)
    
    def update_my_cards(self, cards):
        for widget in self.my_cards_display_frame.winfo_children():
            widget.destroy()
        for card_data in cards:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                tk.Label(self.my_cards_display_frame, image=card_image, bg='#111111').pack(side=tk.LEFT, padx=2)
    
    def update_action_buttons(self, is_my_turn):
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.config(state=tk.DISABLED)

        if not is_my_turn or not self.game_data: return
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data or my_data.get('is_folded') or my_data.get('is_all_in'): return
        
        current_bet, my_bet, my_chips = self.game_data.get('current_bet', 0), my_data.get('current_bet', 0), my_data.get('chips', 0)
        
        self.fold_btn.config(state=tk.NORMAL)
        if my_chips > 0: self.all_in_btn.config(state=tk.NORMAL)
        if current_bet > my_bet:
            call_amount = current_bet - my_bet
            self.call_btn.config(state=tk.NORMAL, text=f"Call ${call_amount}" if my_chips >= call_amount else f"All-in ${my_chips}")
        else:
            self.check_btn.config(state=tk.NORMAL)
            self.call_btn.config(text="Call")
        if my_chips > (current_bet - my_bet):
            self.raise_btn.config(state=tk.NORMAL)

    def send_action(self, action, amount=0):
        if not self.connected: return
        message = {'type': 'action', 'player_id': self.player_id, 'action': action, 'amount': amount}
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending action: {e}")
            self.connected = False
            self.root.after(0, self.root.quit)
    
    def fold_action(self): self.send_action('fold')
    def check_action(self): self.send_action('check')
    def all_in_action(self): self.send_action('all_in')
    
    def call_action(self):
        my_data = self.game_data.get('players', {}).get(self.player_id)
        current_bet = self.game_data.get('current_bet', 0)
        if not my_data or not isinstance(current_bet, int): return
        if my_data['chips'] <= (current_bet - my_data['current_bet']):
            self.send_action('all_in')
        else:
            self.send_action('call')
    
    def raise_action(self):
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data: return
        
        current_bet = self.game_data.get('current_bet', 0)
        my_chips, my_current_bet = my_data.get('chips', 0), my_data.get('current_bet', 0)
        min_raise_increment = self.game_data.get('big_blind', 20)
        min_total_raise = current_bet + min_raise_increment
        max_total_bet = my_chips + my_current_bet
        min_raise_to_show = max(min_total_raise, my_current_bet + 1)

        amount_str = simpledialog.askstring("Raise", f"Raise to (min ${min_raise_to_show}, max ${max_total_bet}):", parent=self.root)
        if amount_str:
            try:
                amount = int(amount_str)
                if min_raise_to_show <= amount <= max_total_bet:
                    self.send_action('raise', amount)
                else:
                    messagebox.showerror("Invalid Raise", f"Amount must be between ${min_raise_to_show} and ${max_total_bet}.")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number.")
    
    def start_game(self):
        """Send request to start a new game to the server."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "You are not connected to the server.")
            return
        
        message = {'type': 'start_game', 'player_id': self.player_id}
        
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error starting game: {e}")
            self.connected = False
            self.root.after(0, lambda: messagebox.showerror("Connection Error", "Failed to send start game request."))
            self.root.after(0, self.root.quit)
    
    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            if self.connected and self.socket:
                self.socket.close()

if __name__ == '__main__':
    client = PokerClient()
    client.run()