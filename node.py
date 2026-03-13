import json
import hashlib
import time
import threading
import os
import requests
import logging
from datetime import datetime
from tkinter import *
from tkinter import messagebox, scrolledtext
from flask import Flask, request, jsonify

# CONFIG
try:
    NODE_PORT = int(open("port.txt").read().strip())
    PEERS = json.load(open("peers.json"))
except Exception as e:
    print("ERROR: Missing port.txt or peers.json →", e)
    exit(1)

DATA_FILE = "data.json"
CHAIN_FILE = "chain.txt"
PENDING_FILE = "pending.json"

app = Flask(__name__)

# FILE LOCKS
chain_lock = threading.Lock()
data_lock = threading.Lock()
pending_lock = threading.Lock()

# LOGGING
log_messages = []
log_lock = threading.Lock()

def setup_logging():
    """Configure logging with custom handler for GUI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    class GUILogHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            with log_lock:
                log_messages.append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': record.levelname,
                    'message': msg
                })
                if len(log_messages) > 500:
                    log_messages.pop(0)
    
    logging.getLogger().addHandler(GUILogHandler())
    return logging.getLogger(__name__)

logger = setup_logging()

def log_activity(category, message, source="local"):
    """Log activity with category"""
    logger.info(f"[{category}] {message} (source: {source})")

# BLOCKCHAIN
def hash_block(block):
    content = f"{block['timestamp']}{block['prev']}{block['data']}"
    return hashlib.sha256(content.encode()).hexdigest()

def get_chain():
    """Load entire blockchain from file"""
    with chain_lock:
        if not os.path.exists(CHAIN_FILE):
            return []
        with open(CHAIN_FILE, "r") as f:
            return [json.loads(line) for line in f if line.strip()]

def get_last_hash():
    """Get hash of last block"""
    chain = get_chain()
    return chain[-1]["hash"] if chain else "0"

def add_to_chain(block):
    """Append block to chain file"""
    with chain_lock:
        with open(CHAIN_FILE, "a") as f:
            f.write(json.dumps(block) + "\n")
        log_activity("CHAIN", f"Block {block['hash'][:8]}... added", "local")

def block_exists(hash_val):
    """Check if block already in chain"""
    chain = get_chain()
    return any(b["hash"] == hash_val for b in chain)

# DATA MANAGEMENT
def get_data():
    """Load current ledger state"""
    with data_lock:
        if not os.path.exists(DATA_FILE):
            default = {"example_data1": 0, "example_data2": 0, "example_data3": 0, "example_data4": 0}
            save_data(default)
            return default
        with open(DATA_FILE, "r") as f:
            return json.load(f)

def save_data(data):
    """Save ledger state"""
    with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

def get_pending():
    """Load pending transactions"""
    with pending_lock:
        if not os.path.exists(PENDING_FILE):
            return []
        with open(PENDING_FILE, "r") as f:
            return json.load(f)

def save_pending(pending):
    """Save pending transactions"""
    with pending_lock:
        with open(PENDING_FILE, "w") as f:
            json.dump(pending, f, indent=2)

def add_pending(block):
    """Add block to pending queue"""
    with pending_lock:
        pending = get_pending()
        if not any(p["hash"] == block["hash"] for p in pending):
            pending.append(block)
            save_pending(pending)
        log_activity("PENDING", f"Transaction queued: {block['hash'][:8]}...", "local")

def clear_pending():
    """Clear pending transactions after sync"""
    with pending_lock:
        save_pending([])
    log_activity("PENDING", "Cleared pending queue", "local")

# NETWORK
def check_peers():
    """Check how many peers are online"""
    online = 0
    for peer in PEERS:
        try:
            r = requests.get(f"{peer}/ping", timeout=2)
            if r.status_code == 200:
                online += 1
        except:
            pass
    return online

def can_sync():
    """Check if we can connect to >50% of peers"""
    total = len(PEERS)
    if total == 0:
        return True
    online = check_peers()
    return online > (total / 2)

def broadcast_block(block):
    """Send block to all peers"""
    for peer in PEERS:
        try:
            requests.post(f"{peer}/block", json=block, timeout=3)
            log_activity("BROADCAST", f"Block {block['hash'][:8]}... sent", peer)
        except Exception as e:
            log_activity("BROADCAST", f"Failed to send to peer", peer)

def sync_from_peers():
    """Sync blockchain from peers"""
    for peer in PEERS:
        try:
            r = requests.get(f"{peer}/chain", timeout=5)
            if r.status_code == 200:
                peer_chain = r.json()["chain"]
                local_chain = get_chain()

                # If peer has longer valid chain, adopt it
                if len(peer_chain) > len(local_chain):
                    log_activity("SYNC", f"Syncing from peer (blocks: {len(peer_chain)})", peer)
                    # Rebuild chain
                    if os.path.exists(CHAIN_FILE):
                        os.remove(CHAIN_FILE)

                    data = {"example_data1": 0, "example_data2": 0, "example_data3": 10000, "example_data4": 0}
                    for block in peer_chain:
                        add_to_chain(block)
                        for k, v in block["data"].items():
                            data[k] = data.get(k, 0) + v
                    save_data(data)
                    log_activity("SYNC", "Sync completed", peer)
                    return True
        except Exception as e:
            log_activity("SYNC", f"Failed to sync from peer", peer)
    return False

# BLOCK OPERATIONS
def create_block(delta):
    """Create new block with transaction"""
    block = {
        "timestamp": time.time(),
        "prev": get_last_hash(),
        "data": delta
    }
    block["hash"] = hash_block(block)
    log_activity("CREATE", f"Block created: {block['hash'][:8]}...", "local")
    return block

def apply_block(block):
    """Apply block to local chain"""
    with chain_lock:
        # Validate hash
        if hash_block(block) != block["hash"]:
            log_activity("VALIDATION", f"Block hash invalid: {block['hash'][:8]}...", "local")
            return False

        # Check if already exists
        if block_exists(block["hash"]):
            log_activity("VALIDATION", f"Block already exists: {block['hash'][:8]}...", "local")
            return False

        # Add to chain
        add_to_chain(block)

        # Update data
        data = get_data()
        for k, v in block["data"].items():
            data[k] = data.get(k, 0) + v
        save_data(data)

        log_activity("VALIDATION", f"Block validated and applied: {block['hash'][:8]}...", "local")
        return True

def process_transaction(delta):
    """Process new transaction"""
    block = create_block(delta)

    if can_sync():
        # Network is available - broadcast immediately
        log_activity("TX", f"Processing transaction (network available)", "local")
        apply_block(block)
        broadcast_block(block)
    else:
        # Network unavailable - store as pending
        log_activity("TX", f"Processing transaction (network unavailable)", "local")
        add_pending(block)

# SYNC WORKER
def sync_worker():
    """Background sync worker"""
    while True:
        if can_sync():
            # Sync chain from peers
            sync_from_peers()

            # Process pending transactions
            pending = get_pending()
            if pending:
                log_activity("SYNC", f"Processing {len(pending)} pending blocks", "local")
                for block in pending:
                    if not block_exists(block["hash"]):
                        apply_block(block)
                        broadcast_block(block)
                clear_pending()

        time.sleep(5)

# FLASK API
@app.route("/ping", methods=["GET"])
def ping():
    return "OK", 200

@app.route("/block", methods=["POST"])
def receive_block():
    block = request.get_json()
    if block:
        source = request.remote_addr
        log_activity("RECEIVE", f"Block received: {block['hash'][:8]}...", f"http://{source}")
        apply_block(block)
    return "OK", 200

@app.route("/chain", methods=["GET"])
def get_chain_api():
    chain = get_chain()
    return jsonify({"length": len(chain), "chain": chain})

# GUI
class LedgerGUI:
    def __init__(self):
        self.root = Tk()
        self.root.title(f"Blockchain Ledger - Port {NODE_PORT}")
        self.root.geometry("700x600")
        self.root.configure(bg="#1a1a2e")

        # Title
        Label(self.root, text="BLOCKCHAIN LEDGER",
              font=("Arial", 28, "bold"), fg="#00ff88", bg="#1a1a2e").pack(pady=20)

        # Status
        self.status = Label(self.root, text="Connecting...",
                           font=("Arial", 11), fg="#ffaa00", bg="#1a1a2e")
        self.status.pack(pady=5)

        # Log Button
        Button(self.root, text="📋 View Activity Logs", font=("Arial", 11, "bold"),
               bg="#2d3250", fg="#00aaff", command=self.show_logs, width=20).pack(pady=5)

        # Data Frame
        data_frame = Frame(self.root, bg="#1a1a2e")
        data_frame.pack(pady=20)

        self.fields = {}
        items = [
            ("example_data1", "example_data1", "#00ff88"),
            ("example_data2", "example_data2", "#ff4444"),
            ("example_data3", "example_data3", "#00aaff"),
            ("example_data4", "example_data4", "#ffaa00")
        ]

        for i, (label, key, color) in enumerate(items):
            # Label
            Label(data_frame, text=f"{label}:", font=("Arial", 14, "bold"),
                  fg="#ffffff", bg="#1a1a2e", width=10, anchor="e").grid(row=i, column=0, padx=10, pady=15)

            # Value
            val = StringVar(value="0")
            Label(data_frame, textvariable=val, font=("Arial", 20, "bold"),
                  fg=color, bg="#16213e", width=15, relief="solid", bd=2).grid(row=i, column=1, pady=15, padx=10)
            self.fields[key] = val

            # Buttons
            Button(data_frame, text="➖", font=("Arial", 14), width=3,
                   bg="#2d3250", fg="#ff4444", command=lambda k=key: self.modify(k, -1)).grid(row=i, column=2, padx=5)
            Button(data_frame, text="➕", font=("Arial", 14), width=3,
                   bg="#2d3250", fg="#00ff88", command=lambda k=key: self.modify(k, 1)).grid(row=i, column=3, padx=5)

        # Info
        self.info = Label(self.root, text="", font=("Arial", 10),
                         fg="#aaaaaa", bg="#1a1a2e")
        self.info.pack(pady=10)

        # Start update loop
        self.update_display()

    def show_logs(self):
        """Open log viewer window"""
        log_window = Toplevel(self.root)
        log_window.title("Activity Logs")
        log_window.geometry("700x500")
        log_window.configure(bg="#16213e")
        log_window.transient(self.root)

        # Header
        Label(log_window, text="BLOCKCHAIN ACTIVITY LOGS",
              font=("Arial", 16, "bold"), fg="#00ff88", bg="#16213e").pack(pady=10)

        # Log text area with scrollbar
        text_frame = Frame(log_window, bg="#0d1117")
        text_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        scrollbar = Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        log_text = scrolledtext.ScrolledText(text_frame, wrap=WORD, font=("Consolas", 10),
                                              bg="#0d1117", fg="#c9d1d9",
                                              yscrollcommand=scrollbar.set)
        log_text.pack(fill=BOTH, expand=True)
        scrollbar.config(command=log_text.yview)

        # Color tags for log levels
        log_text.tag_configure("INFO", foreground="#58a6ff")
        log_text.tag_configure("WARNING", foreground="#d29922")
        log_text.tag_configure("ERROR", foreground="#f85149")
        log_text.tag_configure("DEBUG", foreground="#8b949e")
        log_text.tag_configure("CRITICAL", foreground="#f85149")

        # Load logs
        def refresh_logs():
            log_text.delete(1.0, END)
            with log_lock:
                for log in log_messages:
                    level = log['level']
                    line = f"[{log['time']}] [{level:8}] {log['message']}\n"
                    log_text.insert(END, line, level)
            log_text.see(END)
            log_window.after(1000, refresh_logs)

        refresh_logs()

        # Close button
        Button(log_window, text="Close", font=("Arial", 11),
               bg="#2d3250", fg="#ffffff", command=log_window.destroy).pack(pady=10)
    
    def modify(self, field, direction):
        """Show transaction dialog"""
        popup = Toplevel(self.root)
        popup.title(f"{'Add to' if direction > 0 else 'Subtract from'} {field.capitalize()}")
        popup.geometry("400x250")
        popup.configure(bg="#16213e")
        popup.transient(self.root)
        popup.grab_set()
        
        Label(popup, text=f"Enter amount:", font=("Arial", 14),
              fg="#ffffff", bg="#16213e").pack(pady=30)
        
        entry = Entry(popup, font=("Arial", 16), justify="center", width=15)
        entry.pack(pady=10)
        entry.insert(0, "1000")
        entry.focus()
        
        def confirm():
            try:
                amount = int(entry.get())
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be positive")
                    return
                
                delta = {field: amount * direction}
                process_transaction(delta)
                
                if can_sync():
                    messagebox.showinfo("Success", f"Transaction broadcast!\n{field}: {amount * direction:+}")
                else:
                    messagebox.showwarning("Pending", f"Network unavailable.\nTransaction saved as pending.")
                
                popup.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number")
        
        Button(popup, text="Confirm", command=confirm, font=("Arial", 13, "bold"),
               bg="#00ff88", fg="#000000", width=15).pack(pady=20)
    
    def update_display(self):
        """Update GUI every second"""
        # Update values
        data = get_data()
        for key, var in self.fields.items():
            var.set(f"{data.get(key, 0):,}")
        
        # Update status
        chain = get_chain()
        pending = get_pending()
        online = check_peers()
        total = len(PEERS)
        
        if can_sync():
            status_text = f"🟢 ONLINE • {online}/{total} Peers"
            status_color = "#00ff88"
        else:
            status_text = f"🔴 OFFLINE • {online}/{total} Peers"
            status_color = "#ff4444"
        
        self.status.config(text=status_text, fg=status_color)
        
        # Update info
        info_text = f"Blocks: {len(chain)} • Pending: {len(pending)} • Port: {NODE_PORT}"
        self.info.config(text=info_text)
        
        # Schedule next update
        self.root.after(1000, self.update_display)
    
    def run(self):
        self.root.mainloop()

# START
if __name__ == "__main__":
    # Start Flask API
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=NODE_PORT, 
                     use_reloader=False, debug=False), daemon=True).start()
    
    # Start sync worker
    threading.Thread(target=sync_worker, daemon=True).start()
    
    # Wait for Flask to start
    time.sleep(1)
    
    # Start GUI
    LedgerGUI().run()
