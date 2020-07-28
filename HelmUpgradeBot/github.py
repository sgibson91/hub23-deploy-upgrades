import time
import logging

from subprocess import check_call
from .helper_functions import (
    delete_request,
    get_request,
    post_request,
    run_cmd,
)

logger = logging.getLogger()


def add_commit_push(
    filename: str,
    charts_to_update: list,
    chart_info: dict,
    repo_name: str,
    target_branch: str,
    token: str,
) -> None:
    # Add the edited file
    logger.info("Adding file: %s" % filename)

    add_cmd = ["git", "add", filename]
    result = run_cmd(add_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        # Add clean up functions here
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully added file: %s" % filename)

    # Commit the edited file
    commit_msg = f"Bump chart dependencies {[chart for chart in charts_to_update]} to versions {[chart_info[chart]['version'] for chart in charts_to_update]}, respectively"
    logger.info("Committing file: %s" % filename)

    commit_cmd = ["git", "commit", "-m", commit_msg]
    result = run_cmd(commit_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        # Add clean_up functions here
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully committed file: %s" % filename)

    # Push changes to branch
    logger.info("Pushing commits to branch: %s" % target_branch)

    push_cmd = [
        "git",
        "push",
        f"https://HelmUpgradeBot:{token}@github.com/HelmUpgradeBot/{repo_name}",
        target_branch,
    ]
    result = run_cmd(push_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        # Add clean-up functions here
        raise RuntimeError(result["err_msg"])

    logging.info("Successfully pushed changes to branch: %s" % target_branch)


def add_labels(labels: list, pr_url: str, token: str) -> None:
    logger.info("Adding labels to Pull Request: %s" % pr_url)
    logger.info("Adding labels: %s" % labels)

    post_request(
        pr_url,
        headers={"Authorization": f"token {token}"},
        json={"labels": labels},
    )


def check_fork_exists(repo_name: str) -> bool:
    resp = get_request("https://api.github.com/users/HelmUpgradeBot/repos")

    fork_exists = bool([x for x in resp.json() if x["name"] == repo_name])

    return fork_exists


def delete_old_branch(repo_name: str, target_branch: str) -> None:
    resp = get_request(
        f"https://api.github.com/repos/HelmUpgradeBot/{repo_name}"
    )

    if target_branch in [x["name"] for x in resp.json()]:
        logger.info("Deleting branch: %s" % target_branch)
        delete_cmd = ["git", "push", "--delete", "origin", target_branch]
        result = run_cmd(delete_cmd)

        if result["returncode"] != 0:
            logger.error(result["err_msg"])
            # Add clean-up functions here
            raise RuntimeError(resp["err_msg"])

        logger.info("Successfully deleted remote branch")

        delete_cmd = ["git", "branch", "-d", target_branch]
        result = run_cmd(delete_cmd)

        if result["returncode"] != 0:
            logger.error(result["err_msg"])
            # Add clean-up functions here
            raise RuntimeError(resp["err_msg"])

        logger.info("Successfully deleted local branch")

    else:
        logger.info("Branch does not exist: %s" % target_branch)


def checkout_branch(
    repo_owner: str, repo_name: str, target_branch: str
) -> None:
    fork_exists = check_fork_exists(repo_name)

    if fork_exists:
        delete_old_branch(repo_name, target_branch)

        logger.info("Pulling main branch of: %s/%s" % (repo_owner, repo_name))
        pull_cmd = [
            "git",
            "pull",
            f"https://github.com/{repo_owner}/{repo_name}.git",
            "main",
        ]
        result = run_cmd(pull_cmd)

        if result["returncode"] != 0:
            logger.error(result["err_msg"])
            # Add clean-up functions here
            raise RuntimeError(result["err_msg"])

        logger.info("Successfully pulled main branch")

    logging.info("Checking out branch: %s" % target_branch)
    chkt_cmd = ["git", "checkout", "-b", target_branch]
    result = run_cmd(chkt_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        # Add clean-up functions here
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully checked out branch")


def clone_fork(repo_name: str) -> None:
    logger.info("Cloning fork: %s" % repo_name)

    clone_cmd = [
        "git",
        "clone",
        f"https://github.com/HelmUpgradeBot/{repo_name}.git",
    ]
    result = run_cmd(clone_cmd)

    if result["returncode"] != 0:
        logger.error(result["err_msg"])
        # Add clean-up functions here
        raise RuntimeError(result["err_msg"])

    logger.info("Successfully cloned fork")


def create_pr(
    repo_api: str,
    base_branch: str,
    target_branch: str,
    token: str,
    labels: str = None,
) -> None:
    logger.info("Creating Pull Request")

    pr = {
        "title": "Logging Helm Chart version upgrade",
        "body": "This PR is updating the local Helm Chart to the most recent Chart dependency versions.",
        "base": base_branch,
        "head": f"HelmUpgradeBot:{target_branch}",
    }

    resp = post_request(
        repo_api + "pulls",
        headers={"Authorization": f"token {token}"},
        json=pr,
    )

    logger.info("Pull Request created")

    if labels is not None:
        output = resp.json()
        add_labels(labels, output["issue_url"], token)


def make_fork(repo_name: str, repo_api: str, token: str) -> bool:
    logger.info("Forking repo: %s" % repo_name)

    post_request(
        repo_api + "forks", headers={"Authorization": f"token {token}"}
    )

    logger.info("Created fork")

    return True


def remove_fork(repo_name: str, token: str) -> bool:
    fork_exists = check_fork_exists(repo_name)

    if fork_exists:
        logger.info("HelmUpgradeBot has a fork of: %s" % repo_name)

        delete_request(
            f"https://api.github.com/repos/HelmUpgradeBot/{repo_name}",
            headers={"Authorization": f"token {token}"},
        )

        time.sleep(5)
        logger.info("Deleted fork")

    else:
        logger.info("HelmUpgradeBot does not have a fork of: %s" % repo_name)

    return False


def set_github_config() -> None:
    logger.info("Setting up GitHub configuration for HelmUpgradeBot")

    check_call(["git", "config", "--global", "user.name", "HelmUpgradeBot"])
    check_call(
        [
            "git",
            "config",
            "--global",
            "user.email",
            "helmupgradebot.github@gmail.com",
        ]
    )
