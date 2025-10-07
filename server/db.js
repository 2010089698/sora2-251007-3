const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const crypto = require('crypto');

const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'app.db');
const db = new Database(dbPath);

db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS video_jobs (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    seconds INTEGER,
    size TEXT,
    sora_job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    assets_json TEXT,
    variants_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);

const columns = db.prepare('PRAGMA table_info(video_jobs)').all();
const hasVariantsColumn = columns.some((column) => column.name === 'variants_json');
if (!hasVariantsColumn) {
  db.exec('ALTER TABLE video_jobs ADD COLUMN variants_json TEXT');
}

const insertStmt = db.prepare(`
  INSERT INTO video_jobs (
    id, prompt, seconds, size, sora_job_id, status, assets_json, variants_json,
    error_message, created_at, updated_at
  ) VALUES (
    @id, @prompt, @seconds, @size, @sora_job_id, @status, @assets_json, @variants_json,
    @error_message, @created_at, @updated_at
  )
`);

const listStmt = db.prepare(`
  SELECT * FROM video_jobs ORDER BY datetime(created_at) DESC
`);

const getStmt = db.prepare(`
  SELECT * FROM video_jobs WHERE id = ?
`);

const pendingStmt = db.prepare(`
  SELECT * FROM video_jobs
  WHERE status NOT IN ('completed', 'failed', 'cancelled')
`);

const updateStmt = db.prepare(`
  UPDATE video_jobs
  SET status = @status,
      assets_json = @assets_json,
      variants_json = @variants_json,
      error_message = @error_message,
      updated_at = @updated_at
  WHERE id = @id
`);

function mapRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    prompt: row.prompt,
    seconds: row.seconds,
    size: row.size,
    sora_job_id: row.sora_job_id,
    status: row.status,
    variants: row.variants_json
      ? JSON.parse(row.variants_json)
      : row.assets_json
      ? JSON.parse(row.assets_json)
      : [],
    error_message: row.error_message,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function insertJob({ prompt, seconds, size, sora_job_id, status, variants, error_message }) {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  insertStmt.run({
    id,
    prompt,
    seconds: Number.isFinite(seconds) ? Number(seconds) : null,
    size: size || null,
    sora_job_id,
    status,
    assets_json: null,
    variants_json: variants && variants.length ? JSON.stringify(variants) : null,
    error_message: error_message || null,
    created_at: now,
    updated_at: now,
  });
  return getJob(id);
}

function listJobs() {
  return listStmt.all().map(mapRow);
}

function getJob(id) {
  return mapRow(getStmt.get(id));
}

function getPendingJobs() {
  return pendingStmt.all().map(mapRow);
}

function updateJob(id, { status, variants, error_message }) {
  const now = new Date().toISOString();
  updateStmt.run({
    id,
    status,
    assets_json: null,
    variants_json: variants && variants.length ? JSON.stringify(variants) : null,
    error_message: error_message || null,
    updated_at: now,
  });
  return getJob(id);
}

module.exports = {
  insertJob,
  listJobs,
  getJob,
  getPendingJobs,
  updateJob,
};
