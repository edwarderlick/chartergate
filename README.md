# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, a **mandatory member vote** for every payout, and an **identifiable, protected payout liability recovery mechanism**.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Identifiable, Protected Payout Liability**: When member voting succeeds, `finalize(pid)` approves the payout as an active liability (`STATE_APPROVED`, `PAYOUT_APPROVED`). The proposal's funds remain fully reserved in `reserved_funds`.
- **Security Audit & Resolution of Deployment 0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0**:
  - The previous implementation added `report_failed_delivery(pid)` and `confirm_delivery(pid)` which accepted unverified caller assertions.
  - **Attack 1 (Duplicate Payment / Double Spend)**: A caller could claim a payout, receive the transfer, falsely invoke `report_failed_delivery(pid)`, and invoke `retry_payout(pid)` to receive duplicate payments.
  - **Attack 2 (False Delivery Confirmation / Liability Erasure)**: A sponsor could invoke `confirm_delivery(pid)` without payment delivery, wiping the liability and prematurely decrementing `reserved_funds`, allowing the sponsor to withdraw backing funds after sunset.
  - **Defeat of Attacks**: In the corrected contract, both unverified methods are strictly rejected and revert (`"Unverified delivery failure reporting not permitted by runtime"` and `"Unverified delivery confirmation not permitted by runtime"`). Both attack tests in [test_charter_gate.py](tests/direct/test_charter_gate.py) now fail as attacks, defeating caller manipulation.
  - **Replay & Concurrency Protection**: `claim_payout(pid)` transitions to `PAYOUT_PENDING`. Repeated, concurrent, or replayed claims revert with `"Payout transfer already pending"`.
  - **Dual-Pool Accounting for Asynchronous Messages**: Funds that have left the contract balance into an asynchronous transfer are transferred from `reserved_funds` (on-balance reservations) to `in_flight_payouts` (unresolved in-transit liabilities). This prevents double-counting against remaining balance while keeping unresolved payouts 100% identifiable.
  - **Genuine Failure Handling & Safe Retry**: `claim_payout(pid)` strictly checks available balance. If the contract is underfunded at claim time, the call reverts cleanly without advancing `payout_state` or corrupting accounting. The liability remains preserved in `PAYOUT_APPROVED` and can be safely retried once the treasury is funded.
  - Both `0x71D888072B123C61E553d82a3ffbAceD8B690410` and `0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0` are **SUPERSEDED** and not suitable for resubmission.
- **Sponsor Withdrawal Protection**: The sponsor cannot withdraw treasury funds backing any active or pending payout liability (`self.balance < self.reserved_funds + amount` reverts), even after the sunset timestamp.
- **Deadlines**: Strict screen and vote deadlines enforce bounded decision windows.
- **Lifetime Proposal Cap**: Each deployment accepts at most 25 lifetime proposals, bounding internal storage.

## Why GenLayer?
CharterGate is only possible due to GenLayer's unique Intelligent Contract capabilities:
1. **Web Access**: The contract dynamically fetches off-chain receipts, invoices, or project milestones to verify claims. Standard smart contracts cannot perform native HTTP requests.
2. **LLM Evaluation**: Natural language rules (the charter) are evaluated against unstructured web evidence using LLM-based reasoning, allowing subjective intent-matching that code cannot do.
3. **`strict_eq` Consensus**: GenLayer's equivalence principle (`strict_eq`) requires validators to agree on the normalized eligibility result (`outcome` and boolean `eligible`) before a proposal can enter member voting. A successful member vote is still required before any payout path runs.

## Links and Evidence
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Focused Tests**: [test_charter_gate.py](tests/direct/test_charter_gate.py)
- **Test Summary**: [pytest_summary.txt](pytest_summary.txt)
- **Deployment Receipt (Historical/Superseded)**: [receipt.json](deploy/receipt.json)
- **Schema Validation Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Historical Exploit Evidence (Unsafe)**: [payout_recovery_live_demo.json](deploy/payout_recovery_live_demo.json)
- **Superseded Deployment Address**: [0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0](https://explorer-studio-dev.genlayer.com/address/0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0?chain=studio-devnet)
- **Prior Superseded Address**: [0x71D888072B123C61E553d82a3ffbAceD8B690410](https://explorer-studio-dev.genlayer.com/address/0x71D888072B123C61E553d82a3ffbAceD8B690410?chain=studio-devnet)

## Live Demonstration Analysis & Runtime Settlement Findings
- **Analysis of Historical Live Demo (`payout_recovery_live_demo.json` - Clearly Marked Unsafe)**:
  - Step 7: `claim_payout(0)` emitted 100 wei to recipient `0x81b637d8fCD2C6da6359E6963113a1170de795e4` in TX `0xe4a763d664837ae9e56208ea93dd5d1771c4dca39afeab45319b44cb3e906f5d`. The transfer successfully delivered 100 wei to the recipient.
  - Step 9: The operator manually called `report_failed_delivery(0)` in TX `0x0a8673267bf5df4323be39da72ec1c57d2e10412cf5f19b4b50b04fd9afad0df` despite the transfer having succeeded.
  - Step 10: `retry_payout(0)` was invoked in TX `0x247a732da6a6f6062c675ea176e9885a19327147070a2b1b62d601247fc7112c`, emitting another 100 wei transfer.
  - On-chain verification via studio-dev RPC confirmed the recipient received **200 wei** and the contract balance dropped from 5000 to **4800 wei**.
  - This demonstrates that unverified caller assertions introduce a critical double-spending exploit. The demo does not demonstrate safe recovery, but rather proves the vulnerability of naive caller assertions.
- **Exact Runtime & Settlement Capabilities on Studio-Dev**:
  - Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` (v0.6.0-rc8) / `v0.6.0-rc9`
  - SDK: `py-lib-genlayer-std:kzr02ndm9et4qkmbqpq5djjt5sme2yt76n7sz1qbzax0knt6mam0`
  - In GenVM, `@gl.evm.contract_interface` `emit_transfer()` performs a balance check in GenVM; if insufficient, it raises `SystemError: 7: insufficient_balance` and reverts the transaction cleanly.
  - If sufficient, `emit_transfer()` queues an asynchronous external message (`is_eth_send: true`, `messageType: 0`) scheduled for finalization.
  - Value is deducted from the sender contract's balance upon finalization of the parent transaction.
  - The runtime does not provide any WASI syscall or SDK method for a contract to inspect child transaction execution outcomes or RPC receipts (`_genlayer_wasi` exposes only `storage_read`, `storage_write`, `get_balance`, `get_self_balance`, `gl_call`).
  - Schema validation rejects error callbacks (`__on_errored_message__`), and child message execution failures do not refund value to the sender contract.
  - Therefore, on-chain verification of external message outcomes without unverified caller assertions, timeouts, balance polling, or raw transaction IDs is currently unsupported by the GenVM runtime.

## Deployment Status
- **0x71D888072B123C61E553d82a3ffbAceD8B690410**: SUPERSEDED (rejected: no payout liability retention after finalize).
- **0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0**: SUPERSEDED (rejected: unverified caller assertions allow duplicate payment and liability erasure).
- **Corrected Contract Status**: Defeats duplicate payment and premature erasure attacks. Preserves protected liabilities and accurately accounts for in-flight funds. Not marked resubmission-ready due to missing runtime capability for on-chain child message receipt verification.
- **Tests**: 22 focused direct tests passed (100% pass rate).

