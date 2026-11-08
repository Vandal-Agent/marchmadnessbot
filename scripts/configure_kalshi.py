"""Explicit, backup-first migration to the established central env. No secrets printed."""
from __future__ import annotations

import os
import argparse
import io
import tempfile
import uuid
from pathlib import Path

from dotenv import dotenv_values


def protected_write(path: Path, content: bytes) -> None:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def configure(env: Path, id_path: Path, key_path: Path) -> Path | None:
    key_id=str(uuid.UUID(id_path.read_text().strip()))
    if not key_path.is_file() or env.is_symlink():
        raise ValueError('Check the private-key and central-env paths')
    if os.name=='posix' and key_path.stat().st_mode & 0o077:
        raise ValueError('Private key must have owner-only permissions')
    original=env.read_bytes()
    current=dotenv_values(stream=io.StringIO(original.decode()),interpolate=False)
    additions=[]
    for name,value in [('KALSHI_API_KEY_ID',key_id),('KALSHI_PRIVATE_KEY_PATH',str(key_path.resolve()))]:
        if any(c in value for c in "\r\n'\\"):
            # Backslashes are normal on Windows in the test fixture. dotenv's
            # single quoted form needs escaping them before writing.
            if '\r' in value or '\n' in value or "'" in value:
                raise ValueError('Unsupported configuration value')
        if name in current:
            if current[name]!=value:
                raise ValueError('Existing Kalshi setting differs; central env was not changed')
        else:
            escaped=value.replace('\\','\\\\')
            additions.append(f"{name}='{escaped}'\n")
    if not additions:
        return None
    backup=env.with_name(env.name+'.kalshi-backup-'+uuid.uuid4().hex)
    protected_write(backup,original)
    content=original+(b'\n' if original and not original.endswith(b'\n') else b'')+''.join(additions).encode()
    fd,temp_name=tempfile.mkstemp(prefix='.kalshi-env-',dir=env.parent)
    temp=Path(temp_name)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Do not overwrite concurrent edits to a shared configuration file.
        if env.read_bytes()!=original:
            raise ValueError('Central env changed during setup; retry after review')
        os.replace(temp,env)
    finally:
        temp.unlink(missing_ok=True)
    return backup


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Add Kalshi settings to an existing protected central env')
    parser.add_argument('--env',type=Path,required=True)
    parser.add_argument('--id-file',type=Path,required=True)
    parser.add_argument('--key-file',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=configure(args.env,args.id_file,args.key_file)
        print('Kalshi settings saved; protected env backup created.' if result else 'Kalshi settings already match; unchanged.')
    except Exception:
        print('Setup stopped. Check file permissions and existing Kalshi settings. No secret values are printed.')
        raise SystemExit(1)
