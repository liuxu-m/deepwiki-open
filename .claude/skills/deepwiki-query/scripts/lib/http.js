const { parseRepoUrl } = require('./repo');

function getBaseUrl() {
  return process.env.DEEPWIKI_BASE_URL || 'http://127.0.0.1:8001';
}

async function getJson(path, params = {}) {
  const url = new URL(path, getBaseUrl());
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`backend request failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function listProcessedProjects() {
  return await getJson('/api/processed_projects');
}

async function getWikiCache(repoUrl, language = 'en') {
  const { owner, repo, repoType } = parseRepoUrl(repoUrl);
  return await getJson('/api/wiki_cache', {
    owner,
    repo,
    repo_type: repoType,
    language,
  });
}

module.exports = {
  getBaseUrl,
  getJson,
  listProcessedProjects,
  getWikiCache,
};
