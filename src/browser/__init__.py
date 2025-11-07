"""浏览器控制模块"""

from .playwright_controller import PlaywrightController
from .qwebengine_controller import QWebEngineController

__all__ = ['PlaywrightController', 'QWebEngineController']