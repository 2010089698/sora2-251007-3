const form = document.getElementById("prompt-form");
const formMessage = document.getElementById("form-message");
const jobsList = document.getElementById("jobs-list");
const refreshButton = document.getElementById("refresh-button");

async function submitPrompt(event) {
  event.preventDefault();
  formMessage.textContent = "生成リクエストを送信中...";
  formMessage.className = "info";

  const formData = new FormData(form);
  const secondsValue = Number(formData.get("seconds"));
  const payload = {
    prompt: formData.get("prompt"),
    seconds: Number.isFinite(secondsValue) ? secondsValue : undefined,
    size: formData.get("size"),
  };

  try {
    const response = await fetch("/api/videos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "リクエストに失敗しました");
    }

    const data = await response.json();
    const job = data.job;
    form.reset();
    await loadJobs();
    formMessage.textContent = `ジョブ ${job.id} を作成しました。`;
    formMessage.className = "success";
  } catch (error) {
    console.error(error);
    formMessage.textContent = `エラー: ${error.message}`;
    formMessage.className = "error";
  }
}

async function loadJobs() {
  jobsList.innerHTML = "<p>読み込み中...</p>";
  try {
    const response = await fetch("/api/videos");
    if (!response.ok) {
      throw new Error("ジョブ一覧の取得に失敗しました");
    }
    const data = await response.json();
    renderJobs(data.jobs || []);
  } catch (error) {
    jobsList.innerHTML = `<p class="error">${error.message}</p>`;
  }
}

function renderJobs(jobs) {
  if (jobs.length === 0) {
    jobsList.innerHTML = "<p>まだジョブはありません。</p>";
    return;
  }

  jobsList.innerHTML = "";

  jobs.forEach((job) => {
    const item = document.createElement("div");
    item.className = "job-item";
    const updatedAt = new Date(job.updated_at).toLocaleString();

    let mediaSection = "";
    if (job.assets && job.assets.length > 0) {
      const asset = job.assets[0];
      const source = asset.preview_url || asset.download_url;
      mediaSection = `
        <video controls src="${source}" preload="none"></video>
        <div class="job-meta">
        <small>解像度: ${asset.resolution || job.size || "-"}</small><br/>
          <small>長さ: ${asset.duration_seconds || job.seconds || "-"} 秒</small>
        </div>
        <div class="job-actions">
          ${asset.download_url ? `<a class="secondary" href="${asset.download_url}" target="_blank" rel="noopener">ダウンロード</a>` : ""}
        </div>
      `;
    }

    item.innerHTML = `
      <div class="job-header">
        <div>
          <strong>${job.prompt}</strong>
          <div><small>ID: ${job.id}</small></div>
        </div>
        <span class="job-status" data-status="${job.status}">${job.status}</span>
      </div>
      <div class="job-body">
        <small>OpenAI ジョブID: ${job.sora_job_id}</small><br/>
        ${job.size ? `<small>解像度プリセット: ${job.size}</small><br/>` : ""}
        ${job.seconds ? `<small>指定秒数: ${job.seconds} 秒</small><br/>` : ""}
        <small>更新: ${updatedAt}</small>
        ${job.error_message ? `<p class="error">${job.error_message}</p>` : ""}
      </div>
      ${mediaSection}
    `;

    jobsList.appendChild(item);
  });
}

form.addEventListener("submit", submitPrompt);
refreshButton.addEventListener("click", loadJobs);
document.addEventListener("DOMContentLoaded", () => {
  loadJobs();
  setInterval(loadJobs, 10000);
});
