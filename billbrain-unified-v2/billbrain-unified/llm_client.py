"""
Enhanced LLM Client for BillBrain.
Detects TWO distinct categories:
1. BILLS - financial obligations (keep existing handling with amounts, vendors, reconciliation)
2. ACTIONS - other emails requiring a task/response (sync to Second Brain)
"""
import requests
import json
import logging
from typing import Dict, Any, List

# --- Configuration ---
OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:14b" 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.api_url = f"{OLLAMA_HOST}/api/generate"

    def query(self, prompt: str, system_prompt: str = "") -> str:
        """Standard chat query."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        return self._send_request(payload)

    def extract_batch(self, emails_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process emails and classify into THREE categories:
        1. BILL - financial obligation (vendor, amount, due date)
        2. ACTION - requires task/response (action description, deadline)
        3. IGNORE - marketing/spam/notifications
        
        Bills get full extraction for reconciliation.
        Actions become tasks in Second Brain.
        """
        context_block = ""
        for i, mail in enumerate(emails_list):
            context_block += f"--- EMAIL INDEX: {i} ---\n"
            context_block += f"Subject: {mail.get('subject')}\n"
            context_block += f"From: {mail.get('sender', 'Unknown')}\n"
            context_block += f"Body:\n{mail.get('body', '')[:3000]}\n\n"

        system_prompt = """You are an email triage AI. Classify each email into exactly ONE category.

=== CATEGORY: BILL ===
Financial obligations requiring payment. MUST have a monetary amount.
Examples:
- Utility bills (electric, water, gas, internet, phone)
- Credit card statements with balance due
- Rent/mortgage payment notices
- Insurance premium notices
- Subscription renewals with specific $ amounts
- Medical/dental bills
- Loan payment reminders

For BILL, extract:
{
  "index": int,
  "item_type": "bill",
  "vendor": "COMPANY NAME IN CAPS",
  "amount_due": float (the payment amount, must be > 0),
  "due_date": "YYYY-MM-DD" or null,
  "urgency": "high" | "medium" | "low",
  "is_autopay": boolean,
  "subject": "original subject"
}

Urgency for bills:
- high: Overdue, due within 3 days, final notice, disconnect warning
- medium: Due within 2 weeks
- low: Statement only, autopay enabled, no urgency mentioned

=== CATEGORY: ACTION ===
Emails requiring YOU to DO something (NOT pay money). The action must be clear.
Examples:
- Meeting requests needing confirmation ("Can you attend...?")
- Documents requiring signature or approval
- Questions awaiting YOUR reply
- Deadlines or deliverables mentioned
- Direct requests from people ("Please review...", "Can you send...?")
- Appointments to schedule
- Follow-ups you need to send
- Reviews/feedback requested from you

For ACTION, extract:
{
  "index": int,
  "item_type": "action",
  "action_required": "Verb-first task description",
  "sender_name": "Person's name",
  "deadline": "YYYY-MM-DD" or null,
  "priority": "high" | "medium" | "low",
  "domain": "work" | "personal" | "admin",
  "context": "Brief context (1-2 sentences)",
  "subject": "original subject"
}

Priority for actions:
- high: Urgent, ASAP, today, time-sensitive, boss/client request
- medium: This week, standard importance
- low: Flexible deadline, FYI, when you get a chance

Domain:
- work: From colleagues, clients, work-related services
- personal: Friends, family, personal appointments
- admin: Government, legal, healthcare, banking (non-bill)

=== CATEGORY: IGNORE ===
No action needed from you.
Examples:
- Marketing/promotional emails
- Newsletters (even if interesting)
- Order shipped/delivered confirmations
- Social media notifications
- Automated receipts (payment already processed)
- Spam
- Subscription confirmations (not bills)
- Password reset you didn't request

For IGNORE:
{
  "index": int,
  "item_type": "ignore",
  "reason": "brief explanation",
  "subject": "original subject"
}

=== RULES ===
1. If an email mentions money AND requires payment → BILL
2. If an email requires YOU to do something (not pay) → ACTION
3. Everything else → IGNORE
4. Netflix/subscription RENEWALS with amounts are BILLS
5. Meeting invites needing response are ACTIONS
6. "Your order shipped" is IGNORE (no action needed)
7. Be conservative - if unclear, lean toward IGNORE

Return a JSON array with one object per email."""

        prompt = f"Classify these {len(emails_list)} emails:\n\n{context_block}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "format": "json",
            "stream": False,
            "temperature": 0.1,
            "options": {
                "num_ctx": 16384,
                "top_p": 0.9
            }
        }

        logger.info(f"🧠 Processing batch of {len(emails_list)} emails...")
        response_text = self._send_request(payload)
        
        try:
            results = json.loads(response_text)
            
            # Handle if LLM wraps in a container object
            if isinstance(results, dict):
                for val in results.values():
                    if isinstance(val, list): 
                        return val
                return [results]
            
            return results if isinstance(results, list) else []
            
        except json.JSONDecodeError:
            logger.error(f"❌ JSON parse failed. Raw: {response_text[:500]}")
            return []

    def refine_action(self, action_text: str, email_context: str) -> Dict[str, Any]:
        """
        Refine an action item into an ADHD-friendly task with first step.
        """
        system_prompt = """You help break down tasks for people with ADHD.
Return JSON:
{
  "refined_action": "Clear verb-first task",
  "first_step": "2-minute starter task to overcome activation energy",
  "estimated_minutes": int,
  "needs_clarification": boolean,
  "questions": ["question1", "question2"] (if unclear)
}

First step should be TINY - just open email, just open document, just write one sentence."""

        prompt = f"""Task: {action_text}

Context: {email_context[:800]}

Break this down into a clear task with an easy first step."""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "format": "json",
            "stream": False,
            "temperature": 0.2
        }

        response_text = self._send_request(payload)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                "refined_action": action_text,
                "first_step": f"Open email: {action_text[:30]}...",
                "estimated_minutes": 15,
                "needs_clarification": False
            }

    def _send_request(self, payload: dict) -> str:
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API Error: {e}")
            return ""


# --- Test ---
if __name__ == "__main__":
    client = LLMClient()
    
    mock_batch = [
        {
            "subject": "Verizon Bill - Payment Due Nov 15",
            "sender": "verizon@email.verizon.com",
            "body": "Your bill of $145.32 is due November 15, 2024. Pay online at verizon.com/pay"
        },
        {
            "subject": "URGENT: Q4 Planning Meeting - Please Confirm",
            "sender": "john.smith@marriott.com",
            "body": "Hi Rami,\n\nCan you confirm your availability for the Q4 planning session next Tuesday at 2pm? I need your input on the AI roadmap before the exec presentation.\n\nPlease respond by EOD today.\n\nThanks,\nJohn"
        },
        {
            "subject": "Action Required: Sign NDA by Friday",
            "sender": "legal@konstellate.io",
            "body": "Hi Rami,\n\nPlease review and sign the attached NDA for the new partnership with DataCorp. The deadline is Friday EOD.\n\nDocuSign link: https://docusign.com/xyz\n\nLet me know if you have questions."
        },
        {
            "subject": "Your Netflix membership renewed",
            "sender": "info@netflix.com",
            "body": "Your Netflix Premium subscription has been renewed. Amount: $22.99. Next billing date: December 15, 2024. Manage your account at netflix.com/account"
        },
        {
            "subject": "Your Amazon order has shipped!",
            "sender": "ship-confirm@amazon.com",
            "body": "Great news! Your package is on its way. Track delivery: amazon.com/orders/123"
        },
        {
            "subject": "🔥 50% OFF - Black Friday Deals Inside!",
            "sender": "deals@randomstore.com",
            "body": "Don't miss our biggest sale of the year! Shop now and save 50% on everything!"
        },
        {
            "subject": "RE: Architecture review needed",
            "sender": "sarah.jones@marriott.com", 
            "body": "Hi Rami,\n\nThanks for the initial doc. Can you add a section on the security implications for the TIP.AI integration? Chris Hunter also wants to discuss - can you set up a 30-min call this week?\n\nSarah"
        },
        {
            "subject": "Pepco - Your electricity bill is ready",
            "sender": "billing@pepco.com",
            "body": "Your Pepco bill for October 2024 is now available.\n\nAmount Due: $187.43\nDue Date: November 20, 2024\n\nView and pay at pepco.com/mybill"
        }
    ]

    print("🤖 Testing Enhanced Email Triage (Bills + Actions)")
    print("=" * 70)
    
    results = client.extract_batch(mock_batch)
    
    # Separate by type
    bills = [r for r in results if r.get('item_type') == 'bill']
    actions = [r for r in results if r.get('item_type') == 'action']
    ignored = [r for r in results if r.get('item_type') == 'ignore']
    
    print(f"\n💰 BILLS DETECTED: {len(bills)}")
    print("-" * 50)
    for b in bills:
        print(f"  💵 {b.get('vendor', 'Unknown')}")
        print(f"     Amount: ${b.get('amount_due', 0)} | Due: {b.get('due_date', 'N/A')}")
        print(f"     Urgency: {b.get('urgency', 'medium')} | AutoPay: {b.get('is_autopay', False)}")
        print()
    
    print(f"\n📋 ACTION ITEMS: {len(actions)}")
    print("-" * 50)
    for a in actions:
        print(f"  ✏️  {a.get('action_required', 'Unknown task')}")
        print(f"     From: {a.get('sender_name', '?')} | Priority: {a.get('priority', 'medium')}")
        print(f"     Domain: {a.get('domain', '?')} | Deadline: {a.get('deadline', 'None')}")
        print()
    
    print(f"\n🚫 IGNORED: {len(ignored)}")
    print("-" * 50)
    for i in ignored:
        print(f"  ❌ {i.get('subject', '?')[:40]}...")
        print(f"     Reason: {i.get('reason', 'N/A')}")
        print()
    
    print("=" * 70)
    print("\n📊 Summary:")
    print(f"   Bills: {len(bills)} | Actions: {len(actions)} | Ignored: {len(ignored)}")
    
    # Test action refinement
    if actions:
        print("\n\n🔧 Testing Action Refinement (ADHD-friendly)...")
        print("-" * 50)
        test_action = actions[0]
        refined = client.refine_action(
            test_action.get('action_required', ''),
            test_action.get('context', '')
        )
        print(f"Original: {test_action.get('action_required')}")
        print(f"Refined:  {refined.get('refined_action')}")
        print(f"First Step: {refined.get('first_step')}")
        print(f"Est. Time: {refined.get('estimated_minutes')} min")
