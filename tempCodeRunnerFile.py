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
        self.root.configure(bg='#0D4F3C')  # Poker table green
        
        # Network settings
        self.socket = None
        self.connected = False
        self.player_id = str(uuid.uuid4())
        self.player_name = ""
        
        # Game state
        self.game_data = {}
        self.my_cards = []
        self.community_cards = []
        self.current_player_id = None # To explicitly track whose turn it is
        self.dealer_player_id = None # To explicitly track the dealer
        
        # Card images
        self.card_images = {}
        self.card_back_image = None
        self.load_card_images()
        
        # UI Widgets
        self.player_widgets = {} # To store references to player UI elements
        self.other_player_seats = [] # To store frames for other players
        
        self.setup_ui()
        self.setup_connection_dialog()
        
    def load_card_images(self):
        """Load all card images from the cards folder"""
        cards_folder = "cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", "Cards folder not found! Please create a 'cards' folder with card images (e.g., heart_ace.jpg, back_design.jpg).")
            self.root.quit()
            return
        
        try:
            # Load card back
            back_path = os.path.join(cards_folder, "back_design.jpg")
            if os.path.exists(back_path):
                img = Image.open(back_path)
                img = img.resize((70, 100), Image.Resampling.LANCZOS)
                self.card_back_image = ImageTk.PhotoImage(img)
            else:
                print(f"Warning: {back_path} not found.")
            
            # Load all card faces
            suits = ['club', 'diamond', 'heart', 'spade']
            ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
            
            for suit in suits:
                for rank in ranks:
                    filename = f"{suit}_{rank}.jpg"
                    filepath = os.path.join(cards_folder, filename)
                    if os.path.exists(filepath):
                        img = Image.open(filepath)
                        img = img.resize((70, 100), Image.Resampling.LANCZOS)
                        self.card_images[filename] = ImageTk.PhotoImage(img)
                    else:
                        print(f"Warning: {filepath} not found.")
                        
        except Exception as e:
            print(f"Error loading card images: {e}")
            messagebox.showwarning("Warning", "Some card images could not be loaded.")
    
    def setup_connection_dialog(self):
        """Show connection dialog at startup"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Poker Game")
        dialog.geometry("400x250")
        dialog.grab_set()
        dialog.configure(bg='#0D4F3C')
        
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", self.root.quit)
        
        tk.Label(dialog, text="Server IP:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(20, 2))
        ip_entry = tk.Entry(dialog, font=('Arial', 12), justify='center')
        ip_entry.insert(0, "localhost")
        ip_entry.pack(pady=5, padx=20, fill='x')
        
        tk.Label(dialog, text="Your Name:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        name_entry = tk.Entry(dialog, font=('Arial', 12), justify='center')
        name_entry.pack(pady=5, padx=20, fill='x')
        
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
        
        tk.Button(dialog, text="Connect", command=connect, 
                  bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), 
                  padx=20, pady=10).pack(pady=20)
        
    def setup_ui(self):
        """Setup the main game UI with a better layout"""
        # Main container
        main_container = tk.Frame(self.root, bg='#0D4F3C')
        main_container.pack(fill=tk.BOTH, expand=True)

        # 1. Top Frame for other players
        self.other_players_frame = tk.Frame(main_container, bg='#0D4F3C')
        self.other_players_frame.pack(side=tk.TOP, fill=tk.X, expand=False, padx=20, pady=10)
        
        # Create 6 "seats" for other players in a grid
        num_seats = 6
        for i in range(num_seats):
            col, row = i % 3, i // 3
            self.other_players_frame.grid_columnconfigure(col, weight=1)
            seat_frame = tk.Frame(self.other_players_frame, bg='#2E7D32', relief=tk.RAISED, bd=2, width=150, height=180)
            seat_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            self.other_player_seats.append(seat_frame)

        # 2. Middle Frame for Pot and Community Cards
        middle_frame = tk.Frame(main_container, bg='#0D4F3C')
        middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        info_frame = tk.Frame(middle_frame, bg='#1A5D4A', relief=tk.SUNKEN, bd=2)
        info_frame.pack(pady=10)
        
        self.pot_label = tk.Label(info_frame, text="Pot: $0", 
                                  bg='#1A5D4A', fg='white', font=('Arial', 18, 'bold'))
        self.pot_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.game_state_label = tk.Label(info_frame, text="Waiting for players...", 
                                         bg='#1A5D4A', fg='cyan', font=('Arial', 14))
        self.game_state_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        community_cards_container = tk.Frame(middle_frame, bg='#0D4F3C')
        community_cards_container.pack(pady=20)
        
        self.community_cards_frame = tk.Frame(community_cards_container, bg='#0D4F3C')
        self.community_cards_frame.pack()

        # 3. Bottom Frame for My Player Info and Actions
        my_player_frame = tk.Frame(main_container, bg='#1A5D4A', relief=tk.RAISED, bd=3)
        my_player_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        # My cards and info are grouped on the left
        my_info_and_cards_frame = tk.Frame(my_player_frame, bg='#1A5D4A')
        my_info_and_cards_frame.pack(side=tk.LEFT, padx=20, pady=10)

        self.my_cards_display_frame = tk.Frame(my_info_and_cards_frame, bg='#1A5D4A')
        self.my_cards_display_frame.pack(side=tk.LEFT, padx=10)

        my_info_frame = tk.Frame(my_info_and_cards_frame, bg='#1A5D4A')
        my_info_frame.pack(side=tk.LEFT, padx=10)

        self.my_name_label = tk.Label(my_info_frame, text=f"Player: {self.player_name}", 
                                      bg='#1A5D4A', fg='white', font=('Arial', 14, 'bold'))
        self.my_name_label.pack(anchor='w')
        
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", 
                                       bg='#1A5D4A', fg='white', font=('Arial', 12))
        self.my_chips_label.pack(anchor='w')
        
        self.my_bet_label = tk.Label(my_info_frame, text="Current Bet: $0", 
                                     bg='#1A5D4A', fg='yellow', font=('Arial', 12))
        self.my_bet_label.pack(anchor='w')

        # Action buttons are on the right
        actions_frame = tk.Frame(my_player_frame, bg='#1A5D4A')
        actions_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        
        btn_font = ('Arial', 11, 'bold')
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action, bg='#FF6B6B', fg='white', font=btn_font, padx=15, pady=8, state=tk.DISABLED)
        self.fold_btn.pack(side=tk.LEFT, padx=5)
        
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action, bg='#4ECDC4', fg='white', font=btn_font, padx=15, pady=8, state=tk.DISABLED)
        self.check_btn.pack(side=tk.LEFT, padx=5)
        
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action, bg='#45B7D1', fg='white', font=btn_font, padx=15, pady=8, state=tk.DISABLED)
        self.call_btn.pack(side=tk.LEFT, padx=5)
        
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action, bg='#FFA07A', fg='white', font=btn_font, padx=15, pady=8, state=tk.DISABLED)
        self.raise_btn.pack(side=tk.LEFT, padx=5)

        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action, bg='#9B59B6', fg='white', font=btn_font, padx=15, pady=8, state=tk.DISABLED)
        self.all_in_btn.pack(side=tk.LEFT, padx=5)
        
        # Start/New Hand button is in the middle-right
        self.start_btn = tk.Button(my_player_frame, text="Start New Hand", command=self.start_game, bg='#27AE60', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=10)
        self.start_btn.pack(side=tk.RIGHT, padx=20)

    def connect_to_server(self, server_ip, port=8888):
        """Connect to the poker server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            
            join_message = {'type': 'join', 'player_id': self.player_id, 'name': self.player_name}
            self.socket.send(json.dumps(join_message).encode('utf-8') + b'\n')
            
            listen_thread = threading.Thread(target=self.listen_to_server, daemon=True)
            listen_thread.start()
            
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def listen_to_server(self):
        """Listen for messages from the server"""
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    msg_str, buffer = buffer.split('\n', 1)
                    if msg_str:
                        try:
                            message = json.loads(msg_str)
                            self.root.after(0, self.handle_server_message, message)
                        except json.JSONDecodeError:
                            print(f"Invalid JSON received: {msg_str}")
                
            except Exception as e:
                print(f"Listen error: {e}")
                break
        
        self.connected = False
        self.root.after(0, lambda: messagebox.showinfo("Disconnected", "Lost connection to server."))
        self.root.after(100, self.root.quit)
        
    def handle_server_message(self, message):
        """Handle messages from the server"""
        msg_type = message.get('type')
        
        if msg_type == 'join_success':
            self.update_status("Connected to game!")
            self.my_name_label.config(text=f"Player: {self.player_name}")
        elif msg_type == 'join_failed':
            messagebox.showerror("Error", message.get('message'))
            self.root.quit()
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
        elif msg_type == 'game_started':
            self.update_status("Game started!")
        elif msg_type == 'action_failed':
            messagebox.showwarning("Action Failed", message.get('message'))
        elif msg_type == 'game_result':
            self.handle_game_result(message)
        elif msg_type == 'error':
            messagebox.showerror("Server Error", message.get('message'))
    
    def handle_game_result(self, message):
        """Handle displaying the game result"""
        winners = message.get('winners', [])
        winning_hand_type = message.get('winning_hand_type', 'a high card')
        
        if 'players' in self.game_data:
            winner_names = [self.game_data['players'][pid]['name'] for pid in winners if pid in self.game_data['players']]
            
            display_message = message.get('message', f"Winner(s): {', '.join(winner_names)}!")
            
            if self.player_id in winners:
                display_message += f"\n\nYou won with {winning_hand_type}!"
            elif len(winners) == 1:
                display_message += f"\n\n{winner_names[0]} won with {winning_hand_type}!"
            else:
                 display_message += f"\n\nThe winners had {winning_hand_type}!"

            messagebox.showinfo("Game Result", display_message)
            self.update_status(f"Winners: {', '.join(winner_names)} ({winning_hand_type})")
        else:
            messagebox.showinfo("Game Result", message.get('message'))
            self.update_status("Game ended.")

    def update_game_state(self, game_data):
        """Update the UI with new game state"""
        if not game_data: return
        
        self.game_data = game_data
        self.current_player_id = game_data.get('current_player_id')
        self.dealer_player_id = game_data.get('dealer_player_id')
        
        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        
        game_state = game_data.get('game_state', 'waiting')
        state_text_map = {
            'waiting': 'Waiting for players...', 'dealing': 'Dealing cards...',
            'pre_flop': 'Pre-Flop Betting', 'flop': 'Flop Betting',
            'turn': 'Turn Betting', 'river': 'River Betting',
            'showdown': 'Showdown', 'game_over': 'Game Over'
        }
        state_text = state_text_map.get(game_state, game_state.title())
        
        if self.current_player_id and game_state not in ['waiting', 'showdown', 'game_over']:
            if self.current_player_id == self.player_id:
                state_text += " - Your Turn!"
            elif self.current_player_id in self.game_data.get('players', {}):
                current_player_name = self.game_data['players'][self.current_player_id]['name']
                state_text += f" - {current_player_name}'s Turn"
        self.game_state_label.config(text=state_text)
        
        self.update_community_cards(game_data.get('community_cards', []))
        self.update_players(game_data.get('players', {}))
        self.update_action_buttons(self.current_player_id == self.player_id and game_state in ['pre_flop', 'flop', 'turn', 'river'])
        
        if game_state in ['waiting', 'game_over']:
            self.start_btn.config(state=tk.NORMAL)
        else:
            self.start_btn.config(state=tk.DISABLED)
            
    def update_community_cards(self, cards):
        """Update community cards display"""
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        
        card_list = cards if self.game_data.get('game_state') != 'dealing' else []

        for card_data in card_list:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                label = tk.Label(self.community_cards_frame, image=card_image, bg='#0D4F3C')
                label.pack(side=tk.LEFT, padx=5)
            
        # Add placeholders for the remaining community cards
        for _ in range(len(card_list), 5):
            if self.card_back_image:
                # Create a simple frame as a placeholder to maintain spacing
                placeholder = tk.Frame(self.community_cards_frame, width=70, height=100, bg='#1A5D4A', relief=tk.GROOVE, bd=1)
                placeholder.pack(side=tk.LEFT, padx=5)

    def update_players(self, players_data):
        """Update players display using the new grid layout"""
        # First, clear all existing player "seats"
        for seat in self.other_player_seats:
            for widget in seat.winfo_children():
                widget.destroy()
            seat.configure(bg='#2E7D32') # Reset color

        # Update my player info first
        if self.player_id in players_data:
            my_data = players_data[self.player_id]
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Current Bet: ${my_data.get('current_bet', 0)}")
            self.update_my_cards(my_data.get('cards', []))
        
        other_players = [pid for pid in players_data if pid != self.player_id]
        
        # Populate the seats with other players
        for i, pid in enumerate(other_players):
            if i >= len(self.other_player_seats): break # Don't exceed available seats

            player_data = players_data[pid]
            seat_frame = self.other_player_seats[i]

            # Player name with Dealer tag
            name_text = player_data.get('name', 'Unknown')
            if pid == self.dealer_player_id:
                name_text += " (D)"
            
            name_label = tk.Label(seat_frame, text=name_text, bg='#2E7D32', fg='white', font=('Arial', 12, 'bold'))
            name_label.pack(pady=(5, 2))
            
            chips_label = tk.Label(seat_frame, text=f"Chips: ${player_data.get('chips', 0)}", bg='#2E7D32', fg='white', font=('Arial', 10))
            chips_label.pack()
            
            bet_label = tk.Label(seat_frame, text=f"Bet: ${player_data.get('current_bet', 0)}", bg='#2E7D32', fg='yellow', font=('Arial', 10))
            bet_label.pack()

            # Player Status (Folded, All-In, To Act)
            status_text, status_color = "", 'white'
            if player_data.get('is_folded'): status_text, status_color = "FOLDED", '#FF6B6B'
            elif player_data.get('is_all_in'): status_text, status_color = "ALL IN", '#FFA07A'
            elif pid == self.current_player_id: status_text, status_color = "THINKING...", '#4ECDC4'
            
            status_label = tk.Label(seat_frame, text=status_text, bg='#2E7D32', fg=status_color, font=('Arial', 9, 'italic'))
            status_label.pack(pady=2)
            
            # Player Cards
            cards_frame = tk.Frame(seat_frame, bg='#2E7D32')
            cards_frame.pack(pady=5)
            
            player_cards = player_data.get('cards', [])
            show_cards = self.game_data.get('game_state') in ['showdown', 'game_over'] and not player_data.get('is_folded')
            
            for card_data in player_cards:
                card_image = self.card_images.get(card_data['image']) if show_cards else self.card_back_image
                if card_image:
                    card_label = tk.Label(cards_frame, image=card_image, bg='#2E7D32')
                    card_label.pack(side=tk.LEFT, padx=3)
    
    def update_my_cards(self, cards):
        """Update my cards display"""
        for widget in self.my_cards_display_frame.winfo_children():
            widget.destroy()
        
        for card_data in cards:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                label = tk.Label(self.my_cards_display_frame, image=card_image, bg='#1A5D4A')
                label.pack(side=tk.LEFT, padx=3)
    
    def update_action_buttons(self, is_my_turn):
        """Update action buttons based on game state"""
        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.all_in_btn]:
            btn.config(state=tk.DISABLED)

        if not is_my_turn or not self.game_data: return
            
        players = self.game_data.get('players', {})
        my_data = players.get(self.player_id)
        if not my_data or my_data.get('is_folded') or my_data.get('is_all_in') or my_data.get('chips', 0) <= 0: return
        
        current_bet = self.game_data.get('current_bet', 0)
        my_bet = my_data.get('current_bet', 0)
        my_chips = my_data.get('chips', 0)
        
        self.fold_btn.config(state=tk.NORMAL)
        
        if current_bet == my_bet:
            self.check_btn.config(state=tk.NORMAL)
            self.call_btn.config(text="Call")
        else:
            call_amount = current_bet - my_bet
            self.call_btn.config(state=tk.NORMAL, text=f"Call ${call_amount}")
                
        min_raise_inc = self.game_data.get('big_blind', 20)
        min_raise_total = current_bet + min_raise_inc
        # Player must have enough chips to at least make a minimum raise
        can_raise = my_chips + my_bet >= min_raise_total
        
        if can_raise:
             self.raise_btn.config(state=tk.NORMAL)
        
        if my_chips > 0:
            self.all_in_btn.config(state=tk.NORMAL)

    def send_action(self, action, amount=0):
        """Send action to server"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "You are not connected to the server.")
            return
            
        message = {'type': 'action', 'player_id': self.player_id, 'action': action, 'amount': amount}
        
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending action: {e}")
            self.connected = False
            self.root.after(0, lambda: messagebox.showerror("Connection Error", "Failed to send action."))
            self.root.after(100, self.root.quit)
    
    def fold_action(self): self.send_action('fold')
    def check_action(self): self.send_action('check')
    def all_in_action(self): self.send_action('all_in')
    
    def call_action(self):
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data: return
        call_amount_needed = self.game_data.get('current_bet', 0) - my_data.get('current_bet', 0)
        
        if my_data.get('chips', 0) <= call_amount_needed:
            self.send_action('all_in')
        else:
            self.send_action('call')
    
    def raise_action(self):
        """Show raise dialog and send raise action"""
        my_data = self.game_data.get('players', {}).get(self.player_id)
        if not my_data: return
            
        current_bet = self.game_data.get('current_bet', 0)
        my_chips = my_data.get('chips', 0)
        my_bet = my_data.get('current_bet', 0)

        min_raise_inc = self.game_data.get('big_blind', 20)
        min_raise_total = current_bet + min_raise_inc
        max_raise_total = my_chips + my_bet

        if max_raise_total < min_raise_total:
             messagebox.showinfo("Cannot Raise", "You do not have enough chips to make a minimum raise.")
             return

        amount = simpledialog.askinteger(
            "Raise Amount",
            f"Enter total bet amount.\n\nMin Raise: ${min_raise_total}\nYour Chips: ${my_chips}\nAll-in: ${max_raise_total}",
            parent=self.root,
            minvalue=min_raise_total,
            maxvalue=max_raise_total
        )
        if amount is not None:
            self.send_action('raise', amount)

    def start_game(self):
        """Send request to start a new game"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "You are not connected to the server.")
            return
        
        message = {'type': 'start_game', 'player_id': self.player_id}
        
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error starting game: {e}")
            self.connected = False
            self.root.after(0, lambda: messagebox.showerror("Connection Error", "Failed to start game request."))
            self.root.after(100, self.root.quit)

    def update_status(self, message):
        """Update status message"""
        print(f"Client Status: {message}")

    def run(self):
        """Runs the Tkinter event loop"""
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