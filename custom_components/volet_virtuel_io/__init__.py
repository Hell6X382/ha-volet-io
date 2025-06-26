"""The Volet Virtuel IO integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

# Notre intégration est configurée via YAML (platform cover), donc pas de plateformes à définir ici pour config_flow pour l'instant.
# PLATFORMS = ["cover"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Volet Virtuel IO component from YAML (not used for config flow)."""
    # Si l'intégration avait une configuration globale dans configuration.yaml (pas juste une plateforme),
    # elle serait traitée ici. Pour une plateforme, c'est async_setup_platform dans cover.py qui gère.
    _LOGGER.debug("Volet Virtuel IO - async_setup: Initialisation via YAML gérée par la plateforme cover.")
    hass.data.setdefault("volet_virtuel_io", {}) # Espace pour stocker des données globales si besoin un jour.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Volet Virtuel IO from a config entry (UI configuration)."""
    # Cette fonction est pour la configuration via l'interface utilisateur.
    # Nous ne l'implémentons pas activement pour cette version (YAML uniquement).
    _LOGGER.debug(f"Volet Virtuel IO - async_setup_entry: Non implémenté pour l'entrée {entry.entry_id}. Utiliser la configuration YAML.")
    # Si on supportait les plateformes via config_flow:
    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True # Indique le succès même si rien n'est fait.


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Gérer le déchargement si on utilisait config_flow et les plateformes.
    _LOGGER.debug(f"Volet Virtuel IO - async_unload_entry: Non implémenté pour l'entrée {entry.entry_id}.")
    # Exemple:
    # unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # if unloaded:
    #     hass.data["volet_virtuel_io"].pop(entry.entry_id)
    # return unloaded
    return True
