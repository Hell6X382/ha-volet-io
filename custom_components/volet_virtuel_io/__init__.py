"""The Volet Virtuel IO integration."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Pour l'instant, notre intégration ne gère pas les entrées de configuration via l'interface utilisateur (config flow).
# Si nous ajoutions cela, nous devrions définir les plateformes ici.
# Exemple: PLATFORMS = ["cover"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Volet Virtuel IO component from YAML configuration."""
    # Cette fonction est appelée si l'intégration est définie dans configuration.yaml
    # (ce qui est notre cas car nous allons définir une plateforme cover).
    # Nous n'avons rien de spécifique à initialiser au niveau global de l'intégration ici,
    # car la configuration de la plateforme cover sera gérée par async_setup_platform dans cover.py.
    hass.data.setdefault("volet_virtuel_io", {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Volet Virtuel IO from a config entry."""
    # Cette fonction est appelée si l'intégration est configurée via l'interface utilisateur.
    # Nous ne l'utilisons pas pour l'instant, mais il est bon de l'avoir pour le futur.
    # Si nous avions des plateformes à charger (ex: cover), nous le ferions ici:
    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    _LOGGER.debug(f"Async_setup_entry pour volet_virtuel_io - non implémenté pour {entry.entry_id}")
    return True # Doit retourner True pour une initialisation réussie, même si vide.


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Cette fonction est appelée lors du déchargement d'une entrée de configuration.
    # Exemple:
    # unloaded = all(
    #     await asyncio.gather(
    #         *[
    #             hass.config_entries.async_forward_entry_unload(entry, platform)
    #             for platform in PLATFORMS
    #         ]
    #     )
    # )
    # if unloaded:
    #     hass.data["volet_virtuel_io"].pop(entry.entry_id)
    # return unloaded
    _LOGGER.debug(f"Async_unload_entry pour volet_virtuel_io - non implémenté pour {entry.entry_id}")
    return True # Doit retourner True pour un déchargement réussi.

# Ajouter un logger si on utilise _LOGGER dans les fonctions ci-dessus
import logging
_LOGGER = logging.getLogger(__name__)
