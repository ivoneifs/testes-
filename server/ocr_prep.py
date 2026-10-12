"""Pré-processamento das fotos de anamnese antes da leitura (OCR) pela IA.

Foto de celular costuma vir deitada (EXIF), escura ou pequena demais. Aqui só
endireita, ajusta contraste e leva o lado maior para ~2048 px (resolução que o
modo `detail: high` aproveita). Se algo falhar, devolve a imagem original.
"""
from __future__ import annotations

import io

TARGET = 2048


def prepare_image(data: bytes, mime: str) -> tuple[bytes, str]:
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data, mime
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        w, h = img.size
        scale = TARGET / max(w, h)
        if scale < 1 or scale > 1.25:  # reduz as enormes, amplia as pequenas
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=1)
        out = io.BytesIO()
        img.save(out, 'JPEG', quality=92, optimize=True)
        return out.getvalue(), 'image/jpeg'
    except Exception:
        return data, mime
