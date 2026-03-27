# Red IA — Whitepaper v0.1

**The Bitcoin of AI: A Decentralized P2P Network for Artificial Intelligence**

---

## Abstract

Red IA is a peer-to-peer network where nodes contribute real compute for AI inference and training — and get rewarded with native tokens for doing so. Unlike Bitcoin, where miners perform useless hash computation, every computation on Red IA is the product itself: intelligence.

The network runs on commodity hardware. Any laptop with 8GB RAM can participate. As more nodes join, the network becomes faster, smarter, and more valuable. The model improves continuously through federated learning across all participating nodes.

No central server. No corporate control. The protocol is the law.

---

## 1. The Problem

The AI industry is dominated by a handful of companies controlling massive GPU clusters. Access to powerful AI requires:

- Paying OpenAI, Anthropic, or Google per API call
- Trusting a single point of failure
- Having no ownership over the model or its improvements
- Contributing data that improves models others monetize

This creates a fundamental imbalance: the people who use AI generate the data that trains it, but capture none of the value.

---

## 2. The Solution

Red IA flips this model:

```
Traditional AI:
  Users pay → Compute in centralized servers → Company profits

Red IA:
  Users pay with tokens → Distributed nodes compute → Nodes profit
  Users contribute data → Model improves → Users earn tokens
```

Every participant — node operators, data contributors, and users — owns a piece of what they build.

---

## 3. How It Works

### 3.1 Network Architecture

```
LAYER 1 — P2P Discovery
  Nodes find each other via seed nodes (TCP)
  Each node has a persistent Ed25519 keypair identity
  Bootstrap nodes enable new peers to join

LAYER 2 — Work Protocol
  Inference tasks distributed via coordinator rotation
  Commitment scheme prevents response copying
  Redundant execution validates correctness

LAYER 3 — Shared Model
  Model weights stored on IPFS (content-addressed)
  Model CID recorded in distributed ledger
  Any node can verify and download the latest version

LAYER 4 — Token Ledger
  Replicated across all nodes
  Cryptographically signed transactions
  Fully independent — no external blockchain required
```

### 3.2 Inference Protocol

When a user sends a prompt:

```
1. Coordinator selected via VRF (Verifiable Random Function)
2. Coordinator selects 3 worker nodes at random
3. Each worker runs the model (temperature=0, deterministic)
4. Each worker sends hash(response + nonce) — COMMITMENT
5. All commitments collected → workers reveal responses
6. Majority response wins → tokens distributed
7. Minority nodes penalized → deducted from balance
```

The commitment scheme ensures no node can copy another's response — each must independently run the model.

### 3.3 Coordinator Rotation via VRF

No fixed coordinator. Every round:

```
1. Each node computes: VRF = HMAC-SHA256(private_key, round_number)
2. VRF is broadcast and verifiable by all peers
3. Node with lowest VRF value becomes coordinator
4. Result is unpredictable but mathematically verifiable
```

No node can manipulate the election. No central authority needed.

### 3.4 Quality Arbitration

Every resolved conversation is evaluated by Llama running locally on each node:

```
Node receives conversation result
    ↓
Runs local Llama evaluation (temperature=0, deterministic)
    ↓
Score >= 0.7 → conversation enters training pool
Score < 0.7  → rejected
    ↓
Node earns ARBITRO points for evaluating
```

Llama is open source — any node can verify any score independently.

### 3.5 Federated Learning

Training happens locally. Raw data never leaves the node.

```
Node trains on local conversation pool
    ↓
Only gradients are shared (not raw data)
    ↓
FedProx aggregation handles heterogeneous hardware
    ↓
Krum aggregation rejects Byzantine gradients
    ↓
Model CID updated in ledger
```

FedProx was chosen over FedAvg because Red IA nodes have widely different hardware — a gaming laptop and a datacenter GPU must coexist. FedProx's proximal term keeps slow nodes from destabilizing convergence.

---

## 4. Token Economics

### 4.1 Supply

```
Total supply: 1,000,000,000 (1 billion) — fixed maximum
```

### 4.2 Initial Distribution

| Allocation | % | Notes |
|-----------|---|-------|
| Node miners | 40% | Continuous emission for work |
| Founders | 20% | 2-year vesting, monthly unlock |
| Treasury | 15% | Development and infrastructure |
| Early adopters | 15% | Airdrop to first nodes |
| Ecosystem reserve | 10% | Partnerships, liquidity |

### 4.3 Per-Request Distribution

Every time tokens are spent on inference:

| Recipient | % | Reason |
|-----------|---|--------|
| Workers | 60% | Ran the model |
| Coordinator | 20% | Orchestrated the round |
| Arbiters | 10% | Evaluated quality |
| All active nodes | 9% | Network participation |
| **Burn** | **1%** | **Permanent deflation** |

### 4.4 Burn Mechanism

1% of every request is burned permanently. As network usage grows, supply decreases — creating deflationary pressure that aligns node operators, token holders, and users.

### 4.5 Token Utility

| Use | Description |
|-----|-------------|
| Pay for inference | 1 request = X tokens |
| Queue priority | More tokens = better workers assigned |
| Model access | Advanced models require more tokens |
| Governance | Vote on model updates, parameters |
| Arbiter stake | Lock tokens to evaluate quality, earn more |

### 4.6 Bootstrap: Points Before Token

```
Phase 1 (months 0-6):   Points system — no token yet
                         Early contributors build reputation
Phase 2 (month 6+):     TGE — points convert to tokens at agreed ratio
                         Token has value day 1: working network exists
Phase 3 (month 12+):    DEX listing — market sets price
Phase 4:                USDT on-ramp — external users buy tokens
```

---

## 5. Revenue Model

### 5.1 API (Pay Per Request)

Developers pay per inference call — no monthly commitment:

| Tier | Price/request | Minimum |
|------|--------------|---------|
| Pay-as-you-go | $0.001 | $5 |
| Volume | $0.0005 | $50 |
| Enterprise | $0.0002 | $500 |

Red IA can price 3-5x below Groq because nodes provide their own hardware — no GPU server costs.

### 5.2 Advertising (Tokens for Attention)

Users watch an ad → receive tokens → use tokens for inference.
Advertisers pay USD → converted to tokens → distributed to users and nodes.

Inspired by Brave Browser's model, applied to AI access.

### 5.3 Revenue Flow

```
Advertiser pays $10 USD
    ↓
Converted to Red IA tokens
    ↓
80% → distributed to users (attention) + nodes (compute)
10% → treasury (development)
10% → burned (deflation)
```

---

## 6. Security

### 6.1 Threat Model

| Attack | Defense |
|--------|---------|
| **Sybil attack** | Minimum stake to participate + reputation history |
| **Model poisoning** | Krum aggregation rejects outlier gradients |
| **Free rider** | Commitment scheme + redundant execution |
| **Response copying** | Hash commitment before reveal |
| **Gradient inversion** | Federated Learning (gradients only) + Differential Privacy |
| **Eclipse attack** | Multiple mandatory peer connections + periodic rotation |

### 6.2 Slashing

Nodes that misbehave lose tokens:
- Wrong response in consensus → -5 points
- Failed validation challenge → lose stake
- Disconnecting mid-round → reputation penalty

---

## 7. Current State (v0.1 — Testnet)

**Working today:**

- ✅ P2P TCP network with Ed25519 node identity
- ✅ VRF-based coordinator rotation
- ✅ Commitment + reveal scheme for inference
- ✅ Redundant execution with majority consensus
- ✅ Distributed ledger (JSON-replicated)
- ✅ Seed node for peer discovery (live at 146.190.120.75)
- ✅ Llama 3.2 arbiter for conversation quality (0.0-1.0 score)
- ✅ Local conversation pool with training data export
- ✅ OpenAI-compatible API (`/v1/chat/completions`)
- ✅ Public landing page with web chat
- ✅ Auto-reconnection when nodes disconnect
- ✅ NAT traversal via persistent outbound connections
- ✅ Coordinator-only mode (VPS gateway without Ollama)

**In progress:**
- 🔄 Token/wallet system
- 🔄 Rate limiting + API keys
- 🔄 Ad network integration

**Planned:**
- ⏳ Fine-tuning with local conversation pools
- ⏳ IPFS model weight storage
- ⏳ Pipeline parallelism for large models (70B+)
- ⏳ DEX listing

---

## 8. Roadmap

### Phase 1 — Foundation ✅ (Complete)
P2P network, inference consensus, VRF coordination, seed node, API gateway, web interface.

### Phase 2 — Economics (Months 1-3)
Token/wallet system, API key management, pay-per-request billing, ad network integration, rate limiting.

### Phase 3 — Training (Months 3-6)
Federated learning with FedProx + Krum, training challenges, IPFS model storage, TGE (Token Generation Event).

### Phase 4 — Scale (Months 6-12)
Pipeline parallelism for 70B+ models, DEX listing, governance on-chain, node reputation system.

### Phase 5 — Autonomy (Month 12+)
Network's own model replaces Llama as arbiter. Full self-governance. No external dependencies.

---

## 9. Why This Will Work

**Technical moat:** The commitment + VRF system is live and working. Building a Byzantine-fault-tolerant AI inference network from scratch is hard — we've done it.

**Economic moat:** Nodes provide hardware. No GPU server costs. We can undercut every centralized competitor on price while paying node operators more than they'd earn anywhere else.

**Network effects:** Every new node makes the network faster and cheaper. Every new user generates training data that makes the model smarter. Growth compounds.

**Timing:** AI is at peak public interest. Decentralization is a proven narrative. The intersection of both is wide open.

---

## 10. Comparison

| | Red IA | Bittensor | Akash | OpenAI |
|--|--------|-----------|-------|--------|
| Decentralized | ✅ | ✅ | ✅ | ❌ |
| Own chain | ✅ | ✅ | ❌ | ❌ |
| Runs on laptops | ✅ | ⚠️ | ❌ | ❌ |
| OpenAI-compatible API | ✅ | ❌ | ❌ | ✅ |
| Federated training | ✅ | ⚠️ | ❌ | ❌ |
| Ad-based token earning | ✅ | ❌ | ❌ | ❌ |
| Live testnet | ✅ | ✅ | ✅ | ✅ |

---

## 11. The Philosophy

Artificial intelligence should belong to the people who build it, not the corporations who monetize it. Whoever contributes — hardware, time, or data — owns a proportional share of what that intelligence becomes.

This is not just a business. It is a different model for how collective intelligence can be organized.

---

## Links

- **Live network:** http://146.190.120.75:8080
- **Source code:** https://github.com/jesusneri1024/red_ia
- **Join as node:** `git clone https://github.com/jesusneri1024/red_ia.git && cd red_ia && bash install.sh`

---

*Red IA Whitepaper v0.1 — March 2026*
*Subject to change as the network evolves.*
