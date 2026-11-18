"""Codex integration shared by source plugins and generated distribution.

configure-project creates Codex companions, never replaces Claude settings.
record/catch-up export redacted, line-preserving conversational transcripts,
Claude-compatible digests and deterministic signal reports. No model reasoning
or developer/system messages are exported. Hooks stage ONLY these evidence files;
no commits, pushes or automatic model analysis. Rollout format is versioned here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ADAPTER_VERSION = 3
CATALOG = 'qa-toolkit-codex'
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
START = '<!-- qa-toolkit:codex:start -->'
END = '<!-- qa-toolkit:codex:end -->'
TSTART = '# qa-toolkit:codex:start'
TEND = '# qa-toolkit:codex:end'


def load_lab():
    spec = importlib.util.spec_from_file_location('qa_claude_lab', PLUGIN_ROOT / 'bin/qa-lab.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def codex_runtime():
    return (PLUGIN_ROOT / '.codex-plugin/plugin.json').is_file() or os.environ.get('QA_WITH_CODEX') == '1'


def safe_project_path(path, root):
    """Reject links in every component below the explicitly selected project root."""
    path, root = Path(os.path.abspath(path)), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'{path}: outside project {root}')
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f'{current}: symlink; preserve it and resolve configuration manually')
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'{path}: outside project {root}')
    return path


def managed(path, block, begin, end, dry_run=False, root=None):
    """Only replace our bounded block; preserve unrelated content and avoid symlinks."""
    path = safe_project_path(path, root or Path(path).anchor)
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    if (text.count(begin) != text.count(end) or text.count(begin) > 1
            or (begin in text and text.index(begin) > text.index(end))):
        raise ValueError(f'{path}: damaged qa-toolkit managed block')
    fresh = begin + '\n' + block.rstrip() + '\n' + end
    if begin in text:
        text = re.sub(re.escape(begin) + r'.*?' + re.escape(end), lambda _: fresh, text, flags=re.S)
    else:
        text = text.rstrip() + ('\n\n' if text else '') + fresh + '\n'
    if dry_run:
        return text
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        path.write_text(text, encoding='utf-8')
    return path


def configure_project(root):
    """Opt-in companion setup; Claude project remains source of project knowledge."""
    import tomllib
    from qa_template import read_marker
    root = Path(root).resolve()
    roles = []
    for p in sorted(root.iterdir()):
        marker = p / '.qa/project.yaml'
        if p.is_dir() and marker.is_file():
            safe_project_path(marker, root)
            roles.append((p, read_marker(marker)))
    if (root / '.qa/project.yaml').is_file():
        safe_project_path(root / '.qa/project.yaml', root)
        roles.insert(0, (root, read_marker(root / '.qa/project.yaml')))
    wanted = ['qa'] + (['qa-manual'] if any(m.get('role') == 'kb' for _, m in roles) else [])
    wanted += ['qa-auto'] if any(m.get('role') == 'autotests' for _, m in roles) else []
    folders = list(dict.fromkeys([root, *(p for p, _ in roles)]))
    writes = []
    for folder in folders:
        config = folder / '.codex/config.toml'
        safe_project_path(config, root)
        if config.exists():
            tomllib.loads(config.read_text())
        # Respect explicit local enable/disable values outside our own block.
        outside = re.sub(re.escape(TSTART) + r'.*?' + re.escape(TEND), '', config.read_text(), flags=re.S) if config.exists() else ''
        own = tomllib.loads(outside).get('plugins', {})
        block = '\n\n'.join(f'[plugins.{json.dumps(p + "@" + CATALOG)}]\nenabled = true'
                              for p in wanted if p + '@' + CATALOG not in own)
        preview = managed(config, block, TSTART, TEND, dry_run=True, root=root)
        tomllib.loads(preview)
        writes.append((config, block, TSTART, TEND))
        rules = '''Read CLAUDE.md in this directory for the shared QA project map and procedures.
Claude settings are kept for Claude; use Codex tools and the qa-toolkit-codex plugins here.
Resolve bundled bin/ commands relative to the installed plugin root; do not assume they are on PATH.
Delegate named QA roles by reading their generated role SKILL.md and passing it to a Codex subagent;
if delegation is unavailable, perform the roles sequentially with the same checks.
At the end of each QA turn, ensure the Codex lab hook saved evidence under .qa/labs/.
If hooks are not trusted/available, run qa_codex.py record for the current rollout,
or qa_codex.py catch-up --cwd <project-root>. Do not assume collection ran successfully.
Evidence includes redacted conversations, tools, signals and plugin build fingerprints.
Review findings from either provider; record human-approved lessons in the existing skill labs.
Never edit generated dist/codex files: change common sources and rerun build/codex/build.py --install.
The hook stages only its evidence files; commits and pushes follow the project's usual workflow.'''
        agents = folder / 'AGENTS.md'
        override = folder / 'AGENTS.override.md'
        if agents.is_symlink() or override.exists() or override.is_symlink():
            agents = override
            rules = 'Read AGENTS.md for the existing project instructions, then apply these Codex additions.\n' + rules
        managed(agents, rules, START, END, dry_run=True, root=root)
        writes.append((agents, rules, START, END))
    changed = []
    for path, block, begin, end in writes:
        preview = managed(path, block, begin, end, dry_run=True, root=root)
        if not path.exists() or path.read_text(encoding='utf-8') != preview:
            managed(path, block, begin, end, root=root)
            changed.append(str(path))
    return changed



def maybe_configure(root):
    root = Path(root)
    cfg = root / '.codex/config.toml'
    if codex_runtime() or (cfg.is_file() and TSTART in cfg.read_text()):
        return configure_project(root)
    return []


def verify_project(root):
    import tomllib
    from qa_template import read_marker
    problems = []
    root = Path(root)
    wanted = ['qa']
    for p in root.iterdir():
        marker = p / '.qa/project.yaml'
        if p.is_dir() and marker.is_file():
            role = read_marker(marker).get('role')
            wanted += ['qa-manual'] if role == 'kb' else ['qa-auto'] if role == 'autotests' else []
    try:
        config = tomllib.loads((root / '.codex/config.toml').read_text())
    except (ValueError, OSError) as e:
        return [f'Codex project config missing/invalid: {e}']
    if not (root / 'AGENTS.md').is_file():
        problems.append('Codex project has no AGENTS.md companion')
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    for p in set(wanted):
        if not config.get('plugins', {}).get(p + '@' + CATALOG, {}).get('enabled'):
            problems.append(f'Codex {p}: disabled in project config')
        copies = list((home / 'plugins/cache' / CATALOG / p).glob('*/.codex-plugin/plugin.json'))
        if not copies:
            problems.append(f'Codex {p}: not installed; run build/codex/build.py --install in qa-toolkit')
    return problems


def version_findings(folders):
    info_path = PLUGIN_ROOT / 'codex-build.json'
    if not info_path.exists():
        return []
    info = json.loads(info_path.read_text())
    here = info['plugins']['qa']['version']
    from qa_template import version_key
    later = [m.get('plugin_version') for _, m in folders if m.get('plugin_version') and version_key(m['plugin_version']) > version_key(here)]
    return [f'- Codex qa {here} is older than project {max(later, key=version_key)}; rebuild/install via build/codex/build.py --install, then restart the chat.'] if later else []

def is_rollout(path):
    try:
        with Path(path).open(encoding='utf-8') as f:
            for _, line in zip(range(8), f):
                try:
                    if json.loads(line).get('type') == 'session_meta':
                        return True
                except (ValueError, AttributeError):
                    continue
    except OSError:
        pass
    return False


def read_rollout(path, snapshot=None):
    rows, broken = [], 0
    snapshot = Path(path).read_bytes() if snapshot is None else snapshot
    for line in snapshot.decode('utf-8').splitlines():
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('not an object')
            rows.append(row)
        except ValueError:
            broken += 1
            rows.append({})  # retain source line numbers
    return rows, broken


def content_text(content):
    return '\n'.join(c.get('text', '') for c in content or [] if isinstance(c, dict) and isinstance(c.get('text'), str))


def mask_arguments(value, lab):
    """Redact structures without running text substitutions across JSON syntax."""
    if isinstance(value, dict):
        sensitive = re.compile(r'(?i)^(?:token|password|passwd|secret|api[_-]?key|authorization)$')
        return {k: '***' if sensitive.match(k) else mask_arguments(v, lab) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_arguments(v, lab) for v in value]
    return lab.mask(value) if isinstance(value, str) else value



def output_failed(value, depth=0):
    """Inspect structured nested tool status, not error words in successfully read files."""
    if depth > 8:
        return False
    if isinstance(value, str):
        try:
            return output_failed(json.loads(value), depth + 1)
        except ValueError:
            return bool(re.search(r'(?im)^(?:Error:|Traceback|error:)|(?:exit(?:ed with)? code|exited with code)\s*[:=]?\s*[1-9]', value))
    if isinstance(value, list):
        return any(output_failed(x, depth + 1) for x in value)
    if isinstance(value, dict):
        if value.get('isError') or value.get('is_error') or value.get('exit_code'):
            return True
        # Successful process output can contain examples of errors; its explicit status wins.
        if value.get('exit_code') == 0:
            return False
        return any(output_failed(value[k], depth + 1) for k in ('content', 'text', 'structuredContent') if k in value)
    return False

def digest(path):
    lab = load_lab()
    snapshot = Path(path).read_bytes()
    rows, broken = read_rollout(path, snapshot)
    meta = next((r.get('payload', {}) for r in rows if r.get('type') == 'session_meta'), None)
    if not isinstance(meta, dict) or not meta.get('id'):
        raise ValueError('unsupported Codex transcript: session_meta/id missing')
    normalized, kinds = [], {}
    models = set()
    consulted, observations = [], []
    total = {'input_tokens': 0, 'output_tokens': 0}
    last_usage = None
    for n, row in enumerate(rows):
        p = row.get('payload') or {}
        if not isinstance(p, dict):
            p = {}
        kind = row.get('type', '?')
        kinds[kind] = kinds.get(kind, 0) + 1
        item = {'type': 'system', 'timestamp': row.get('timestamp'), 'cwd': meta.get('cwd'),
                'version': meta.get('cli_version'), 'gitBranch': (meta.get('git') or {}).get('branch'),
                'uuid': f'{meta["id"]}:{n + 1}'}
        if kind == 'turn_context' and p.get('model'):
            models.add(p['model'])
        if kind == 'response_item':
            t = p.get('type')
            if t == 'message' and p.get('role') in ('user', 'assistant'):
                text = content_text(p.get('content'))
                # Context injection is not a human request. Export no environment/system context.
                if p['role'] != 'user' or not text.startswith(('<environment_context>', '<external_codex_apps_open_page>')):
                    item.update(type=p['role'], message={'content': [{'type': 'text', 'text': lab.mask(text)}]})
            elif t in ('function_call', 'custom_tool_call'):
                name = p.get('name', '?').split('.')[-1]
                raw = p.get('arguments', p.get('input', ''))
                for found in re.finditer(r'/plugins/cache/([^/\s"\\]+)/([^/\s"\\]+)/([^/\s"\\]+)', str(raw)):
                    if found[1] == CATALOG and found[2] in ('qa', 'qa-manual', 'qa-auto'):
                        observations.append({'name': found[2], 'version': found[3], 'line': n + 1})
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except ValueError:
                    args = {'command': raw}
                args = args if isinstance(args, dict) else {'command': str(args)}
                if name in ('exec_command', 'shell', 'shell_command', 'exec'):
                    name = 'Bash'
                    args['command'] = args.get('cmd', args.get('command', ''))
                elif name == 'apply_patch':
                    name = 'Edit'
                    args = {'file_path': '<patch>', 'new_string': args.get('command', raw)}
                elif name in ('spawn_agent', 'followup_task'):
                    name = 'Agent'
                    args['subagent_type'] = args.get('task_name', args.get('target', 'codex'))
                elif name in ('request_user_input', 'request_user_input_async'):
                    name = 'AskUserQuestion'
                    args['questions'] = [{**q, 'question': q.get('question', q.get('title', ''))}
                                         for q in args.get('questions', []) if isinstance(q, dict)]
                for found in re.finditer(r'/skills/([^/\s]+)/SKILL\.md', str(raw)):
                    consulted.append({'name': found[1], 'how': 'consulted', 'line': n + 1})
                args = mask_arguments(args, lab)
                item.update(type='assistant', message={'content': [{'type': 'tool_use', 'id': p.get('call_id'), 'name': name, 'input': args}]})
            elif t in ('function_call_output', 'custom_tool_call_output'):
                output = p.get('output', '')
                text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
                failed = output_failed(output)
                item.update(type='user', message={'content': [{'type': 'tool_result', 'tool_use_id': p.get('call_id'), 'content': lab.mask(text), 'is_error': failed}]})
        if kind == 'event_msg' and p.get('type') in ('task_aborted', 'turn_aborted', 'turn_interrupted'):
            item.update(type='user', message={'content': [{'type': 'text', 'text': lab.INTERRUPT + ']'}]})
        if kind == 'event_msg' and p.get('type') == 'token_count':
            usage = (p.get('info') or {}).get('total_token_usage')
            if isinstance(usage, dict):
                total = {k: usage.get(k, 0) for k in total}
                last_usage = n
        normalized.append(item)
    if last_usage is not None:
        normalized[last_usage].update(type='assistant', message={'id': meta['id'] + ':usage', 'usage': total, 'content': []})
    with tempfile.TemporaryDirectory(prefix='qa-codex-') as td:
        tmp = Path(td) / 'normalized.jsonl'
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in normalized), encoding='utf-8')
        d = lab.digest(tmp, {})
    d.update(provider='codex', session=meta['id'], cc=None, codex=meta.get('cli_version'),
             adapter_version=ADAPTER_VERSION, models=sorted(models), broken=broken,
             source_kinds=kinds, resumed_from=meta.get('forked_from_id'))
    d['consulted_skills'] = consulted
    observed = {}
    for observation in observations:
        observed.setdefault(observation['name'], set()).add(observation['version'])
    d['source_sha256'] = hashlib.sha256(snapshot).hexdigest()
    d['plugins'] = {name: next(iter(versions)) for name, versions in observed.items() if len(versions) == 1}
    d['execution_provenance'] = {'status': 'observed-cache-paths' if observations else 'unknown',
                               'observations': observations}
    build_info = PLUGIN_ROOT / 'codex-build.json'
    if build_info.is_file():
        d['collector_build'] = json.loads(build_info.read_text())
    return d, normalized


def atomic_write(path, data, root):
    safe_project_path(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def record(path, cwd=None, stage=True, parent_session=None):
    import fcntl
    lab = load_lab()
    d, rows = digest(path)
    repo = lab.lab_repo(d['cwd'] or cwd or '.')
    if repo is None:
        return None
    # A supplied cwd is a filter, not permission to reroute a different project's session.
    if cwd is not None and lab.lab_repo(cwd) != repo:
        return None
    # Root sessions may route to a child KB; never follow a linked role outside it.
    origin = Path(d['cwd'] or cwd or '.').resolve()
    if repo.resolve() != origin and repo.resolve() not in origin.parents:
        safe_project_path(repo, origin)
    repo = repo.resolve()
    sid = re.sub(r'[^A-Za-z0-9._-]', '_', d['session'])
    host = lab.machine()
    transcript = Path('.qa/labs/transcripts/codex') / host / (sid + '.jsonl')
    analysis = Path('.qa/labs/analysis/codex') / host / (sid + '.md')
    sessions = Path('.qa/labs/sessions') / (host + '-codex.jsonl')
    for rel in (transcript, analysis, sessions):
        safe_project_path(repo / rel, repo)
    if parent_session:
        d['parent_session'] = 'codex:' + parent_session
        d['actor'] = 'subagent'
    else:
        d['actor'] = 'main'
    d.update(session='codex:' + d['session'], transcript=transcript.as_posix(), analysis=analysis.as_posix(), machine=host)
    report = f'# Codex session {sid}\n\nProvider: codex; CLI: {d["codex"]}; parser: {ADAPTER_VERSION}\n\n'
    report += f'Prompts: {d["prompts"]}; tokens: {d["tokens"]["main"]}; models: {", ".join(d["models"])}\n\n'
    report += '## Observed signals\n\n' + ('\n'.join(f'- {s["kind"]}, line {s["line"]}: {s.get("what", "")}' for s in d['signals']) or 'No heuristic signals.')
    report += '\n\nThese are mechanical observations, not judgments. Read the redacted transcript around the source lines before proposing changes.\n'
    (repo / sessions).parent.mkdir(parents=True, exist_ok=True)
    # Serialize transcript + report + index updates, so simultaneous hooks for a resumed session cannot produce mismatched evidence.
    lock = Path(tempfile.gettempdir()) / ('qa-codex-' + hashlib.sha256(str(repo / sessions).encode()).hexdigest()[:24] + '.lock')
    with lock.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != d['source_sha256']:
            raise RuntimeError('Codex transcript changed during collection; retry record or catch-up')
        atomic_write(repo / transcript, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), repo)
        atomic_write(repo / analysis, report, repo)
        index = repo / sessions
        old = index.read_text().splitlines() if index.exists() else []
        prior = next((json.loads(r) for r in old if lab.session_of(r) == d['session']), {})
        if not parent_session:
            if prior.get('parent_session'):
                d.update(actor='subagent', parent_session=prior['parent_session'])
        previous = prior.get('execution_provenance', {})
        if (not d['execution_provenance']['observations'] and prior.get('plugins')
                and previous.get('status') in ('observed-cache-paths', 'previous-observed-cache-paths')):
            d['plugins'] = prior['plugins']
            d['execution_provenance'] = {**previous, 'status': 'previous-observed-cache-paths',
                                         'previous_source_sha256': prior.get('source_sha256')}
        kept = [r for r in old if lab.session_of(r) != d['session']]
        atomic_write(index, '\n'.join([*kept, json.dumps(d, ensure_ascii=False)]) + '\n', repo)
        if stage:
            git = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
            if git.returncode == 0:
                added = subprocess.run(['git', '-C', str(repo), 'add', '--', str(transcript), str(analysis), str(sessions)], capture_output=True, text=True)
                if added.returncode:
                    raise RuntimeError('Codex evidence saved but git add failed: ' + added.stderr.strip())
    return d


def sessions_root():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'sessions'


def catch_up(folder, cwd, skip=None, stage=True):
    lab = load_lab()
    if lab.lab_repo(cwd) is None:
        return 0
    repo = lab.lab_repo(cwd)
    index = repo / '.qa/labs/sessions' / (lab.machine() + '-codex.jsonl')
    known = {}
    if index.exists():
        for line in index.read_text().splitlines():
            try:
                entry = json.loads(line); known[entry['session']] = entry.get('source_sha256')
            except (ValueError, KeyError):
                pass
    count = 0
    for p in sorted(Path(folder).rglob('*.jsonl')):
        if not is_rollout(p):
            continue
        # Filter via metadata BEFORE parsing full sessions (no unrelated project conversations).
        with p.open(encoding='utf-8') as f:
            first = json.loads(f.readline()).get('payload', {})
        if first.get('id') == skip or lab.lab_repo(first.get('cwd') or '.') != lab.lab_repo(cwd):
            continue
        if known.get('codex:' + first.get('id', '')) == hashlib.sha256(p.read_bytes()).hexdigest():
            continue
        if record(p, cwd, stage) is not None:
            count += 1
    return count


def hook(event):
    lab = load_lab()
    cwd = event.get('cwd')
    if not cwd or lab.lab_repo(cwd) is None:
        return {}
    kind = event.get('hook_event_name', '')
    try:
        if kind == 'SessionStart':
            catch_up(sessions_root(), cwd, event.get('session_id'))
        else:
            path = event.get('agent_transcript_path') if kind == 'SubagentStop' else event.get('transcript_path')
            if path and Path(path).is_file():
                record(path, cwd, parent_session=event.get('session_id') if kind == 'SubagentStop' else None)
            else:
                return {'systemMessage': 'QA lab: Codex transcript unavailable; run catch-up before committing evidence.'}
    except (OSError, ValueError, RuntimeError) as e:
        return {'systemMessage': f'QA lab collection failed: {e}'}
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('configure-project'); p.add_argument('root', type=Path)
    for cmd in ['record', 'digest']:
        p = sub.add_parser(cmd); p.add_argument('transcript', type=Path); p.add_argument('--cwd')
        p.add_argument('--no-stage', action='store_true')
    p = sub.add_parser('catch-up'); p.add_argument('folder', nargs='?', type=Path, default=sessions_root())
    p.add_argument('--cwd', required=True); p.add_argument('--skip'); p.add_argument('--no-stage', action='store_true')
    sub.add_parser('hook')
    args = parser.parse_args()
    try:
        if args.cmd == 'hook':
            print(json.dumps(hook(json.load(sys.stdin)), ensure_ascii=False))
        elif args.cmd == 'configure-project':
            print(json.dumps({'configured': configure_project(args.root)}, ensure_ascii=False))
        elif args.cmd == 'record':
            print(json.dumps(record(args.transcript, args.cwd, not args.no_stage), ensure_ascii=False))
        elif args.cmd == 'digest':
            print(json.dumps(digest(args.transcript)[0], ensure_ascii=False))
        else:
            print(json.dumps({'recorded': catch_up(args.folder, args.cwd, args.skip, not args.no_stage)}))
    except (OSError, ValueError, RuntimeError) as e:
        print(f'qa-codex: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
