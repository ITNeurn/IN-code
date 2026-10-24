# -*- coding: utf-8 -*-
"""配置模块：负责软件配置的读写与全局路径管理。"""
from .settings import Settings, APP_DATA_DIR, RUNTIME_DIR, ASSETS_DIR

__all__ = ["Settings", "APP_DATA_DIR", "RUNTIME_DIR", "ASSETS_DIR"]
