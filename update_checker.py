import json
import re
import urllib.request

_GITHUB_API_BASE = "https://api.github.com"

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def normalize_version(value):
    value = (value or "").strip()
    if value.lower().startswith("v"):
        return value[1:].strip()
    return value


def extract_version(text):
    if not text:
        return ""
    match = re.search(
        r"\bv?(\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)\b",
        str(text),
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return normalize_version(match.group(1))


def parse_semver(version):
    version = normalize_version(version)
    match = _SEMVER_RE.match(version)
    if not match:
        extracted = extract_version(version)
        if extracted and extracted != version:
            return parse_semver(extracted)
        return None

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    prerelease = match.group("prerelease") or ""

    prerelease_ids = []
    if prerelease:
        for ident in prerelease.split("."):
            if ident.isdigit():
                prerelease_ids.append((0, int(ident)))
            else:
                prerelease_ids.append((1, ident))

    return major, minor, patch, tuple(prerelease_ids)


def compare_semver(a, b):
    """
    Semantic Versioning 2.0.0 precedence:
    - Compare MAJOR, MINOR, PATCH numerically.
    - A version without prerelease > a version with prerelease.
    - Otherwise compare prerelease identifiers.
    """
    a_parsed = parse_semver(a)
    b_parsed = parse_semver(b)
    if not a_parsed or not b_parsed:
        raise ValueError("Invalid semantic version.")

    a_major, a_minor, a_patch, a_pre = a_parsed
    b_major, b_minor, b_patch, b_pre = b_parsed

    core_a = (a_major, a_minor, a_patch)
    core_b = (b_major, b_minor, b_patch)
    if core_a != core_b:
        return -1 if core_a < core_b else 1

    if not a_pre and not b_pre:
        return 0
    if not a_pre and b_pre:
        return 1
    if a_pre and not b_pre:
        return -1

    for a_id, b_id in zip(a_pre, b_pre):
        if a_id == b_id:
            continue
        return -1 if a_id < b_id else 1

    if len(a_pre) == len(b_pre):
        return 0
    return -1 if len(a_pre) < len(b_pre) else 1


def is_newer_version(current_version, latest_version):
    return compare_semver(latest_version, current_version) > 0


def _request_json(url, timeout):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PortableX-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def github_latest_release_url(repo):
    repo = (repo or "").strip()
    if not repo or "/" not in repo:
        raise ValueError("Repo must be in the form 'owner/repo'.")
    return f"{_GITHUB_API_BASE}/repos/{repo}/releases/latest"


def get_latest_github_release(repo, timeout=6.0):
    repo = (repo or "").strip()
    url = github_latest_release_url(repo)

    payload = _request_json(url, timeout=timeout)
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected response from GitHub.")

    tag = str(payload.get("tag_name") or "").strip()
    name = str(payload.get("name") or "").strip()
    html_url = str(payload.get("html_url") or "").strip()
    published_at = str(payload.get("published_at") or "").strip()

    tag_candidate = extract_version(tag) or normalize_version(tag)
    name_candidate = extract_version(name) or normalize_version(name)

    version = ""
    for candidate in (tag_candidate, name_candidate):
        if candidate and parse_semver(candidate):
            version = candidate
            break
    if not version:
        version = tag_candidate or name_candidate

    return {
        "repo": repo,
        "api_url": url,
        "version": version,
        "tag_version_candidate": tag_candidate,
        "name_version_candidate": name_candidate,
        "tag_name": tag,
        "name": name,
        "html_url": html_url,
        "published_at": published_at,
    }
