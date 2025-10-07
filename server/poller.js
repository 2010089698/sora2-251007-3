const db = require('./db');
const openaiClient = require('./openaiClient');

function startPolling({ intervalMs = 10000 } = {}) {
  async function tick() {
    const pending = db.getPendingJobs();
    if (!pending.length) {
      return;
    }

    await Promise.all(
      pending.map(async (job) => {
        try {
          const remote = await openaiClient.retrieveVideoJob(job.sora_job_id);
          if (!remote) {
            return;
          }
          if (
            remote.status !== job.status ||
            JSON.stringify(remote.variants) !== JSON.stringify(job.variants) ||
            remote.error_message !== job.error_message
          ) {
            db.updateJob(job.id, {
              status: remote.status || job.status,
              variants: remote.variants || job.variants,
              error_message: remote.error_message || null,
            });
          }
        } catch (error) {
          console.error(`Failed to update job ${job.id}:`, error.message);
        }
      })
    );
  }

  tick();
  return setInterval(tick, intervalMs);
}

module.exports = { startPolling };
