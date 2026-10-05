# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, and a **mandatory member vote** for every payout.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Reservations & Payout**: During the proposal lifecycle, funds are reserved so that eligible proposals are guaranteed funding if finalized. After deadlines pass and votes succeed, a single payout is emitted. 
- **Deadlines**: The contract uses strict screen and vote deadlines.
- **Lifetime Proposal Cap**: Each deployment accepts at most 25 lifetime proposals. Historical proposal and vote JSON are intentionally bounded by this explicit cap.
- **Sponsor Recovery**: The sponsor may recover the unreserved treasury funds only after a predetermined sunset timestamp, ensuring safety from permanent lockup without circumventing active proposal guarantees.
- **Failed-Payment Callback Limitation**: The pinned studio-dev runtime has no accepted `__on_errored_message__` dispatch path, and its schema generator rejects public method names beginning with `__`. The unsupported automatic failed-payment recovery hook was removed rather than renamed into an ordinary public method.

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
- **Schema/Rejection Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Explorer Address**: [0x71D888072B123C61E553d82a3ffbAceD8B690410](https://explorer-studio-dev.genlayer.com/address/0x71D888072B123C61E553d82a3ffbAceD8B690410?chain=studio-devnet)
- **Explorer Transaction**: [0x67cf9de6b7bc0dfb9f6fc28604ca763edd352e4464bda92b87ef49ea19c94171](https://explorer-studio-dev.genlayer.com/transactions/0x67cf9de6b7bc0dfb9f6fc28604ca763edd352e4464bda92b87ef49ea19c94171?chain=studio-devnet)

## Verification Status
- **Schema Validation**: `gen_getContractSchemaForCode` rejects the original public `__on_errored_message__` method and accepts the corrected source with 9 public methods.
- **Tests**: 12 focused direct tests passed, including schema generation, zero-sponsor rejection, and the lifetime proposal cap boundary.
- **Payout Verification**: Precisely one payout message was emitted in the direct test. 
- **Unverified Features**: Live recipient delivery and sponsor recovery after sunset remain unverified on the live network. Automatic failed-payment recovery is unsupported by the pinned runtime/schema pair.

## Final Deployment Details
- **Address**: `0x71D888072B123C61E553d82a3ffbAceD8B690410`
- **TX**: `0x67cf9de6b7bc0dfb9f6fc28604ca763edd352e4464bda92b87ef49ea19c94171`
- **Source SHA-256**: `15ee6dad22333fe0f36a1de9d1a74075b7145acf430b01744d718757ff72cac7`
- **Supersedes**: `0x6905BF2041682aCea85b2d24Cb02BAa271BB5700`
