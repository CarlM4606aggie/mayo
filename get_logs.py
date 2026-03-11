import os, requests
from dotenv import load_dotenv
load_dotenv()
from github import GithubIntegration
APP_ID = os.environ.get('APP_ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').replace('\\n', '\n')
integration = GithubIntegration(APP_ID, PRIVATE_KEY)
token = integration.get_access_token(integration.get_installations()[0].id).token
headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
runs = requests.get('https://api.github.com/repos/HOLYKEYZ/mayo/actions/runs?per_page=1', headers=headers).json()
if runs.get('workflow_runs'):
    run_id = runs['workflow_runs'][0]['id']
    jobs = requests.get(f'https://api.github.com/repos/HOLYKEYZ/mayo/actions/runs/{run_id}/jobs', headers=headers).json()
    if jobs.get('jobs'):
        job_id = jobs['jobs'][0]['id']
        logs = requests.get(f'https://api.github.com/repos/HOLYKEYZ/mayo/actions/jobs/{job_id}/logs', headers=headers)
        print(logs.text[-4000:])
