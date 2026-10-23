"""Server-side OpenAI image provider. Never exposes or persists API credentials."""
from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

class ImageProviderError(Exception):
    pass


def _call(url: str, body: bytes, content_type: str) -> bytes:
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ImageProviderError('OPENAI_API_KEY is not configured. Demo art remains available.')
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': content_type})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read(18 * 1024 * 1024)
        obj = json.loads(raw)
        if not obj.get('data') or not obj['data'][0].get('b64_json'):
            raise ImageProviderError('Image API returned an unexpected response')
        content = base64.b64decode(obj['data'][0]['b64_json'], validate=True)
        if len(content) < 100 or len(content) > 12 * 1024 * 1024:
            raise ImageProviderError('Unexpected image size')
        return content
    except urllib.error.HTTPError as e:
        # Do not return provider error body (which may echo submitted prompts).
        raise ImageProviderError(f'Image provider returned HTTP {e.code}. Check billing, permissions or prompt policy.') from None
    except (urllib.error.URLError, TimeoutError):
        raise ImageProviderError('Image provider is currently unreachable') from None


def generate(prompt: str, parent_image: Path | None = None) -> bytes:
    model = os.environ.get('OPENAI_IMAGE_MODEL','gpt-image-1-mini')
    full_prompt = ('Create a professional e-commerce product concept rendering. ' 
        'Original friendly jellyfish-inspired product, no trademarks or existing licensed characters. ' 
        'Centered studio photograph, soft blue lighting, premium packaging visual, no textual logo. ' 
        'Requested design: ' + prompt[:700])
    if parent_image and parent_image.is_file() and parent_image.suffix.lower() == '.png':
        boundary = '----ZOKU' + secrets.token_hex(12)
        chunks=[]
        def field(name: str, value: bytes, filename: str | None = None, mime='text/plain'):
            cd=f'Content-Disposition: form-data; name="{name}"'
            if filename: cd+=f'; filename="{filename}"'
            chunks.append(f'--{boundary}\r\n{cd}\r\nContent-Type: {mime}\r\n\r\n'.encode()+value+b'\r\n')
        field('model',model.encode());field('prompt',('Reinterpret and improve the attached product concept while preserving some of its visual lineage. '+full_prompt).encode())
        field('size',b'1024x1024');field('quality',b'low')
        field('image',parent_image.read_bytes(),filename='source.png',mime='image/png')
        body=b''.join(chunks)+f'--{boundary}--\r\n'.encode()
        return _call('https://api.openai.com/v1/images/edits',body,f'multipart/form-data; boundary={boundary}')
    payload={'model':model,'prompt':full_prompt,'size':'1024x1024','quality':'low','n':1}
    return _call('https://api.openai.com/v1/images/generations',json.dumps(payload).encode(),'application/json')
