"""Start/stop an approved local VLM runtime. No installer or downloader."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import time
from urllib.request import build_opener, ProxyHandler
from ave.core import sha256
from .pipeline import within_project
from ..ai.adapters import _NoRedirect


def sandbox_profile(writable):
    # macOS sandbox network filters require literal 'localhost', not numeric IP.
    path=str(within_project(writable)).replace('\\','\\\\').replace('"','\\"')
    return ('(version 1)(allow default)(deny network*)'
            '(allow network-bind (local ip "localhost:*"))'
            '(allow network-inbound (local ip "localhost:*"))'
            '(allow network-outbound (remote ip "localhost:*"))'
            '(deny file-write*)(allow file-write* (subpath "'+path+'"))')


@contextmanager
def local_server(manifest_path, port=11435):
    """Manifest lists approved file paths/hashes; preparation is explicitly separate."""
    if not 1024<=port<=65535: raise ValueError('Invalid local port')
    manifest=json.loads(within_project(manifest_path).read_text())
    paths={}
    for role in ('binary','model','projector'):
        spec=manifest[role]; p=within_project(spec['path'])
        if sha256(p)!=spec['sha256']: raise PermissionError('Runtime/model changed since approval')
        paths[role]=p
    for spec in manifest.get('libraries',[]):
        if sha256(within_project(spec['path']))!=spec['sha256']:
            raise PermissionError('Runtime library changed since approval')
    work=within_project('temp/analyzer-runtime'); work.mkdir(parents=True,exist_ok=True)
    endpoint=f'http://127.0.0.1:{port}'
    opener=build_opener(ProxyHandler({}),_NoRedirect())
    try:
        opener.open(endpoint+'/health',timeout=1).close()
    except OSError: pass
    else: raise RuntimeError('Port already serves a process; refusing to reuse or terminate it')
    command=['/usr/bin/sandbox-exec','-p',sandbox_profile(work),str(paths['binary']),
             '--offline','-m',str(paths['model']),'--mmproj',str(paths['projector']),
             '--host','127.0.0.1','--port',str(port),'--ctx-size','8192','--parallel','1',
             '--alias',manifest['model_name'],'--no-webui','--log-verbosity','1']
    log=work/'managed-server.log'
    with log.open('ab') as output:
        process=subprocess.Popen(command,cwd=within_project('.'),stdout=output,stderr=output,
            env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8','TMPDIR':str(work)})
    try:
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if process.poll() is not None: raise RuntimeError('Local runtime failed under sandbox')
            try:
                with opener.open(endpoint+'/health',timeout=1) as response:
                    if response.status==200: break
            except OSError: pass
            time.sleep(.25)
        else: raise TimeoutError('Local model load timed out')
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
