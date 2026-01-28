"""Financial service for managing bills, subscriptions, and loans."""

import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

from src.config import settings


class FinancialService:
    """Manage financial entities: bills, subscriptions, loans."""
    
    def __init__(self):
        self.db_path = settings.sqlite_db_path
    
    # ==================== BILLS ====================
    
    def create_bill(self, data: Dict[str, Any]) -> int:
        """Create a new bill."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO bills (name, amount, due_date, category, vendor, status, source, source_email_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("amount"),
            data.get("due_date"),
            data.get("category"),
            data.get("vendor"),
            data.get("status", "pending"),
            data.get("source"),
            data.get("source_email_id"),
            data.get("notes")
        ))
        
        bill_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created bill #{bill_id}: {data.get('name')} - ${data.get('amount')}")
        return bill_id
    
    def get_bills(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get bills, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT id, name, amount, due_date, category, vendor, status, paid_date, paid_amount, notes, created_at
                FROM bills WHERE status = ? ORDER BY due_date ASC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT id, name, amount, due_date, category, vendor, status, paid_date, paid_amount, notes, created_at
                FROM bills ORDER BY due_date ASC LIMIT ?
            """, (limit,))
        
        bills = []
        for row in cursor.fetchall():
            bills.append({
                "id": row[0], "name": row[1], "amount": row[2], "due_date": row[3],
                "category": row[4], "vendor": row[5], "status": row[6],
                "paid_date": row[7], "paid_amount": row[8], "notes": row[9], "created_at": row[10]
            })
        
        conn.close()
        return bills
    
    def mark_bill_paid(self, bill_id: int, paid_amount: float, paid_date: str = None) -> bool:
        """Mark a bill as paid."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        paid_date = paid_date or date.today().isoformat()
        
        cursor.execute("""
            UPDATE bills SET status = 'paid', paid_date = ?, paid_amount = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (paid_date, paid_amount, bill_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Bill #{bill_id} marked as paid: ${paid_amount}")
        return True
    
    def get_upcoming_bills(self, days: int = 14) -> List[Dict]:
        """Get bills due in the next N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        future_date = (date.today() + timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT id, name, amount, due_date, category, vendor
            FROM bills 
            WHERE status = 'pending' AND due_date <= ?
            ORDER BY due_date ASC
        """, (future_date,))
        
        bills = [{"id": r[0], "name": r[1], "amount": r[2], "due_date": r[3], "category": r[4], "vendor": r[5]} 
                 for r in cursor.fetchall()]
        
        conn.close()
        return bills
    
    # ==================== SUBSCRIPTIONS ====================
    
    def create_subscription(self, data: Dict[str, Any]) -> int:
        """Create a new subscription."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO subscriptions (name, amount, frequency, category, vendor, status, start_date, next_due_date, auto_pay, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("amount"),
            data.get("frequency", "monthly"),
            data.get("category"),
            data.get("vendor"),
            data.get("status", "active"),
            data.get("start_date"),
            data.get("next_due_date"),
            data.get("auto_pay", False),
            data.get("notes")
        ))
        
        sub_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created subscription #{sub_id}: {data.get('name')} - ${data.get('amount')}/{data.get('frequency')}")
        return sub_id
    
    def get_subscriptions(self, status: Optional[str] = None) -> List[Dict]:
        """Get all subscriptions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT id, name, amount, frequency, category, vendor, status, next_due_date, auto_pay, notes
                FROM subscriptions WHERE status = ? ORDER BY next_due_date ASC
            """, (status,))
        else:
            cursor.execute("""
                SELECT id, name, amount, frequency, category, vendor, status, next_due_date, auto_pay, notes
                FROM subscriptions ORDER BY next_due_date ASC
            """)
        
        subs = []
        for row in cursor.fetchall():
            subs.append({
                "id": row[0], "name": row[1], "amount": row[2], "frequency": row[3],
                "category": row[4], "vendor": row[5], "status": row[6],
                "next_due_date": row[7], "auto_pay": bool(row[8]), "notes": row[9]
            })
        
        conn.close()
        return subs
    
    def get_monthly_subscription_total(self) -> float:
        """Calculate total monthly subscription cost."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT amount, frequency FROM subscriptions WHERE status = 'active'
        """)
        
        total = 0.0
        for amount, frequency in cursor.fetchall():
            if frequency == "monthly":
                total += amount
            elif frequency == "yearly":
                total += amount / 12
            elif frequency == "weekly":
                total += amount * 4.33
            elif frequency == "quarterly":
                total += amount / 3
        
        conn.close()
        return round(total, 2)
    
    # ==================== LOANS ====================
    
    def create_loan(self, data: Dict[str, Any]) -> int:
        """Create a new loan."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate monthly payment if not provided
        monthly_payment = data.get("monthly_payment")
        if not monthly_payment:
            monthly_payment = self._calculate_monthly_payment(
                data.get("original_principal"),
                data.get("interest_rate"),
                data.get("term_months")
            )
        
        cursor.execute("""
            INSERT INTO loans (name, lender, loan_type, original_principal, current_balance, 
                             interest_rate, term_months, start_date, monthly_payment, payment_due_day, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("lender"),
            data.get("loan_type"),
            data.get("original_principal"),
            data.get("current_balance") or data.get("original_principal"),
            data.get("interest_rate"),
            data.get("term_months"),
            data.get("start_date"),
            monthly_payment,
            data.get("payment_due_day", 1),
            data.get("notes")
        ))
        
        loan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created loan #{loan_id}: {data.get('name')} - ${data.get('original_principal')}")
        return loan_id
    
    def get_loans(self, status: Optional[str] = None) -> List[Dict]:
        """Get all loans."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT id, name, lender, loan_type, original_principal, current_balance,
                       interest_rate, term_months, start_date, monthly_payment, payment_due_day, status, notes
                FROM loans WHERE status = ? ORDER BY current_balance DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT id, name, lender, loan_type, original_principal, current_balance,
                       interest_rate, term_months, start_date, monthly_payment, payment_due_day, status, notes
                FROM loans ORDER BY current_balance DESC
            """)
        
        loans = []
        for row in cursor.fetchall():
            loans.append({
                "id": row[0], "name": row[1], "lender": row[2], "loan_type": row[3],
                "original_principal": row[4], "current_balance": row[5],
                "interest_rate": row[6], "term_months": row[7], "start_date": row[8],
                "monthly_payment": row[9], "payment_due_day": row[10], "status": row[11], "notes": row[12]
            })
        
        conn.close()
        return loans
    
    def record_loan_payment(self, loan_id: int, amount: float, payment_date: str = None, extra_principal: float = 0) -> Dict:
        """Record a loan payment and update balance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        payment_date = payment_date or date.today().isoformat()
        
        # Get loan details
        cursor.execute("SELECT current_balance, interest_rate FROM loans WHERE id = ?", (loan_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": "Loan not found"}
        
        current_balance, rate = row
        
        # Calculate interest/principal split
        monthly_rate = rate / 100 / 12
        interest_amount = round(current_balance * monthly_rate, 2)
        principal_amount = round(amount - interest_amount, 2)
        total_principal = principal_amount + extra_principal
        new_balance = round(current_balance - total_principal, 2)
        
        # Record payment
        cursor.execute("""
            INSERT INTO loan_payments (loan_id, payment_date, amount, principal_amount, interest_amount, extra_principal, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (loan_id, payment_date, amount + extra_principal, principal_amount, interest_amount, extra_principal, new_balance))
        
        # Update loan balance
        cursor.execute("""
            UPDATE loans SET current_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (new_balance, loan_id))
        
        if new_balance <= 0:
            cursor.execute("UPDATE loans SET status = 'paid_off' WHERE id = ?", (loan_id,))
        
        conn.commit()
        conn.close()
        
        return {
            "payment_id": cursor.lastrowid,
            "interest_paid": interest_amount,
            "principal_paid": total_principal,
            "new_balance": new_balance
        }
    
    def get_amortization_schedule(self, loan_id: int) -> List[Dict]:
        """Generate amortization schedule for a loan."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT current_balance, interest_rate, monthly_payment, term_months, start_date
            FROM loans WHERE id = ?
        """, (loan_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return []
        
        balance, rate, payment, term, start_date = row
        monthly_rate = rate / 100 / 12
        
        schedule = []
        for month in range(1, term + 1):
            interest = round(balance * monthly_rate, 2)
            principal = round(payment - interest, 2)
            balance = round(balance - principal, 2)
            
            if balance < 0:
                principal += balance
                balance = 0
            
            schedule.append({
                "month": month,
                "payment": payment,
                "principal": principal,
                "interest": interest,
                "balance": balance
            })
            
            if balance <= 0:
                break
        
        return schedule
    
    def _calculate_monthly_payment(self, principal: float, annual_rate: float, term_months: int) -> float:
        """Calculate monthly payment using amortization formula."""
        if annual_rate == 0:
            return round(principal / term_months, 2)
        
        monthly_rate = annual_rate / 100 / 12
        payment = principal * (monthly_rate * (1 + monthly_rate)**term_months) / ((1 + monthly_rate)**term_months - 1)
        return round(payment, 2)
    
    # ==================== DASHBOARD ====================
    
    def get_financial_summary(self) -> Dict[str, Any]:
        """Get overall financial summary for dashboard."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Pending bills
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM bills WHERE status = 'pending'")
        pending_bills_count, pending_bills_total = cursor.fetchone()
        
        # Overdue bills
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM bills 
            WHERE status = 'pending' AND due_date < date('now')
        """)
        overdue_count, overdue_total = cursor.fetchone()
        
        # Active subscriptions
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
        active_subs = cursor.fetchone()[0]
        
        # Monthly subscription cost
        monthly_subs = self.get_monthly_subscription_total()
        
        # Active loans
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(current_balance), 0), COALESCE(SUM(monthly_payment), 0) FROM loans WHERE status = 'active'")
        active_loans, total_debt, monthly_loan_payments = cursor.fetchone()
        
        conn.close()
        
        return {
            "pending_bills": {"count": pending_bills_count, "total": pending_bills_total},
            "overdue_bills": {"count": overdue_count, "total": overdue_total},
            "subscriptions": {"count": active_subs, "monthly_cost": monthly_subs},
            "loans": {"count": active_loans, "total_debt": total_debt, "monthly_payments": monthly_loan_payments},
            "total_monthly_obligations": round(monthly_subs + (monthly_loan_payments or 0), 2)
        }


# Global instance
financial_service = FinancialService()
