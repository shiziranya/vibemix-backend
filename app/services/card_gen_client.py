from __future__ import annotations
"""
Client for card_gen service integration.

Handles HTTP communication with the standalone card_gen FastAPI service,
which uses Playwright to render high-quality cocktail cards.
"""
import logging
import os
import random
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class CardGenClient:
    """Client to interact with card_gen microservice."""

    @property
    def base_url(self) -> str:
        """Get card_gen service base URL from config."""
        try:
            from flask import current_app
            return current_app.config.get("CARD_GEN_SERVICE_URL", "http://localhost:8001")
        except RuntimeError:
            # Fallback when outside Flask context (e.g., in tests)
            return os.environ.get("CARD_GEN_SERVICE_URL", "http://localhost:8001")

    @property
    def timeout(self) -> int:
        """Get request timeout from config."""
        try:
            from flask import current_app
            return current_app.config.get("CARD_GEN_TIMEOUT", 60)
        except RuntimeError:
            # Fallback when outside Flask context
            return int(os.environ.get("CARD_GEN_TIMEOUT", "60"))

    def get_available_templates(self) -> list[str]:
        """
        Get list of available templates from card_gen service.
        
        Returns:
            list[str]: List of template names
        """
        try:
            response = requests.get(
                urljoin(self.base_url, "/health"),
                timeout=5
            )
            response.raise_for_status()
            result = response.json()
            return result.get("templates", [])
        except Exception as e:
            logger.error("Failed to get templates from card_gen service: %s", e)
            return []

    def generate_card(
        self,
        cocktail_id: int,
        cocktail_name: str,
        cocktail_name_zh: str,
        ai_poetic: str,
        mood_caption: str,
        ingredients: list[dict],
        user_photo_url: Optional[str] = None,
        template_name: Optional[str] = None,
        abv_level: Optional[str] = None,
        difficulty: Optional[int] = None,
        mood_tags: Optional[list[str]] = None,
        flavor_tags: Optional[list[str]] = None,
        glass_type: Optional[str] = None,
        steps: Optional[list[dict]] = None,
        session_id: Optional[str] = None,
        ai_reason: Optional[str] = None,
        ai_tweaks: Optional[dict] = None,
        prototype_name: Optional[str] = None,
        prototype_name_zh: Optional[str] = None,
    ) -> bytes:
        """
        Generate a cocktail card by calling card_gen service.

        The service generates N variants (default 4), we randomly pick one.

        Args:
            cocktail_id: Cocktail database ID
            cocktail_name: English name
            cocktail_name_zh: Chinese name
            ai_poetic: AI-generated poetic description
            mood_caption: User mood caption
            ingredients: List of ingredient dicts with name, name_zh, measure, etc.
            user_photo_url: Optional user-uploaded photo URL
            template_name: Optional template name (amber/blue/noir/white)
            abv_level: Optional ABV level string
            difficulty: Optional difficulty level (1-5)
            mood_tags: Optional list of mood tags
            flavor_tags: Optional list of flavor tags
            glass_type: Optional glass type
            steps: Optional preparation steps
            session_id: Optional recommendation session ID
            ai_reason: Optional AI recommendation reason
            ai_tweaks: Optional recipe tweaks (for original mode)
            prototype_name: Optional prototype cocktail name (for original mode)
            prototype_name_zh: Optional prototype cocktail Chinese name (for original mode)

        Returns:
            bytes: PNG image data

        Raises:
            Exception: If card_gen service fails
        """
        # Build card_gen service payload
        payload = {
            "input": {
                "session_id": session_id,
                "cocktail": {
                    "id": cocktail_id,
                    "name": cocktail_name,
                    "name_zh": cocktail_name_zh,
                    "abv_level": abv_level,
                    "difficulty": difficulty,
                    "image_url": user_photo_url,
                    "mood_tags": mood_tags or [],
                    "flavor_tags": flavor_tags or [],
                    "glass_type": glass_type,
                },
                "ai": {
                    "reason": ai_reason,
                    "poetic_copy": ai_poetic,
                    "mood_caption": mood_caption,
                    "cocktail_name": cocktail_name,
                    "cocktail_name_zh": cocktail_name_zh,
                    "prototype_name": prototype_name,
                    "prototype_name_zh": prototype_name_zh,
                    "tweaks": ai_tweaks,
                },
                "ingredients": ingredients,
                "steps": steps or [],
            },
            "n": 4,  # Generate 4 variants
            "template": template_name,
        }

        try:
            # Call card_gen service
            logger.info(
                "Calling card_gen service at %s for cocktail_id=%s",
                self.base_url,
                cocktail_id,
            )

            response = requests.post(
                urljoin(self.base_url, "/generate"),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()
            files = result.get("files", [])

            if not files:
                raise ValueError("card_gen service returned no files")

            # Randomly pick one variant
            selected_file = random.choice(files)
            logger.info("Generated %d variants, selected: %s", len(files), selected_file)

            # Fetch the selected file
            file_url = urljoin(self.base_url, f"/file?path={selected_file}")
            file_response = requests.get(file_url, timeout=self.timeout)
            file_response.raise_for_status()

            return file_response.content

        except requests.exceptions.RequestException as e:
            logger.error("card_gen service request failed: %s", e)
            raise Exception(f"Failed to generate card: {e}")
        except Exception as e:
            logger.error("Unexpected error calling card_gen service: %s", e)
            raise


# Singleton instance
card_gen_client = CardGenClient()
