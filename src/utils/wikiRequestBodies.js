export const buildStructureRequestBody = (
  repoUrl,
  repoType,
  owner,
  repo,
  fileTree,
  readme,
  isComprehensiveView,
) => ({
  repo_url: repoUrl,
  type: repoType,
  wiki_task: 'structure',
  wiki_file_tree: fileTree,
  wiki_readme: readme,
  wiki_is_comprehensive: isComprehensiveView,
  messages: [
    {
      role: 'user',
      content: `Generate wiki structure for ${owner}/${repo}`,
    },
  ],
})
