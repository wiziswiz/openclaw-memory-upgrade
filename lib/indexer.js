const fs = require('fs');
const path = require('path');
const { getFileMeta, insertChunks, getAllFilePaths, deleteFileChunks } = require('./store');
const { extractFacts } = require('./retain');
const { resolveFileType } = require('./config');

const MAX_CHUNK = 2000;

function extractEntities(text) {
  const entities = new Set();
  // @mentions
  for (const m of text.matchAll(/@(\w+)/g)) entities.add('@' + m[1]);
  // **bold terms**
  for (const m of text.matchAll(/\*\*([^*]+)\*\*/g)) entities.add(m[1]);
  // Acronyms (2+ uppercase letters, not inside words)
  for (const m of text.matchAll(/\b([A-Z]{2,})\b/g)) {
    // Skip common non-entity uppercase words
    if (!ACRONYM_SKIP.has(m[1])) entities.add(m[1]);
  }
  // Tickers ($BTC, $ETH)
  for (const m of text.matchAll(/\$([A-Z]{2,6})\b/g)) entities.add('$' + m[1]);
  // "Quoted terms" (3-50 chars)
  for (const m of text.matchAll(/"([^"]{3,50})"/g)) entities.add(m[1]);
  // URLs
  for (const m of text.matchAll(/https?:\/\/[^\s)>\]]+/g)) entities.add(m[0]);
  return [...entities];
}

const ACRONYM_SKIP = new Set([
  'OK', 'AM', 'PM', 'US', 'OR', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO',
  'GO', 'IF', 'IN', 'IS', 'IT', 'ME', 'MY', 'NO', 'OF', 'ON', 'SO',
  'TO', 'UP', 'WE', 'ID', 'VS', 'MD', 'IE', 'EG',
]);

function extractDateFromPath(filePath) {
  const m = filePath.match(/(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] + 'T00:00:00.000Z' : null;
}

function chunkMarkdown(text) {
  const lines = text.split('\n');
  const chunks = [];
  let current = { heading: null, lines: [], lineStart: 1 };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const headingMatch = line.match(/^(#{1,4})\s+(.+)/);

    if (headingMatch && current.lines.length > 0) {
      // flush
      pushChunk(chunks, current);
      current = { heading: headingMatch[2].trim(), lines: [], lineStart: i + 1 };
    } else if (headingMatch && current.lines.length === 0) {
      current.heading = headingMatch[2].trim();
      current.lineStart = i + 1;
    }
    current.lines.push(line);
  }
  if (current.lines.length > 0) pushChunk(chunks, current);
  return chunks;
}

// Speaker turn pattern: "Name:", "Speaker Name:", "[00:00:00] Name:", etc.
const SPEAKER_TURN = /^(?:\[\d{1,2}:\d{2}(?::\d{2})?\]\s*)?[A-Z][A-Za-z\s]{0,30}:/m;

/**
 * Split oversized text by speaker turns (for transcripts) or sentence boundaries (last resort).
 */
function splitOversized(text, heading, lineStart, maxLineEnd, chunks) {
  // Try speaker-turn splitting first
  const turns = text.split(SPEAKER_TURN);
  const turnMatches = [...text.matchAll(new RegExp(SPEAKER_TURN.source, 'gm'))];
  if (turnMatches.length >= 2) {
    let buf = turns[0] || '';
    let bufStart = lineStart;
    let cumLines = buf.split('\n').length;
    for (let i = 0; i < turnMatches.length; i++) {
      const turnContent = (turnMatches[i][0] || '') + (turns[i + 1] || '');
      const turnLines = turnContent.split('\n').length;
      if (buf && (buf.length + turnContent.length + 1) > MAX_CHUNK) {
        if (buf.trim()) {
          const lineEnd = Math.min(bufStart + cumLines - 1, maxLineEnd);
          chunks.push({ heading, content: buf.trim(), lineStart: bufStart, lineEnd, entities: extractEntities(buf) });
          bufStart = lineEnd + 1;
        }
        buf = '';
        cumLines = 0;
      }
      buf += (buf ? '\n' : '') + turnContent;
      cumLines += turnLines;
    }
    if (buf.trim()) {
      chunks.push({ heading, content: buf.trim(), lineStart: bufStart, lineEnd: maxLineEnd, entities: extractEntities(buf) });
    }
    return;
  }

  // Last resort: hard split on sentence boundaries
  const sentences = text.split(/(?<=[.!?])\s+/);
  let buf = '', bufStart = lineStart, cumLines = 0;
  for (const sentence of sentences) {
    const sLines = sentence.split('\n').length;
    if (buf && (buf.length + sentence.length + 1) > MAX_CHUNK) {
      if (buf.trim()) {
        const lineEnd = Math.min(bufStart + cumLines - 1, maxLineEnd);
        chunks.push({ heading, content: buf.trim(), lineStart: bufStart, lineEnd, entities: extractEntities(buf) });
        bufStart = lineEnd + 1;
      }
      buf = '';
      cumLines = 0;
    }
    buf += (buf ? ' ' : '') + sentence;
    cumLines += sLines;
  }
  if (buf.trim()) {
    chunks.push({ heading, content: buf.trim(), lineStart: bufStart, lineEnd: maxLineEnd, entities: extractEntities(buf) });
  }
}

function pushChunk(chunks, current) {
  const content = current.lines.join('\n').trim();
  if (!content) return;

  // Skip heading-only chunks with no substantive content
  const stripped = content.replace(/^#{1,6}\s+.*$/gm, '').trim();
  if (stripped.length < 5) return;

  // Split oversized chunks by paragraph
  if (content.length > MAX_CHUNK) {
    const maxLineEnd = current.lineStart + current.lines.length - 1;
    const paragraphs = content.split(/\n\n+/);
    let buf = '', bufStart = current.lineStart, cumLines = 0;
    for (const para of paragraphs) {
      const paraLines = para.split('\n').length;
      if (buf && (buf.length + para.length + 2) > MAX_CHUNK) {
        // If paragraph-split buffer is still oversized, use deeper splitting
        if (buf.trim().length > MAX_CHUNK) {
          const lineEnd = Math.min(bufStart + cumLines - 1, maxLineEnd);
          splitOversized(buf.trim(), current.heading, bufStart, lineEnd, chunks);
        } else {
          const lineEnd = Math.min(bufStart + cumLines - 1, maxLineEnd);
          chunks.push({
            heading: current.heading,
            content: buf.trim(),
            lineStart: bufStart,
            lineEnd,
            entities: extractEntities(buf)
          });
        }
        buf = '';
        bufStart = Math.min(bufStart + cumLines, maxLineEnd);
        cumLines = 0;
      }
      buf += (buf ? '\n\n' : '') + para;
      cumLines += paraLines + (cumLines > 0 ? 1 : 0);
    }
    if (buf.trim()) {
      // Final buffer may also be oversized
      if (buf.trim().length > MAX_CHUNK) {
        splitOversized(buf.trim(), current.heading, bufStart, maxLineEnd, chunks);
      } else {
        chunks.push({
          heading: current.heading,
          content: buf.trim(),
          lineStart: bufStart,
          lineEnd: maxLineEnd,
          entities: extractEntities(buf)
        });
      }
    }
  } else {
    chunks.push({
      heading: current.heading,
      content,
      lineStart: current.lineStart,
      lineEnd: current.lineStart + current.lines.length - 1,
      entities: extractEntities(content)
    });
  }
}


function chunkJson(text, filePath) {
  let data;
  try { data = JSON.parse(text); } catch(e) { return []; }
  if (!Array.isArray(data)) return [];
  
  const parts = filePath.split(path.sep);
  const entityIdx = parts.lastIndexOf('items.json');
  const entityName = entityIdx > 0 ? parts[entityIdx - 1] : path.basename(path.dirname(filePath));
  const categoryIdx = parts.indexOf('areas');
  const category = categoryIdx >= 0 && categoryIdx + 1 < parts.length ? parts[categoryIdx + 1] : 'entity';
  
  const chunks = [];
  const activeFacts = data.filter(f => f.status === 'active');
  if (activeFacts.length === 0) return [];
  
  const BATCH = 5;
  for (let i = 0; i < activeFacts.length; i += BATCH) {
    const batch = activeFacts.slice(i, i + BATCH);
    const lines = batch.map(f => {
      const meta = [f.category, f.timestamp].filter(Boolean).join(', ');
      return `- [${f.id}] ${f.fact} (${meta})`;
    });
    
    const content = `Entity: ${entityName} (${category})\n` + lines.join('\n');
    const entities = [entityName];
    
    for (const f of batch) {
      for (const m of f.fact.matchAll(/@(\w+)/g)) entities.push('@' + m[1]);
      for (const m of f.fact.matchAll(/\*\*([^*]+)\*\*/g)) entities.push(m[1]);
      for (const m of f.fact.matchAll(/\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b/g)) {
        if (!['The', 'This', 'That', 'When', 'Where', 'What', 'How', 'Entity'].includes(m[1])) {
          entities.push(m[1]);
        }
      }
    }
    
    chunks.push({
      heading: `${entityName} facts`,
      content,
      lineStart: i + 1,
      lineEnd: i + batch.length,
      entities: [...new Set(entities)],
      chunkType: 'confirmed',
      confidence: 0.9
    });
  }
  return chunks;
}

function discoverFiles(workspace, { include = [] } = {}) {
  const files = [];
  const defaultFiles = ['MEMORY.md', 'SOUL.md', 'USER.md', 'STATE.md', 'TOOLS.md', 'VOICE.md', 'IDENTITY.md'];
  for (const name of defaultFiles) {
    const p = path.join(workspace, name);
    if (fs.existsSync(p)) files.push(p);
  }

  const memDir = path.join(workspace, 'memory');
  if (fs.existsSync(memDir)) {
    for (const f of fs.readdirSync(memDir)) {
      if (f.endsWith('.md')) files.push(path.join(memDir, f));
    }
  }

  // Ingest directory — markdown generated from external sources
  const ingestDir = path.join(workspace, 'ingest');
  if (fs.existsSync(ingestDir)) {
    for (const f of fs.readdirSync(ingestDir)) {
      if (f.endsWith('.md')) files.push(path.join(ingestDir, f));
    }
  }


  // Knowledge graph items.json files (life/areas entities)
  const areasDir = path.join(workspace, 'life', 'areas');
  if (fs.existsSync(areasDir)) {
    const walkAreas = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) walkAreas(path.join(dir, entry.name));
        else if (entry.name === 'items.json') files.push(path.join(dir, entry.name));
      }
    };
    walkAreas(areasDir);
  }

  // Additional include patterns/paths
  for (const pattern of include) {
    const p = path.resolve(workspace, pattern);
    if (fs.existsSync(p) && fs.statSync(p).isFile() && !files.includes(p)) {
      files.push(p);
    }
  }
  return files;
}

function indexWorkspace(db, workspace, { force = false, include = [], fileTypeDefaults = {} } = {}) {
  const files = discoverFiles(workspace, { include });
  let indexed = 0, skipped = 0;

  const errors = [];
  for (const filePath of files) {
    try {
      const stat = fs.statSync(filePath);
      const mtimeMs = Math.floor(stat.mtimeMs);
      const relPath = path.relative(workspace, filePath);

      if (!force) {
        const meta = getFileMeta(db, relPath);
        if (meta && meta.mtime_ms === mtimeMs) { skipped++; continue; }
      }

      const text = fs.readFileSync(filePath, 'utf-8');
      const chunks = filePath.endsWith('.json') ? chunkJson(text, path.relative(workspace, filePath)) : chunkMarkdown(text);
      const createdAt = extractDateFromPath(filePath);

      // v4.2: Apply file-level type defaults (config overrides raw, inline tags override config)
      const fileDefault = resolveFileType(relPath, fileTypeDefaults);
      if (fileDefault) {
        for (const chunk of chunks) {
          chunk.chunkType = fileDefault.type;
          chunk.confidence = fileDefault.confidence;
        }
      }

      // v2 Retain: extract structured facts and upgrade matching chunks
      // Facts upgrade their parent chunk's type/confidence — no standalone duplicates
      const facts = extractFacts(text, relPath);
      if (facts.length > 0) {
        for (const chunk of chunks) {
          // Find the best (highest confidence) fact within this chunk's line range
          let bestFact = null;
          for (const f of facts) {
            if (f.lineStart >= chunk.lineStart && f.lineStart <= chunk.lineEnd) {
              if (!bestFact || f.confidence > bestFact.confidence) bestFact = f;
            }
          }
          if (bestFact) {
            chunk.chunkType = bestFact.type;
            chunk.confidence = bestFact.confidence;
          }
        }
      }

      insertChunks(db, relPath, mtimeMs, chunks, createdAt);
      indexed++;
    } catch (err) {
      errors.push({ file: filePath, error: err.message });
    }
  }

  // Orphan cleanup: remove DB entries for files no longer on disk
  let cleaned = 0;
  const discoveredRelPaths = new Set(files.map(f => path.relative(workspace, f)));
  for (const dbPath of getAllFilePaths(db)) {
    if (!discoveredRelPaths.has(dbPath)) {
      deleteFileChunks(db, dbPath);
      cleaned++;
    }
  }

  return { indexed, skipped, errors, total: files.length, cleaned };
}

/**
 * indexSingleFile — index (or skip) a single file. Shared implementation used by
 * MCP server, programmatic API, and hook.
 */
function indexSingleFile(db, workspace, filePath, fileTypeDefaults) {
  const stat = fs.statSync(filePath);
  const mtimeMs = Math.floor(stat.mtimeMs);
  const relPath = path.relative(workspace, filePath);

  const meta = getFileMeta(db, relPath);
  if (meta && meta.mtime_ms === mtimeMs) return { skipped: true };

  const text = fs.readFileSync(filePath, 'utf-8');
  const chunks = filePath.endsWith('.json') ? chunkJson(text, relPath) : chunkMarkdown(text);
  const createdAt = extractDateFromPath(filePath);

  const fileDefault = resolveFileType(relPath, fileTypeDefaults || {});
  if (fileDefault) {
    for (const chunk of chunks) {
      chunk.chunkType = fileDefault.type;
      chunk.confidence = fileDefault.confidence;
    }
  }

  const facts = extractFacts(text, relPath);
  if (facts.length > 0) {
    for (const chunk of chunks) {
      let bestFact = null;
      for (const f of facts) {
        if (f.lineStart >= chunk.lineStart && f.lineStart <= chunk.lineEnd) {
          if (!bestFact || f.confidence > bestFact.confidence) bestFact = f;
        }
      }
      if (bestFact) {
        chunk.chunkType = bestFact.type;
        chunk.confidence = bestFact.confidence;
      }
    }
  }

  insertChunks(db, relPath, mtimeMs, chunks, createdAt);
  return { skipped: false };
}

module.exports = { indexWorkspace, indexSingleFile, chunkMarkdown, chunkJson, extractEntities, discoverFiles };
