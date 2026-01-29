"""Brain dump service - LLM-FIRST approach with hierarchical project support.

Supports:
- Platform: Top-level thing user owns/builds (like iOS, ECMP)
- Module: Major subsystem that can have children (ECMP AI under ECMP)
- Service: Leaf-level capability (RAG, Consent, Messaging)
- System: External tool user integrates WITH but doesn't own (TIP.AI, AEM, Syniverse)
"""

import sqlite3
from typing import List, Dict, Optional
from loguru import logger

from src.llm.llm_service import llm_service as llm
from src.config import settings


class EntityCache:
    """Cache for learned entity classifications."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.sqlite_db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Learned entities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_entities (
                    name TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT,
                    confidence REAL DEFAULT 0.7,
                    user_corrected BOOLEAN DEFAULT FALSE,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Migration: add canonical_name if missing
            try:
                conn.execute("ALTER TABLE learned_entities ADD COLUMN canonical_name TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Add project_type to projects table if missing
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN project_type TEXT DEFAULT 'project'")
            except sqlite3.OperationalError:
                pass
            
            # Add parent_project_id if missing (for hierarchy)
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN parent_project_id INTEGER REFERENCES projects(id)")
            except sqlite3.OperationalError:
                pass
            
            # Add integrates_with for tracking external system connections
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN integrates_with TEXT")
            except sqlite3.OperationalError:
                pass
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Table setup failed: {e}")
    
    def get_all(self) -> Dict[str, Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT name, entity_type, canonical_name, user_corrected FROM learned_entities")
            result = {}
            for row in cursor:
                result[row[0].lower()] = {
                    "entity_type": row[1],
                    "canonical_name": row[2],
                    "user_corrected": bool(row[3])
                }
            conn.close()
            return result
        except:
            return {}
    
    def save(self, name: str, entity_type: str, canonical_name: str = None, user_corrected: bool = False):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO learned_entities (name, entity_type, canonical_name, user_corrected)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    canonical_name = excluded.canonical_name,
                    user_corrected = CASE WHEN excluded.user_corrected THEN 1 ELSE user_corrected END,
                    last_seen = CURRENT_TIMESTAMP
            """, (name.lower(), entity_type, canonical_name or name, user_corrected))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def learn_from_user(self, corrections: Dict[str, str]):
        for name, chosen_type in corrections.items():
            # Map UI choices to entity types
            if chosen_type in ("platform", "module", "service"):
                entity_type = chosen_type
            elif chosen_type == "system":
                entity_type = "system"
            elif chosen_type == "project":
                entity_type = "platform"  # Default owned things to platform
            else:
                continue
            self.save(name, entity_type, user_corrected=True)
            logger.info(f"Learned: {name} -> {entity_type}")


class BrainDumpService:
    """LLM-first brain dump processing with hierarchy support."""
    
    def __init__(self):
        self.cache = EntityCache()
    
    def process_brain_dump(self, content: str, domain: str,
                          existing_projects: List[Dict] = None,
                          organization_choices: Dict = None) -> Dict:
        logger.info("Processing brain dump (LLM-first with hierarchy)")
        
        if organization_choices:
            self.cache.learn_from_user(organization_choices.get("group_assignments", {}))
        
        known_entities = self.cache.get_all()
        existing_names = [p.get('name', str(p)) if isinstance(p, dict) else str(p) 
                        for p in (existing_projects or [])]
        
        known_context = ""
        if known_entities:
            known_context = "Previously learned entities:\n"
            for name, info in list(known_entities.items())[:20]:
                known_context += f"  - {name}: {info['entity_type']}"
                if info['user_corrected']:
                    known_context += " (user confirmed)"
                known_context += "\n"
        
        existing_context = ""
        if existing_names:
            existing_context = f"Existing projects in system: {', '.join(existing_names)}\n"
        
        prompt = f"""You are processing a messy brain dump for a productivity system.

DOMAIN: {domain}

{known_context}
{existing_context}

=== RAW BRAIN DUMP ===
{content}
=== END BRAIN DUMP ===

Analyze this completely and return a structured JSON response.

YOUR TASKS:
1. IDENTIFY GROUPS - Find organizational headers
2. CLASSIFY GROUPS using this hierarchy:
   - PLATFORM: Top-level thing user owns/builds (like iOS, ECMP)
   - MODULE: Major subsystem that can have children (ECMP AI under ECMP)
   - SERVICE: Leaf-level capability (RAG, Consent, Messaging)
   - SYSTEM: External tool user integrates WITH but doesn't own (TIP.AI, AEM, Syniverse, GXP)
   - PERSON: Human being
3. DETECT HIERARCHY - "ECMP AI" under "ECMP", "ECMP RAG" under "ECMP AI"
4. MERGE DUPLICATES - "ECMP NOTES" and "ECMP" are the same
5. FILTER GARBAGE - Skip "---", "yes", meaningless items
6. FIX TYPOS - Clean up obvious typos
7. CLASSIFY ITEMS - task, note, idea, question, decision, reference

CLASSIFICATION RULES:
- PLATFORM: User owns/builds, top-level, has sub-components
- MODULE: User owns, has children, part of a platform
- SERVICE: User owns, leaf-level capability
- SYSTEM: External tool/service user integrates WITH (TIP.AI, AEM, Syniverse)
- PERSON: Human being

ITEM TYPE RULES:
- TASK: Has action verb (need to, should, must, talk to, create, fix, send)
- NOTE: Pure fact/info (is, has, will, uses, supports)
- QUESTION: Contains "?" or "what if"
- IDEA: Exploration (could, might, maybe)
- DECISION: "decided", "agreed", "we will"
- REFERENCE: URLs, doc links

RETURN THIS JSON STRUCTURE:
{{
  "groups": [
    {{
      "name": "Canonical Name",
      "type": "platform|module|service|system|person",
      "parent": "Parent group name or null",
      "confidence": 0.85,
      "reason": "Why this classification",
      "merged_from": ["ECMP NOTES", "ECMP"],
      "items_count": 14,
      "integrates_with": ["TIP.AI"]
    }}
  ],
  "hierarchy": [
    {{
      "child": "ECMP AI",
      "parent": "ECMP",
      "reason": "ECMP AI is a module within ECMP platform"
    }}
  ],
  "items": [
    {{
      "type": "task|note|idea|question|decision|reference",
      "text": "Cleaned up text",
      "original": "Original messy text",
      "group": "Which group this belongs to",
      "person": "Person mentioned or null",
      "priority": "high|medium|low",
      "tags": ["relevant", "tags"]
    }}
  ],
  "ambiguous": [
    {{
      "text": "vague text",
      "question": "What is this?",
      "suggestions": ["option 1", "option 2"]
    }}
  ],
  "people_mentioned": [
    {{"name": "Chris Hunter", "context": "Owns AEM integration"}}
  ],
  "typos_fixed": [
    {{"from": "synbiverse", "to": "Syniverse"}}
  ],
  "garbage_filtered": ["---", "yes"],
  "summary": {{
    "total_raw_lines": 50,
    "total_useful_items": 42,
    "garbage_removed": 8,
    "typos_fixed": 3,
    "groups_found": 5,
    "groups_merged": 2
  }}
}}

Be thorough. Return ONLY valid JSON."""

        try:
            result = llm.generate_json(prompt, task_type='task_extraction')
            
            for group in result.get("groups", []):
                self.cache.save(
                    name=group["name"],
                    entity_type=group["type"],
                    canonical_name=group["name"]
                )
            
            return self._transform_result(result, existing_projects)
            
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return self._fallback_response(content)
    
    def _transform_result(self, llm_result: Dict, existing_projects: List[Dict] = None) -> Dict:
        groups = llm_result.get("groups", [])
        items = llm_result.get("items", [])
        
        existing_names = set()
        if existing_projects:
            for p in existing_projects:
                name = p.get('name', str(p)) if isinstance(p, dict) else str(p)
                existing_names.add(name.lower())
        
        org_groups = []
        for g in groups:
            suggested = g.get("type", "service")
            if g["name"].lower() in existing_names:
                suggested = "existing"
            
            org_groups.append({
                "name": g["name"],
                "type": g["type"],
                "parent": g.get("parent"),
                "items_count": g.get("items_count", 0),
                "sample_items": [i["text"][:100] for i in items if i.get("group", "").lower() == g["name"].lower()][:5],
                "suggested_as": suggested,
                "confidence": g.get("confidence", 0.7),
                "classification_reason": g.get("reason", ""),
                "merged_from": g.get("merged_from", []),
                "integrates_with": g.get("integrates_with", [])
            })
        
        items_by_type = {
            "task": [], "note": [], "idea": [], "question": [],
            "decision": [], "project": [], "reference": []
        }
        
        structured_items = []
        for item in items:
            item_type = item.get("type", "task")
            structured = {
                "item_type": item_type,
                "action": item.get("text", ""),
                "original_text": item.get("original", item.get("text", "")),
                "project": item.get("group"),
                "person": item.get("person"),
                "priority": item.get("priority", "medium"),
                "tags": item.get("tags", []),
                "is_ambiguous": False
            }
            structured_items.append(structured)
            
            if item_type in items_by_type:
                items_by_type[item_type].append(structured)
            else:
                items_by_type["task"].append(structured)
        
        summary = llm_result.get("summary", {})
        
        return {
            "detected_organization": {
                "groups": org_groups,
                "unassigned_count": len([i for i in items if not i.get("group")]),
                "unassigned_samples": [i["text"][:100] for i in items if not i.get("group")][:5],
                "needs_organization": len(org_groups) > 0
            },
            "items": structured_items,
            "items_by_type": items_by_type,
            "ambiguous_items": llm_result.get("ambiguous", []),
            "people_detected": llm_result.get("people_mentioned", []),
            "teams_detected": [g for g in groups if g["type"] == "system"],
            "projects_detected": [g for g in groups if g["type"] in ("platform", "module", "service")],
            "project_consolidations": [],
            "project_hierarchy": llm_result.get("hierarchy", []),
            "header_contexts": [g["name"] for g in groups],
            "typos_fixed": llm_result.get("typos_fixed", []),
            "garbage_filtered": llm_result.get("garbage_filtered", []),
            "summary": {
                "total_items": summary.get("total_useful_items", len(items)),
                "total_structured": len(structured_items),
                "tasks": len(items_by_type["task"]),
                "notes": len(items_by_type["note"]),
                "ideas": len(items_by_type["idea"]),
                "questions": len(items_by_type["question"]),
                "decisions": len(items_by_type["decision"]),
                "needs_clarification": len(llm_result.get("ambiguous", [])),
                "garbage_removed": summary.get("garbage_removed", 0),
                "typos_fixed": summary.get("typos_fixed", 0),
                "groups_merged": summary.get("groups_merged", 0),
                "organization_groups": len(org_groups),
                "people_count": len(llm_result.get("people_mentioned", [])),
                "hierarchy_suggestions": len(llm_result.get("hierarchy", []))
            }
        }
    
    def _fallback_response(self, content: str) -> Dict:
        lines = [l.strip() for l in content.split('\n') if l.strip() and l.strip() not in ('---', '-', '----')]
        return {
            "detected_organization": {"groups": [], "unassigned_count": len(lines), "needs_organization": True},
            "items": [{"item_type": "task", "action": l, "original_text": l} for l in lines],
            "items_by_type": {"task": [], "note": [], "idea": [], "question": [], "decision": [], "reference": []},
            "ambiguous_items": [],
            "people_detected": [],
            "teams_detected": [],
            "projects_detected": [],
            "project_consolidations": [],
            "project_hierarchy": [],
            "header_contexts": [],
            "summary": {"total_items": len(lines), "error": "LLM processing failed"}
        }
    
    def suggest_projects_from_content(self, content: str, existing_projects: List[str]) -> List[str]:
        return []


brain_dump_service = BrainDumpService()