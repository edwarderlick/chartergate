# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import json
import hashlib
import re
import datetime
from dataclasses import dataclass, asdict

import genlayer as gl
from genlayer import *

@gl.evm.contract_interface
class _PayoutTarget:
    class View:
        pass
    class Write:
        pass

# States
STATE_PENDING = 0
STATE_ELIGIBLE = 1
STATE_INELIGIBLE = 2
STATE_EVIDENCE_FAILED = 3
STATE_APPROVED = 4
STATE_REJECTED = 5
STATE_EXPIRED = 6
STATE_FINALIZED = 7


def _get_now_ts() -> int:
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@dataclass
class Proposal:
    sponsor: str
    recipient: str
    amount: int
    purpose: str
    evidence_url: str
    evidence_hash: str
    deadline_screen: int
    deadline_vote: int
    state: int
    yes_votes: int
    no_votes: int
    eligibility_details: str

class CharterGate(gl.contract.Contract):
    debug_error: str
    sponsor: str
    charter_text: str
    members_json: str
    quorum: u256
    threshold: u256
    sunset_time: u256
    
    proposal_count: u256
    active_proposals: u256
    proposals_json: str
    has_voted_json: str
    
    total_funded: u256
    reserved_funds: u256

    def __init__(self, sponsor: str, charter_text: str, members: str, quorum: u256, threshold: u256, sunset_time: u256):
        self.debug_error = "None"
        if not charter_text.strip():
            raise ValueError("Charter text cannot be empty")
        if len(charter_text) > 5000:
            raise ValueError("Charter text too long")
            
        self.charter_text = charter_text
        self.sponsor = Address(sponsor).as_hex

        unique_members = set()
        members_list = []
        for m in members.split(","):
            m = m.strip()
            if m:
                if len(m) != 42 or not m.startswith("0x"):
                    raise ValueError("Malformed member address")
                if m == "0x0000000000000000000000000000000000000000":
                    raise ValueError("Zero address member not allowed")
                
                addr_hex = Address(m).as_hex
                if addr_hex in unique_members:
                    raise ValueError("Duplicate member")
                unique_members.add(addr_hex)
                members_list.append(addr_hex)

        if len(unique_members) == 0:
            raise ValueError("Empty member list")
        if len(unique_members) > 50:
            raise ValueError("Oversized member list")

        if quorum <= 0 or threshold <= 0:
            raise ValueError("Quorum and threshold must be > 0 to require a YES vote")
        if quorum > len(unique_members):
            raise ValueError("Quorum cannot exceed member count")
        if threshold > len(unique_members):
            raise ValueError("Threshold cannot exceed member count")
        if threshold > quorum:
            raise ValueError("Threshold cannot exceed quorum")
            
        # VOTING RULE DOCUMENTATION:
        # AI eligibility alone MUST NEVER pay anyone.
        # A proposal becomes ELIGIBLE through AI screening, but this only opens the voting phase.
        # For a proposal to become APPROVED and pay the recipient, it MUST:
        # 1. Be in the ELIGIBLE state.
        # 2. Receive a successful MEMBER VOTE where:
        #    a. Total votes (YES + NO) >= quorum
        #    b. YES votes >= threshold
        self.quorum = u256(quorum)
        self.threshold = u256(threshold)
        
        now = _get_now_ts()
        if sunset_time <= now:
            raise ValueError("Sunset time must be in the future")
        self.sunset_time = u256(sunset_time)
        
        self.proposal_count = u256(0)
        self.active_proposals = u256(0)
        self.total_funded = u256(0)
        self.reserved_funds = u256(0)
        
        self.members_json = json.dumps(members_list)
        self.proposals_json = "{}"
        self.has_voted_json = "{}"

    @gl.public.view
    def get_error(self) -> str:
        return self.debug_error

    @gl.public.write.payable
    def deposit(self) -> None:
        self.total_funded += u256(gl.message.value)

    def _is_member(self, addr: str) -> bool:
        members_list = json.loads(self.members_json)
        for m in members_list:
            if m.lower() == addr.lower():
                return True
        return False
        
    def _get_proposal(self, pid: int) -> Proposal:
        proposals_dict = json.loads(self.proposals_json)
        pid_str = str(pid)
        if pid_str not in proposals_dict:
            raise ValueError("Invalid proposal ID")
        return Proposal(**proposals_dict[pid_str])
        
    def _save_proposal(self, pid: int, p: Proposal) -> None:
        proposals_dict = json.loads(self.proposals_json)
        proposals_dict[str(pid)] = asdict(p)
        self.proposals_json = json.dumps(proposals_dict)

    @gl.public.write
    def propose(self, recipient: str, amount: int, purpose: str, evidence_url: str, evidence_hash: str, screen_deadline: int, vote_deadline: int) -> u256:
        now = _get_now_ts()
        if now >= int(self.sunset_time):
            raise ValueError("Treasury has reached sunset time")
            
        sender = gl.message.sender_address.as_hex
        if not self._is_member(sender):
            raise ValueError("Caller is not a member of the treasury.")
            
        if self.active_proposals >= u256(100):
            raise ValueError("Max active proposals reached")

        if len(recipient) != 42 or not recipient.startswith("0x"):
            raise ValueError("Malformed recipient address")
        if recipient == "0x0000000000000000000000000000000000000000":
            raise ValueError("Zero address recipient not allowed")
            
        if not purpose.strip():
            raise ValueError("Empty purpose")
        if len(purpose) > 1000:
            raise ValueError("Purpose too long")
            
        if not evidence_url.startswith("https://raw.githubusercontent.com/"):
            raise ValueError("Evidence URL must be a raw GitHub URL")
        if len(evidence_url) > 200:
            raise ValueError("URL too long")
            
        if not re.match(r"^[a-f0-9]{64}$", evidence_hash.lower()):
            raise ValueError("Invalid SHA-256 evidence hash format")
            
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        amount_u256 = u256(amount)
        
        # Max proposal amount is 10% of total funded or a fixed bound.
        if amount_u256 > u256(1000000000000000000000): # 1000 ETH/GL max
            raise ValueError("Amount exceeds hard limit")

        if self.balance < self.reserved_funds + amount_u256:
            raise ValueError(f"Insufficient available funds for this proposal. Balance: {self.balance}, Reserved: {self.reserved_funds}, Amount: {amount_u256}")
            
        if screen_deadline <= now:
            raise ValueError("Screen deadline must be in the future")
        if screen_deadline > now + 30 * 86400:
            raise ValueError("Screen deadline too far in the future")
            
        if vote_deadline <= screen_deadline:
            raise ValueError("Vote deadline must be after screen deadline")
        if vote_deadline > screen_deadline + 30 * 86400:
            raise ValueError("Vote deadline too far after screen deadline")

        self.reserved_funds += amount_u256

        pid = int(self.proposal_count)
        self.proposal_count += u256(1)
        self.active_proposals += u256(1)
        
        p = Proposal(
            sponsor=sender,
            recipient=Address(recipient).as_hex,
            amount=int(amount_u256),
            purpose=purpose,
            evidence_url=evidence_url,
            evidence_hash=evidence_hash.lower(),
            deadline_screen=int(screen_deadline),
            deadline_vote=int(vote_deadline),
            state=int(STATE_PENDING),
            yes_votes=0,
            no_votes=0,
            eligibility_details=""
        )
        self._save_proposal(pid, p)
        return u256(pid)

    @gl.public.write
    def screen_proposal(self, pid: u256) -> None:
        if pid >= self.proposal_count:
            raise ValueError("Invalid proposal ID")
        p = self._get_proposal(int(pid))
        if p.state != int(STATE_PENDING):
            raise ValueError("Proposal is not PENDING")
            
        now = _get_now_ts()
        if now > int(p.deadline_screen):
            p.state = int(STATE_EXPIRED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
            self._save_proposal(int(pid), p)
            return
            
        def get_eval_result() -> str:
            try:
                # Fetch up to 100kb
                web_data = gl.nondet.web.render(p.evidence_url, mode="text")
            except Exception:
                return json.dumps({"outcome": "FETCH_FAILED"})
                
            if len(web_data) == 0 or len(web_data) > 100000:
                return json.dumps({"outcome": "FETCH_FAILED"})
                
            fetched_hash = _hash(web_data)
            if fetched_hash != p.evidence_hash:
                return json.dumps({"outcome": "MISMATCH"})
                
            # Send exactly the hashed content to the LLM
            task = f"""
Evaluate if the proposed payment is eligible under the following charter.
Charter Text: {self.charter_text}

Payment Details:
- Amount: {p.amount} wei
- Recipient: {p.recipient}

Untrusted User Input (Proposed Purpose):
---
{p.purpose}
---

Untrusted Evidence (Fetched from URL):
---
{web_data}
---

Respond in JSON with a structured eligibility report. You must provide exactly these fields:
{{
    "rule_results": ["rule 1 met", "rule 2 not met"],
    "eligible": true
}}
or
{{
    "rule_results": ["rule 1 not met"],
    "eligible": false
}}
"""
            try:
                result_str = gl.nondet.exec_prompt(task)
                try:
                    result = json.loads(result_str) if isinstance(result_str, str) else result_str
                except Exception:
                    return json.dumps({"outcome": "MALFORMED_LLM_OUTPUT"})
                
                if not isinstance(result, dict):
                    return json.dumps({"outcome": "MALFORMED_LLM_OUTPUT"})
                    
                eligible = result.get("eligible")
                if not isinstance(eligible, bool):
                    return json.dumps({"outcome": "MALFORMED_LLM_OUTPUT"})
                
                # To support strict_eq consensus, we drop the non-deterministic rule_results 
                # because different validators will get slightly different wording.
                return json.dumps({
                    "outcome": "SUCCESS", 
                    "eligible": eligible
                })
            except Exception as e:
                return json.dumps({"outcome": f"LLM_ERROR__{e}"})

        try:
            result_str = gl.eq_principle.strict_eq(get_eval_result)
        except Exception:
            result_str = json.dumps({"outcome": "CONSENSUS_FAILED"})
            
        try:
            res = json.loads(result_str)
        except Exception:
            res = {"outcome": "CONSENSUS_FAILED"}
            
        outcome = res.get("outcome", "")
        
        if outcome in ["FETCH_FAILED", "MISMATCH", "LLM_ERROR", "MALFORMED_LLM_OUTPUT", "CONSENSUS_FAILED"]:
            p.state = int(STATE_EVIDENCE_FAILED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
            p.eligibility_details = f"{outcome} (raw={result_str})"
        elif outcome == "SUCCESS":
            is_eligible = res.get("eligible")
            if is_eligible is True:
                p.state = int(STATE_ELIGIBLE)
                p.eligibility_details = "SUCCESS"
            else:
                p.state = int(STATE_INELIGIBLE)
                self.reserved_funds -= u256(p.amount)
                self.active_proposals -= u256(1)
                p.eligibility_details = "SUCCESS"
        else:
            p.state = int(STATE_EVIDENCE_FAILED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
            p.eligibility_details = f"UNKNOWN: {outcome} (raw={result_str})"
            
        self._save_proposal(int(pid), p)

    @gl.public.write
    def vote(self, pid: u256, approve: bool) -> None:
        sender = gl.message.sender_address.as_hex
        if not self._is_member(sender):
            raise ValueError("Caller is not a member")
            
        if pid >= self.proposal_count:
            raise ValueError("Invalid proposal ID")
        p = self._get_proposal(int(pid))
        if p.state != int(STATE_ELIGIBLE):
            raise ValueError("Proposal is not in voting phase")
            
        now = _get_now_ts()
        if now > int(p.deadline_vote):
            raise ValueError("Voting phase has expired")
            
        vote_key = f"{int(pid)}_{sender.lower()}"
        has_voted_dict = json.loads(self.has_voted_json)
        if has_voted_dict.get(vote_key, False):
            raise ValueError("Already voted")
            
        has_voted_dict[vote_key] = True
        self.has_voted_json = json.dumps(has_voted_dict)
        
        if approve:
            p.yes_votes += 1
        else:
            p.no_votes += 1
            
        self._save_proposal(int(pid), p)

    @gl.public.write
    def finalize(self, pid: u256) -> None:
        if pid >= self.proposal_count:
            raise ValueError("Invalid proposal ID")
        p = self._get_proposal(int(pid))
        
        if p.state == int(STATE_ELIGIBLE):
            now = _get_now_ts()
            total_votes = p.yes_votes + p.no_votes
            members_count = len(json.loads(self.members_json))
            can_finalize = (now > int(p.deadline_vote)) or (total_votes == members_count)
            if not can_finalize:
                raise ValueError("Voting still in progress")
                
            if total_votes >= int(self.quorum) and p.yes_votes >= int(self.threshold):
                p.state = int(STATE_APPROVED)
            else:
                p.state = int(STATE_REJECTED)
                
        if p.state == int(STATE_APPROVED):
            p.state = int(STATE_FINALIZED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
            _PayoutTarget(Address(p.recipient)).emit_transfer(value=u256(p.amount))
        elif p.state == int(STATE_REJECTED):
            p.state = int(STATE_FINALIZED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
        else:
            raise ValueError("Proposal already finalized or not eligible")
            
        self._save_proposal(int(pid), p)

    @gl.public.write
    def release_expired(self, pid: u256) -> None:
        if pid >= self.proposal_count:
            raise ValueError("Invalid proposal ID")
        p = self._get_proposal(int(pid))
        now = _get_now_ts()
        if p.state == int(STATE_PENDING) and now > int(p.deadline_screen):
            p.state = int(STATE_EXPIRED)
            self.reserved_funds -= u256(p.amount)
            self.active_proposals -= u256(1)
            self._save_proposal(int(pid), p)
        elif p.state == int(STATE_ELIGIBLE) and now > int(p.deadline_vote):
            # Expired in eligible means voting is over. Delegate to finalize!
            self.finalize(pid)
        else:
            raise ValueError(f"Proposal is not expired in a reservable state (state={p.state}, now={now}, ds={p.deadline_screen}, dv={p.deadline_vote})")
            
    @gl.public.write
    def withdraw_treasury(self, amount: int) -> None:
        sender = gl.message.sender_address.as_hex
        if sender.lower() != self.sponsor.lower():
            raise ValueError("Only sponsor can withdraw")
            
        now = _get_now_ts()
        if now < int(self.sunset_time):
            raise ValueError("Cannot withdraw before sunset time")
            
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        amount_u256 = u256(amount)
        if self.balance < self.reserved_funds + amount_u256:
            raise ValueError("Insufficient balance (accounting for reserved funds)")
            
        _PayoutTarget(Address(sender)).emit_transfer(value=amount_u256)

    @gl.public.view
    def get_proposal(self, pid: u256) -> dict:
        if pid >= self.proposal_count:
            raise ValueError("Invalid proposal ID")
        return asdict(self._get_proposal(int(pid)))
