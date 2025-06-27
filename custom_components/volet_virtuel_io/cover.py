"""Platform for the Volet Virtuel IO cover integration."""
import logging
import asyncio
from datetime import datetime, timedelta, timezone

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    # DEVICE_CLASS_SHUTTER,  <-- Supprimé
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA, # Renamed to avoid conflict
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

# Configuration keys
CONF_ENTITY_UP = "entity_up"
CONF_ENTITY_DOWN = "entity_down"
CONF_ENTITY_STOP = "entity_stop"
CONF_TRAVEL_TIME_UP = "travel_time_up"
CONF_TRAVEL_TIME_DOWN = "travel_time_down"
CONF_INITIAL_POSITION = "initial_position" # Position if no state restored (0-100)

# Defaults
DEFAULT_NAME = "Volet Virtuel IO"
DEFAULT_TRAVEL_TIME = 30  # seconds
DEFAULT_INITIAL_POSITION = 50 # Default to half open

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITY_UP): cv.entity_id,
        vol.Required(CONF_ENTITY_DOWN): cv.entity_id,
        vol.Optional(CONF_ENTITY_STOP): cv.entity_id,
        vol.Optional(CONF_TRAVEL_TIME_UP, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
        vol.Optional(CONF_TRAVEL_TIME_DOWN, default=DEFAULT_TRAVEL_TIME): cv.positive_int,
        vol.Optional(CONF_INITIAL_POSITION, default=DEFAULT_INITIAL_POSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Volet Virtuel IO cover platform."""
    name = config[CONF_NAME]
    entity_up = config[CONF_ENTITY_UP]
    entity_down = config[CONF_ENTITY_DOWN]
    entity_stop = config.get(CONF_ENTITY_STOP) # Optional
    travel_time_up = config[CONF_TRAVEL_TIME_UP]
    travel_time_down = config[CONF_TRAVEL_TIME_DOWN]
    initial_position = config[CONF_INITIAL_POSITION]

    async_add_entities([
        VirtualIOCover(
            hass, name, entity_up, entity_down, entity_stop,
            travel_time_up, travel_time_down, initial_position
        )
    ])


class VirtualIOCover(CoverEntity, RestoreEntity):
    """Representation of a Virtual IO Cover."""

    def __init__(
        self, hass, name, entity_up_id, entity_down_id, entity_stop_id,
        travel_time_up, travel_time_down, initial_position
    ):
        """Initialize the cover."""
        self.hass = hass
        self._name = name
        self._entity_up_id = entity_up_id
        self._entity_down_id = entity_down_id
        self._entity_stop_id = entity_stop_id

        self._travel_time_up_sec = travel_time_up
        self._travel_time_down_sec = travel_time_down
        self._initial_position_cfg = initial_position

        self._current_position = None  # 0 (closed) to 100 (open)
        self._target_position = None   # Target for current movement
        self._is_opening = False
        self._is_closing = False

        self._movement_start_utc = None  # UTC Timestamp of when movement began
        self._movement_start_pos = None  # Position when movement began
        self._movement_task = None       # asyncio.Task for simulating movement

        # Home Assistant entity attributes
        self._attr_unique_id = f"volet_virtuel_io_{name.lower().replace(' ', '_')}"
        self._attr_device_class = "shutter"  # Remplacé par la chaîne de caractères
        self._attr_supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        )

    async def async_added_to_hass(self):
        """Call when entity is added to HASS, restore state, and set up listeners."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes.get(ATTR_POSITION) is not None:
            self._current_position = int(last_state.attributes[ATTR_POSITION])
            _LOGGER.debug(f"'{self.name}': Restored position to {self._current_position}%")
        else:
            self._current_position = self._initial_position_cfg
            _LOGGER.debug(f"'{self.name}': No prior state, set to initial config position {self._current_position}%")

        self._target_position = self._current_position # Ensure target is aligned initially
        self.async_write_ha_state()

        # Listen for state changes on control entities
        control_entities = [self._entity_up_id, self._entity_down_id]
        if self._entity_stop_id:
            control_entities.append(self._entity_stop_id)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, control_entities, self._async_control_entity_state_changed
            )
        )

    @callback
    def _async_control_entity_state_changed(self, event):
        """Handle state changes of the physical control entities."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.warning(f"'{self.name}': Control entity {entity_id} became unavailable.")
            return

        _LOGGER.debug(f"'{self.name}': Control entity {entity_id} changed to {new_state.state}")

        # Assuming 'on' means "start action" and 'off' (if it happens during movement) means "stop action"
        if entity_id == self._entity_up_id:
            if new_state.state == "on" and not self._is_opening:
                _LOGGER.info(f"'{self.name}': Detected UP command. Opening...")
                self.hass.async_create_task(self.async_open_cover())
            elif new_state.state == "off" and self._is_opening:
                _LOGGER.info(f"'{self.name}': UP command entity turned off during opening. Stopping...")
                self.hass.async_create_task(self.async_stop_cover())

        elif entity_id == self._entity_down_id:
            if new_state.state == "on" and not self._is_closing:
                _LOGGER.info(f"'{self.name}': Detected DOWN command. Closing...")
                self.hass.async_create_task(self.async_close_cover())
            elif new_state.state == "off" and self._is_closing:
                _LOGGER.info(f"'{self.name}': DOWN command entity turned off during closing. Stopping...")
                self.hass.async_create_task(self.async_stop_cover())

        elif self._entity_stop_id and entity_id == self._entity_stop_id:
            if new_state.state == "on": # Assuming stop is also a momentary 'on'
                _LOGGER.info(f"'{self.name}': Detected STOP command. Stopping...")
                self.hass.async_create_task(self.async_stop_cover())
                # Optional: if stop entity is an input_boolean, you might want to turn it off
                # self.hass.async_create_task(
                #     self.hass.services.async_call('input_boolean', 'turn_off', {'entity_id': self._entity_stop_id})
                # )

    def _update_current_position_on_stop(self):
        """Calculate and set current position when movement is stopped."""
        if self._movement_start_utc is None or self._movement_start_pos is None:
            _LOGGER.debug(f"'{self.name}': Stop called but no active movement to calculate position from.")
            return

        elapsed_seconds = (datetime.now(timezone.utc) - self._movement_start_utc).total_seconds()
        start_pos = self._movement_start_pos
        current_pos = start_pos

        if self._is_opening:
            if self._travel_time_up_sec > 0:
                percentage_moved = (elapsed_seconds / self._travel_time_up_sec) * 100
                current_pos = start_pos + percentage_moved
        elif self._is_closing:
            if self._travel_time_down_sec > 0:
                percentage_moved = (elapsed_seconds / self._travel_time_down_sec) * 100
                current_pos = start_pos - percentage_moved

        self._current_position = round(max(0, min(100, current_pos)))
        # Also ensure it doesn't go past the intended target if it was a partial move
        if self._is_opening and self._target_position is not None:
            self._current_position = min(self._current_position, self._target_position)
        elif self._is_closing and self._target_position is not None:
            self._current_position = max(self._current_position, self._target_position)

        _LOGGER.info(f"'{self.name}': Movement stopped. New calculated position: {self._current_position}% after {elapsed_seconds:.2f}s")

    async def _async_simulate_movement(self, duration_seconds):
        """Task to simulate movement for a given duration."""
        try:
            await asyncio.sleep(duration_seconds)
            # Movement completed naturally (reached target)
            self._current_position = self._target_position
            _LOGGER.info(f"'{self.name}': Movement finished naturally. Reached target position {self._current_position}%.")
        except asyncio.CancelledError:
            # Movement was cancelled (stopped)
            self._update_current_position_on_stop()
            _LOGGER.info(f"'{self.name}': Movement simulation cancelled.")
            raise # Important to re-raise CancelledError
        finally:
            self._is_opening = False
            self._is_closing = False
            self._movement_start_utc = None
            self._movement_start_pos = None
            self._movement_task = None # Clear the task reference
            self.async_write_ha_state()

    async def _async_start_movement(self, target_pos):
        """Start or update cover movement to a new target position."""
        if self._movement_task:
            self._movement_task.cancel() # Cancel existing movement
            # _update_current_position_on_stop will be called by the cancelled task's handler
            self._movement_task = None

        self._target_position = target_pos
        self._movement_start_utc = datetime.now(timezone.utc)
        self_movement_start_pos = self._current_position # Current position before this new movement

        if self._target_position == self_movement_start_pos:
            _LOGGER.debug(f"'{self.name}': Already at target position {self._target_position}%.")
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
            return

        if self._target_position > self_movement_start_pos:
            self._is_opening = True
            self._is_closing = False
            travel_time_total_sec = self._travel_time_up_sec
            distance_to_target_percent = self._target_position - self_movement_start_pos
        else: # target_position < _current_position
            self._is_opening = False
            self._is_closing = True
            travel_time_total_sec = self._travel_time_down_sec
            distance_to_target_percent = self_movement_start_pos - self._target_position

        self.async_write_ha_state() # Update is_opening/is_closing state

        if travel_time_total_sec == 0 or distance_to_target_percent == 0:
            duration_for_this_move_sec = 0
        else:
            duration_for_this_move_sec = (distance_to_target_percent / 100.0) * travel_time_total_sec

        duration_for_this_move_sec = max(0, duration_for_this_move_sec)

        _LOGGER.info(
            f"'{self.name}': Moving from {self_movement_start_pos}% to {self._target_position}%. "
            f"Estimated duration for this segment: {duration_for_this_move_sec:.2f}s."
        )

        # Store the start position for this specific movement segment
        self._movement_start_pos = self_movement_start_pos

        if duration_for_this_move_sec == 0: # Instantaneous move
            self._current_position = self._target_position
            self._is_opening = False
            self._is_closing = False
            self._movement_start_utc = None
            self._movement_start_pos = None
            _LOGGER.info(f"'{self.name}': Movement instantaneous. Reached position {self._current_position}%.")
            self.async_write_ha_state()
        else:
            self._movement_task = self.hass.loop.create_task(
                self._async_simulate_movement(duration_for_this_move_sec)
            )

    # --- CoverEntity Properties ---
    @property
    def name(self):
        return self._name

    @property
    def current_cover_position(self):
        return self._current_position

    @property
    def is_opening(self):
        return self._is_opening

    @property
    def is_closing(self):
        return self._is_closing

    @property
    def is_closed(self):
        if self._current_position is None:
            return None # Not yet determined
        return self._current_position == 0

    # --- CoverEntity Methods ---
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug(f"'{self.name}': Service call: open_cover.")
        if self._current_position == 100 and not self._is_opening:
             _LOGGER.debug(f"'{self.name}': Already fully open.")
             return
        await self._async_start_movement(100)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.debug(f"'{self.name}': Service call: close_cover.")
        if self._current_position == 0 and not self._is_closing:
             _LOGGER.debug(f"'{self.name}': Already fully closed.")
             return
        await self._async_start_movement(0)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover movement."""
        _LOGGER.debug(f"'{self.name}': Service call: stop_cover.")
        if self._movement_task:
            self._movement_task.cancel() # This will call _update_current_position_on_stop via task handler
            self._movement_task = None # Ensure it's cleared
        else: # Not moving, but ensure flags are correct and state is written
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
        _LOGGER.info(f"'{self.name}': Cover stopped at position {self._current_position}%.")

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = int(kwargs[ATTR_POSITION])
        _LOGGER.debug(f"'{self.name}': Service call: set_cover_position to {position}%.")
        if position == self._current_position and not (self._is_opening or self._is_closing) :
            _LOGGER.debug(f"'{self.name}': Already at desired position {position}%.")
            return
        await self._async_start_movement(position)

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {
            "target_position": self._target_position if self._target_position is not None else "N/A",
            "travel_time_up_seconds": self._travel_time_up_sec,
            "travel_time_down_seconds": self._travel_time_down_sec,
            "linked_entity_up": self._entity_up_id,
            "linked_entity_down": self._entity_down_id,
        }
        if self._entity_stop_id:
            attrs["linked_entity_stop"] = self._entity_stop_id
        if self._movement_start_utc:
             attrs["movement_start_utc"] = self._movement_start_utc.isoformat()
        if self._movement_start_pos is not None:
            attrs["movement_start_pos"] = self._movement_start_pos
        return attrs
