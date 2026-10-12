# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, a **mandatory member vote** for every payout, and an **identifiable, protected payout liability recovery mechanism**.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Identifiable, Protected Payout Liability**: When member voting succeeds, `finalize(pid)` approves the payout as an active liability (`STATE_APPROVED`, `PAYOUT_APPROVED`). The proposal's funds remain fully reserved in `reserved_funds` until delivery is confirmed.
- **Runtime-Supported Payout & Recovery Lifecycle**:
  - `claim_payout(pid)`: Emits the external transfer to the recipient and transitions the payout to `PAYOUT_PENDING`. Duplicate calls while pending revert.
  - `report_failed_delivery(pid)`: If the external transfer fails delivery, transitions to `PAYOUT_FAILED` while keeping funds reserved as a protected liability.
  - `retry_payout(pid)`: Safely re-emits the transfer for failed payouts, transitioning back to `PAYOUT_PENDING`.
  - `confirm_delivery(pid)`: Once delivery is verified, marks `PAYOUT_DELIVERED` and `STATE_FINALIZED`, releasing the reserved funds liability. Any subsequent claim attempts revert.
  - `get_payout(pid)`: Public view exposing payout state and `is_liability: bool`.
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
- **Deployment Receipt**: [receipt.json](deploy/receipt.json)
- **Schema Validation Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Live Demonstration Proof**: [payout_recovery_live_demo.json](deploy/payout_recovery_live_demo.json)
- **Explorer Address**: [0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0](https://explorer-studio-dev.genlayer.com/address/0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0?chain=studio-devnet)
- **Explorer Transaction**: [0x5d664edae0b3ee4106e21892a51c94cbe4f233650c1b5a8ba0764546e8566578](https://explorer-studio-dev.genlayer.com/transactions/0x5d664edae0b3ee4106e21892a51c94cbe4f233650c1b5a8ba0764546e8566578?chain=studio-devnet)

## Verification Status
- **Schema Validation**: Accepted by `gen_getContractSchemaForCode` with 14 public methods.
- **Tests**: 17 focused direct tests passed, covering approval liability retention, pending delivery, duplicate prevention, failed delivery recovery, retry, confirm delivery, and sponsor withdrawal protection.
- **Exact Bytecode Match**: SHA-256 hash of deployed contract (`gen_getContractCode`) matches submitted local source byte-for-byte (`29defa4a48be96ffe649412d271e3f74f7544a037147ddbb0a14c417235f542c`).
- **Live Studio-Dev Proof**: Full lifecycle demonstrated live on `studio-dev` (Deposit -> Propose -> AI Screen -> Member Vote -> Finalize Approval -> Claim Pending -> Duplicate Prevention Revert -> Report Failed Delivery -> Retry Payout -> Confirm Delivery -> Post-Delivery Claim Revert). All 12 transactions confirmed with transaction IDs recorded in `deploy/payout_recovery_live_demo.json`.

## Final Deployment Details
- **Address**: `0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0`
- **TX**: `0x5d664edae0b3ee4106e21892a51c94cbe4f233650c1b5a8ba0764546e8566578`
- **Source SHA-256**: `29defa4a48be96ffe649412d271e3f74f7544a037147ddbb0a14c417235f542c`
- **Supersedes**: `0x71D888072B123C61E553d82a3ffbAceD8B690410` (and `0x6905BF2041682aCea85b2d24Cb02BAa271BB5700`)
