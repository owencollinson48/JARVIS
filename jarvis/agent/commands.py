"""Reviewed user-level commands with cancellation, limits and no automatic retries."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import psutil
from . import filesystem as fs,policy
from .. import windows


def run_process(ctx,argv,cwd,timeout=30):
    if not windows.supported():raise ValueError('Commands require your Windows installation.')
    policy.computer_access(ctx)
    # Avoid inheriting known provider credentials. This is NOT a security sandbox.
    env={k:v for k,v in os.environ.items() if not any(word in k.upper() for word in ('OPENAI','TWILIO','API_KEY','AUTH_TOKEN'))}
    with tempfile.TemporaryFile() as output:
        process=subprocess.Popen(argv,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,shell=False)
        ctx.process=process;started=time.monotonic()
        try:
            while process.poll() is None:
                policy.check(ctx.job_id)
                if time.monotonic()-started>timeout:raise TimeoutError('Command time limit reached; known child processes were stopped. Inspect side effects before repeating.')
                if output.tell()>1_000_000:raise ValueError('Command output limit reached.')
                time.sleep(.1)
        finally:
            if process.poll() is None:
                try:
                    children=psutil.Process(process.pid).children(recursive=True)
                    for child in children:
                        try:child.terminate()
                        except psutil.Error:pass
                    process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill()
                    for child in children:
                        try:
                            if child.is_running():child.kill()
                        except psutil.Error:pass
                except (psutil.Error,OSError):
                    try:process.kill()
                    except OSError:pass
            ctx.process=None
        output.seek(0);raw=output.read(8001)
    return policy.guard_data(dict(exit_code=process.returncode,output=raw[:8000].decode('utf-8',errors='replace'),truncated=len(raw)>8000,
                                  verified='Process exit status only; filesystem/application effects need their own checks.'))


def execute(ctx,a):
    policy.require(ctx,3,'Run this exact code under your Windows account? It can change files and applications. Review interpreter, working folder and script. No elevation or UAC bypass.')
    cwd=fs.resolve(a['root'],a['folder'],'allow_edit')
    if not cwd.is_dir():raise ValueError('Choose an approved working folder.')
    if a['interpreter']=='python':argv=[sys.executable,'-c',a['script']]
    elif a['interpreter']=='powershell':
        executable=shutil.which('powershell.exe')
        if not executable:raise ValueError('Windows PowerShell is unavailable.')
        argv=[executable,'-NoProfile','-NonInteractive','-Command',a['script']]
    else:
        executable=shutil.which('cmd.exe')
        if not executable:raise ValueError('Command Prompt is unavailable.')
        argv=[executable,'/D','/S','/C',a['script']]
    return run_process(ctx,argv,str(cwd),30)


def software(ctx,a):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{1,119}',a['package']):raise ValueError('Use an exact package ID from the trusted Windows package source.')
    policy.require(ctx,3,f'{a["operation"].title()} package {a["package"]} using Windows Package Manager? Review the publisher/package yourself. No automatic UAC or licence acceptance.')
    executable=shutil.which('winget.exe')
    if not executable:raise ValueError('Windows Package Manager (App Installer) is unavailable. Install/manage this app manually through Windows.')
    argv=[executable,a['operation'],'--exact','--id',a['package'],'--disable-interactivity']
    if a['operation']=='install':argv += ['--source','winget','--scope','user']
    result=run_process(ctx,argv,str(Path.cwd()),60)
    result['note']='Provider agreements/UAC may require your manual action. A zero exit code is the package manager result, not a trust assessment.'
    return result
