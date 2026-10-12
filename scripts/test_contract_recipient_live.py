import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

from eth_account import Account
from gltest_cli.config.user import load_user_config
from gltest_cli.config.general import get_general_config
from gltest import get_contract_factory
from gltest.assertions import tx_execution_failed

RPC_URL = "https://studio-dev.genlayer.com/api"

FEES_CONFIG = {
    "distribution": {
        "leaderTimeunitsAllocation": 100,
        "validatorTimeunitsAllocation": 200,
        "appealRounds": 0,
        "executionBudgetPerRound": 100000000000000000,
        "executionConsumed": 0,
        "totalMessageFees": 0,
        "rotations": [3],
        "maxPriceGenPerTimeUnit": 2,
        "storageFeeMaxGasPrice": 300000000,
        "receiptFeeMaxGasPrice": 300000000
    }
}
FEE_VALUE = 500000000000010352

def rpc_call(method, params):
    r = requests.post(RPC_URL, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    return r.json()

def get_balance(address):
    res = rpc_call("eth_getBalance", [address, "latest"])
    return int(res.get("result", "0x0"), 16)

def main():
    load_dotenv()
    key = os.environ.get("PRIVATE_KEY")
    if not key:
        raise ValueError("PRIVATE_KEY not set")

    general_config = get_general_config()
    user_config = load_user_config(Path("gltest.config.yaml"))
    if user_config.networks.get("studio-dev"):
        user_config.networks["studio-dev"].accounts = [key]
        user_config.networks["studio-dev"].from_account = key
    general_config.user_config = user_config

    operator_account = Account.from_key(key)
    contract_address = "0x4841065CC06A4a1A4f5f418867EE8A5c9451dDC1"
    contract_recipient = "0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0"

    print(f"CharterGate: {contract_address}")
    print(f"Contract Recipient: {contract_recipient}")

    # Check recipient is indeed a deployed contract
    code_res = rpc_call("gen_getContractCode", [contract_recipient])
    assert "result" in code_res, f"Recipient must be a contract: {code_res}"
    print(f"Verified recipient is a deployed Intelligent Contract (code len: {len(code_res['result'])} bytes)")

    bal_recip_before = get_balance(contract_recipient)
    bal_cg_before = get_balance(contract_address)
    print(f"Before - Contract Recipient Balance: {bal_recip_before} wei")
    print(f"Before - CharterGate Balance:       {bal_cg_before} wei")

    factory = get_contract_factory("CharterGate")
    contract = factory.build_contract(contract_address, account=operator_account)

    now = int(time.time())
    screen_dl = now + 86400
    vote_dl = screen_dl + 86400
    payout_amount = 10
    evidence_url = "https://raw.githubusercontent.com/edwarderlick/chartergate/fix/payout-recovery/evidence/subscription_invoice.md"
    evidence_hash = "159d5d83d41b837b89c2147e396070546dcbb2279353ab0b3d29ee3a1dc04b63"

    print("\n--- Submitting Proposal 1 (Recipient = Contract Address) ---")
    tx_prop = contract.propose([
        contract_recipient, payout_amount, "Testing contract recipient payout settlement",
        evidence_url, evidence_hash, screen_dl, vote_dl
    ]).transact(fee_value=FEE_VALUE, fees=FEES_CONFIG)
    if tx_execution_failed(tx_prop):
        raise RuntimeError(f"Propose failed: {tx_prop}")
    print(f"Propose TX: {tx_prop['hash']}")
    time.sleep(5)

    pid = 1
    p1 = contract.get_proposal([pid]).call()
    print(f"Proposal 1 created: state={p1['state']}, recipient={p1['recipient']}")

    print("\n--- Screening Proposal 1 ---")
    tx_screen = contract.screen_proposal([pid]).transact(fee_value=FEE_VALUE, fees=FEES_CONFIG)
    if tx_execution_failed(tx_screen):
        raise RuntimeError(f"Screen failed: {tx_screen}")
    print(f"Screen TX: {tx_screen['hash']}")
    time.sleep(10)

    p1_screen = contract.get_proposal([pid]).call()
    print(f"Screening outcome: state={p1_screen['state']}")

    print("\n--- Voting on Proposal 1 ---")
    tx_vote = contract.vote([pid, True]).transact(fee_value=FEE_VALUE, fees=FEES_CONFIG)
    if tx_execution_failed(tx_vote):
        raise RuntimeError(f"Vote failed: {tx_vote}")
    print(f"Vote TX: {tx_vote['hash']}")
    time.sleep(5)

    print("\n--- Finalizing Proposal 1 ---")
    tx_fin = contract.finalize([pid]).transact(fee_value=FEE_VALUE, fees=FEES_CONFIG)
    if tx_execution_failed(tx_fin):
        raise RuntimeError(f"Finalize failed: {tx_fin}")
    print(f"Finalize TX: {tx_fin['hash']}")
    time.sleep(5)

    p1_fin = contract.get_proposal([pid]).call()
    p1_payout = contract.get_payout([pid]).call()
    print(f"Approved State: state={p1_fin['state']}, payout_state={p1_fin['payout_state']}, is_liability={p1_payout['is_liability']}")

    print("\n--- Claiming Payout to Contract Recipient ---")
    tx_claim = contract.claim_payout([pid]).transact(fee_value=FEE_VALUE, fees=FEES_CONFIG)
    if tx_execution_failed(tx_claim):
        raise RuntimeError(f"Claim payout failed: {tx_claim}")
    claim_hash = tx_claim["hash"]
    print(f"Claim TX Hash: {claim_hash}")
    time.sleep(6)

    # Fetch raw claim receipt
    raw_tx = rpc_call("eth_getTransactionByHash", [claim_hash])
    print(f"Claim Status: {raw_tx.get('result', {}).get('status')}")
    print(f"Claim Exec Result: {raw_tx.get('result', {}).get('txExecutionResultName')}")

    bal_recip_after = get_balance(contract_recipient)
    bal_cg_after = get_balance(contract_address)
    print(f"\nAfter - Contract Recipient Balance: {bal_recip_after} wei (Delta: {bal_recip_after - bal_recip_before})")
    print(f"After - CharterGate Balance:       {bal_cg_after} wei (Delta: {bal_cg_after - bal_cg_before})")

    p1_after = contract.get_proposal([pid]).call()
    print(f"Final Proposal State: state={p1_after['state']}, payout_state={p1_after['payout_state']}")

    result_data = {
        "test": "contract_recipient_payout_settlement",
        "contract_address": contract_address,
        "contract_recipient": contract_recipient,
        "claim_tx_hash": claim_hash,
        "claim_status": raw_tx.get("result", {}).get("status"),
        "claim_execution_result": raw_tx.get("result", {}).get("txExecutionResultName"),
        "bal_recip_before": bal_recip_before,
        "bal_recip_after": bal_recip_after,
        "recip_delta": bal_recip_after - bal_recip_before,
        "bal_cg_before": bal_cg_before,
        "bal_cg_after": bal_cg_after,
        "cg_delta": bal_cg_after - bal_cg_before,
        "raw_claim_tx": raw_tx.get("result", {})
    }
    with open("evidence/contract_recipient_test.json", "w") as f:
        json.dump(result_data, f, indent=2)
    print("Test result saved to evidence/contract_recipient_test.json")

if __name__ == "__main__":
    main()
