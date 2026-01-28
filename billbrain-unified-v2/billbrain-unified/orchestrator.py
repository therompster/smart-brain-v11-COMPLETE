"""
Enhanced Orchestrator for BillBrain.
Processes emails and routes them to:
1. BILLS → BillInstance table (for reconciliation)
2. ACTIONS → ActionItem table (for Second Brain sync)
3. IGNORE → Just mark as processed
"""
import logging
import hashlib
from datetime import datetime
from connectors.gmail_connector import GmailConnector
from llm_client import LLMClient
from models import (
    init_db, get_session, 
    Evidence, BillInstance, BillEntity, BillStatus,
    ActionItem, ActionStatus, ActionPriority
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Init
engine = init_db()
llm = LLMClient()
gmail = GmailConnector()


def get_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_date(date_str: str):
    """Parse various date formats."""
    if not date_str:
        return None
    try:
        # Try common formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def process_bill(session, res: dict, mail_data: dict, evidence: Evidence):
    """Create BillEntity and BillInstance from extraction."""
    vendor_name = res.get("vendor", "UNKNOWN").upper().strip()
    
    # Get or create entity
    entity = session.query(BillEntity).filter_by(vendor_normalized=vendor_name).first()
    if not entity:
        entity = BillEntity(vendor_normalized=vendor_name)
        session.add(entity)
        session.flush()
    
    # Determine status
    amount = res.get("amount_due", 0)
    status = BillStatus.DETECTED if amount and amount > 0 else BillStatus.NEEDS_INFO
    
    # Create instance
    new_instance = BillInstance(
        entity_id=entity.id,
        amount_due=amount,
        urgency=res.get("urgency", "medium"),
        due_date=parse_date(res.get("due_date")),
        is_autopay=res.get("is_autopay", False),
        status=status
    )
    session.add(new_instance)
    session.flush()
    
    # Link evidence
    evidence.bill_instance_id = new_instance.id
    evidence.item_type = "bill"
    
    logger.info(f"✅ BILL: {vendor_name} | ${amount} | Due: {res.get('due_date', 'N/A')}")
    return new_instance


def process_action(session, res: dict, mail_data: dict, evidence: Evidence):
    """Create ActionItem from extraction."""
    action_text = res.get("action_required", "Review email")
    
    # Map priority
    priority_map = {
        "high": ActionPriority.high,
        "medium": ActionPriority.medium,
        "low": ActionPriority.low
    }
    priority = priority_map.get(res.get("priority", "medium"), ActionPriority.medium)
    
    # Get ADHD-friendly refinement
    context = res.get("context", mail_data.get("body", "")[:500])
    refined = llm.refine_action(action_text, context)
    
    # Create action item
    new_action = ActionItem(
        action_required=refined.get("refined_action", action_text),
        sender_name=res.get("sender_name", mail_data.get("sender", "Unknown")),
        sender_email=mail_data.get("sender"),
        subject=res.get("subject", mail_data.get("subject")),
        priority=priority,
        domain=res.get("domain", "work"),
        deadline=parse_date(res.get("deadline")),
        context=context,
        email_snippet=mail_data.get("body", "")[:500],
        status=ActionStatus.PENDING,
        evidence_id=evidence.id,
        first_step=refined.get("first_step"),
        estimated_minutes=refined.get("estimated_minutes", 15),
        needs_clarification=refined.get("needs_clarification", False),
        clarification_questions=refined.get("questions") if refined.get("needs_clarification") else None
    )
    session.add(new_action)
    
    evidence.item_type = "action"
    
    logger.info(f"✅ ACTION: {action_text[:50]}... | Priority: {res.get('priority')} | Domain: {res.get('domain')}")
    return new_action


def run_ingestion_loop(limit: int = 999999, batch_size: int = 5):
    """
    Main ingestion loop:
    1. Fetch unprocessed emails from Gmail
    2. Classify with LLM (bill/action/ignore)
    3. Route to appropriate handlers
    4. Mark as processed
    """
    print(f"🚀 Starting Enhanced Ingestion (Bills + Actions)...")
    print(f"   Batch size: {batch_size}")
    print("=" * 60)
    
    session = get_session(engine)
    
    # Stats
    stats = {"bills": 0, "actions": 0, "ignored": 0, "errors": 0}
    
    # 1. Fetch from Gmail
    raw_emails = gmail.fetch_potential_bills(limit=limit)
    print(f"📬 Fetched {len(raw_emails)} emails from Gmail")
    
    # 2. Filter duplicates
    to_process = []
    for mail in raw_emails:
        body_hash = get_text_hash(mail['body'])
        if session.query(Evidence).filter_by(raw_text_hash=body_hash).first():
            print(f"⏩ Skip (duplicate): {mail['subject'][:40]}...")
            gmail.mark_as_processed(mail['external_id'])
            continue
        to_process.append(mail)
    
    if not to_process:
        print("☕ No new emails to process.")
        return stats
    
    print(f"📨 {len(to_process)} new emails to process\n")
    
    # 3. Process in batches
    for i in range(0, len(to_process), batch_size):
        chunk = to_process[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"🧠 Batch {batch_num}: Processing {len(chunk)} emails...")
        
        # LLM batch classification
        results = llm.extract_batch(chunk)
        
        if not results:
            print(f"⚠️ Warning: Batch {batch_num} returned no results")
            continue
        
        # 4. Process each result
        for res in results:
            try:
                idx = res.get('index')
                if idx is None or idx >= len(chunk):
                    continue
                
                mail_data = chunk[idx]
                item_type = res.get("item_type", "ignore")
                
                # Create evidence record first
                evidence = Evidence(
                    source_type="gmail",
                    external_id=mail_data['external_id'],
                    raw_text_hash=get_text_hash(mail_data['body']),
                    raw_content=mail_data['body'],
                    meta_data={
                        "sender": mail_data['sender'],
                        "subject": mail_data['subject']
                    },
                    item_type=item_type
                )
                session.add(evidence)
                session.flush()
                
                # Route based on type
                if item_type == "bill":
                    process_bill(session, res, mail_data, evidence)
                    stats["bills"] += 1
                    
                elif item_type == "action":
                    process_action(session, res, mail_data, evidence)
                    stats["actions"] += 1
                    
                else:  # ignore
                    print(f"🚫 IGNORE: {mail_data['subject'][:40]}... ({res.get('reason', 'N/A')})")
                    stats["ignored"] += 1
                
                # Mark as processed in Gmail
                gmail.mark_as_processed(mail_data['external_id'])
                
            except Exception as e:
                logger.error(f"⚠️ Error processing index {res.get('index')}: {e}")
                stats["errors"] += 1
        
        # Commit after each batch
        session.commit()
        print(f"   ✓ Batch {batch_num} committed\n")
    
    # Final summary
    print("=" * 60)
    print("📊 INGESTION COMPLETE")
    print(f"   💰 Bills:   {stats['bills']}")
    print(f"   📋 Actions: {stats['actions']}")
    print(f"   🚫 Ignored: {stats['ignored']}")
    print(f"   ⚠️  Errors:  {stats['errors']}")
    print("=" * 60)
    
    return stats


def get_pending_actions(session=None):
    """Get all pending action items."""
    if session is None:
        session = get_session(engine)
    return session.query(ActionItem).filter(
        ActionItem.status == ActionStatus.PENDING
    ).order_by(ActionItem.created_at.desc()).all()


def get_pending_bills(session=None):
    """Get all pending bills."""
    if session is None:
        session = get_session(engine)
    return session.query(BillInstance).filter(
        BillInstance.status.in_([BillStatus.DETECTED, BillStatus.NEEDS_INFO])
    ).order_by(BillInstance.created_at.desc()).all()


if __name__ == "__main__":
    run_ingestion_loop()
