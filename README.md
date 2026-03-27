# ⬡ Red IA — Decentralized AI Network

> The Bitcoin of AI. Every computation makes the network smarter.

[![Live Network](https://img.shields.io/badge/network-live-brightgreen)](http://146.190.120.75:8080)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)

**[Try the chat →](http://146.190.120.75:8080)** &nbsp;|&nbsp; **[Read the whitepaper →](WHITEPAPER.md)** &nbsp;|&nbsp; **[Run a node ↓](#run-a-node)**

---

## What is Red IA?

Red IA is a peer-to-peer network where nodes contribute real compute for AI inference — and earn native tokens for doing so.

Unlike Bitcoin, where miners perform useless hash computation, every computation on Red IA **is the product itself**: intelligence.

```
Bitcoin:   Miners waste electricity on SHA256 → earn BTC → network gets secure
Red IA:    Nodes run AI models on real prompts → earn tokens → AI gets smarter
```

No central server. No GPU cloud. Just people contributing their hardware and getting rewarded for it.

---

## How it works

```
User sends a prompt
        ↓
Coordinator selected via VRF (provably fair, unpredictable)
        ↓
3 worker nodes independently run Llama 3.2
        ↓
Each sends hash(response) before revealing → no copying possible
        ↓
Majority response wins → tokens distributed to workers
        ↓
Conversation evaluated by Llama arbiter → enters training pool
```

Every participant earns:

| Role | Reward |
|------|--------|
| Worker node | 60% of request tokens |
| Coordinator | 20% of request tokens |
| Arbiter | 10% of request tokens |
| All active nodes | 9% pool share |
| Burned | 1% permanent deflation |

---

## Run a node

**Requirements:** Mac or Linux, 8GB RAM, ~2GB disk for the model.

```bash
# 1. Clone and install
git clone https://github.com/jesusneri1024/red_ia.git
cd red_ia
bash install.sh

# 2. Join the network
./start.sh

# 3. Check your points
./start.sh --status
```

That's it. Your node will connect to the seed, download Llama 3.2, and start earning points for every prompt it processes.

---

## Use the API

Red IA is **OpenAI-compatible**. Switch with 2 lines of code:

```python
from openai import OpenAI

# Before (OpenAI)
# client = OpenAI(api_key="sk-...", base_url="https://api.openai.com/v1")

# After (Red IA) — change only these 2 lines
client = OpenAI(
    api_key="your-token",
    base_url="http://146.190.120.75:8080/v1"
)

# Everything else stays the same
response = client.chat.completions.create(
    model="red-ia",
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)
```

Or run your own API gateway:

```bash
./start.sh --api
# API available at http://localhost:8080/v1
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Public Users                    │
│           http://146.190.120.75:8080             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│            VPS — Coordinator Gateway             │
│  seed.py (peer discovery)  +  api.py (HTTP)      │
│              146.190.120.75                      │
└──────┬──────────────┬──────────────┬────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌───▼────────┐
│   Node A    │ │   Node B   │ │   Node C   │
│  Your Mac   │ │  Laptop B  │ │  Laptop C  │
│  Llama 3.2  │ │  Llama 3.2 │ │  Llama 3.2 │
└─────────────┘ └────────────┘ └────────────┘
```

---

## Tokenomics

**Supply:** 1,000,000,000 tokens — fixed maximum

| Allocation | % |
|-----------|---|
| Node miners (continuous emission) | 40% |
| Founders (2-year vesting) | 20% |
| Treasury / development | 15% |
| Early adopters airdrop | 15% |
| Ecosystem reserve | 10% |

**1% of every request is burned permanently** — deflation grows with usage.

Currently in **Phase 1**: points system. Points convert to tokens at TGE (month 6).

---

## Network status

Live seed node: `146.190.120.75:7000`

Check status:
```bash
echo '{"type":"STATUS"}' | nc 146.190.120.75 7000
```

---

## Project structure

```
red_ia/
├── node.py          # Main P2P node — coordinator + worker logic
├── network.py       # TCP server + peer connections
├── seed.py          # Lightweight discovery node (runs on VPS)
├── api.py           # OpenAI-compatible HTTP gateway
├── inference.py     # Llama inference + commitment scheme
├── vrf.py           # Verifiable Random Function for coordinator election
├── identity.py      # Ed25519 keypair — persistent node identity
├── ledger.py        # Distributed points/token ledger
├── data_pool.py     # Conversation pool for training data
├── arbiter.py       # Llama-based quality evaluation
├── main.py          # CLI entry point
├── install.sh       # One-command node installer
├── start.sh         # Node launcher (node / api / prompt / status modes)
├── instalar_seed.sh # VPS seed node installer
├── static/
│   └── index.html   # Landing page + web chat
└── config.json      # Network configuration
```

---

## Roadmap

- ✅ P2P inference with commitment + consensus
- ✅ VRF coordinator rotation
- ✅ OpenAI-compatible API
- ✅ Live seed node + web chat
- ✅ Auto-reconnection
- 🔄 Token/wallet system + pay-per-request
- 🔄 Ad network integration (earn tokens by watching ads)
- ⏳ Federated fine-tuning (FedProx + Krum)
- ⏳ IPFS model storage
- ⏳ Pipeline parallelism for 70B+ models
- ⏳ DEX listing + USDT conversion

---

## Why run a node?

- **Earn tokens** for every prompt your node processes
- **Early adopter airdrop** — 15% of total supply to first nodes
- **Points accumulate now** → convert to tokens at TGE
- **The network grows** → tokens become more valuable
- **2GB RAM model** — runs on any modern laptop

---

## License

MIT — free to use, modify, and distribute.

---

*Red IA — Decentralized AI Network | v0.1.0 Testnet | March 2026*
