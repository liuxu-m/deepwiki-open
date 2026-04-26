from urllib.parse import quote, urlparse

import requests


def detect_default_branch(repo_url: str, repo_type: str, access_token: str | None = None) -> str:
    try:
        if repo_type == 'github':
            parsed = urlparse(repo_url)
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) < 2:
                return 'main'
            owner = path_parts[-2]
            repo = path_parts[-1].replace('.git', '')
            api_base = 'https://api.github.com' if parsed.netloc == 'github.com' else f'{parsed.scheme}://{parsed.netloc}/api/v3'
            headers = {'Authorization': f'token {access_token}'} if access_token else {}
            response = requests.get(f'{api_base}/repos/{owner}/{repo}', headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('default_branch', 'main')
            return 'main'

        if repo_type == 'gitlab':
            parsed = urlparse(repo_url)
            gitlab_domain = f'{parsed.scheme}://{parsed.netloc}'
            project_path = '/'.join(parsed.path.strip('/').split('/')).replace('.git', '')
            encoded_project_path = quote(project_path, safe='')
            headers = {'PRIVATE-TOKEN': access_token} if access_token else {}
            response = requests.get(f'{gitlab_domain}/api/v4/projects/{encoded_project_path}', headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('default_branch', 'main')
            return 'main'

        if repo_type == 'bitbucket':
            parts = repo_url.rstrip('/').split('/')
            if len(parts) < 5:
                return 'main'
            owner = parts[-2]
            repo = parts[-1].replace('.git', '')
            headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}
            response = requests.get(f'https://api.bitbucket.org/2.0/repositories/{owner}/{repo}', headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('mainbranch', {}).get('name', 'main')
            return 'main'
    except Exception:
        return 'main'

    return 'main'
