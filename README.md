# Simple Blockchain Showcase

A lightweight blockchain demonstration project built for a university cloud computing course. This project showcases fundamental blockchain concepts including distributed ledgers, peer-to-peer networking, consensus mechanisms, and transaction processing.

## Features

- **Distributed Ledger**: Each node maintains a copy of the blockchain and ledger state
- **Peer-to-Peer Network**: Nodes communicate and synchronize over HTTP
- **Consensus Mechanism**: Longest chain rule with majority peer validation (>50%)
- **Transaction Processing**: Create, validate, and broadcast transactions as blocks
- **Pending Queue**: Offline transactions are queued and synced when network is available
- **GUI Dashboard**: Real-time visualization of ledger state and network status
- **Activity Logging**: View all blockchain activities (requests, validation, sync) in real-time
- **Thread-Safe**: File locks prevent race conditions during concurrent access

## Tech Stack

- **Python 3** - Core blockchain logic
- **Flask** - REST API for peer communication
- **Tkinter** - Cross-platform GUI
- **SHA-256** - Block hashing

## Project Structure

```
simple-blockchain-showcase/
├── node.py          # Main blockchain node implementation
├── chain.txt        # Blockchain storage (one JSON block per line)
├── data.json        # Current ledger state
├── pending.json     # Pending transactions queue
├── peers.json       # Peer node addresses
├── port.txt         # This node's port number
└── README.md        # This file
```

## Quick Start

### Prerequisites

```bash
pip install flask requests
```

### Running a Node

1. Configure `port.txt` with your node's port (e.g., `5000`)
2. Configure `peers.json` with other node addresses
3. Run the node:

```bash
python node.py
```

### Multi-Node Setup

### Production Deployment (4 VMs)

This project was demonstrated across **4 separate VMs** to showcase real distributed blockchain behavior:

```
VM 1: 192.168.1.100:5000
VM 2: 192.168.1.101:5001
VM 3: 192.168.1.102:5002
VM 4: 192.168.1.103:5003
```

Each VM runs the same code with:
- `port.txt` - unique port per VM
- `peers.json` - addresses of the other 3 VMs

This setup demonstrates:
- Real network latency and partitioning
- True distributed consensus across machines
- Cross-machine block propagation
- Fault tolerance when VMs go offline

### Local Testing

For quick testing, run multiple instances with different ports on the same machine:

```bash
# Terminal 1 - Port 5000
echo "5000" > port.txt
python node.py

# Terminal 2 - Port 5001
echo "5001" > port.txt
python node.py
```

Update `peers.json` on each instance to include all other nodes.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check |
| `/block` | POST | Receive a new block from peer |
| `/chain` | GET | Return full blockchain |

## How It Works

### Block Structure

```json
{
  "timestamp": 1234567890.123,
  "prev": "previous_block_hash",
  "data": { "example_data1": 1000 },
  "hash": "sha256_hash_of_block"
}
```

### Transaction Flow

1. User modifies ledger value via GUI
2. Transaction is packaged into a block
3. If network available (>50% peers online): broadcast immediately
4. If offline: store in `pending.json` for later sync
5. Peers validate and apply block to their chain

### Consensus

- Nodes sync every 5 seconds
- Longer valid chains replace local chain
- Requires >50% peer connectivity for network operations

## Testing

Run the unit tests with pytest:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest test_node.py -v
```

Tests cover:
- Block hashing (deterministic, SHA-256 format)
- Chain operations (add, retrieve, existence check)
- Data operations (save, load, pending queue)
- Thread safety (concurrent access with locks)

## License

MIT
