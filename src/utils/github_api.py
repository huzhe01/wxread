import os
import requests
import base64
import logging
from nacl import encoding, public

logger = logging.getLogger(__name__)

class GitHubAPI:
    def __init__(self, token=None, repository=None):
        self.token = token or os.getenv('GH_PAT')
        self.repository = repository or os.getenv('GITHUB_REPOSITORY')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt secret value using GitHub public key"""
        public_key_bytes = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_bytes)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def update_secret(self, secret_name: str, secret_value: str) -> bool:
        """Update GitHub Actions Secret"""
        if not self.token or not self.repository:
            logger.warning("⚠️ GH_PAT or GITHUB_REPOSITORY not set, skipping secret update")
            return False
        
        try:
            # Get public key
            key_url = f"https://api.github.com/repos/{self.repository}/actions/secrets/public-key"
            key_response = requests.get(key_url, headers=self.headers)
            key_response.raise_for_status()
            key_data = key_response.json()
            
            # Encrypt value
            encrypted_value = self.encrypt_secret(key_data["key"], secret_value)
            
            # Update secret
            secret_url = f"https://api.github.com/repos/{self.repository}/actions/secrets/{secret_name}"
            update_response = requests.put(
                secret_url,
                headers=self.headers,
                json={
                    "encrypted_value": encrypted_value,
                    "key_id": key_data["key_id"]
                }
            )
            update_response.raise_for_status()
            logger.info(f"✅ Successfully updated GitHub Secret: {secret_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update GitHub Secret: {e}")
            return False
