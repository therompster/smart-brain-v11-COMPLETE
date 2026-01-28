"""Enhanced brain dump parsing service.

Handles messy notes with:
- Person-based groupings (GREG:, STEPHANIE-)
- Project headers (TODO for driftguard, TIP AI:)
- Indented sub-items
- Inline item type detection (task, note, idea, question, decision)
- Ambiguous items needing clarification
- Project consolidation suggestions

CONSERVATIVE APPROACH:
- Headers (TIP AI:, ECMP:) are CONTEXT for tasks, not projects
- Systems (AEM, GXP, Syniverse) are tools, not user-owned projects
- Projects are RARE - only explicit "new project" statements
- People are individuals, teams are groups
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

from src.llm.llm_service import llm_service as llm


@dataclass
class ParsedItem:
    """A single item from brain dump."""
    text: str
    context: str  # Person/project it was under
    indent_level: int
    parent_text: Optional[str]  # If this was indented under something
    is_header: bool
    header_type: str  # 'person', 'project', 'section', 'none'


@dataclass 
class StructuredItem:
    """A structured item ready for storage."""
    item_type: str  # 'task', 'note', 'idea', 'question', 'decision', 'project'
    action: str  # Cleaned up text
    original_text: str
    project: Optional[str]
    person: Optional[str]
    context: str
    is_ambiguous: bool
    clarifying_question: Optional[str]
    priority: str
    estimated_minutes: int
    sub_items: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class ProjectConsolidation:
    """Suggestion to consolidate similar projects."""
    variants: List[str]  # ["TIP AI", "tip.ai", "TIP AI stuff"]
    suggested_name: str  # "TIP AI"
    confidence: float
    reason: str


# Systems/tools that should NOT be treated as user projects
SYSTEM_NAMES = {
    'aem', 'gxp', 'syniverse', 'harness', 'ecmp', 'uxl', 'dtt',
    'bonvoy', 'api', 'json', 'templates', 'catalog', 'platform'
}


class BrainDumpService:
    """Parse messy brain dumps into structured data."""
    
    # Common patterns for headers
    PERSON_PATTERNS = [
        r'^([A-Z][A-Z\s]+)\s*[-:–]',  # GREG - or GREG:
        r'^([A-Za-z]+)\s*[-:–]\s*$',   # Greg: (whole line)
        r'^@([A-Za-z]+)',              # @Greg
    ]
    
    PROJECT_PATTERNS = [
        r'^TODO\s+for\s+([A-Za-z0-9_-]+)',  # TODO for driftguard
        r'^([A-Z][A-Z0-9\s]+):\s*$',         # TIP AI: (all caps with colon)
        r'^([A-Z][A-Z0-9\s]{2,})$',          # TIP AI (all caps alone)
        r'^\[([^\]]+)\]',                     # [Project Name]
    ]
    
    def parse_structure(self, content: str) -> List[ParsedItem]:
        """Parse raw content into structured items."""
        lines = content.split('\n')
        items = []
        current_context = None
        current_context_type = 'none'
        last_item_text = None
        
        for line in lines:
            # Skip empty lines
            stripped = line.strip()
            if not stripped:
                continue
            
            # Calculate indent level
            indent = len(line) - len(line.lstrip())
            indent_level = indent // 4 if indent >= 4 else (1 if indent > 0 else 0)
            
            # Check if it's a header
            header_type, header_name = self._detect_header(stripped)
            
            if header_type != 'none':
                current_context = header_name
                current_context_type = header_type
                items.append(ParsedItem(
                    text=stripped,
                    context=header_name,
                    indent_level=0,
                    parent_text=None,
                    is_header=True,
                    header_type=header_type
                ))
                last_item_text = None
            else:
                # Regular item
                parent = last_item_text if indent_level > 0 else None
                items.append(ParsedItem(
                    text=stripped,
                    context=current_context or '',
                    indent_level=indent_level,
                    parent_text=parent,
                    is_header=False,
                    header_type='none'
                ))
                if indent_level == 0:
                    last_item_text = stripped
        
        return items
    
    def _detect_header(self, text: str) -> Tuple[str, str]:
        """Detect if line is a header and return (type, name)."""
        # Check person patterns
        for pattern in self.PERSON_PATTERNS:
            match = re.match(pattern, text)
            if match:
                return 'person', match.group(1).strip()
        
        # Check project patterns
        for pattern in self.PROJECT_PATTERNS:
            match = re.match(pattern, text)
            if match:
                return 'project', match.group(1).strip()
        
        return 'none', ''
    
    def process_brain_dump(self, content: str, domain: str, existing_projects: List = None) -> Dict:
        """
        Process a brain dump and return structured data with item type detection.
        
        Args:
            content: Raw brain dump text
            domain: Domain for routing
            existing_projects: List of existing project dicts or names
        
        Returns:
            {
                "projects_detected": [...],  # Only EXPLICIT new projects (usually empty)
                "people_detected": [...],    # Individual humans only
                "teams_detected": [...],     # Teams, systems, groups
                "items": [...],
                "items_by_type": {"task": [...], "note": [...], ...},
                "ambiguous_items": [...],
                "project_consolidations": [...],
                "project_hierarchy": [...],
                "summary": {...}
            }
        """
        logger.info("Processing brain dump with item type detection")
        
        # Parse structure
        items = self.parse_structure(content)
        
        # Extract unique contexts (these are HEADERS, not projects to create)
        header_contexts = set()
        people_from_headers = set()
        
        for item in items:
            if item.header_type == 'project':
                header_contexts.add(item.context)
            elif item.header_type == 'person':
                people_from_headers.add(item.context)
        
        # Use LLM to structure items with type detection
        structured_items, ambiguous, detected_entities = self._llm_structure_items(
            items, domain, list(header_contexts), list(people_from_headers)
        )
        
        # Extract entities from LLM response
        projects_detected = detected_entities.get('projects', [])
        people_detected = detected_entities.get('people', [])
        teams_detected = detected_entities.get('teams', [])
        
        # Build list of all project names for consolidation check
        all_project_names = list(header_contexts)
        existing_project_names = []
        if existing_projects:
            for p in existing_projects:
                if isinstance(p, dict):
                    existing_project_names.append(p.get('name', str(p)))
                else:
                    existing_project_names.append(str(p))
            all_project_names.extend(existing_project_names)
        
        # Assign items to existing projects (semantic matching)
        if existing_projects:
            structured_items = self._assign_items_to_projects(structured_items, existing_projects)
        
        # Group items by type
        items_by_type = {
            "task": [],
            "note": [],
            "idea": [],
            "question": [],
            "decision": [],
            "project": [],
            "reference": []
        }
        for item in structured_items:
            item_type = item.get('item_type', 'task')
            if item_type in items_by_type:
                items_by_type[item_type].append(item)
            else:
                items_by_type['task'].append(item)
        
        # Get project consolidation suggestions (merge duplicates) - conservative
        consolidations = self._suggest_project_consolidations(existing_project_names, content)
        
        # Get project hierarchy suggestions - conservative
        hierarchy = self._suggest_project_hierarchy(existing_project_names)
        
        return {
            "projects_detected": projects_detected,  # Explicit new projects only
            "people_detected": people_detected,      # Individual humans
            "teams_detected": teams_detected,        # Teams/systems
            "header_contexts": list(header_contexts),  # Headers found (for task assignment)
            "items": structured_items,
            "items_by_type": items_by_type,
            "ambiguous_items": ambiguous,
            "project_consolidations": consolidations,
            "project_hierarchy": hierarchy,
            "summary": {
                "total_items": len([i for i in items if not i.is_header]),
                "total_structured": len(structured_items),
                "tasks": len(items_by_type['task']),
                "notes": len(items_by_type['note']),
                "ideas": len(items_by_type['idea']),
                "questions": len(items_by_type['question']),
                "decisions": len(items_by_type['decision']),
                "projects_defined": len(items_by_type['project']),
                "needs_clarification": len(ambiguous),
                "header_contexts_count": len(header_contexts),
                "people_count": len(people_detected),
                "teams_count": len(teams_detected),
                "consolidation_suggestions": len(consolidations),
                "hierarchy_suggestions": len(hierarchy),
                "items_assigned_to_projects": len([i for i in structured_items if i.get('assigned_project')])
            }
        }
    
    def _llm_structure_items(self, items: List[ParsedItem], domain: str, 
                            header_contexts: List[str], people_from_headers: List[str]) -> Tuple[List[Dict], List[Dict], Dict]:
        """Use LLM to structure items with type detection."""
        
        # Build context for LLM
        items_text = []
        for item in items:
            if item.is_header:
                items_text.append(f"\n[{item.header_type.upper()}: {item.context}]")
            else:
                prefix = "  " * item.indent_level
                context_note = f" (under: {item.parent_text})" if item.parent_text else ""
                items_text.append(f"{prefix}- {item.text}{context_note}")
        
        prompt = f"""Analyze these brain dump items and classify each one.

Domain: {domain}
Headers found (these organize tasks, NOT projects to create): {', '.join(header_contexts) if header_contexts else 'None'}
People from headers: {', '.join(people_from_headers) if people_from_headers else 'None'}

Items:
{''.join(items_text)}

=== CRITICAL RULES ===

**HEADERS vs PROJECTS:**
- Headers like "TIP AI:", "ECMP:", "RAG:" are CONTEXT for organizing tasks
- Put the header name in the "project" FIELD on tasks
- Do NOT add headers to the "projects" array
- The "projects" array is for EXPLICIT "create new project" statements ONLY
- Expected: 0 projects in most brain dumps

**PEOPLE vs TEAMS vs SYSTEMS:**
- PEOPLE (for "person" field): Individual humans ONLY
  Examples: Chris Hunter, Arun, Vijay, Greg, Stephanie
- TEAMS (for "teams" array): Groups, departments
  Examples: Product Team, Engineering, Guest Team, Associate Team
- SYSTEMS (for "teams" array or tags): Tools, platforms
  Examples: AEM, GXP, Syniverse, Harness, ECMP, TIP AI platform, DTT, UXL

**ITEM TYPES:**
- "task": Action needed (DEFAULT - use when uncertain)
- "note": Pure information, fact, constraint (e.g., "AEM will only send JSON")
- "idea": Exploration, not committed
- "question": Needs answer
- "decision": Was/needs to be decided
- "project": EXTREMELY RARE - explicit "new project" only
- "reference": Links, documents

**TASK SIGNAL WORDS:** need to, should, must, talk to, ask, get with, make, create, fix, add, remove, schedule, find, formalize

**NOTE SIGNAL WORDS:** is, has, will, there's, owned by (facts without action verbs)

=== OUTPUT FORMAT ===
{{
  "projects": [],  // Usually EMPTY - only explicit new project definitions
  "people": [
    {{"name": "Chris Hunter", "role": "owns AEM", "context": "from notes"}}
  ],
  "teams": [
    {{"name": "GXP", "type": "system", "context": "suggested actions workflow"}},
    {{"name": "Product Team", "type": "department", "context": "intake process"}}
  ],
  "items": [
    {{
      "item_type": "task",
      "action": "Talk to Chris Hunter about extra AI engineering resources",
      "original_text": "talk to chris hunter about extra AI eng",
      "project": "TIP AI",
      "person": "Chris Hunter",
      "team": null,
      "context": "temporary solution needed",
      "is_ambiguous": false,
      "clarifying_question": null,
      "priority": "medium",
      "estimated_minutes": 30,
      "sub_items": [],
      "tags": ["ai", "staffing"]
    }},
    {{
      "item_type": "note",
      "action": "AEM is owned by Chris Hunter",
      "original_text": "AEM is owned by him",
      "project": "TIP AI",
      "person": "Chris Hunter",
      "team": null,
      "context": "ownership info",
      "is_ambiguous": false,
      "clarifying_question": null,
      "priority": "low",
      "estimated_minutes": 0,
      "sub_items": [],
      "tags": ["aem", "ownership"]
    }}
  ],
  "ambiguous_items": [
    {{
      "text": "theres a go fetch",
      "question": "What is 'go fetch' and what action is needed?",
      "suggested_type": "note"
    }}
  ]
}}

REMEMBER:
- "projects" array should be EMPTY unless user explicitly says "create new project"
- Headers (TIP AI, ECMP, RAG) go in "project" FIELD on items, not projects array
- GXP, DTT, AEM = systems → "teams" array with type="system"
- Product Team, Engineering = departments → "teams" array with type="department"
- Chris Hunter, Arun = individuals → "people" array
- Default to item_type="task" when uncertain

Return ONLY the JSON."""

        try:
            response = llm.generate_json(prompt, task_type='task_extraction')
            
            items_list = response.get("items", [])
            ambiguous = response.get("ambiguous_items", [])
            
            # Extract entities - filter out invalid ones
            raw_projects = response.get("projects", [])
            raw_people = response.get("people", [])
            raw_teams = response.get("teams", [])
            
            # Filter projects - remove systems/tools that aren't user projects
            valid_projects = []
            for p in raw_projects:
                name = p.get('name', '') if isinstance(p, dict) else str(p)
                name_lower = name.lower().strip()
                # Only keep if not a system name and has real confidence
                if name_lower not in SYSTEM_NAMES and len(name) > 2:
                    if isinstance(p, dict) and p.get('confidence', 0) > 0.8:
                        valid_projects.append(p)
            
            # Filter people - remove team/system names
            valid_people = []
            for p in raw_people:
                name = p.get('name', '') if isinstance(p, dict) else str(p)
                name_lower = name.lower().strip()
                # Must have a space (first + last name) or be from headers
                # and not be a system/team name
                if name_lower not in SYSTEM_NAMES:
                    if ' ' in name or name in people_from_headers:
                        valid_people.append(p)
            
            detected_entities = {
                'projects': valid_projects,
                'people': valid_people,
                'teams': raw_teams
            }
            
            return items_list, ambiguous, detected_entities
            
        except Exception as e:
            logger.error(f"LLM structuring failed: {e}")
            return [], [], {'projects': [], 'people': [], 'teams': []}
    
    def _suggest_project_consolidations(self, project_names: List[str], content: str) -> List[Dict]:
        """Suggest project consolidations - CONSERVATIVE, only obvious duplicates."""
        if len(project_names) < 2:
            return []
        
        prompt = f"""Look for OBVIOUS duplicate project names that should be merged.

Existing project names: {', '.join(project_names)}

ONLY suggest consolidation if:
- Same name with different casing (TIP AI vs tip ai)
- Same name with typo (ECMP vs ECNP)
- Obvious abbreviation (TIP.AI vs TIP AI)

Do NOT suggest consolidation for:
- Different projects that are related (ECMP and ECMP AI are different)
- Projects that might overlap but are distinct

{{
  "variants": ["TIP AI", "tip.ai"],
  "suggested_name": "TIP AI",
  "confidence": 0.95,
  "reason": "Same project name with different format"
}}

Return JSON array. Usually return [] (empty).
Only include if confidence > 0.9.

Return ONLY JSON array."""

        try:
            response = llm.generate_json(prompt, task_type='routing')
            if isinstance(response, list):
                return [c for c in response if c.get('confidence', 0) > 0.9][:2]
            return [c for c in response.get("consolidations", []) if c.get('confidence', 0) > 0.9][:2]
        except Exception as e:
            logger.error(f"Project consolidation suggestion failed: {e}")
            return []
    
    def _suggest_project_hierarchy(self, project_names: List[str]) -> List[Dict]:
        """Suggest parent-child relationships - CONSERVATIVE."""
        if len(project_names) < 2:
            return []
        
        prompt = f"""Look for OBVIOUS parent-child project relationships.

Projects: {', '.join(project_names)}

ONLY suggest hierarchy if:
- One project name contains another (ECMP AI → ECMP)
- One is clearly a sub-project with explicit naming (Phase 1 → Main Project)

Do NOT suggest:
- Related but separate projects
- Uncertain relationships

{{
  "child_project": "ECMP AI Features",
  "parent_project": "ECMP", 
  "confidence": 0.9,
  "reason": "ECMP AI Features is explicitly part of ECMP"
}}

Return JSON array. Usually return [] (empty).
Only include if confidence > 0.85 and BOTH projects exist.

Return ONLY JSON array."""

        try:
            response = llm.generate_json(prompt, task_type='routing')
            if isinstance(response, list):
                # Verify both projects exist
                valid = []
                for h in response:
                    if (h.get('confidence', 0) > 0.85 and 
                        h.get('child_project') in project_names and 
                        h.get('parent_project') in project_names):
                        valid.append(h)
                return valid[:2]
            return []
        except Exception as e:
            logger.error(f"Project hierarchy suggestion failed: {e}")
            return []
    
    def _assign_items_to_projects(self, items: List[Dict], existing_projects: List[Dict]) -> List[Dict]:
        """Assign items to existing projects using semantic matching."""
        if not items or not existing_projects:
            return items
        
        # Build project context for LLM
        project_context = []
        for p in existing_projects:
            if isinstance(p, dict):
                project_context.append(f"- {p.get('name', p)}: {p.get('description', 'No description')}")
            else:
                project_context.append(f"- {p}")
        
        # Prepare items (just text for assignment)
        item_texts = []
        for i, item in enumerate(items):
            text = item.get('action', item.get('original_text', ''))
            context = item.get('project', item.get('context', ''))
            item_texts.append(f"{i}. [{context}] {text}")
        
        prompt = f"""Assign these items to the most relevant existing project.

EXISTING PROJECTS:
{chr(10).join(project_context)}

ITEMS TO ASSIGN:
{chr(10).join(item_texts)}

For each item:
{{
  "item_index": 0,
  "assigned_project": "Project Name" or null,
  "confidence": 0.8,
  "reason": "Brief explanation"
}}

Rules:
- Only assign if clearly related (confidence > 0.7)
- Use null if item doesn't fit any project
- The [context] hint shows what header it was under - use this

Return JSON array with one object per item.
Return ONLY JSON array."""

        try:
            response = llm.generate_json(prompt, task_type='routing')
            assignments = response if isinstance(response, list) else response.get("assignments", [])
            
            # Apply assignments to items
            for assignment in assignments:
                idx = assignment.get('item_index')
                if idx is not None and 0 <= idx < len(items):
                    if assignment.get('confidence', 0) > 0.7 and assignment.get('assigned_project'):
                        items[idx]['assigned_project'] = assignment['assigned_project']
                        items[idx]['assignment_confidence'] = assignment['confidence']
                        items[idx]['assignment_reason'] = assignment.get('reason', '')
            
            return items
            
        except Exception as e:
            logger.error(f"Item-to-project assignment failed: {e}")
            return items
    
    def suggest_projects_from_content(self, content: str, existing_projects: List[str]) -> List[Dict]:
        """Suggest new projects - VERY CONSERVATIVE. Only explicit new initiatives."""
        
        prompt = f"""Analyze this content for EXPLICIT new project definitions ONLY.

Content:
{content[:2000]}

Existing projects: {', '.join(existing_projects) if existing_projects else 'None'}

=== STRICT RULES ===

DO NOT suggest projects for:
- Headers organizing tasks (TIP AI:, ECMP:, RAG:) - these are CONTEXT, not projects
- Systems/tools mentioned (AEM, Syniverse, GXP, Harness) - user doesn't own these
- Task clusters around a theme - those are just grouped tasks
- Features or improvements to existing systems
- Anything without explicit "new project", "new initiative", "launch", "build new"

ONLY suggest a project if user EXPLICITLY writes:
- "new project: X" or "create project for X"
- "launching new initiative"  
- "starting new product/system we're building from scratch"

Expected output: EMPTY array []. New projects are very rare in brain dumps.

If you find an EXPLICIT project definition (rare):
{{
  "name": "Project Name",
  "description": "What user explicitly said about it",
  "confidence": 0.95,
  "evidence": "Exact quote showing explicit project creation intent"
}}

Return JSON array. Return [] if no EXPLICIT project definitions found.
Return ONLY JSON array."""

        try:
            response = llm.generate_json(prompt, task_type='routing')
            suggestions = response if isinstance(response, list) else response.get("projects", [])
            # Only return if confidence > 0.9 AND has explicit evidence
            return [s for s in suggestions if s.get('confidence', 0) > 0.9 and s.get('evidence')][:2]
        except Exception as e:
            logger.error(f"Project suggestion failed: {e}")
            return []
    
    def batch_process_notes(self, notes: List[Dict]) -> Dict:
        """Process multiple notes and consolidate."""
        all_projects = set()
        all_people = set()
        all_tasks = []
        all_ambiguous = []
        
        for note in notes:
            result = self.process_brain_dump(note['content'], note.get('domain', 'work'))
            all_projects.update(result.get('header_contexts', []))
            all_people.update([p.get('name', p) for p in result.get('people_detected', [])])
            all_tasks.extend(result['items'])
            all_ambiguous.extend(result['ambiguous_items'])
        
        # Deduplicate tasks by similarity
        unique_tasks = self._dedupe_tasks(all_tasks)
        
        return {
            "header_contexts": list(all_projects),
            "people_detected": list(all_people),
            "tasks": unique_tasks,
            "ambiguous_items": all_ambiguous,
            "summary": {
                "notes_processed": len(notes),
                "total_tasks": len(unique_tasks),
                "duplicates_removed": len(all_tasks) - len(unique_tasks),
                "needs_clarification": len(all_ambiguous)
            }
        }
    
    def _dedupe_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Remove duplicate tasks by action similarity."""
        if not tasks:
            return []
        
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            actions = [t.get('action', t.get('original_text', '')) for t in tasks]
            embeddings = model.encode(actions)
            
            keep = []
            seen_indices = set()
            
            for i, task in enumerate(tasks):
                if i in seen_indices:
                    continue
                
                keep.append(task)
                
                # Mark similar tasks as seen
                for j in range(i + 1, len(tasks)):
                    if j in seen_indices:
                        continue
                    similarity = np.dot(embeddings[i], embeddings[j])
                    if similarity > 0.85:
                        seen_indices.add(j)
                        # Merge sub_tasks if any
                        if tasks[j].get('sub_tasks'):
                            existing = task.get('sub_tasks', [])
                            task['sub_tasks'] = list(set(existing + tasks[j]['sub_tasks']))
            
            return keep
            
        except Exception as e:
            logger.warning(f"Deduplication failed, returning all: {e}")
            return tasks


# Global instance
brain_dump_service = BrainDumpService()