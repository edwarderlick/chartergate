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

### The Finding & Vulnerability History
1. **Initial Deployment (`0x71D888072B123C61E553d82a3ffbAceD8B690410` - Superseded)**:
   - In `finalize(pid)`, the contract immediately marked the proposal `STATE_FINALIZED` and decremented `reserved_funds` before emitting `emit_transfer`.
   - The Steward correctly identified that approved payouts were not preserved as liabilities on the contract balance sheet, and funds were unreserved prematurely.
2. **Interim Attempt (`0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0` - Superseded & Unsafe)**:
   - Added `claim_payout`, `report_failed_delivery`, `confirm_delivery`, and `retry_payout`.
   - **Vulnerability**: `report_failed_delivery` and `confirm_delivery` trusted unverified caller assertions. A recipient could receive payment, falsely call `report_failed_delivery`, and retry to double-spend. A sponsor could falsely call `confirm_delivery` without payment and erase liabilities. The historical demo (`payout_recovery_live_demo.json`) demonstrated this flaw when a recipient was paid 200 wei for a 100 wei proposal.
3. **Interim State Machine Mismatch (Superseded)**:
   - Rejecting unverified methods caused `claim_payout` to leave payouts in `PAYOUT_PENDING` indefinitely, while `PAYOUT_FAILED` and `retry_payout` became unreachable.

### Exact Runtime & Consensus Settlement Proof on Studio-Dev
- **Runner**: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` (v0.6.0-rc8)
- **SDK**: `py-lib-genlayer-std:kzr02ndm9et4qkmbqpq5djjt5sme2yt76n7sz1qbzax0knt6mam0`
- **CPython**: `cpython:3t4hs1eyrs8rb0qf538cbc227jskqeke9pfys0vaftapv91xn9v0`
- **Protocol Settlement Guarantee**:
  - In GenLayer, sending value to an EOA is an **external message** (`is_eth_send: true`, `messageType: 0` in `IMessages.MessageType.External`).
  - As defined in protocol specifications and consensus accounting (`genlayer_py/transactions/fees.py:170`), external value transfers emit with `call_key: 0x0...0` and `on: "finalized"`.
  - An EOA has no smart contract bytecode, no fallback handler, cannot revert, cannot reject transfers, and cannot run out of gas during recipient handling.
  - During GenVM execution, balance sufficiency is strictly validated (`self.balance >= value`). If underfunded, GenVM aborts and the transaction reverts cleanly.
  - Upon consensus finalization (commit, reveal, appeal window close), the consensus state transition executes `pending_transactions` where `on == "finalized"`, permanently and directly crediting the recipient account balance on the ledger.
  - **Live Proof on Deployment `0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1`**:
    - Conducted full live lifecycle test on Proposal 0 with fresh recipient EOA `0xD085ad7f55050279162B1a3dc8AD04503b330c86` (initial balance: 0 wei).
    - Deposited 500 wei into CharterGate (TX `0xb3b53122faf4e3ced884e4258c2b3819c8aca2c18c9d6cfe9bff5d982fb3ddf4`).
    - Proposal 0 created for 100 wei (TX `0x84afebe2bef38ad938e59bd1d51c03137ad8ac188336fdf38ce28adaaff7329e`).
    - AI evidence screening approved with SUCCESS (TX `0x3fe9bd737b0774760208f43f5061da0866e2c8cd760b6916a13f8c37061aeecd`).
    - Member voted YES (TX `0xfbe57f7a5d33ecaba3fce3a450c3dc7b6c4bb4ea58127e6bfb20004e6b4cc936`).
    - Finalize approved proposal as protected liability: `STATE_APPROVED` (4), `PAYOUT_APPROVED` (1), `is_liability: true` (TX `0x69bc59afa7074c2b25c545ada633c92cd6dcf64e72f9456de961265e3b667a3e`).
    - Claim payout executed (TX `0xb02d6e8104779568b37346730dd62cf2e4606fe0c9a4766c8f5c7edc5e2d6ff0`).
    - Upon finalization, recipient balance increased from **0 wei to 100 wei**, and CharterGate balance decreased from **500 wei to 400 wei**.
    - Proposal transitioned to `STATE_FINALIZED` (7), `PAYOUT_DELIVERED` (2), `is_liability: false`.
    - Duplicate claim attempt reverted with `FINISHED_WITH_ERROR` (TX `0x618d2957b9e42e7712290edeb06560069029f53d4b28d07210220b8f9d60278e`), keeping recipient balance at 100 wei.
    - Retry payout attempt reverted with `FINISHED_WITH_ERROR` (TX `0x6c35fe1c53315c073305f196c002a035553efdbb2cded6361e2614df6a36e25d`), preventing any double-spending.
    - Full sanitized evidence recorded in [`settlement_proof_0x4841065c.json`](evidence/settlement_proof_0x4841065c.json).
- **Design Around the Guarantee**:
  - Because external value transfers to EOAs have protocol-guaranteed settlement upon finalization, post-emission delivery failure is impossible.
  - Unreachable retry states (`PAYOUT_PENDING` limbo, `PAYOUT_FAILED`, unverified `report_failed_delivery` and `confirm_delivery`) have been completely removed.
  - Approved proposals are preserved as balance-sheet liabilities (`STATE_APPROVED`, `PAYOUT_APPROVED`) with locked `reserved_funds`.
  - Payout execution via `claim_payout` or `retry_payout` safely delivers funds and transitions to `PAYOUT_DELIVERED` / `STATE_FINALIZED`, strictly preventing duplicate payments.

## Deployment & Verification Evidence
- **Active Verified Deployment**: [0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1](https://explorer-studio-dev.genlayer.com/address/0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1?chain=studio-devnet)
- **Deploy Transaction**: `0x75ee6da56dc7933fd104b09fed1763822e1a04fb54ccaa2cf7ea4c16c4ec1015`
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Deployment Receipt**: [receipt.json](deploy/receipt.json)
- **Live Settlement Proof on Deployment**: [settlement_proof_0x4841065c.json](evidence/settlement_proof_0x4841065c.json)
- **Schema Validation Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
  - Deployed Code SHA-256: `a4d8748418c9b9165cc8a135111006444a87dc54c85b29790ddff13aafc82930`
  - Local Source SHA-256: `a4d8748418c9b9165cc8a135111006444a87dc54c85b29790ddff13aafc82930`
  - Result: **100% Exact Match**
- **Focused Test Suite**: [test_charter_gate.py](tests/direct/test_charter_gate.py)
- **Test Results**: [pytest_summary.txt](pytest_summary.txt) (22 passed, 100% pass rate)
- **Superseded Deployments (Do Not Use)**:
  - `0x71D888072B123C61E553d82a3ffbAceD8B690410`: Rejected (no payout liability retention after finalize).
  - `0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0`: Rejected (unverified caller assertions allow duplicate payment and liability erasure).

