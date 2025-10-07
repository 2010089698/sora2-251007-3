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
          const nextStatus = remote.status || job.status;
          const contentVariant = remote.content_variant || job.content_variant || null;
          const contentToken = remote.content_token || job.content_token || null;
          const contentTokenExpiresAt = remote.content_token_expires_at || job.content_token_expires_at || null;
          const contentReadyAt =
            nextStatus === 'completed'
              ? job.content_ready_at || new Date().toISOString()
              : job.content_ready_at;

          if (
            nextStatus !== job.status ||
            contentVariant !== job.content_variant ||
            contentToken !== job.content_token ||
            contentTokenExpiresAt !== job.content_token_expires_at ||
            remote.error_message !== job.error_message ||
            contentReadyAt !== job.content_ready_at
          ) {
            db.updateJob(job.id, {
              status: nextStatus,
              content_variant: contentVariant,
              content_token: contentToken,
              content_token_expires_at: contentTokenExpiresAt,
              content_ready_at: contentReadyAt,
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
