import RepoInfo from "@/types/repoinfo";

export default function getRepoUrl(repoInfo: RepoInfo): string {
  console.log('getRepoUrl', repoInfo);
  if (repoInfo.type === 'local' && repoInfo.localPath) {
    return repoInfo.localPath;
  }

  if (repoInfo.repoUrl) {
    return repoInfo.repoUrl;
  }

  if (repoInfo.owner && repoInfo.repo) {
    if (repoInfo.type === 'gitlab') {
      return `https://gitlab.com/${repoInfo.owner}/${repoInfo.repo}`;
    }
    if (repoInfo.type === 'bitbucket') {
      return `https://bitbucket.org/${repoInfo.owner}/${repoInfo.repo}`;
    }
    return `https://github.com/${repoInfo.owner}/${repoInfo.repo}`;
  }

  return '';
};