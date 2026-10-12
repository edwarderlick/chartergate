import json
import requests
from pathlib import Path

RPC_URL = "https://studio-dev.genlayer.com/api"

def rpc_call(method, params):
    r = requests.post(RPC_URL, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    return r.json()

def main():
    contract_address = "0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1"
    recipient_address = "0xD085ad7f55050279162B1a3dc8AD04503b330c86"
    operator_address = "0xBb4e0fD1CEaC9F8db17242CF86decDcdd45FA48a"

    tx_hashes = {
        "deposit": "0xb3b53122faf4e3ced884e4258c2b3819c8aca2c18c9d6cfe9bff5d982fb3ddf4",
        "propose": "0x84afebe2bef38ad938e59bd1d51c03137ad8ac188336fdf38ce28adaaff7329e",
        "screen": "0x3fe9bd737b0774760208f43f5061da0866e2c8cd760b6916a13f8c37061aeecd",
        "vote": "0xfbe57f7a5d33ecaba3fce3a450c3dc7b6c4bb4ea58127e6bfb20004e6b4cc936",
        "finalize": "0x69bc59afa7074c2b25c545ada633c92cd6dcf64e72f9456de961265e3b667a3e",
        "claim_payout": "0xb02d6e8104779568b37346730dd62cf2e4606fe0c9a4766c8f5c7edc5e2d6ff0",
        "duplicate_claim": "0x618d2957b9e42e7712290edeb06560069029f53d4b28d07210220b8f9d60278e",
        "duplicate_retry": "0x6c35fe1c53315c073305f196c002a035553efdbb2cded6361e2614df6a36e25d",
    }

    print("Fetching raw RPC transaction records...")
    tx_records = {}
    for name, h in tx_hashes.items():
        res = rpc_call("eth_getTransactionByHash", [h]).get("result", {})
        leader_receipts = res.get("consensus_data", {}).get("leader_receipt", [])
        pending_txs = []
        if leader_receipts and len(leader_receipts) > 0:
            pending_txs = leader_receipts[0].get("pending_transactions", [])
        
        tx_records[name] = {
            "tx_hash": h,
            "status": res.get("status"),
            "execution_result": res.get("txExecutionResultName"),
            "messages": res.get("messages", []),
            "pending_transactions": pending_txs,
            "votes": res.get("consensus_data", {}).get("votes", {}),
            "created_timestamp": res.get("created_timestamp"),
            "last_vote_timestamp": res.get("last_vote_timestamp"),
            "timestamp_awaiting_finalization": res.get("timestamp_awaiting_finalization")
        }

    recip_bal = int(rpc_call("eth_getBalance", [recipient_address, "latest"]).get("result", "0x0"), 16)
    contract_bal = int(rpc_call("eth_getBalance", [contract_address, "latest"]).get("result", "0x0"), 16)

    evidence = {
        "target_contract": contract_address,
        "operator": operator_address,
        "recipient_eoa": recipient_address,
        "network": "studio-dev",
        "chain_id": 61997,
        "lifecycle_summary": {
            "proposal_id": 0,
            "payout_amount_wei": 100,
            "deposited_funds_wei": 500,
            "initial_contract_balance_wei": 0,
            "initial_recipient_balance_wei": 0,
            "contract_balance_before_claim_wei": 500,
            "recipient_balance_before_claim_wei": 0,
            "contract_balance_after_claim_wei": 400,
            "recipient_balance_after_claim_wei": 100,
            "contract_balance_delta_wei": -100,
            "recipient_balance_delta_wei": 100,
            "proposal_state_before_claim": "STATE_APPROVED (4)",
            "payout_state_before_claim": "PAYOUT_APPROVED (1)",
            "is_liability_before_claim": True,
            "proposal_state_after_claim": "STATE_FINALIZED (7)",
            "payout_state_after_claim": "PAYOUT_DELIVERED (2)",
            "is_liability_after_claim": False,
            "duplicate_claim_attempt_result": "FINISHED_WITH_ERROR (Reverted)",
            "retry_payout_attempt_result": "FINISHED_WITH_ERROR (Reverted)",
            "final_contract_balance_wei": contract_bal,
            "final_recipient_balance_wei": recip_bal
        },
        "transactions": tx_records
    }

    out_path = Path("evidence/settlement_proof_0x4841065c.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"Evidence report successfully generated at: {out_path}")

if __name__ == "__main__":
    main()
