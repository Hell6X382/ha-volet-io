"""Platform for Virtual IO Cover integration."""
import logging
import asyncio
from datetime import timedelta, datetime, timezone

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA, # Renommé pour éviter conflit
    CoverEntity,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    DEVICE_CLASS_SHUTTER,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_OPENING,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_CLOSED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

# --- Configuration constants ---
CONF_ENTITY_UP = "entity_up"
CONF_ENTITY_DOWN = "entity_down"
CONF_ENTITY_STOP = "entity_stop" # Optional physical stop button
CONF_TRAVEL_TIME_UP = "travel_time_up"
CONF_TRAVEL_TIME_DOWN = "travel_time_down"
CONF_INITIAL_POSITION = "initial_position" # Optional: 0 (closed) to 100 (open)

DEFAULT_TRAVEL_TIME = 25  # seconds
DEFAULT_NAME = "Volet Virtuel IO"
DEFAULT_INITIAL_POSITION = 50 # Default to half open if not restored and not specified

# --- Platform Schema for configuration.yaml ---
PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITY_UP): cv.entity_id,
        vol.Required(CONF_ENTITY_DOWN): cv.entity_id,
        vol.Optional(CONF_ENTITY_STOP): cv.entity_id,
        vol.Optional(
            CONF_TRAVEL_TIME_UP, default=DEFAULT_TRAVEL_TIME
        ): cv.positive_int,
        vol.Optional(
            CONF_TRAVEL_TIME_DOWN, default=DEFAULT_TRAVEL_TIME
        ): cv.positive_int,
        vol.Optional(CONF_INITIAL_POSITION, default=DEFAULT_INITIAL_POSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Virtual IO cover platform from YAML."""
    name = config.get(CONF_NAME)
    entity_up_id = config.get(CONF_ENTITY_UP)
    entity_down_id = config.get(CONF_ENTITY_DOWN)
    entity_stop_id = config.get(CONF_ENTITY_STOP)
    travel_time_up = config.get(CONF_TRAVEL_TIME_UP)
    travel_time_down = config.get(CONF_TRAVEL_TIME_DOWN)
    initial_position = config.get(CONF_INITIAL_POSITION)

    virtual_cover = VirtualIOCover(
        hass,
        name,
        entity_up_id,
        entity_down_id,
        entity_stop_id,
        travel_time_up,
        travel_time_down,
        initial_position
    )
    async_add_entities([virtual_cover])


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
        self._entity_stop_id = entity_stop_id # May be None

        self._travel_time_up_seconds = travel_time_up
        self._travel_time_down_seconds = travel_time_down
        self._initial_position_config = initial_position # Used if no restored state

        self._current_position = None  # Current position (0-100), None until restored or set
        self._target_position = None # Target position during movement

        self._is_opening = False
        self._is_closing = False

        self._movement_start_time = None # Timestamp when current movement started
        self._movement_task = None       # asyncio.Task for current movement simulation
        self._movement_start_position = None # Position when the movement started

        # Attributes for Home Assistant
        self._attr_unique_id = f"volet_virtuel_io_{name.lower().replace(' ', '_')}"
        self._attr_device_class = DEVICE_CLASS_SHUTTER
        self._attr_supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        )

    async def async_added_to_hass(self):
        """Call when entity about to be added to HASS."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes.get(ATTR_POSITION) is not None:
            self._current_position = int(last_state.attributes.get(ATTR_POSITION))
            _LOGGER.debug(f"[{self.name}] Restored position to {self._current_position}")
        else:
            self._current_position = self._initial_position_config
            _LOGGER.debug(f"[{self.name}] No restored state, set to initial config position {self._current_position}")

        self._target_position = self._current_position # Ensure target matches current initially
        self.async_write_ha_state()

        # Listen to state changes of control entities
        entities_to_watch = [self._entity_up_id, self._entity_down_id]
        if self._entity_stop_id:
            entities_to_watch.append(self._entity_stop_id)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, entities_to_watch, self._async_control_entity_changed
            )
        )

    @callback
    def _async_control_entity_changed(self, event):
        """Handle state changes of linked control entities."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        # old_state = event.data.get("old_state") # Not used for now

        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(f"[{self.name}] Control entity {entity_id} became unavailable/unknown.")
            return

        _LOGGER.debug(f"[{self.name}] Control entity {entity_id} changed to {new_state.state}")

        # We assume 'on' means "start action" and 'off' means "stop action" for UP/DOWN entities
        # This matches typical input_boolean behavior used as momentary switches.
        if entity_id == self._entity_up_id:
            if new_state.state == "on" and not self._is_opening:
                _LOGGER.info(f"[{self.name}] Physical UP activated. Opening.")
                self.hass.async_create_task(self.async_open_cover())
            elif new_state.state == "off" and self._is_opening:
                _LOGGER.info(f"[{self.name}] Physical UP deactivated while opening. Stopping.")
                self.hass.async_create_task(self.async_stop_cover())

        elif entity_id == self._entity_down_id:
            if new_state.state == "on" and not self._is_closing:
                _LOGGER.info(f"[{self.name}] Physical DOWN activated. Closing.")
                self.hass.async_create_task(self.async_close_cover())
            elif new_state.state == "off" and self._is_closing:
                _LOGGER.info(f"[{self.name}] Physical DOWN deactivated while closing. Stopping.")
                self.hass.async_create_task(self.async_stop_cover())

        elif self._entity_stop_id and entity_id == self._entity_stop_id:
            if new_state.state == "on": # Assuming stop is also a momentary action
                _LOGGER.info(f"[{self.name}] Physical STOP activated. Stopping.")
                self.hass.async_create_task(self.async_stop_cover())
                # Optional: if stop entity is an input_boolean, turn it off
                # self.hass.async_create_task(
                #     self.hass.services.async_call('input_boolean', 'turn_off', {'entity_id': self._entity_stop_id})
                # )

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def current_cover_position(self):
        """Return current position of cover (0-100)."""
        return self._current_position

    @property
    def is_opening(self):
        """Return if the cover is currently opening."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is currently closing."""
        return self._is_closing

    @property
    def is_closed(self):
        """Return if the cover is fully closed."""
        if self._current_position is None: # Not yet determined
            return None
        return self._current_position == 0

    async def _async_start_movement(self, target_position):
        """Initiate a movement towards the target position."""
        if self._movement_task:
            self._movement_task.cancel()
            self._update_current_position() # Update based on partial movement
            self._movement_task = None

        self._target_position = target_position
        self._movement_start_time = datetime.now(timezone.utc)
        self._movement_start_position = self._current_position # Position at the very start of this new movement

        if self._target_position > self._current_position:
            self._is_opening = True
            self._is_closing = False
            total_travel_time_seconds = self._travel_time_up_seconds
            distance_to_travel = self._target_position - self._current_position
        elif self._target_position < self._current_position:
            self._is_opening = False
            self._is_closing = True
            total_travel_time_seconds = self._travel_time_down_seconds
            distance_to_travel = self._current_position - self._target_position
        else: # Already at target
            _LOGGER.debug(f"[{self.name}] Already at target position {self._target_position}.")
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
            return

        if total_travel_time_seconds == 0 or distance_to_travel == 0:
            duration_for_this_movement = 0
        else:
            # Duration = (distance_to_target_percent / 100_percent) * total_time_for_100_percent
            duration_for_this_movement = (distance_to_travel / 100.0) * total_travel_time_seconds

        duration_for_this_movement = max(0, duration_for_this_movement) # Ensure non-negative

        _LOGGER.info(
            f"[{self.name}] Starting movement from {self._current_position} to {self._target_position}. "
            f"Travel time for this segment: {duration_for_this_movement:.2f}s."
        )
        self.async_write_ha_state() # Update is_opening/is_closing state

        if duration_for_this_movement == 0:
            self._current_position = self._target_position
            self._is_opening = False
            self._is_closing = False
            self._movement_start_time = None
            self._movement_start_position = None
            _LOGGER.info(f"[{self.name}] Movement instantaneous. Reached position {self._current_position}.")
            self.async_write_ha_state()
        else:
            self._movement_task = self.hass.loop.create_task(
                self._async_process_movement(duration_for_this_movement)
            )

    async def _async_process_movement(self, duration):
        """Simulate the cover movement over a given duration."""
        try:
            await asyncio.sleep(duration)
            # Movement completed naturally
            self._current_position = self._target_position
            _LOGGER.info(f"[{self.name}] Movement finished. Reached position {self._current_position}.")
        except asyncio.CancelledError:
            # Movement was cancelled (e.g., by stop_cover or new set_position)
            _LOGGER.info(f"[{self.name}] Movement cancelled.")
            self._update_current_position() # Calculate position at time of cancellation
            # Raiser la CancelledError pour que le _movement_task soit bien nettoyé
            raise
        finally:
            self._is_opening = False
            self._is_closing = False
            self._movement_start_time = None
            self._movement_start_position = None
            self._movement_task = None # Clear the task reference
            self.async_write_ha_state()


    def _update_current_position(self):
        """Update position based on elapsed time since movement started."""
        if not self._movement_start_time or self._movement_start_position is None:
            # No active movement or start position not set
            return

        elapsed_time_seconds = (datetime.now(timezone.utc) - self._movement_start_time).total_seconds()

        start_pos = self._movement_start_position

        if self._is_opening:
            travel_time_total_seconds = self._travel_time_up_seconds
            if travel_time_total_seconds > 0:
                # Percentage moved = (elapsed_time / total_time_for_100_percent) * 100
                percentage_moved = (elapsed_time_seconds / travel_time_total_seconds) * 100
                new_pos = start_pos + percentage_moved
                self._current_position = min(max(0, new_pos), 100) # Clamp between 0 and 100
                self._current_position = min(self._current_position, self._target_position) # Don't overshoot target
            # else: position doesn't change if travel time is zero (should have been handled by duration=0)
        elif self._is_closing:
            travel_time_total_seconds = self._travel_time_down_seconds
            if travel_time_total_seconds > 0:
                percentage_moved = (elapsed_time_seconds / travel_time_total_seconds) * 100
                new_pos = start_pos - percentage_moved
                self._current_position = min(max(0, new_pos), 100) # Clamp
                self._current_position = max(self._current_position, self._target_position) # Don't overshoot target

        self._current_position = round(self._current_position)
        _LOGGER.debug(f"[{self.name}] Position updated to {self._current_position} after {elapsed_time_seconds:.2f}s.")


    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug(f"[{self.name}] Command: Open Cover.")
        if self._current_position == 100 and not self._is_opening:
            _LOGGER.debug(f"[{self.name}] Already fully open.")
            return
        await self._async_start_movement(100)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.debug(f"[{self.name}] Command: Close Cover.")
        if self._current_position == 0 and not self._is_closing:
            _LOGGER.debug(f"[{self.name}] Already fully closed.")
            return
        await self._async_start_movement(0)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover movement."""
        _LOGGER.debug(f"[{self.name}] Command: Stop Cover.")
        if self._movement_task:
            self._movement_task.cancel() # This will trigger _update_current_position via _async_process_movement's finally block
            self._movement_task = None # Ensure it's cleared here too
            # Position update and state write is handled by _async_process_movement's cancellation path
        else: # Not moving, but ensure flags are correct
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
        _LOGGER.info(f"[{self.name}] Stopped at position {self._current_position}")


    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = int(kwargs[ATTR_POSITION])
        _LOGGER.debug(f"[{self.name}] Command: Set Cover Position to {position}.")
        if position == self._current_position and not (self._is_opening or self._is_closing):
             _LOGGER.debug(f"[{self.name}] Already at position {position}.")
             return
        await self._async_start_movement(position)

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {
            "target_position": self._target_position if self._target_position is not None else "N/A",
            "travel_time_up": self._travel_time_up_seconds,
            "travel_time_down": self._travel_time_down_seconds,
            "linked_entity_up": self._entity_up_id,
            "linked_entity_down": self._entity_down_id,
        }
        if self._entity_stop_id:
            attrs["linked_entity_stop"] = self._entity_stop_id
        if self._movement_start_time:
             attrs["movement_start_utc"] = self._movement_start_time.isoformat()
        return attrs
