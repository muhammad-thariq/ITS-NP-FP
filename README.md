
## The Good Poker: The party game for many

A Github Repository for Network Programming IUP 2024/2025 Final Project

## Members:

| Name           | NRP        | 
| ---            | ---        | 
| Omar Shinichi Ghifari	| 5025231004 |
| Muiz Surya Fata | 5025231005 |
| Alfa Radithya Fanany | 5025231008 | 
| Muhammad Iqbal Shafarel | 5025231080 |
| Ali Ridho | 5025231162 |
| Muhammad Thariq Darobi | 5025231163 |

## Description

For our final project, we’re making a simple server and client-based poker game simulation using Transmission Control Protocol (TCP) sockets for all network communication. TCP was chosen to ensure reliable, ordered, and error-checked delivery of game-critical information between the server and all connected clients. This is crucial for a poker game where the integrity of game state (e.g., card dealing, player actions, chip counts, pot size) must be maintained consistently across all participants.

## How to Run:

1. Download all necessary files from the Github (assets, poker_server, poker_client)
2. Run server and client in a different terminal
3. For Client:
    1. In the login page, change "Server IP" to the actual server's IP
        1. If playing locally with 1 device, keep the "Server IP" as "localhost"
        2. If the server is in a different device, change the IP to the server's IP

        (note: make sure all device is connected to the same wifi)
    2. Enter your Username, and click on "Connect"
4. After all player has joined, one player then could click on "Start New Hand"
5. Game on, enjoy!
