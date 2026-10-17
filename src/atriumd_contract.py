"""Portable Atrium sidecar validator shared by source CLI and trusted registry handler.

No deployment URL or service credential may occur in sidecar metadata.
"""
import re

COMPONENT_RE = re.compile(r'^[a-z][a-z0-9-]{0,47}$')
GAME_RE = re.compile(r'^[a-z][a-z0-9.-]{2,119}$')
NAME_RE = re.compile(r'^[a-z][a-z0-9-]{0,63}$')
ENTRY_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$')
URL_RE = re.compile(r'(?i)\b(?:https?|wss?|file)://')

class SidecarError(ValueError):
    pass


def _mapping(value, keys, required, name):
    if type(value) is not dict or set(value) - keys or not required <= set(value):
        raise SidecarError(name + ': invalid object properties')
    return value


def _match(value, regex, name):
    if type(value) is not str or not regex.fullmatch(value):
        raise SidecarError(name + ': invalid string')
    return value


def _no_addresses(value):
    if type(value) is str and (URL_RE.search(value) or value.startswith(('/', '\\'))):
        raise SidecarError('sidecar cannot contain deployment URLs or absolute paths')
    if type(value) is dict:
        for child in value.values(): _no_addresses(child)
    if type(value) is list:
        for child in value: _no_addresses(child)


def validate_document(doc, *, component):
    _mapping(doc, {'schema', 'component', 'game'}, {'schema', 'component', 'game'}, 'sidecar')
    if doc['schema'] != 'atriumd/v1': raise SidecarError('unsupported sidecar schema')
    if _match(doc['component'], COMPONENT_RE, 'component') != component:
        raise SidecarError('sidecar component differs from activated game component')
    game = _mapping(doc['game'], {'id','publisher','title','summary','kind','platforms','launch','services','integration'},
                    {'id','publisher','title','kind','platforms','launch'}, 'game')
    _match(game['id'], GAME_RE, 'game.id')
    _match(game['publisher'], NAME_RE, 'game.publisher')
    if type(game['title']) is not str or not 1 <= len(game['title'].strip()) <= 160:
        raise SidecarError('invalid game title')
    if 'summary' in game and (type(game['summary']) is not str or not 1 <= len(game['summary'].strip()) <= 300):
        raise SidecarError('invalid game summary')
    if game['kind'] != 'game': raise SidecarError('unsupported application kind')
    platforms = game['platforms']
    if type(platforms) is not list or not 1 <= len(platforms) <= 12: raise SidecarError('invalid platforms')
    runtimes = set()
    for platform in platforms:
        _mapping(platform, {'runtime','formFactors','installMode'}, {'runtime','formFactors','installMode'}, 'platform')
        runtime, install = platform['runtime'], platform['installMode']
        if type(runtime) is not str or runtime not in {'web','windows','linux','macos','android','ios'} or runtime in runtimes:
            raise SidecarError('invalid or duplicate runtime')
        if type(install) is not str or install not in {'none','pwa','offline-web','native'}:
            raise SidecarError('invalid install mode')
        if (runtime != 'web' and install in {'pwa','offline-web'}) or (runtime == 'web' and install == 'native'):
            raise SidecarError('install mode incompatible with runtime')
        forms = platform['formFactors']
        if type(forms) is not list or not forms or any(type(x) is not str or x not in {'desktop','tablet','phone'} for x in forms) or len(forms) != len(set(forms)):
            raise SidecarError('invalid form factors')
        runtimes.add(runtime)
    launch = _mapping(game['launch'], {'mode','originRef','entrypoint'}, {'mode','originRef','entrypoint'}, 'launch')
    if launch['mode'] != 'hosted-web' or 'web' not in runtimes:
        raise SidecarError('unsupported launch mode')
    _match(launch['originRef'], NAME_RE, 'originRef')
    entry = _match(launch['entrypoint'], ENTRY_RE, 'entrypoint')
    if any(x in {'.','..',''} for x in entry.split('/')): raise SidecarError('unsafe entrypoint')
    services = game.get('services', [])
    if type(services) is not list or len(services) > 12: raise SidecarError('invalid services')
    seen = set()
    for service in services:
        _mapping(service, {'component','role'}, {'component','role'}, 'service')
        _match(service['component'], COMPONENT_RE, 'service.component')
        if service['role'] not in {'multiplayer','activity','achievements','content'}:
            raise SidecarError('invalid service role')
        key = service['component'], service['role']
        if key in seen: raise SidecarError('duplicate service')
        seen.add(key)
    if 'integration' in game:
        integration = _mapping(game['integration'], {'atriumOptional','sessions','state','identity'},
                               {'atriumOptional','sessions','state','identity'}, 'integration')
        if type(integration['atriumOptional']) is not bool or not integration['atriumOptional'] or any(integration[key] != 'game-owned' for key in ('sessions','state','identity')):
            raise SidecarError('game remains authority for state, identity and sessions')
    _no_addresses(doc)
    return doc
