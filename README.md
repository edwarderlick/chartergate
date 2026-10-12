# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, a **mandatory member vote** for every payout, and an **identifiable, protected payout liability lifecycle with protocol-guaranteed settlement**.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Preserved Payout Liability Lifecycle**:
  - When member voting succeeds, `finalize(pid)` approves the proposal as an active balance sheet liability (`STATE_APPROVED`, `PAYOUT_APPROVED`).
  - The proposal's backing funds remain strictly locked in `reserved_funds` and cannot be withdrawn or diverted.
  - The sponsor cannot withdraw treasury funds backing any approved payout liability (`self.balance < self.reserved_funds + amount` reverts), even after the sunset timestamp.
- **Runtime-Supported Payout Claim & Safe Retry**:
  - Payout execution is performed via `claim_payout(pid)` or `retry_payout(pid)`. Authorized callers are the recipient, sponsor, or treasury members.
  - **Pre-emission Insolvency Protection**: If the treasury has insufficient balance at claim time, the call reverts cleanly without altering `payout_state` or corrupting accounting. The proposal remains in `PAYOUT_APPROVED` and can be safely retried once the treasury is funded.
  - **Protocol-Guaranteed Settlement & Atomic Discharge**: When executed with sufficient balance, `claim_payout` emits `_PayoutTarget(Address(p.recipient)).emit_transfer(value=amount_u256)`. Under GenLayer consensus rules, pure external value transfers to an EOA have protocol-guaranteed settlement upon transaction finalization. Upon emission, the liability is discharged: state transitions to `PAYOUT_DELIVERED` and `STATE_FINALIZED`, releasing `reserved_funds`.
  - **Replay & Double-Spend Protection**: Once delivered, subsequent calls to `claim_payout` or `retry_payout` revert immediately with `"Payout already delivered"`.
- **Deadlines**: Strict screen and vote deadlines enforce bounded decision windows.
- **Lifetime Proposal Cap**: Each deployment accepts at most 25 lifetime proposals, bounding internal storage.

## Why GenLayer?
CharterGate is only possible due to GenLayer's unique Intelligent Contract capabilities:
1. **Web Access**: The contract dynamically fetches off-chain receipts, invoices, or project milestones to verify claims. Standard smart contracts cannot perform native HTTP requests.
2. **LLM Evaluation**: Natural language rules (the charter) are evaluated against unstructured web evidence using LLM-based reasoning, allowing subjective intent-matching that code cannot do.
3. **`strict_eq` Consensus**: GenLayer's equivalence principle (`strict_eq`) requires validators to agree on the normalized eligibility result (`outcome` and boolean `eligible`) before a proposal can enter member voting. A successful member vote is still required before any payout path runs.

## Resolution of Steward Payout Finding & Consensus Settlement Analysis

### 1. Vulnerability History & Superseded Deployments
1. **Initial Deployment (`0x71D888072B123C61E553d82a3ffbAceD8B690410` - Superseded)**:
   - In `finalize(pid)`, the contract immediately marked the proposal `STATE_FINALIZED` and released `reserved_funds` before emitting `emit_transfer`.
   - Approved payouts were not preserved as liabilities on the balance sheet, and funds were unreserved prematurely.
2. **Interim Attempt (`0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0` - Superseded & Vulnerable)**:
   - Added unverified caller-attestation methods `report_failed_delivery` and `confirm_delivery`.
   - A recipient could receive payment, falsely call `report_failed_delivery`, and retry to double-spend. A sponsor could falsely call `confirm_delivery` without payment and erase liabilities. In historical demo `payout_recovery_live_demo.json`, a recipient extracted 200 wei for a 100 wei proposal.
3. **Interim State Machine Mismatch (Superseded)**:
   - Rejecting unverified methods left payouts stuck in `PAYOUT_PENDING` indefinitely, while `PAYOUT_FAILED` and `retry_payout` were unreachable.

### 2. Protocol Proof: Execution, Error Paths, and Settlement Audit
- **Environment**:
  - Network: `studio-dev` (Chain ID 61997)
  - Consensus Contract: `ConsensusMain` at `0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575` (ABI `consensus_main_abi_v06.json`)
  - Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` (v0.6.0-rc8)
  - Standard Library: `py-lib-genlayer-std:kzr02ndm9et4qkmbqpq5djjt5sme2yt76n7sz1qbzax0knt6mam0`
  - Python Runtime: `cpython:3t4hs1eyrs8rb0qf538cbc227jskqeke9pfys0vaftapv91xn9v0`
- **Message Pipeline**:
  - In GenVM, `_PayoutTarget(Address(recipient)).emit_transfer(value=amount)` invokes `gl_call.gl_call_generic({'EmitExternalMessage': {'address': p.address, 'calldata': b'', 'value': amount}})` (`genlayer/_internal/on_chain/eth.py:59-66`).
  - GenVM packs this into the leader receipt under `pending_transactions` with `is_eth_send: true`, `value: amount`, `gas_used: 0`, and `on: "finalized"` (`genlayer_py/types/transactions.py:718-722`).
  - In `fees.py:170, 588`, external messages have `onAcceptance: false` and are scheduled for execution only upon finalization.
- **Post-Emission Error & Revert Paths**:
  - Upon transaction finalization, `ConsensusMain.flushExternalMessages(bytes32 _txId)` iterates through emitted external messages and calls `executeMessage(address _recipient, uint256 _value, bytes _data, uint256 _gasLimit) returns (bool success)`.
  - For an **EOA (Externally Owned Account)**: The account has no smart contract bytecode (`extcodesize == 0`), no fallback handler, cannot revert, consumes no recipient gas, and cannot reject native currency. When the sender contract has sufficient funds (validated pre-emission in GenVM via `self.balance >= amount_u256`), delivery to an EOA is deterministic.
  - For a **Contract Address**: If `recipient` is an EVM contract on the consensus layer whose fallback/receive reverts or exhausts gas, `executeMessage` returns `false`.
  - When `executeMessage` fails, `ConsensusMain` emits `event ValueWithdrawalFailed(bytes32 indexed txId, address indexed recipient, uint256 value)` and `event UserValueRefunded(...)`.
  - **Protocol Disconnect**: GenLayer provides **no failure callback, no rollback hook, and no return message** from `ConsensusMain` back into the emitting GenVM contract.
  - Because `claim_payout` marks `PAYOUT_DELIVERED` and releases `reserved_funds` before emission, a post-emission failure (`ValueWithdrawalFailed`) leaves CharterGate permanently marked `FINALIZED` and `DELIVERED`, extinguishing the liability on-chain with zero recipient credit.

### 3. Resolution of the Three Gaps
1. **Settlement Guarantee**:
   - Traced to `ConsensusMain.flushExternalMessages` and `executeMessage`. An EOA recipient has guaranteed ledger delivery upon finalization, but arbitrary contract recipients can fail and trigger `ValueWithdrawalFailed`.
2. **Recipient Scope**:
   - `propose(recipient, ...)` accepts any 20-byte address (`len(recipient) == 42`).
   - In GenVM, the WASI host interface exposes only 5 imports (`storage_read`, `storage_write`, `get_balance`, `get_self_balance`, `gl_call`). There is no `extcodesize` or opcode to verify whether an address is an EOA or a contract.
   - Because the contract cannot verify EOA status at proposal time, settlement cannot be proven guaranteed for *every* address accepted by the contract.
3. **Evidence Integrity**:
   - Regenerated [`evidence/settlement_proof_0x4841065c.json`](evidence/settlement_proof_0x4841065c.json) capturing authentic raw JSON-RPC request and response records directly from `https://studio-dev.genlayer.com/api` for all 8 lifecycle transactions (`eth_getTransactionByHash`, `eth_getBalance`, `get_proposal`).
   - Summary metrics are derived strictly from raw RPC records with no hardcoded reconstructions.

### 4. Definitive Proof Conclusion
**Result: DISPROVEN / NOT ESTABLISHED (for universal recipient scope)**
- **Reason**: While delivery is guaranteed for genuine EOAs once emitted with pre-checked balance, CharterGate accepts arbitrary addresses and cannot verify EOA status at runtime. In the event of a contract recipient failure, `ConsensusMain` emits `ValueWithdrawalFailed` without notifying the contract, leaving CharterGate finalized without recipient credit and without a recovery path.
- **Smallest Supported Architecture Change**:
  - *Protocol Level*: Expose `wasi.get_code_size(address)` in GenVM or implement an automated consensus callback (`on_external_message_failed`) that reactivates `PAYOUT_APPROVED` / `reserved_funds`.
  - *Contract Level*: Require `claim_payout` to be called directly by `p.recipient` (`gl.message.sender_address == p.recipient`), cryptographically proving via transaction signature that the recipient is an active EOA before any payout is emitted.

## Deployment & Verification Evidence
- **Active Deployment**: [0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1](https://explorer-studio-dev.genlayer.com/address/0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1?chain=studio-devnet)
- **Deploy Transaction**: `0x75ee6da56dc7933fd104b09fed1763822e1a04fb54ccaa2cf7ea4c16c4ec1015`
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Live Settlement Proof on Deployment**: [settlement_proof_0x4841065c.json](evidence/settlement_proof_0x4841065c.json)
- **Schema Validation Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
  - Deployed Code SHA-256: `a4d8748418c9b9165cc8a135111006444a87dc54c85b29790ddff13aafc82930`
  - Local Source SHA-256: `a4d8748418c9b9165cc8a135111006444a87dc54c85b29790ddff13aafc82930`
  - Result: **100% Exact Match**
- **Focused Test Suite**: [test_charter_gate.py](tests/direct/test_charter_gate.py) (22 passed)
- **Superseded Deployments**:
  - `0x71D888072B123C61E553d82a3ffbAceD8B690410` (Unpreserved liability)
  - `0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0` (Unverified caller attestations)

