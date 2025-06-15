import click
from github import Github
from datetime import datetime, timedelta
import os
import requests

def get_github_commits(token, date):
    g = Github(token)
    user = g.get_user()
    repos = user.get_repos()
    all_commits = []
    since = datetime.strptime(date, '%Y-%m-%d')
    until = since + timedelta(days=1)
    for repo in repos:
        try:
            commits = repo.get_commits(author=user, since=since, until=until)
            commit_list = [f"{c.sha[:7]} {c.commit.message.splitlines()[0]}" for c in commits]
            if commit_list:
                all_commits.append((repo.full_name, commit_list))
        except Exception:
            continue
    return all_commits

def get_commit_diffs(repo, commits):
    diffs = []
    for commit in commits:
        try:
            c = repo.get_commit(commit.split()[0])
            diff = c.files
            diff_text = "\n".join([f.filename + "\n" + (f.patch or "") for f in diff if hasattr(f, 'patch')])
            diffs.append((commit, diff_text))
        except Exception:
            diffs.append((commit, "[Diff not available]"))
    return diffs

def create_ai_prompt(repo_name, commit_diffs, date):
    prompt = f"""
You are an expert software engineer. Summarize the following git commit diffs for repository '{repo_name}' for {date}. Focus on the main changes, improvements, and bug fixes. Be concise and clear.

"""
    for commit, diff in commit_diffs:
        prompt += f"Commit: {commit}\nDiff:\n{diff}\n\n"
    prompt += "\nSummary:"
    return prompt

def get_ai_summary(prompt):
    # Assumes lmstudio is running locally with the Python API
    try:
        import lmstudio
        response = lmstudio.generate(prompt=prompt, max_tokens=300)
        return response['choices'][0]['text'].strip()
    except Exception as e:
        return f"[AI summary failed: {e}]"

@click.command()
@click.option('--date', default=datetime.now().strftime('%Y-%m-%d'), help='Date for which to aggregate pushed commits (YYYY-MM-DD)')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub token for API access')
@click.option('--ai-summary/--no-ai-summary', default=False, help='Include an AI-generated summary of commit diffs')
def main(date, github_token, ai_summary):  # type: ignore
    """
    Aggregate all pushed git commits across all your GitHub repositories for a given day and generate a summary.
    Optionally, generate an AI summary of the commit diffs using lmstudio.
    """
    if not github_token:
        print("GitHub token required for pushed commit summary.")
        return
    print(f"Aggregating pushed commits for {date}...")
    gh_commits = get_github_commits(github_token, date)
    print_summary(gh_commits, date)
    if ai_summary:
        print("\nAI Summaries:")
        g = Github(github_token)
        user = g.get_user()
        for repo_name, commits in gh_commits:
            repo = g.get_repo(repo_name)
            commit_diffs = get_commit_diffs(repo, commits)
            prompt = create_ai_prompt(repo_name, commit_diffs, date)
            summary = get_ai_summary(prompt)
            print(f"\nRepository: {repo_name}\n{summary}")

def print_summary(all_commits, date):
    print(f"\nSummary of pushed commits for {date}:")
    for repo, commits in all_commits:
        print(f"\nRepository: {repo}")
        for commit in commits:
            print(f"  {commit}")

if __name__ == '__main__':
    main()
