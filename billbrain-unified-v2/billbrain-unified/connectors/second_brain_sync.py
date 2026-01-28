"""
Second Brain Sync Connector.
Pushes approved ActionItems to the Smart Second Brain via API.

UPDATED: Now uses /api/tasks/from-email endpoint instead of direct DB insert.
This enables:
- Semantic deduplication against existing tasks
- Proper domain routing
- Metadata tracking
"""
import logging
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Smart Second Brain API URL (configurable)
SECOND_BRAIN_API_URL = "http://localhost:8000"


class SecondBrainSync:
    """Sync action items to Second Brain via API."""
    
    def __init__(self, api_url: str = SECOND_BRAIN_API_URL):
        self.api_url = api_url.rstrip('/')
        self.endpoint = f"{self.api_url}/api/tasks/from-email"
    
    def sync_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Push a single action item to Second Brain via API.
        
        Args:
            action: Dict with action item fields
            
        Returns:
            API response dict with task_id, was_duplicate, assigned_domain, message
        """
        try:
            # Map priority
            priority = action.get("priority", "medium")
            if hasattr(priority, 'value'):
                priority = priority.value
            
            # Map domain hint
            domain_hint = action.get("domain", "work")
            if domain_hint == "work":
                domain_hint = "work/marriott"
            
            # Build request payload matching EmailTaskCreate model
            payload = {
                "action": action.get("action_required") or action.get("first_step") or "Review email",
                "sender": action.get("sender_name") or action.get("sender_email"),
                "subject": action.get("subject", "")[:200],  # Limit subject length
                "priority": priority,
                "domain_hint": domain_hint,
                "deadline": action.get("deadline"),
                "context": action.get("context"),
                "first_step": action.get("first_step"),
                "estimated_minutes": action.get("estimated_minutes", 15),
                "source_email_id": action.get("email_id") or action.get("message_id")
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Make API call
            response = requests.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("was_duplicate"):
                    logger.info(f"⏭️ Duplicate detected - matches task #{result.get('duplicate_of')}")
                else:
                    logger.info(f"✅ Synced to Second Brain: Task #{result.get('task_id')} → {result.get('assigned_domain')}")
                
                return result
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                return {
                    "task_id": None,
                    "was_duplicate": False,
                    "duplicate_of": None,
                    "assigned_domain": None,
                    "message": f"API error: {response.status_code}"
                }
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Second Brain API at {self.api_url}")
            return {
                "task_id": None,
                "was_duplicate": False,
                "duplicate_of": None,
                "assigned_domain": None,
                "message": "Connection error - is Smart Second Brain running?"
            }
        except Exception as e:
            logger.error(f"Failed to sync action: {e}")
            return {
                "task_id": None,
                "was_duplicate": False,
                "duplicate_of": None,
                "assigned_domain": None,
                "message": str(e)
            }
    
    def sync_batch(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync multiple actions in one API call.
        
        Args:
            actions: List of action dicts
            
        Returns:
            Stats dict with created/duplicates/failed counts
        """
        try:
            # Build batch payload
            tasks = []
            for action in actions:
                priority = action.get("priority", "medium")
                if hasattr(priority, 'value'):
                    priority = priority.value
                
                domain_hint = action.get("domain", "work")
                if domain_hint == "work":
                    domain_hint = "work/marriott"
                
                task = {
                    "action": action.get("action_required") or action.get("first_step") or "Review email",
                    "sender": action.get("sender_name") or action.get("sender_email"),
                    "subject": action.get("subject", "")[:200],
                    "priority": priority,
                    "domain_hint": domain_hint,
                    "deadline": action.get("deadline"),
                    "context": action.get("context"),
                    "first_step": action.get("first_step"),
                    "estimated_minutes": action.get("estimated_minutes", 15),
                    "source_email_id": action.get("email_id") or action.get("message_id")
                }
                # Remove None values
                tasks.append({k: v for k, v in task.items() if v is not None})
            
            response = requests.post(
                f"{self.endpoint}/batch",
                json={"tasks": tasks},
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Batch sync: {result.get('created')} created, {result.get('duplicates')} duplicates")
                return result
            else:
                logger.error(f"Batch API error {response.status_code}: {response.text}")
                return {"created": 0, "duplicates": 0, "results": []}
                
        except Exception as e:
            logger.error(f"Batch sync failed: {e}")
            return {"created": 0, "duplicates": 0, "results": []}
    
    def sync_all_approved(self, session, ActionItem, ActionStatus) -> Dict[str, int]:
        """
        Sync all approved actions to Second Brain.
        
        Args:
            session: SQLAlchemy session for BillBrain DB
            ActionItem: The ActionItem model class
            ActionStatus: The ActionStatus enum
            
        Returns:
            Stats dict with synced/duplicates/failed counts
        """
        stats = {"synced": 0, "duplicates": 0, "failed": 0}
        
        # Get approved actions not yet synced
        approved = session.query(ActionItem).filter(
            ActionItem.status == ActionStatus.APPROVED
        ).all()
        
        if not approved:
            logger.info("No approved actions to sync")
            return stats
        
        logger.info(f"Syncing {len(approved)} approved actions to Second Brain...")
        
        for action in approved:
            action_dict = {
                "action_required": action.action_required,
                "sender_name": action.sender_name,
                "sender_email": action.sender_email,
                "subject": action.subject,
                "priority": action.priority,
                "domain": action.domain,
                "first_step": action.first_step,
                "estimated_minutes": action.estimated_minutes,
                "context": action.context,
                "email_id": action.email_id
            }
            
            result = self.sync_action(action_dict)
            
            if result.get("task_id"):
                # Successfully created
                action.second_brain_task_id = result["task_id"]
                action.synced_at = datetime.now()
                action.status = ActionStatus.SYNCED
                stats["synced"] += 1
            elif result.get("was_duplicate"):
                # Duplicate - mark as synced anyway
                action.second_brain_task_id = result.get("duplicate_of")
                action.synced_at = datetime.now()
                action.status = ActionStatus.SYNCED
                stats["duplicates"] += 1
            else:
                stats["failed"] += 1
        
        session.commit()
        
        logger.info(f"Sync complete: {stats['synced']} new, {stats['duplicates']} duplicates, {stats['failed']} failed")
        return stats
    
    def test_connection(self) -> bool:
        """Test if Second Brain API is accessible."""
        try:
            response = requests.get(f"{self.api_url}/", timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Second Brain API connected at {self.api_url}")
                return True
            else:
                logger.error(f"API returned {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to Second Brain API at {self.api_url}")
            return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    # ==================== BILL SYNC ====================
    
    def sync_bill(self, bill: Dict[str, Any]) -> Dict[str, Any]:
        """
        Push a bill to Second Brain financial module.
        
        Args:
            bill: Dict with bill fields (vendor, amount, due_date, etc.)
            
        Returns:
            API response dict with bill_id
        """
        try:
            payload = {
                "name": bill.get("vendor") or bill.get("description") or "Unknown Bill",
                "amount": bill.get("amount"),
                "due_date": bill.get("due_date"),
                "category": bill.get("category"),
                "vendor": bill.get("vendor"),
                "source": "billbrain",
                "source_email_id": bill.get("email_id") or bill.get("message_id"),
                "notes": bill.get("context") or bill.get("notes")
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            response = requests.post(
                f"{self.api_url}/api/financial/bills",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Synced bill #{result.get('id')}: {payload.get('name')} - ${payload.get('amount')}")
                return result
            else:
                logger.error(f"Bill API error {response.status_code}: {response.text}")
                return {"id": None, "message": f"API error: {response.status_code}"}
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Second Brain API at {self.api_url}")
            return {"id": None, "message": "Connection error"}
        except Exception as e:
            logger.error(f"Failed to sync bill: {e}")
            return {"id": None, "message": str(e)}
    
    def sync_all_approved_bills(self, session, Bill, BillStatus) -> Dict[str, int]:
        """
        Sync all approved bills to Second Brain financial module.
        
        Args:
            session: SQLAlchemy session for BillBrain DB
            Bill: The Bill model class
            BillStatus: The BillStatus enum
            
        Returns:
            Stats dict with synced/failed counts
        """
        stats = {"synced": 0, "failed": 0}
        
        approved = session.query(Bill).filter(
            Bill.status == BillStatus.APPROVED
        ).all()
        
        if not approved:
            logger.info("No approved bills to sync")
            return stats
        
        logger.info(f"Syncing {len(approved)} approved bills to Second Brain...")
        
        for bill in approved:
            bill_dict = {
                "vendor": bill.vendor,
                "amount": bill.amount,
                "due_date": bill.due_date.isoformat() if bill.due_date else None,
                "category": bill.category,
                "email_id": bill.email_id,
                "context": getattr(bill, 'context', None)
            }
            
            result = self.sync_bill(bill_dict)
            
            if result.get("id"):
                bill.second_brain_bill_id = result["id"]
                bill.synced_at = datetime.now()
                bill.status = BillStatus.SYNCED
                stats["synced"] += 1
            else:
                stats["failed"] += 1
        
        session.commit()
        
        logger.info(f"Bill sync complete: {stats['synced']} synced, {stats['failed']} failed")
        return stats
    
    def sync_all(self, session, ActionItem, ActionStatus, Bill=None, BillStatus=None) -> Dict[str, Any]:
        """
        Sync all approved items (actions and bills) to Second Brain.
        
        Returns:
            Combined stats for actions and bills
        """
        results = {}
        
        # Sync actions
        results["actions"] = self.sync_all_approved(session, ActionItem, ActionStatus)
        
        # Sync bills if models provided
        if Bill and BillStatus:
            results["bills"] = self.sync_all_approved_bills(session, Bill, BillStatus)
        
        return results


# Global instance
second_brain = SecondBrainSync()


if __name__ == "__main__":
    # Test connection
    print("Testing Second Brain API connection...")
    if second_brain.test_connection():
        print("✅ Connection successful!")
        
        # Test sync
        test_action = {
            "action_required": "Test task from BillBrain",
            "sender_name": "Test Sender",
            "subject": "Test Email Subject",
            "priority": "medium",
            "domain": "work",
            "first_step": "Review this test task",
            "estimated_minutes": 5
        }
        
        print("\nTesting single action sync...")
        result = second_brain.sync_action(test_action)
        print(f"Result: {result}")
    else:
        print("❌ Connection failed - ensure Smart Second Brain is running on port 8000")
