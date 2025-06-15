import click
from github import Github
from datetime import datetime, timedelta
import os
import requests
import time
import json

CACHE_FILE = ".gh_commit_cache.json"
CACHE_TTL = 15 * 60  # 15 minutes in seconds

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

def estimate_token_count(text):
    # Rough estimate: 1 token ≈ 4 characters (for English text)
    return len(text) // 4

AI_CONTEXT_LIMIT = 15000
AI_SUMMARY_LIMIT = 12000  # Leave room for response

def get_ai_summary(prompt):
    try:
        import lmstudio as lms
        model = lms.llm()
        if estimate_token_count(prompt) > AI_SUMMARY_LIMIT:
            return "[Prompt too long for LLM context window, skipping summary.]"
        return model.respond(prompt)
    except Exception as e:
        return f"[AI summary failed: {e}]"

def cache_key(date):
    return date

def load_cache(date):
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        entry = data.get(cache_key(date))
        if entry and time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["commits"]
    except Exception:
        pass
    return None

def save_cache(date, commits):
    key = cache_key(date)
    data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[key] = {"timestamp": time.time(), "commits": commits}
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

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
    gh_commits = load_cache(date)
    if gh_commits is None:
        gh_commits = get_github_commits(github_token, date)
        save_cache(date, gh_commits)
    print_summary(gh_commits, date)
    if ai_summary:
        print("\nAI Summaries:")
        g = Github(github_token)
        user = g.get_user()
        commit_summaries = []
        for repo_name, commits in gh_commits:
            repo = g.get_repo(repo_name)
            commit_diffs = get_commit_diffs(repo, commits)
            per_commit_summaries = []
            for commit, diff in commit_diffs:
                prompt = create_ai_prompt(repo_name, [(commit, diff)], date)
                summary = get_ai_summary(prompt)
                per_commit_summaries.append((commit, summary))
                print(f"\nRepository: {repo_name}\nCommit: {commit}\n{summary}")
            # Now, summarize all commit summaries for the repo if needed
            all_commit_text = "\n".join([f"Commit: {c}\nSummary: {s}" for c, s in per_commit_summaries])
            if estimate_token_count(all_commit_text) < AI_SUMMARY_LIMIT:
                final_prompt = f"You are an expert software engineer. Summarize the following commit summaries for repository '{repo_name}' for {date}.\n\n{all_commit_text}\n\nFinal Summary:"
                final_summary = get_ai_summary(final_prompt)
                print(f"\nRepository: {repo_name}\nFinal AI Summary:\n{final_summary}")
            else:
                print(f"\nRepository: {repo_name}\n[Final summary skipped: too much content for LLM context window]")

def print_summary(all_commits, date):
    print(f"\nSummary of pushed commits for {date}:")
    for repo, commits in all_commits:
        print(f"\nRepository: {repo}")
        for commit in commits:
            print(f"  {commit}")

if __name__ == '__main__':
    main()
