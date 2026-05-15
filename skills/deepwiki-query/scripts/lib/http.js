const BASE_URL = (process.env.DEEPWIKI_BASE_URL || 'http://dreamxu.xyz:8001').replace(/\/+$/, '');

async function api(path) {
  const url = `${BASE_URL}${path}`;
  let res;
  try {
    res = await fetch(url);
  } catch (err) {
    throw new Error(`无法连接到 DeepWiki 后端 (${BASE_URL}): ${err.message}`);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`DeepWiki API 返回 ${res.status}: ${body || res.statusText} (${url})`);
  }
  return res.json();
}

function parseRepoUrl(raw) {
  // 支持: "https://github.com/owner/repo", "github:owner/repo", "owner/repo"
  let repoType, owner, repo;
  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    const u = new URL(raw);
    const parts = u.pathname.replace(/^\//, '').replace(/\/$/, '').split('/');
    owner = parts[0];
    repo = parts[1];
    if (u.hostname.includes('gitlab')) repoType = 'gitlab';
    else if (u.hostname.includes('bitbucket')) repoType = 'bitbucket';
    else repoType = 'github';
  } else if (raw.includes(':')) {
    [repoType, rest] = raw.split(':');
    [owner, repo] = rest.replace(/^\//, '').split('/');
  } else {
    // owner/repo (默认 github)
    [owner, repo] = raw.replace(/^\//, '').split('/');
    repoType = 'github';
  }
  return { repoType, owner, repo };
}

async function getWikiCache(repoUrl, language = 'en') {
  const { repoType, owner, repo } = parseRepoUrl(repoUrl);
  const params = new URLSearchParams({ owner, repo, repo_type: repoType, language });
  const data = await api(`/api/wiki_cache?${params}`);
  return data; // null if not cached
}

async function listProcessedProjects() {
  return api('/api/processed_projects');
}

async function postApi(path, body) {
  const url = `${BASE_URL}${path}`;
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new Error(`无法连接到 DeepWiki 后端 (${BASE_URL}): ${err.message}`);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`DeepWiki API 返回 ${res.status}: ${text || res.statusText} (${url})`);
  }
  return res.json();
}

async function createTask(repoUrl, options = {}) {
  const { repoType, owner, repo } = parseRepoUrl(repoUrl);
  const payload = {
    owner,
    repo,
    repo_type: repoType,
    repo_url: repoUrl.startsWith('http') ? repoUrl : `https://github.com/${owner}/${repo}`,
    language: options.language || 'en',
    is_comprehensive: options.is_comprehensive !== false,
    provider: options.provider || 'minimax',
    model: options.model || 'MiniMax-M2.7',
    token: options.token || null,
    local_path: options.localPath || null,
    excluded_dirs: options.excludedDirs || null,
    excluded_files: options.excludedFiles || null,
    included_dirs: options.includedDirs || null,
    included_files: options.includedFiles || null,
    task_type: options.taskType || 'generate',
  };
  return postApi('/api/tasks', payload);
}

module.exports = { getWikiCache, listProcessedProjects, createTask };
