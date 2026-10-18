"""One-shot local screenshots, with exact-image approval before external vision."""
import hashlib
from pathlib import Path
from flask import current_app
from . import policy
from .. import windows


def folder():
    path=Path(current_app.config['DATABASE']).resolve().parent/'agent-screens'
    path.mkdir(mode=0o700,exist_ok=True);return path


def prepare(ctx):
    policy.computer_access(ctx)
    if not windows.supported():raise ValueError('Screen capture requires your Windows desktop session.')
    from PIL import ImageGrab
    image=ImageGrab.grab(all_screens=False).convert('RGB');original=image.size
    image.thumbnail((1280,900));token=__import__('secrets').token_hex(24);path=folder()/token
    image.save(path,format='PNG')
    preview=dict(token=token,hash=hashlib.sha256(path.read_bytes()).hexdigest(),original_size=list(original),shared_size=list(image.size),note='Primary-screen snapshot. Coordinates must be scaled back to original pixels. This is a captured moment, not a live feed.')
    ctx.prepared=preview
    return preview


def share(ctx,a):
    if not ctx.approved:raise policy.ApprovalRequired('Review this locally captured screen before sending it to OpenAI for vision.',preview=prepare(ctx))
    preview=ctx.prepared
    if not preview:raise ValueError('The approved screen preview is no longer available.')
    raw=(folder()/preview['token']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=preview['hash']:raise ValueError('Screenshot changed since approval; no image shared.')
    return dict(result=preview,images=[preview['token']])
