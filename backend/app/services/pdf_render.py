"""PDF 渲染公共辅助：内置 CID 中文字体注册。

reportlab 内置 `STSong-Light`（Adobe GB1 CID 字体），不需要任何字体文件即可
渲染简体中文，本地 Windows 与 Linux 容器输出一致。注册是幂等的（pdfmetrics
以字体名去重），多个渲染服务共享本模块即可。
"""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

CID_FONT = "STSong-Light"

_registered = False


def ensure_cid_font() -> str:
    """注册并返回中文字体名。"""
    global _registered
    if not _registered:
        pdfmetrics.registerFont(UnicodeCIDFont(CID_FONT))
        _registered = True
    return CID_FONT
