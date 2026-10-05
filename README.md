# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, and a **mandatory member vote** for every payout.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Reservations & Payout**: During the proposal lifecycle, funds are reserved so that eligible proposals are guaranteed funding if finalized. After deadlines pass and votes succeed, a single payout is emitted. 
- **Deadlines**: The contract uses strict screen and vote deadlines.
- **Sponsor Recovery**: The sponsor may recover the unreserved treasury funds only after a predetermined sunset timestamp, ensuring safety from permanent lockup without circumventing active proposal guarantees.
- **Failed-Payment Callback Limitation**: The pinned studio-dev runtime has no accepted `__on_errored_message__` dispatch path, and its schema generator rejects public method names beginning with `__`. The unsupported automatic failed-payment recovery hook was removed rather than renamed into an ordinary public method.

## Why GenLayer?
CharterGate is only possible due to GenLayer's unique Intelligent Contract capabilities:
1. **Web Access**: The contract dynamically fetches off-chain receipts, invoices, or project milestones to verify claims. Standard smart contracts cannot perform native HTTP requests.
2. **LLM Evaluation**: Natural language rules (the charter) are evaluated against unstructured web evidence using LLM-based reasoning, allowing subjective intent-matching that code cannot do.
3. **`strict_eq` Consensus**: GenLayer's equivalence principle (`strict_eq`) requires validator consensus on exactly formatted boolean LLM outputs, preventing hallucinated payouts.

## Links and Evidence
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Focused Tests**: [test_charter_gate.py](tests/direct/test_charter_gate.py)
- **Test Summary**: [pytest_summary.txt](pytest_summary.txt)
- **Deployment Receipt**: [receipt.json](deploy/receipt.json)
- **Schema/Rejection Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Explorer Address**: [0x6905BF2041682aCea85b2d24Cb02BAa271BB5700](https://explorer-studio-dev.genlayer.com/address/0x6905BF2041682aCea85b2d24Cb02BAa271BB5700?chain=studio-devnet)
- **Explorer Transaction**: [0x1887de6926c6281b08a227c676b17db185c94ad4e0f6678fcdcb058a06fc8bec](https://explorer-studio-dev.genlayer.com/transactions/0x1887de6926c6281b08a227c676b17db185c94ad4e0f6678fcdcb058a06fc8bec?chain=studio-devnet)

## Verification Status
- **Schema Validation**: `gen_getContractSchemaForCode` rejects the original public `__on_errored_message__` method and accepts the corrected source with 9 public methods.
- **Tests**: 10 focused direct tests passed, including the schema-generation regression.
- **Payout Verification**: Precisely one payout message was emitted in the direct test. 
- **Unverified Features**: Live recipient delivery and sponsor recovery after sunset remain unverified on the live network. Automatic failed-payment recovery is unsupported by the pinned runtime/schema pair.

## Final Deployment Details
- **Address**: `0x6905BF2041682aCea85b2d24Cb02BAa271BB5700`
- **TX**: `0x1887de6926c6281b08a227c676b17db185c94ad4e0f6678fcdcb058a06fc8bec`
- **Source SHA-256**: `9ceae4d0b0a1963cb0282054a229d5e6721b93354422dd3feb7dbda3072e501e`
- **Supersedes**: `0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F`
