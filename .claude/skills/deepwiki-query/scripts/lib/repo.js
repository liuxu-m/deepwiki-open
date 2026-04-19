function normalizeRepoUrl(repoUrl) {
  if (repoUrl.startsWith('github:')) {
    return `https://github.com/${repoUrl.slice('github:'.length)}`;
  }
  if (repoUrl.startsWith('gitlab:')) {
    return `https://gitlab.com/${repoUrl.slice('gitlab:'.length)}`;
  }
  return repoUrl;
}

function parseRepoUrl(repoUrl) {
  const normalized = normalizeRepoUrl(repoUrl);
  const url = new URL(normalized);
  const parts = url.pathname.replace(/^\/+|\/+$/g, '').split('/');
  if (parts.length < 2) {
    throw new Error('invalid repo_url');
  }
  const owner = parts[0];
  const repo = parts.slice(1).join('/').replace(/\.git$/, '');
  const repoType = url.hostname.toLowerCase().includes('gitlab') ? 'gitlab' : 'github';
  return { owner, repo, repoType, normalized };
}

module.exports = { normalizeRepoUrl, parseRepoUrl };
