import socket
import threading
import json
import random
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import time

class GameState(Enum):
    WAITING = "waiting"
    DEALING = "dealing"
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    AWAITING_SHOWDOWN = "awaiting_showdown"
    SHOWDOWN = "showdown"
    GAME_OVER = "game_over"

class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"

@dataclass
class Card:
    suit: str
    rank: str
    
    def get_image_name(self):
        # The client already expects rank names like 'jack', 'queen', etc.
        # No mapping needed here if server-side ranks are consistent.
        return f"{self.suit}_{self.rank}.jpg"
    
    def get_value(self):
        if self.rank in ['jack', 'queen', 'king']:
            return {'jack': 11, 'queen': 12, 'king': 13}[self.rank]
        elif self.rank == 'ace':
            return 14
        else:
            return int(self.rank)

@dataclass
class Player:
    id: str
    name: str
    chips: int
    cards: List[Card]
    current_bet: int # Amount player has put into the pot in the current betting round
    total_bet: int # Total amount player has put into the pot for the entire hand
    is_folded: bool
    is_all_in: bool
    connection: socket.socket
    has_acted_this_round: bool = False
    has_revealed: bool = False

    def can_act(self) -> bool:
        """Determines if a player is eligible to make an action."""
        return not self.is_folded and not self.is_all_in and self.chips > 0

class PokerGame:
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.community_cards: List[Card] = []
        self.deck: List[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.dealer_position = -1
        self.current_player_index = -1
        self.game_state = GameState.WAITING
        self.small_blind = 10
        self.big_blind = 20
        self.action_history = []
        self.last_raiser = None
        
    def create_deck(self):
        """Creates and shuffles a standard 52-card deck."""
        suits = ['heart', 'diamond', 'club', 'spade']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
        self.deck = [Card(suit, rank) for suit in suits for rank in ranks]
        random.shuffle(self.deck)
    
    def add_player(self, player_id: str, name: str, connection: socket.socket):
        """Adds a new player to the game if there's space."""
        if len(self.players) < 6:
            self.players[player_id] = Player(
                id=player_id, name=name, chips=1000, cards=[], current_bet=0,
                total_bet=0, is_folded=False, is_all_in=False, connection=connection
            )
            return True
        return False
    
    def remove_player(self, player_id: str):
        """Removes a player from the game."""
        if player_id in self.players:
            del self.players[player_id]
            if len([p for p in self.players.values() if p.chips > 0]) < 2 and self.game_state != GameState.WAITING:
                self.game_state = GameState.GAME_OVER

    def _prepare_for_new_hand(self) -> List[Player]:
        """Resets states for a new hand and returns active players."""
        print("Preparing for new hand, resetting player states.")
        active_players = []
        for player in self.players.values():
            if player.chips > 0:
                active_players.append(player)
            player.cards = []
            player.current_bet = 0
            player.total_bet = 0
            player.is_folded = False
            player.is_all_in = False
            player.has_acted_this_round = False
            player.has_revealed = False # Also reset revealed status
        
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        self.action_history = []
        self.last_raiser = None
        self.create_deck()
        return active_players
    
    def start_new_hand(self):
        """Starts a new hand of poker."""
        active_players = self._prepare_for_new_hand()
        
        if len(active_players) < 2:
            print("Not enough active players to start a new hand.")
            self.game_state = GameState.GAME_OVER
            self.broadcast_game_state_to_all() # Inform clients game is over
            return False

        # Dealer Button Rotation
        all_player_ids = list(self.players.keys())
        if self.dealer_position == -1:
             # Find first player with chips to be the first dealer
            self.dealer_position = next((i for i, pid in enumerate(all_player_ids) if self.players[pid].chips > 0), 0)
        else:
            self.dealer_position = (self.dealer_position + 1) % len(all_player_ids)
            # Find next active player for dealer
            while self.players[all_player_ids[self.dealer_position]].chips <= 0:
                self.dealer_position = (self.dealer_position + 1) % len(all_player_ids)

        # Deal Cards
        active_player_ids_in_order = self.get_player_order_from(self.dealer_position + 1)
        for _ in range(2):
            for player_id in active_player_ids_in_order:
                if self.deck:
                    self.players[player_id].cards.append(self.deck.pop())
        
        self.post_blinds()
        self.game_state = GameState.PRE_FLOP
        
        dealer_name = self.players[all_player_ids[self.dealer_position]].name
        current_player_name = self.players[all_player_ids[self.current_player_index]].name
        print(f"New hand started. Dealer: {dealer_name}. First to act: {current_player_name}")
        return True
    
    def get_player_order_from(self, start_index: int) -> List[str]:
        """Gets a list of active player IDs in order, starting from an index."""
        all_ids = list(self.players.keys())
        num_players = len(all_ids)
        ordered_ids = []
        for i in range(num_players):
            idx = (start_index + i) % num_players
            player_id = all_ids[idx]
            if self.players[player_id].chips > 0:
                ordered_ids.append(player_id)
        return ordered_ids
        
    def post_blinds(self):
        """Handles posting blinds by finding the next active players."""
        all_player_ids = list(self.players.keys())
        active_player_ids = self.get_player_order_from(self.dealer_position + 1)
        num_active = len(active_player_ids)

        if num_active < 2: return

        # Determine blind positions
        sb_player_id = active_player_ids[0]
        bb_player_id = active_player_ids[1 % num_active]
        first_to_act_id = active_player_ids[2 % num_active]
        
        if num_active == 2: # Heads-up case
            sb_player_id = self.get_player_order_from(self.dealer_position)[0]
            bb_player_id = self.get_player_order_from(self.dealer_position + 1)[0]
            first_to_act_id = sb_player_id

        self.current_player_index = all_player_ids.index(first_to_act_id)
        
        # Post Blinds
        sb_player = self.players[sb_player_id]
        sb_amount = min(self.small_blind, sb_player.chips)
        self._apply_bet(sb_player, sb_amount)
        print(f"{sb_player.name} posted Small Blind of ${sb_amount}")

        bb_player = self.players[bb_player_id]
        bb_amount = min(self.big_blind, bb_player.chips)
        self._apply_bet(bb_player, bb_amount)
        print(f"{bb_player.name} posted Big Blind of ${bb_amount}")

        self.current_bet = bb_player.current_bet
        self.last_raiser = bb_player.id

    def _apply_bet(self, player: Player, amount: int):
        """Helper to apply a bet from a player."""
        actual_amount = min(amount, player.chips)
        player.chips -= actual_amount
        player.current_bet += actual_amount
        # total_bet will be calculated at the end of the round
        self.pot += actual_amount
        if player.chips == 0:
            player.is_all_in = True
            print(f"{player.name} is all-in.")

    def process_action(self, player_id: str, action: str, amount: int = 0) -> bool:
        """Processes a player's action (fold, check, call, raise, all-in)."""
        player = self.players[player_id]
        
        success = False
        action_type = ActionType(action)

        if action_type == ActionType.FOLD:
            player.is_folded = True
            print(f"{player.name} folds.")
            success = True
        
        elif action_type == ActionType.CHECK:
            if player.current_bet < self.current_bet:
                print(f"Error: {player.name} cannot check, a bet of ${self.current_bet} is active.")
                return False
            print(f"{player.name} checks.")
            success = True

        elif action_type == ActionType.CALL:
            call_amount = self.current_bet - player.current_bet
            self._apply_bet(player, call_amount)
            print(f"{player.name} calls ${call_amount}.")
            success = True

        elif action_type == ActionType.RAISE:
            if amount <= self.current_bet:
                print(f"Error: Raise amount ${amount} must be higher than current bet ${self.current_bet}.")
                return False
            
            total_new_bet = amount
            amount_to_add = total_new_bet - player.current_bet

            if amount_to_add > player.chips:
                print(f"Error: {player.name} cannot afford to raise to ${amount}.")
                # Or handle as an all-in
                return False

            self._apply_bet(player, amount_to_add)
            self.current_bet = player.current_bet
            self.last_raiser = player.id
            print(f"{player.name} raises to ${self.current_bet}.")
            success = True
        
        elif action_type == ActionType.ALL_IN:
            all_in_amount = player.chips
            self._apply_bet(player, all_in_amount)
            if player.current_bet > self.current_bet:
                self.current_bet = player.current_bet
                self.last_raiser = player.id
            print(f"{player.name} is ALL-IN with ${all_in_amount}.")
            success = True

        if success:
            player.has_acted_this_round = True
            self.action_history.append((player_id, action, amount))
        
        return success
    
    def advance_to_next_street(self):
        """Advances the game to the next betting street."""
        for player in self.players.values():
            player.total_bet += player.current_bet
            player.current_bet = 0
            # Only reset has_acted for players who are not folded or all-in
            if not player.is_folded and not player.is_all_in:
                player.has_acted_this_round = False
        
        self.current_bet = 0
        self.last_raiser = None

        # Set first player to act post-flop (first active player after dealer)
        active_players_after_dealer = self.get_player_order_from(self.dealer_position + 1)
        if not active_players_after_dealer: # Should not happen if hand is live
             self.current_player_index = -1
        else:
            self.current_player_index = list(self.players.keys()).index(active_players_after_dealer[0])

        if self.game_state == GameState.PRE_FLOP:
            self.deal_community_cards("flop", 3)
            self.game_state = GameState.FLOP
        elif self.game_state == GameState.FLOP:
            self.deal_community_cards("turn", 1)
            self.game_state = GameState.TURN
        elif self.game_state == GameState.TURN:
            self.deal_community_cards("river", 1)
            self.game_state = GameState.RIVER
        elif self.game_state == GameState.RIVER:
            self.game_state = GameState.AWAITING_SHOWDOWN
            print("--- All betting rounds complete. Awaiting showdown. ---")

    def deal_community_cards(self, street_name: str, count: int):
        """Deals community cards for a given street."""
        if self.deck: self.deck.pop()  # Burn card
        print(f"--- Dealing {street_name.upper()} ---")
        for _ in range(count):
            if self.deck:
                self.community_cards.append(self.deck.pop())

    def check_all_revealed(self) -> bool:
        """Check if all non-folded players have revealed their cards."""
        players_in_hand = [p for p in self.players.values() if not p.is_folded]
        if not players_in_hand or len(players_in_hand) == 1:
            return True # No one to wait for
        return all(p.has_revealed for p in players_in_hand)

    def evaluate_hand(self, player_cards: List[Card], community_cards: List[Card]) -> Tuple[int, List[int]]:
        """Evaluate poker hand strength. Returns (hand_rank, tiebreakers)."""
        # This function's logic is complex and appears mostly correct. No changes made here.
        all_cards = player_cards + community_cards
        all_cards.sort(key=lambda x: x.get_value(), reverse=True)
        
        suits, ranks = {}, {}
        for card in all_cards:
            suits[card.suit] = suits.get(card.suit, 0) + 1
            ranks[card.get_value()] = ranks.get(card.get_value(), 0) + 1
        
        is_flush = any(count >= 5 for count in suits.values())
        flush_suit = next((s for s, c in suits.items() if c >= 5), None)
        
        unique_ranks = sorted(list(set(card.get_value() for card in all_cards)), reverse=True)
        is_straight = False
        straight_high = 0
        if len(unique_ranks) >= 5:
            for i in range(len(unique_ranks) - 4):
                if unique_ranks[i] - unique_ranks[i+4] == 4:
                    is_straight = True
                    straight_high = unique_ranks[i]
                    break
            # Ace-low straight (wheel)
            if {14, 2, 3, 4, 5}.issubset(set(unique_ranks)):
                is_straight = True
                straight_high = 5 if straight_high == 0 else straight_high

        rank_counts = sorted(ranks.items(), key=lambda x: (x[1], x[0]), reverse=True)
        
        # Straight Flush
        if is_straight and is_flush:
            flush_cards_ranks = sorted([c.get_value() for c in all_cards if c.suit == flush_suit], reverse=True)
            if len(flush_cards_ranks) >= 5:
                for i in range(len(flush_cards_ranks) - 4):
                    if flush_cards_ranks[i] - flush_cards_ranks[i+4] == 4:
                        # Royal Flush
                        if flush_cards_ranks[i] == 14: return (9, [14]) 
                        # Straight Flush
                        return (8, [flush_cards_ranks[i]]) 
                # Ace-low straight flush
                if {14, 2, 3, 4, 5}.issubset(set(flush_cards_ranks)): return (8, [5])

        if rank_counts[0][1] == 4:  # Four of a Kind
            kickers = sorted([r for r, c in rank_counts if r != rank_counts[0][0]], reverse=True)
            return (7, [rank_counts[0][0], kickers[0]])
        
        if rank_counts[0][1] == 3 and rank_counts[1][1] >= 2:  # Full House
            return (6, [rank_counts[0][0], rank_counts[1][0]])

        if is_flush:
            flush_cards = sorted([c.get_value() for c in all_cards if c.suit == flush_suit], reverse=True)
            return (5, flush_cards[:5])

        if is_straight:
            return (4, [straight_high])

        if rank_counts[0][1] == 3:  # Three of a Kind
            kickers = sorted([r for r, c in rank_counts if r != rank_counts[0][0]], reverse=True)
            return (3, [rank_counts[0][0]] + kickers[:2])
        
        if rank_counts[0][1] == 2 and rank_counts[1][1] == 2:  # Two Pair
            pairs = sorted([rank_counts[0][0], rank_counts[1][0]], reverse=True)
            kickers = sorted([r for r, c in rank_counts if r not in pairs], reverse=True)
            return (2, pairs + kickers[:1])

        if rank_counts[0][1] == 2:  # One Pair
            pair_rank = rank_counts[0][0]
            kickers = sorted([r for r, c in rank_counts if r != pair_rank], reverse=True)
            return (1, [pair_rank] + kickers[:3])
            
        return (0, unique_ranks[:5]) # High Card


    def determine_winners(self) -> Dict[str, int]:
        """Determines winner(s) and calculates winnings for main and side pots."""
        # This function was updated in the previous turn and its logic is kept.
        winnings_map = {}
        active_players = [p for p in self.players.values() if not p.is_folded]

        if not active_players: return {}
        if len(active_players) == 1:
            winner = active_players[0]
            amount = self.pot
            winnings_map[winner.id] = amount
            self.players[winner.id].chips += amount
            self.pot = 0
            print(f"Player {winner.name} wins ${amount} as the only remaining player.")
            return winnings_map

        player_hands = { p.id: self.evaluate_hand(p.cards, self.community_cards) for p in active_players }
        
        # Finalize total bets for this hand before calculating side pots
        for p in self.players.values():
            p.total_bet += p.current_bet
        
        all_in_bets = sorted(list(set(p.total_bet for p in active_players if p.is_all_in)))
        bet_levels = sorted(list(set([0] + all_in_bets + [max(p.total_bet for p in active_players)])))

        last_level = 0
        for level in bet_levels:
            if level <= last_level: continue

            pot_amount = 0
            eligible_ids = [p.id for p in active_players if p.total_bet >= level]
            
            # This logic can be simplified. Let's rebuild the main pot from contributions.
        
        # Simpler Side Pot Logic
        main_pot = 0
        side_pots = [] # List of {'amount': int, 'eligible_ids': List[str]}
        
        # Sort players by total bet to handle side pots correctly
        sorted_players = sorted(active_players, key=lambda p: p.total_bet)
        
        while True:
            active_in_pot = [p for p in sorted_players if not p.is_folded and p.total_bet > 0]
            if not active_in_pot: break

            lowest_bet = min(p.total_bet for p in active_in_pot)
            current_pot_amount = 0
            pot_eligible_ids = [p.id for p in active_in_pot]

            for p in list(self.players.values()): # Iterate over all players for contribution
                contribution = min(p.total_bet, lowest_bet)
                current_pot_amount += contribution
                p.total_bet -= contribution
            
            if current_pot_amount > 0:
                side_pots.append({'amount': current_pot_amount, 'eligible_ids': pot_eligible_ids})

            sorted_players = [p for p in sorted_players if p.total_bet > 0] # Players left for next pot
        
        # Distribute pots
        for pot in side_pots:
            eligible_hands = {pid: hand for pid, hand in player_hands.items() if pid in pot['eligible_ids']}
            if not eligible_hands: continue
            
            best_hand = max(eligible_hands.values())
            pot_winners_ids = [pid for pid, hand in eligible_hands.items() if hand == best_hand]
            
            win_amount_per_player = pot['amount'] // len(pot_winners_ids)
            remainder = pot['amount'] % len(pot_winners_ids)

            for i, winner_id in enumerate(pot_winners_ids):
                winnings = win_amount_per_player + (1 if i < remainder else 0)
                if winnings > 0:
                    self.players[winner_id].chips += winnings
                    winnings_map[winner_id] = winnings_map.get(winner_id, 0) + winnings
                    print(f"Player {self.players[winner_id].name} wins ${winnings} from a pot.")

        self.pot = 0
        return winnings_map

    def get_game_state(self, player_id: Optional[str] = None) -> dict:
        """Returns the current game state, with player-specific card visibility."""
        players_data = {}
        all_player_ids = list(self.players.keys())
        
        for pid, p in self.players.items():
            show_cards = (
                player_id == pid or 
                p.has_revealed or
                self.game_state in [GameState.SHOWDOWN, GameState.GAME_OVER]
            )
            
            if show_cards:
                player_cards_data = [{'suit': card.suit, 'rank': card.rank, 'image': card.get_image_name()} for card in p.cards]
            else:
                player_cards_data = [{'suit': 'back', 'rank': 'back', 'image': 'card_back.jpg'} for _ in p.cards]

            players_data[pid] = {
                'name': p.name,
                'chips': p.chips,
                'current_bet': p.current_bet,
                'total_bet': p.total_bet, # Send total for clarity
                'is_folded': p.is_folded,
                'is_all_in': p.is_all_in,
                'cards': player_cards_data,
                'is_current_player': (all_player_ids[self.current_player_index] == pid) if self.current_player_index != -1 else False
            }
        
        return {
            'game_state': self.game_state.value,
            'players': players_data,
            'community_cards': [{'suit': card.suit, 'rank': card.rank, 'image': card.get_image_name()} for card in self.community_cards],
            'pot': self.pot,
            'current_bet': self.current_bet,
            'current_player_id': all_player_ids[self.current_player_index] if self.current_player_index != -1 else None,
            'dealer_player_id': all_player_ids[self.dealer_position] if self.dealer_position != -1 else None,
            'small_blind': self.small_blind,
            'big_blind': self.big_blind
        }

    # Method to easily broadcast state from the game logic if needed
    def broadcast_game_state_to_all(self):
        # This is a placeholder; the actual broadcast is managed by the server class
        pass

class PokerServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.game = PokerGame()
        self.game.broadcast_game_state_to_all = self.broadcast_game_state # Link broadcast method
        self.clients: Dict[str, socket.socket] = {}
        
    def start(self):
        """Starts the poker server."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(6)
        print(f"Poker server started on {self.host}:{self.port}")
        
        threading.Thread(target=self.game_loop, daemon=True).start()

        while True:
            client_socket, address = self.server_socket.accept()
            print(f"New connection from {address}")
            threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()
    
    def handle_client(self, client_socket, address):
        """Handles a single client connection."""
        player_id = None
        try:
            buffer = ""
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data: break
                
                buffer += data
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    if message_str:
                        message = json.loads(message_str)
                        # First message from a client must be 'join'
                        if not player_id and message.get('type') == 'join':
                            player_id = message['player_id']
                            player_name = message['name']
                            if self.game.add_player(player_id, player_name, client_socket):
                                self.clients[player_id] = client_socket
                                self.send_to_client(player_id, {'type': 'join_success', 'message': 'Joined game successfully'})
                                print(f"Player {player_name} ({player_id}) joined.")
                                self.broadcast_game_state()
                            else:
                                self.send_to_client(player_id, {'type': 'join_failed', 'message': 'Game is full or an error occurred.'})
                                player_id = None # Prevent further messages
                        elif player_id:
                            self.process_client_message(message, player_id)
        except Exception as e:
            print(f"Error with client {address} (Player ID: {player_id}): {e}")
        finally:
            if player_id:
                print(f"Player {self.game.players.get(player_id, Player(id=player_id, name='Unknown', chips=0, cards=[], current_bet=0, total_bet=0, is_folded=True, is_all_in=True, connection=None)).name} disconnected.")
                self.game.remove_player(player_id)
                if player_id in self.clients:
                    del self.clients[player_id]
                self.broadcast_game_state()
            client_socket.close()
    
    def process_client_message(self, message: dict, player_id: str):
        """Processes a validated message from a client."""
        msg_type = message.get('type')
        
        if msg_type == 'start_game':
            if self.game.game_state == GameState.WAITING and len(self.game.players) >= 2:
                if self.game.start_new_hand():
                    print("Game started by a client.")
                    self.broadcast_game_state()
            else:
                self.send_to_client(player_id, {'type': 'error', 'message': 'Cannot start game (not enough players or game in progress).'})
        
        # --- BUG FIX STARTS HERE ---
        elif msg_type == 'action':
            action_type = message.get('action')
            amount = message.get('amount', 0)
            
            # Ensure actions are only processed during active betting rounds
            if self.game.game_state not in [GameState.PRE_FLOP, GameState.FLOP, GameState.TURN, GameState.RIVER]:
                self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Actions not allowed in current game state.'})
                return

            all_player_ids = list(self.game.players.keys())
            current_player_id = all_player_ids[self.game.current_player_index] if self.game.current_player_index != -1 else None
            
            if player_id != current_player_id:
                self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Not your turn.'})
                return

            if self.game.process_action(player_id, action_type, amount):
                print(f"Player {self.game.players[player_id].name} action: {action_type} {amount}")
                # Action was successful, now check if the round is over or move to the next player
                if self.is_betting_round_complete():
                    print(f"Betting round for {self.game.game_state.value} is complete.")
                    self.game.advance_to_next_street()
                else:
                    self.advance_to_next_player()
                self.broadcast_game_state()
            else:
                self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Invalid action.'})
        # --- BUG FIX ENDS HERE ---

        elif msg_type == 'reveal_cards':
            if self.game.game_state == GameState.AWAITING_SHOWDOWN and player_id in self.game.players:
                self.game.players[player_id].has_revealed = True
                print(f"Player {self.game.players[player_id].name} has revealed their cards.")
                self.broadcast_game_state()
    
    def is_betting_round_complete(self) -> bool:
        """Checks if the current betting round is complete."""
        # Players still in the hand (not folded)
        active_players = [p for p in self.game.players.values() if not p.is_folded]
        if not active_players: return True
        
        # Players who can still act (not folded and not all-in)
        players_that_can_act = [p for p in active_players if not p.is_all_in]
        if len(players_that_can_act) < 2:
             # Check if all remaining players have acted. This is for the case where one player bets and everyone else folds.
             if all(p.has_acted_this_round for p in players_that_can_act):
                 return True

        # Check if all players who can act have acted and bet the same amount
        all_acted = all(p.has_acted_this_round for p in players_that_can_act)
        bets_equal = len(set(p.current_bet for p in players_that_can_act)) == 1

        return all_acted and bets_equal

    def advance_to_next_player(self):
        """Advances the turn to the next player who can act."""
        all_player_ids = list(self.game.players.keys())
        num_players = len(all_player_ids)
        if num_players == 0: return

        start_index = self.game.current_player_index
        for i in range(1, num_players + 1):
            next_index = (start_index + i) % num_players
            next_player_id = all_player_ids[next_index]
            player = self.game.players[next_player_id]
            if player.can_act():
                self.game.current_player_index = next_index
                print(f"Next turn: {player.name}")
                return
        
    def game_loop(self):
        """The main server-side game logic loop."""
        while True:
            time.sleep(0.5)

            if self.game.game_state in [GameState.WAITING, GameState.GAME_OVER]:
                pass # Wait for client action to start
            
            else: # Active game states
                # Check for end of hand by folding
                players_in_hand = [p for p in self.game.players.values() if not p.is_folded]
                if len(players_in_hand) == 1:
                    print(f"Hand ended. Winner by fold: {players_in_hand[0].name}")
                    winnings_map = self.game.determine_winners() # This will assign the pot
                    self.handle_game_result(winnings_map)
                    time.sleep(5)
                    self.game.start_new_hand()
                    self.broadcast_game_state()
                    continue

                # Check for end of betting (all remaining players are all-in)
                players_can_act = [p for p in players_in_hand if not p.is_all_in]
                if not players_can_act and self.game.game_state != GameState.AWAITING_SHOWDOWN:
                    print("All remaining players are all-in. Advancing to the end.")
                    while self.game.game_state not in [GameState.AWAITING_SHOWDOWN, GameState.GAME_OVER]:
                        self.game.advance_to_next_street()
                    self.broadcast_game_state()
                
                # Handle showdown transition
                if self.game.game_state == GameState.AWAITING_SHOWDOWN:
                    if self.game.check_all_revealed():
                        print("All players revealed. Proceeding to showdown.")
                        self.game.game_state = GameState.SHOWDOWN
                        self.broadcast_game_state()
                
                if self.game.game_state == GameState.SHOWDOWN:
                    print("Executing showdown...")
                    winnings_map = self.game.determine_winners()
                    self.handle_game_result(winnings_map)
                    time.sleep(10) # Time for clients to see results
                    self.game.start_new_hand()
                    self.broadcast_game_state()

    def handle_game_result(self, winnings_map: Dict[str, int]):
        """Broadcasts the game result to all clients."""
        winners = list(winnings_map.keys())
        winning_hand_type = "Unknown"
        if winners:
            first_winner_id = winners[0]
            if first_winner_id in self.game.players:
                winner_player = self.game.players[first_winner_id]
                hand_rank = self.game.evaluate_hand(winner_player.cards, self.game.community_cards)[0]
                hand_rank_map = {9: "Royal Flush", 8: "Straight Flush", 7: "Four of a Kind", 6: "Full House", 5: "Flush", 4: "Straight", 3: "Three of a Kind", 2: "Two Pair", 1: "One Pair", 0: "High Card"}
                winning_hand_type = hand_rank_map.get(hand_rank, "Unknown")
            winner_names = [self.game.players[pid].name for pid in winners if pid in self.game.players]
        else:
            winner_names = ["No one"]
            
        result_message = {
            'type': 'game_result',
            'winners': winners,
            'winnings_map': winnings_map,
            'winning_hand_type': winning_hand_type,
            'message': f"Winner(s): {', '.join(winner_names)}"
        }
        self.broadcast(json.dumps(result_message).encode('utf-8') + b'\n')
        self.broadcast_game_state() # Show final table state

    def send_to_client(self, player_id: str, message: dict):
        """Sends a JSON message to a specific client."""
        if player_id in self.clients:
            try:
                self.clients[player_id].sendall(json.dumps(message).encode('utf-8') + b'\n')
            except Exception as e:
                print(f"Error sending message to client {player_id}: {e}")

    def broadcast_game_state(self):
        """Broadcasts the game state to all clients, customized for each."""
        for player_id in list(self.clients.keys()):
            game_state_for_player = self.game.get_game_state(player_id)
            message = {'type': 'game_update', 'data': game_state_for_player}
            self.send_to_client(player_id, message)
    
    def broadcast(self, raw_message: bytes):
        """Broadcasts a raw byte message to all clients."""
        for player_id in list(self.clients.keys()):
            try:
                self.clients[player_id].sendall(raw_message)
            except Exception as e:
                print(f"Error broadcasting to {player_id}: {e}")

if __name__ == '__main__':
    server = PokerServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.server_socket.close()