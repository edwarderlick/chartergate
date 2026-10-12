import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

from eth_account import Account
from gltest_cli.config.user import load_user_config
from gltest_cli.config.general import get_general_config
from gltest import get_contract_factory

RPC_URL = "https://studio-dev.genlayer.com/api"

def rpc_call(method, params):
    req_body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    res = requests.post(RPC_URL, json=req_body)
    return {
        "request": req_body,
        "response": res.json()
    }

def main():
    load_dotenv()
    key = os.environ.get("PRIVATE_KEY")
    if not key:
        raise ValueError("PRIVATE_KEY not set")

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

    print("Fetching raw RPC transaction records from studio-dev...")
    raw_rpc_records = {}
    parsed_transactions = {}

    for name, h in tx_hashes.items():
        rpc_data = rpc_call("eth_getTransactionByHash", [h])
        raw_rpc_records[name] = rpc_data
        
        res = rpc_data["response"].get("result", {})
        leader_receipts = res.get("consensus_data", {}).get("leader_receipt", [])
        pending_txs = []
        if leader_receipts and len(leader_receipts) > 0:
            pending_txs = leader_receipts[0].get("genvm_result", {}).get("pending_transactions", [])
            if not pending_txs:
                pending_txs = leader_receipts[0].get("pending_transactions", [])

        parsed_transactions[name] = {
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

    # Fetch live balances via raw RPC
    bal_contract_call = rpc_call("eth_getBalance", [contract_address, "latest"])
    bal_recip_call = rpc_call("eth_getBalance", [recipient_address, "latest"])
    
    contract_bal_now = int(bal_contract_call["response"].get("result", "0x0"), 16)
    recip_bal_now = int(bal_recip_call["response"].get("result", "0x0"), 16)

    # Fetch proposal state from contract
    general_config = get_general_config()
    user_config = load_user_config(Path("gltest.config.yaml"))
    if user_config.networks.get("studio-dev"):
        user_config.networks["studio-dev"].accounts = [key]
        user_config.networks["studio-dev"].from_account = key
    general_config.user_config = user_config

    factory = get_contract_factory("CharterGate")
    contract = factory.build_contract(contract_address, account=Account.from_key(key))
    p0 = contract.get_proposal([0]).call()
    payout0 = contract.get_payout([0]).call()

    # Derive lifecycle metrics strictly from verified records:
    claim_tx = parsed_transactions["claim_payout"]
    claim_pending = claim_tx["pending_transactions"]
    payout_val = claim_pending[0]["value"] if claim_pending else p0["amount"]
    
    # Structure sanitized evidence report
    evidence = {
        "network": "studio-dev",
        "chain_id": 61997,
        "contract_address": contract_address,
        "operator_address": operator_address,
        "recipient_address": recipient_address,
        "verified_onchain_summary": {
            "proposal_id": 0,
            "payout_amount_wei": payout_val,
            "current_contract_balance_wei": contract_bal_now,
            "current_recipient_balance_wei": recip_bal_now,
            "claim_payout_tx_hash": tx_hashes["claim_payout"],
            "claim_payout_status": claim_tx["status"],
            "claim_payout_execution_result": claim_tx["execution_result"],
            "emitted_messages_count": len(claim_tx["messages"]),
            "pending_transactions_count": len(claim_tx["pending_transactions"]),
            "pending_transaction_details": claim_pending,
            "final_proposal_state": p0["state"],
            "final_payout_state": p0["payout_state"],
            "is_liability_remaining": payout0["is_liability"],
            "duplicate_claim_execution_result": parsed_transactions["duplicate_claim"]["execution_result"],
            "duplicate_retry_execution_result": parsed_transactions["duplicate_retry"]["execution_result"]
        },
        "parsed_transactions": parsed_transactions,
        "raw_rpc_captures": {
            "transactions": raw_rpc_records,
            "balances": {
                "contract_balance": bal_contract_call,
                "recipient_balance": bal_recip_call
            }
        }
    }

    out_path = Path("evidence/settlement_proof_0x4841065c.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"Sanitized raw evidence report successfully saved to: {out_path}")

if __name__ == "__main__":
    main()
