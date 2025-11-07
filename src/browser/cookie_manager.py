"""
Cookie管理器 - 负责Cookie的加密存储和会话管理
"""

import json
import base64
from pathlib import Path
from typing import List, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CookieManager:
    """Cookie管理器"""

    def __init__(self, storage_dir: str = "data/cookies"):
        """初始化Cookie管理器"""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cipher = self._init_cipher()

    def _init_cipher(self) -> Fernet:
        """初始化加密器"""
        # 使用固定的salt和password生成密钥(实际应用中应该让用户设置)
        password = b"web_crawler_secret_key_2024"
        salt = b"web_crawler_salt"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)

    def save_cookies(self, site_id: str, cookies: List[Dict]) -> bool:
        """保存Cookie到加密文件"""
        try:
            cookie_file = self.storage_dir / f"{site_id}.cookie"
            cookie_data = json.dumps(cookies)
            encrypted_data = self._cipher.encrypt(cookie_data.encode())
            cookie_file.write_bytes(encrypted_data)
            return True
        except Exception as e:
            print(f"保存Cookie失败: {e}")
            return False

    def load_cookies(self, site_id: str) -> Optional[List[Dict]]:
        """从加密文件加载Cookie"""
        try:
            cookie_file = self.storage_dir / f"{site_id}.cookie"
            if not cookie_file.exists():
                return None

            encrypted_data = cookie_file.read_bytes()
            decrypted_data = self._cipher.decrypt(encrypted_data)
            cookies = json.loads(decrypted_data.decode())
            return cookies
        except Exception as e:
            print(f"加载Cookie失败: {e}")
            return None

    def delete_cookies(self, site_id: str) -> bool:
        """删除Cookie文件"""
        try:
            cookie_file = self.storage_dir / f"{site_id}.cookie"
            if cookie_file.exists():
                cookie_file.unlink()
            return True
        except Exception as e:
            print(f"删除Cookie失败: {e}")
            return False

    def clear_all_cookies(self) -> bool:
        """清除所有Cookie"""
        try:
            for cookie_file in self.storage_dir.glob("*.cookie"):
                cookie_file.unlink()
            return True
        except Exception as e:
            print(f"清除所有Cookie失败: {e}")
            return False
