import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

from eth_account import Account
from eth_utils import to_checksum_address
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

def get_balance_wei(address):
    res = rpc_call("eth_getBalance", [address, "latest"])
    hex_val = res.get("result", "0x0")
    return int(hex_val, 16)

def log_step(title):
    print("\n" + "=" * 70)
    print(f"[*] {title}")
    print("=" * 70)

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
    
    print(f"Operator: {operator_account.address}")
    print(f"Target Contract: {contract_address}")

    # Generate fresh recipient account with 0 balance
    fresh_recipient = Account.create()
    recipient_address = to_checksum_address(fresh_recipient.address)
    print(f"Fresh Recipient (EOA): {recipient_address}")

    evidence = {
        "contract_address": contract_address,
        "operator": operator_account.address,
        "recipient_eoa": recipient_address,
        "timestamp_start": int(time.time()),
        "steps": []
    }

    # Step 1: Initial Balances
    log_step("Step 1: Check Initial Balances")
    init_recip_bal = get_balance_wei(recipient_address)
    init_contract_bal = get_balance_wei(contract_address)
    print(f"Initial Recipient Balance: {init_recip_bal} wei")
    print(f"Initial Contract Balance:  {init_contract_bal} wei")
    assert init_recip_bal == 0, "Fresh recipient must have 0 balance"

    evidence["initial_balances"] = {
        "recipient_balance_wei": init_recip_bal,
        "contract_balance_wei": init_contract_bal
    }

    factory = get_contract_factory("CharterGate")
    contract = factory.build_contract(contract_address, account=operator_account)

    # Step 2: Deposit treasury funds (500 wei)
    log_step("Step 2: Deposit 500 wei Treasury Funds")
    tx_deposit = contract.deposit().transact(
        value=500,
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_deposit):
        raise RuntimeError(f"Deposit failed: {tx_deposit}")
    print(f"Deposit TX: {tx_deposit['hash']}")
    time.sleep(5)

    contract_bal_after_dep = get_balance_wei(contract_address)
    print(f"Contract Balance after Deposit: {contract_bal_after_dep} wei")
    evidence["steps"].append({
        "step": "deposit",
        "tx_hash": tx_deposit["hash"],
        "deposited_wei": 500,
        "contract_balance_after": contract_bal_after_dep
    })

    # Step 3: Propose payout to fresh recipient
    log_step("Step 3: Propose 100 wei Payout to Recipient")
    evidence_url = "https://raw.githubusercontent.com/edwarderlick/chartergate/fix/payout-recovery/evidence/subscription_invoice.md"
    evidence_hash = "159d5d83d41b837b89c2147e396070546dcbb2279353ab0b3d29ee3a1dc04b63"
    now = int(time.time())
    screen_dl = now + 86400
    vote_dl = screen_dl + 86400
    payout_amount = 100

    tx_propose = contract.propose([
        recipient_address, payout_amount, "Software subscription for cloud developer tooling.",
        evidence_url, evidence_hash, screen_dl, vote_dl
    ]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_propose):
        raise RuntimeError(f"Propose failed: {tx_propose}")
    print(f"Propose TX: {tx_propose['hash']}")
    time.sleep(5)

    pid = 0
    p_prop = contract.get_proposal([pid]).call()
    print(f"Proposal {pid} Created: state={p_prop['state']}, amount={p_prop['amount']}")
    evidence["steps"].append({
        "step": "propose",
        "pid": pid,
        "tx_hash": tx_propose["hash"],
        "recipient": recipient_address,
        "amount_wei": payout_amount,
        "state": p_prop["state"],
        "reserved_funds": contract.reserved_funds().call() if hasattr(contract, "reserved_funds") else "checked_via_view"
    })

    # Step 4: Screen Proposal
    log_step("Step 4: AI Evidence Screening")
    tx_screen = contract.screen_proposal([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_screen):
        raise RuntimeError(f"Screen failed: {tx_screen}")
    print(f"Screen TX: {tx_screen['hash']}")
    time.sleep(10)

    p_screen = contract.get_proposal([pid]).call()
    print(f"Screen Result: state={p_screen['state']}, details={p_screen.get('eligibility_details')}")
    assert p_screen['state'] == 1, f"Expected STATE_ELIGIBLE (1), got {p_screen['state']}"
    evidence["steps"].append({
        "step": "screen_proposal",
        "pid": pid,
        "tx_hash": tx_screen["hash"],
        "state": p_screen["state"],
        "eligibility_details": p_screen.get("eligibility_details")
    })

    # Step 5: Member Vote
    log_step("Step 5: Member Vote YES")
    tx_vote = contract.vote([pid, True]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_vote):
        raise RuntimeError(f"Vote failed: {tx_vote}")
    print(f"Vote TX: {tx_vote['hash']}")
    time.sleep(5)

    p_vote = contract.get_proposal([pid]).call()
    print(f"Vote recorded: yes_votes={p_vote['yes_votes']}")
    evidence["steps"].append({
        "step": "vote",
        "pid": pid,
        "tx_hash": tx_vote["hash"],
        "yes_votes": p_vote["yes_votes"]
    })

    # Step 6: Finalize (Approve Payout Liability)
    log_step("Step 6: Finalize Vote -> Approve Liability")
    tx_finalize = contract.finalize([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_finalize):
        raise RuntimeError(f"Finalize failed: {tx_finalize}")
    print(f"Finalize TX: {tx_finalize['hash']}")
    time.sleep(5)

    p_fin = contract.get_proposal([pid]).call()
    payout_fin = contract.get_payout([pid]).call()
    print(f"Proposal State: {p_fin['state']} (STATE_APPROVED=4)")
    print(f"Payout State:   {p_fin['payout_state']} (PAYOUT_APPROVED=1)")
    print(f"Is Liability:   {payout_fin.get('is_liability')} (True)")
    assert p_fin['state'] == 4
    assert p_fin['payout_state'] == 1
    assert payout_fin['is_liability'] is True

    evidence["steps"].append({
        "step": "finalize",
        "pid": pid,
        "tx_hash": tx_finalize["hash"],
        "state": p_fin["state"],
        "payout_state": p_fin["payout_state"],
        "is_liability": payout_fin["is_liability"]
    })

    # Step 7: Pre-Claim Balance Verification
    log_step("Step 7: Pre-Claim Balances Check")
    bal_contract_before_claim = get_balance_wei(contract_address)
    bal_recip_before_claim = get_balance_wei(recipient_address)
    print(f"Pre-Claim Contract Balance:  {bal_contract_before_claim} wei")
    print(f"Pre-Claim Recipient Balance: {bal_recip_before_claim} wei")

    # Step 8: Execute Claim Payout
    log_step("Step 8: Execute claim_payout(0)")
    tx_claim = contract.claim_payout([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_claim):
        raise RuntimeError(f"Claim payout failed: {tx_claim}")
    claim_tx_hash = tx_claim["hash"]
    print(f"Claim Payout TX Hash: {claim_tx_hash}")
    time.sleep(6)

    # Fetch full raw transaction receipt via RPC
    raw_tx = rpc_call("eth_getTransactionByHash", [claim_tx_hash])
    tx_res = raw_tx.get("result", {})
    
    # Extract leader pending_transactions and execution result
    leader_receipt = tx_res.get("consensus_data", {}).get("leader_receipt", [])
    pending_txs = []
    if leader_receipt and len(leader_receipt) > 0:
        pending_txs = leader_receipt[0].get("genvm_result", {}).get("pending_transactions", [])
    
    print(f"Claim TX Status: {tx_res.get('status')}")
    print(f"Claim TX Execution Result: {tx_res.get('txExecutionResultName')}")
    print(f"Emitted Pending Transactions: {json.dumps(pending_txs, indent=2)}")

    # Step 9: Post-Claim Balance Verification
    log_step("Step 9: Post-Claim Balances Check (Settlement Verification)")
    bal_contract_after_claim = get_balance_wei(contract_address)
    bal_recip_after_claim = get_balance_wei(recipient_address)
    print(f"Post-Claim Contract Balance:  {bal_contract_after_claim} wei (Decreased by {bal_contract_before_claim - bal_contract_after_claim} wei)")
    print(f"Post-Claim Recipient Balance: {bal_recip_after_claim} wei (Increased by {bal_recip_after_claim - bal_recip_before_claim} wei)")

    assert bal_contract_before_claim - bal_contract_after_claim == 100, "Contract balance must decrease by exactly 100 wei"
    assert bal_recip_after_claim - bal_recip_before_claim == 100, "Recipient balance must increase by exactly 100 wei"
    assert bal_recip_after_claim == 100, "Fresh recipient must hold exactly 100 wei"

    # Step 10: Proposal State Verification
    p_after_claim = contract.get_proposal([pid]).call()
    payout_after_claim = contract.get_payout([pid]).call()
    print(f"Post-Claim Proposal State: {p_after_claim['state']} (STATE_FINALIZED=7)")
    print(f"Post-Claim Payout State:   {p_after_claim['payout_state']} (PAYOUT_DELIVERED=2)")
    print(f"Post-Claim Is Liability:   {payout_after_claim.get('is_liability')} (False)")

    assert p_after_claim['state'] == 7
    assert p_after_claim['payout_state'] == 2
    assert payout_after_claim['is_liability'] is False

    evidence["claim_payout_execution"] = {
        "tx_hash": claim_tx_hash,
        "status": tx_res.get("status"),
        "tx_execution_result_name": tx_res.get("txExecutionResultName"),
        "pending_transactions": pending_txs,
        "contract_balance_before_wei": bal_contract_before_claim,
        "contract_balance_after_wei": bal_contract_after_claim,
        "recipient_balance_before_wei": bal_recip_before_claim,
        "recipient_balance_after_wei": bal_recip_after_claim,
        "recipient_credited_wei": bal_recip_after_claim - bal_recip_before_claim,
        "proposal_state_after": p_after_claim["state"],
        "payout_state_after": p_after_claim["payout_state"],
        "is_liability_after": payout_after_claim["is_liability"]
    }

    # Step 11: Realistic Failure Testing - Duplicate Claim
    log_step("Step 11: Realistic Failure Testing - Duplicate Claim Rejection")
    dup_failed = False
    try:
        tx_dup = contract.claim_payout([pid]).transact(
            fee_value=FEE_VALUE,
            fees=FEES_CONFIG
        )
        time.sleep(5)
        raw_dup = rpc_call("eth_getTransactionByHash", [tx_dup["hash"]])
        dup_exec_res = raw_dup.get("result", {}).get("txExecutionResultName")
        print(f"Duplicate Claim TX Result: {dup_exec_res}")
        dup_failed = (dup_exec_res == "FINISHED_WITH_ERROR")
    except Exception as e:
        print(f"Duplicate claim reverted cleanly at invocation: {e}")
        dup_failed = True

    assert dup_failed, "Duplicate claim MUST revert"
    bal_recip_after_dup = get_balance_wei(recipient_address)
    assert bal_recip_after_dup == 100, "Recipient balance must remain 100 wei (no duplicate payment)"
    print("Duplicate payout strictly prevented!")

    # Step 12: Realistic Failure Testing - Retry after Delivery
    log_step("Step 12: Realistic Failure Testing - Retry after Delivery Rejection")
    retry_failed = False
    try:
        tx_retry = contract.retry_payout([pid]).transact(
            fee_value=FEE_VALUE,
            fees=FEES_CONFIG
        )
        time.sleep(5)
        raw_retry = rpc_call("eth_getTransactionByHash", [tx_retry["hash"]])
        retry_exec_res = raw_retry.get("result", {}).get("txExecutionResultName")
        print(f"Retry Payout TX Result: {retry_exec_res}")
        retry_failed = (retry_exec_res == "FINISHED_WITH_ERROR")
    except Exception as e:
        print(f"Retry payout reverted cleanly at invocation: {e}")
        retry_failed = True

    assert retry_failed, "Retry payout after delivery MUST revert"
    bal_recip_after_retry = get_balance_wei(recipient_address)
    assert bal_recip_after_retry == 100, "Recipient balance must remain 100 wei"
    print("Retry after delivery strictly prevented!")

    evidence["failure_tests"] = {
        "duplicate_claim_prevented": dup_failed,
        "retry_after_delivery_prevented": retry_failed,
        "final_recipient_balance_wei": bal_recip_after_retry,
        "final_contract_balance_wei": get_balance_wei(contract_address)
    }

    # Save evidence file
    evidence_path = Path("evidence/settlement_proof_0x4841065c.json")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\n[+] Proof execution completed successfully!")
    print(f"[+] Evidence recorded at: {evidence_path}")

if __name__ == "__main__":
    main()
