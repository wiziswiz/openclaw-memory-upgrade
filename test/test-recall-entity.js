#!/usr/bin/env node
/**
 * Tests for person-aware recall boost (entity matching in retrieve pipeline).
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const { openDb } = require('../lib/store');
const { matchQueryEntities, invalidateEntityNames } = require('../lib/retrieve');
const { buildEntityIndex } = require('../lib/entities');
const { recall } = require('../lib/recall');

let passed = 0, failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; }
  else { failed++; console.error(`  ✗ ${msg}`); }
}

function tmpWorkspace() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'sme-entity-recall-'));
}

function insertChunk(db, { content, entities = '[]', chunkType = 'fact', filePath = 'test.md', heading = null } = {}) {
  const now = new Date().toISOString();
  db.prepare(`INSERT INTO chunks (file_path, heading, content, line_start, line_end, entities, chunk_type, confidence, created_at, indexed_at, file_weight, access_count, last_accessed, stale)
    VALUES (?, ?, ?, 1, 10, ?, ?, 1.0, ?, ?, 1.0, 0, NULL, 0)`).run(
    filePath, heading, content, entities, chunkType, now, now
  );
}

// --- matchQueryEntities ---

console.log('Test 1: Matches known entity in query');
{
  const entities = new Set(['dana', 'marcus', 'sarah']);
  const matched = matchQueryEntities('What do I know about Dana?', entities);
  assert(matched.has('dana'), 'Should match Dana');
  assert(matched.size === 1, `Expected 1 match, got ${matched.size}`);
}

console.log('Test 2: Case-insensitive matching');
{
  const entities = new Set(['marcus', 'sarah']);
  const matched = matchQueryEntities('Tell me about MARCUS', entities);
  assert(matched.has('marcus'), 'Should match marcus case-insensitively');
}

console.log('Test 3: Word boundary — no partial matches');
{
  const entities = new Set(['dana', 'art']);
  const matched = matchQueryEntities('particularly artistic work', entities);
  assert(!matched.has('dana'), 'Should NOT match "dana" in "particularly"');
  assert(!matched.has('art'), 'Should NOT match "art" in "artistic"');
}

console.log('Test 4: Multiple entities matched');
{
  const entities = new Set(['dana', 'marcus', 'sarah']);
  const matched = matchQueryEntities('What did Dana and Marcus discuss?', entities);
  assert(matched.has('dana'), 'Should match dana');
  assert(matched.has('marcus'), 'Should match marcus');
  assert(!matched.has('sarah'), 'Should not match sarah');
}

console.log('Test 5: No entities in query → empty set');
{
  const entities = new Set(['dana', 'marcus']);
  const matched = matchQueryEntities('what supplements does JB take?', entities);
  assert(matched.size === 0, `Expected 0 matches, got ${matched.size}`);
}

console.log('Test 6: Empty entity set → empty matches');
{
  const matched = matchQueryEntities('Dana test', new Set());
  assert(matched.size === 0, 'Empty entity set should return empty matches');
}

// --- Integration: entity match flag in recall pipeline ---

console.log('Test 7: Recall sets _entityMatch for matching chunks');
{
  invalidateEntityNames();
  const ws = tmpWorkspace();
  const db = openDb(ws);

  insertChunk(db, {
    content: 'Dana mentioned she prefers Italian food for dinner',
    entities: JSON.stringify(['Dana']),
    chunkType: 'fact',
  });
  insertChunk(db, {
    content: 'The weather was nice today in the park',
    entities: '[]',
    chunkType: 'raw',
  });

  // Build entity index so the entity lookup works
  buildEntityIndex(db);

  const results = recall(db, 'Dana', { workspace: ws });
  assert(results.length > 0, `Expected results for Dana query, got ${results.length}`);

  // The chunk mentioning Dana should have entity boost reflected in score
  const danaResult = results.find(r => r.content.includes('Dana'));
  assert(danaResult != null, 'Should find Dana chunk in results');

  db.close();
  fs.rmSync(ws, { recursive: true });
}

console.log('Test 8: Entity boost improves ranking');
{
  invalidateEntityNames();
  const ws = tmpWorkspace();
  const db = openDb(ws);

  // Both mention "meeting" but only one has the entity
  insertChunk(db, {
    content: 'Marcus discussed the meeting schedule and project timeline for March',
    entities: JSON.stringify(['Marcus']),
    chunkType: 'fact',
    heading: 'People',
  });
  insertChunk(db, {
    content: 'The meeting schedule was updated and shared with the whole team today',
    entities: '[]',
    chunkType: 'raw',
    heading: 'Notes',
  });

  buildEntityIndex(db);

  const results = recall(db, 'Marcus meeting', { workspace: ws });
  if (results.length >= 2) {
    assert(results[0].content.includes('Marcus'), `Marcus chunk should rank first, got: "${results[0].content.slice(0, 50)}"`);
  }

  db.close();
  fs.rmSync(ws, { recursive: true });
}

// --- Summary ---
console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
