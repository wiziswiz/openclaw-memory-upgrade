#!/usr/bin/env python3
"""
Extraction Pipeline Agent
Scans daily notes for new facts and extracts them to entity items.json files.
Designed to run as cron job or on-demand.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Set
import uuid

def get_workspace_dir() -> str:
    """Get workspace directory from environment or current working directory."""
    return os.environ.get('WORKSPACE_DIR', os.getcwd())

class ExtractionPipeline:
    def __init__(self, workspace_dir: str = None, dry_run: bool = False):
        self.workspace_dir = workspace_dir or get_workspace_dir()
        self.dry_run = dry_run
        self.checkpoint_file = Path(self.workspace_dir) / ".last-extraction.json"
        self.memory_dir = Path(self.workspace_dir) / "memory"
        self.entities_dir = Path(self.workspace_dir) / "life" / "areas"
        
        # Import existing memory typing logic
        self.type_patterns = self._load_type_patterns()
        
    def _load_type_patterns(self) -> Dict[str, List[str]]:
        """Load memory typing patterns for auto-classification."""
        return {
            'profile': [
                r'\\b(works? at|employed by|job at|position at|role at)\\b',
                r'\\b(based in|located in|lives? in|from)\\b',
                r'\\b(age \\d+|born in|\\d+ years old)\\b',
                r'\\b(education|degree|graduated|studied at)\\b'
            ],
            'preference': [
                r'\\b(prefers?|likes?|dislikes?|hates?|loves?)\\b',
                r'\\b(favorite|favourite|best|worst)\\b',
                r'\\b(wants?|needs?|requires?)\\b.*\\b(reminders?|notifications?)\\b',
                r'\\b(uses?|tools?).*\\b(slack|email|linear|notion|jira)\\b'
            ],
            'milestone': [
                r'\\b(completed|finished|shipped|launched|released)\\b',
                r'\\b(promoted|hired|fired|left|joined)\\b',
                r'\\b(achieved|reached|hit|exceeded)\\b.*\\b(target|goal|milestone)\\b',
                r'\\b(won|earned|received|got)\\b.*\\b(award|prize|recognition)\\b'
            ],
            'relationship': [
                r'\\b(reports? to|managed? by|team lead|manager)\\b',
                r'\\b(married to|partner|spouse|dating)\\b',
                r'\\b(friend|colleague|teammate|collaborator)\\b',
                r'\\b(met through|introduced by|connected via)\\b'
            ],
            'event': [
                r'\\b(meeting|call|conference|interview)\\b.*\\b(scheduled|planned|upcoming)\\b',
                r'\\b(traveling|trip|vacation|visiting)\\b',
                r'\\b(speaking at|presenting|attending)\\b.*\\b(conference|event|meetup)\\b',
                r'\\b(deadline|due date|target date)\\b'
            ],
            'decision': [
                r'\\b(decided|chose|selected|picked)\\b',
                r'\\b(will use|switching to|moving to|adopting)\\b',
                r'\\b(approved|rejected|cancelled|postponed)\\b',
                r'\\b(agreed|disagreed|consensus|voted)\\b'
            ],
            'task': [
                r'\\b(todo|task|action item|follow[- ]up)\\b',
                r'\\b(assigned|delegated|responsible for)\\b',
                r'\\b(needs? to|should|must|have to)\\b',
                r'\\b(remind|ping|check in|follow up)\\b'
            ],
            'opportunity': [
                r'\\b(interested in|exploring|considering)\\b.*\\b(partnership|collaboration)\\b',
                r'\\b(potential|opportunity|lead|prospect)\\b',
                r'\\b(looking for|seeking|need|want)\\b.*\\b(investment|funding|partners?)\\b'
            ]
        }
    
    def load_checkpoint(self) -> datetime:
        """Load last extraction checkpoint or return default start date."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_processed'])
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        # Default to 7 days ago if no checkpoint
        return datetime.now() - timedelta(days=7)
    
    def save_checkpoint(self, last_processed: datetime):
        """Save extraction checkpoint."""
        if not self.dry_run:
            checkpoint_data = {
                'last_processed': last_processed.isoformat(),
                'last_run': datetime.now().isoformat()
            }
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
    
    def get_daily_notes_to_process(self, since_date: datetime = None) -> List[Path]:
        """Get list of daily notes to process since last checkpoint."""
        if since_date is None:
            since_date = self.load_checkpoint()
        
        daily_notes = []
        if not self.memory_dir.exists():
            return daily_notes
        
        for note_file in self.memory_dir.glob("*.md"):
            # Extract date from filename (YYYY-MM-DD.md)
            try:
                date_str = note_file.stem
                note_date = datetime.strptime(date_str, "%Y-%m-%d")
                if note_date > since_date:
                    daily_notes.append(note_file)
            except ValueError:
                # Skip files that don't match date format
                continue
        
        return sorted(daily_notes)
    
    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """Extract mentions of people, companies, and projects from text."""
        entities = {
            'people': [],
            'companies': [],
            'projects': []
        }
        
        # People patterns (names with capitals)
        people_patterns = [
            r'\\b([A-Z][a-z]+ [A-Z][a-z]+)\\b',  # First Last
            r'\\b([A-Z][a-z]+)\\s+(?:said|told|mentioned|asked|wants?)\\b',  # Name + verb
            r'\\b(?:met with|talked to|called|emailed)\\s+([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\b'
        ]
        
        # Company patterns
        company_patterns = [
            r'\\b([A-Z][a-zA-Z]*(?:\\s+[A-Z][a-zA-Z]*)*(?:\\s+(?:Inc|Corp|LLC|Ltd|Co)\\.?))\\b',
            r'\\b(Google|Apple|Microsoft|Amazon|Meta|Tesla|OpenAI|Anthropic)\\b',
            r'\\bat\\s+([A-Z][a-zA-Z]+(?:\\s+[A-Z][a-zA-Z]+)*)\\b'  # "at Company"
        ]
        
        # Project patterns
        project_patterns = [
            r'\\b(project\\s+([A-Z][a-zA-Z-]+))\\b',
            r'\\b([A-Z][a-zA-Z-]+\\s+(?:project|initiative|program))\\b',
            r'\\bworking on\\s+([A-Z][a-zA-Z-]+(?:\\s+[A-Z][a-zA-Z-]+)?)\\b'
        ]
        
        # Extract entities
        for pattern in people_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['people'].extend([match.strip() for match in matches if isinstance(match, str)])
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            entities['companies'].extend([match.strip() for match in matches if isinstance(match, str)])
        
        for pattern in project_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    entities['projects'].extend([m.strip() for m in match if m.strip()])
                else:
                    entities['projects'].append(match.strip())
        
        # Clean and deduplicate
        for entity_type in entities:
            # Remove common false positives
            entities[entity_type] = [
                entity for entity in set(entities[entity_type])
                if len(entity) > 2 and not entity.lower() in ['the', 'and', 'inc', 'corp', 'ltd', 'llc']
            ]
        
        return entities
    
    def classify_fact(self, fact: str) -> tuple:
        """Classify a fact into category and type using memory-typing logic."""
        fact_lower = fact.lower()
        
        for category, patterns in self.type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, fact_lower):
                    # Determine more specific type based on category
                    if category == 'profile':
                        if 'work' in fact_lower or 'job' in fact_lower:
                            return category, 'role'
                        elif 'location' in fact_lower or 'based' in fact_lower:
                            return category, 'location'
                        else:
                            return category, 'bio'
                    elif category == 'preference':
                        if 'tool' in fact_lower or 'use' in fact_lower:
                            return category, 'tool'
                        else:
                            return category, 'behavior'
                    elif category == 'milestone':
                        return category, 'achievement'
                    elif category == 'event':
                        return category, 'scheduled'
                    else:
                        return category, category
        
        # Default classification
        return 'knowledge', 'general'
    
    def extract_facts_from_text(self, text: str, source_date: str) -> List[Dict[str, Any]]:
        """Extract structured facts from text content."""
        facts = []
        
        # Split into sentences for fact extraction
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Skip metadata lines (markdown headers, timestamps, etc.)
            if sentence.startswith('#') or sentence.startswith('*') or sentence.startswith('-'):
                continue
            
            # Extract mentioned entities
            entities = self.extract_entities_from_text(sentence)
            
            # Check if sentence contains factual information
            fact_indicators = [
                r'\\b(decided|chose|will|wants?|needs?|prefers?|uses?)\\b',
                r'\\b(completed|finished|started|began|launched)\\b',
                r'\\b(met with|talked to|assigned|delegated)\\b',
                r'\\b(works? at|based in|responsible for)\\b'
            ]
            
            has_fact = any(re.search(pattern, sentence.lower()) for pattern in fact_indicators)
            
            if has_fact or any(entities.values()):
                category, fact_type = self.classify_fact(sentence)
                
                fact = {
                    'id': str(uuid.uuid4())[:8],  # Short ID
                    'fact': sentence,
                    'category': category,
                    'type': fact_type,
                    'timestamp': source_date,
                    'source': 'extraction_pipeline',
                    'status': 'active',
                    'supersededBy': None,
                    'entities': entities
                }
                
                facts.append(fact)
        
        return facts
    
    def get_entity_path(self, entity_type: str, entity_name: str) -> Path:
        """Get the path for an entity's directory."""
        # Normalize entity name for directory
        normalized_name = entity_name.lower().replace(' ', '-').replace('.', '')
        return self.entities_dir / entity_type / normalized_name
    
    def ensure_entity_exists(self, entity_type: str, entity_name: str):
        """Ensure entity directory and files exist."""
        entity_path = self.get_entity_path(entity_type, entity_name)
        
        if not self.dry_run:
            entity_path.mkdir(parents=True, exist_ok=True)
            
            # Create items.json if it doesn't exist
            items_file = entity_path / "items.json"
            if not items_file.exists():
                with open(items_file, 'w') as f:
                    json.dump([], f, indent=2)
            
            # Create summary.md if it doesn't exist
            summary_file = entity_path / "summary.md"
            if not summary_file.exists():
                with open(summary_file, 'w') as f:
                    f.write(f"# {entity_name}\n\n*Auto-generated entity - needs manual summary*\n")
    
    def load_existing_facts(self, entity_path: Path) -> List[Dict[str, Any]]:
        """Load existing facts from entity items.json."""
        items_file = entity_path / "items.json"
        if items_file.exists():
            try:
                with open(items_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def check_duplicate_fact(self, new_fact: str, existing_facts: List[Dict[str, Any]]) -> bool:
        """Check if fact already exists using simple similarity."""
        new_fact_normalized = new_fact.lower().strip()
        
        for existing in existing_facts:
            if existing.get('status') != 'active':
                continue
            
            existing_fact = existing.get('fact', '').lower().strip()
            
            # Simple similarity check (could be enhanced)
            if new_fact_normalized == existing_fact:
                return True
            
            # Check if substantially similar (80%+ word overlap)
            new_words = set(new_fact_normalized.split())
            existing_words = set(existing_fact.split())
            
            if len(new_words) > 0 and len(existing_words) > 0:
                overlap = len(new_words.intersection(existing_words))
                similarity = overlap / min(len(new_words), len(existing_words))
                if similarity > 0.8:
                    return True
        
        return False
    
    def write_fact_to_entity(self, fact: Dict[str, Any], entity_type: str, entity_name: str) -> bool:
        """Write a fact to the appropriate entity's items.json."""
        entity_path = self.get_entity_path(entity_type, entity_name)
        
        # Ensure entity exists
        self.ensure_entity_exists(entity_type, entity_name)
        
        # Load existing facts
        existing_facts = self.load_existing_facts(entity_path)
        
        # Check for duplicates
        if self.check_duplicate_fact(fact['fact'], existing_facts):
            return False  # Duplicate, skip
        
        # Add new fact
        existing_facts.append(fact)
        
        # Write back to file
        if not self.dry_run:
            items_file = entity_path / "items.json"
            with open(items_file, 'w') as f:
                json.dump(existing_facts, f, indent=2)
        
        return True  # Successfully added
    
    def process_daily_note(self, note_file: Path) -> Dict[str, Any]:
        """Process a single daily note file and extract facts."""
        try:
            with open(note_file, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            return {'processed': False, 'error': 'File not found'}
        
        date_str = note_file.stem
        
        # Extract facts from content
        facts = self.extract_facts_from_text(content, date_str)
        
        results = {
            'processed': True,
            'total_facts': len(facts),
            'written_facts': 0,
            'skipped_duplicates': 0,
            'entities_created': [],
            'entities_updated': []
        }
        
        # Process each fact
        for fact in facts:
            entities = fact.pop('entities', {})
            fact_written = False
            
            # Write fact to relevant entities
            for entity_type, entity_names in entities.items():
                for entity_name in entity_names:
                    if self.write_fact_to_entity(fact.copy(), entity_type, entity_name):
                        results['written_facts'] += 1
                        fact_written = True
                        
                        entity_key = f"{entity_type}/{entity_name}"
                        if entity_key not in results['entities_updated']:
                            results['entities_updated'].append(entity_key)
            
            if not fact_written and not entities:
                # Fact with no specific entities - could be general knowledge
                # For now, skip or could write to a general knowledge store
                results['skipped_duplicates'] += 1
        
        return results
    
    def run_extraction(self, since_date: datetime = None) -> Dict[str, Any]:
        """Run the extraction pipeline for daily notes since the given date."""
        if since_date is None:
            since_date = self.load_checkpoint()
        
        # Get daily notes to process
        daily_notes = self.get_daily_notes_to_process(since_date)
        
        overall_results = {
            'processed_files': 0,
            'total_facts': 0,
            'written_facts': 0,
            'skipped_duplicates': 0,
            'entities_updated': set(),
            'errors': []
        }
        
        print(f"Processing {len(daily_notes)} daily notes since {since_date.strftime('%Y-%m-%d')}")
        
        latest_processed = since_date
        
        for note_file in daily_notes:
            print(f"Processing {note_file.name}...")
            
            results = self.process_daily_note(note_file)
            
            if results['processed']:
                overall_results['processed_files'] += 1
                overall_results['total_facts'] += results['total_facts']
                overall_results['written_facts'] += results['written_facts']
                overall_results['skipped_duplicates'] += results['skipped_duplicates']
                overall_results['entities_updated'].update(results['entities_updated'])
                
                # Update latest processed date
                try:
                    note_date = datetime.strptime(note_file.stem, "%Y-%m-%d")
                    if note_date > latest_processed:
                        latest_processed = note_date
                except ValueError:
                    pass
            else:
                overall_results['errors'].append(f"{note_file.name}: {results.get('error', 'Unknown error')}")
        
        # Save checkpoint
        self.save_checkpoint(latest_processed)
        
        return overall_results

def main():
    parser = argparse.ArgumentParser(description="Extraction Pipeline Agent")
    parser.add_argument("action", choices=['run', 'status', 'reset'], help="Action to perform")
    parser.add_argument("--since", help="Extract since date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    parser.add_argument("--workspace", help="Workspace directory")
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = ExtractionPipeline(
        workspace_dir=args.workspace,
        dry_run=args.dry_run
    )
    
    if args.action == 'status':
        # Show status
        last_processed = pipeline.load_checkpoint()
        daily_notes = pipeline.get_daily_notes_to_process()
        
        print(f"Last processed: {last_processed.strftime('%Y-%m-%d %H:%M')}")
        print(f"Pending daily notes: {len(daily_notes)}")
        if daily_notes:
            print("Files to process:")
            for note in daily_notes[:5]:  # Show first 5
                print(f"  - {note.name}")
            if len(daily_notes) > 5:
                print(f"  ... and {len(daily_notes) - 5} more")
    
    elif args.action == 'reset':
        # Reset checkpoint
        if not args.dry_run:
            if pipeline.checkpoint_file.exists():
                pipeline.checkpoint_file.unlink()
                print("Checkpoint reset")
            else:
                print("No checkpoint to reset")
        else:
            print("Would reset checkpoint")
    
    elif args.action == 'run':
        # Run extraction
        since_date = None
        if args.since:
            try:
                since_date = datetime.strptime(args.since, "%Y-%m-%d")
            except ValueError:
                print(f"Error: Invalid date format '{args.since}'. Use YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
        
        results = pipeline.run_extraction(since_date)
        
        # Print results
        print("\\nExtraction Results:")
        print(f"Processed files: {results['processed_files']}")
        print(f"Total facts extracted: {results['total_facts']}")
        print(f"New facts written: {results['written_facts']}")
        print(f"Duplicates skipped: {results['skipped_duplicates']}")
        print(f"Entities updated: {len(results['entities_updated'])}")
        
        if results['entities_updated']:
            print("\\nUpdated entities:")
            for entity in sorted(results['entities_updated'])[:10]:  # Show first 10
                print(f"  - {entity}")
            if len(results['entities_updated']) > 10:
                print(f"  ... and {len(results['entities_updated']) - 10} more")
        
        if results['errors']:
            print("\\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")

if __name__ == "__main__":
    main()