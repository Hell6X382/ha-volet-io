# ha-volet-io

`ha-volet-io` is a custom component for Home Assistant that creates a virtual IO shutter (cover) entity. This virtual shutter can operate in two modes:

1.  **Standalone Simulated Shutter**: If not linked to an existing entity, the virtual shutter simulates movement based on configured travel times for up and down actions. It keeps track of its position and state internally.
2.  **Linked Shutter (Proxy/Mirror)**: The virtual shutter can be linked to an existing Home Assistant cover entity (e.g., a real Z-Wave or Zigbee shutter). In this mode, the virtual shutter mirrors the state and position of the linked entity. Commands sent to the virtual shutter (open, close, stop, set position) are forwarded to the linked entity. This allows you to use the virtual shutter as a proxy, potentially with different physical controls.

## Features

*   Creates a `cover` entity in Home Assistant.
*   **Standalone Mode**:
    *   Simulates shutter movement with configurable travel times.
    *   Supports open, close, stop, and set position commands.
    *   Restores its last known position on Home Assistant restart.
*   **Linked Mode**:
    *   Links to an existing Home Assistant `cover` entity.
    *   Mirrors the position and operational state (opening, closing, closed) of the linked entity.
    *   Forwards commands received by the virtual shutter to the linked entity.
    *   Physical control entities (for up, down, stop) configured for the virtual shutter will control the linked entity.

## Configuration

To add the Volet Virtuel IO to your Home Assistant, add the following to your `configuration.yaml` file:

```yaml
cover:
  - platform: volet_virtuel_io
    name: "Nom de Votre Volet Virtuel" # Optional, Default: "Volet Virtuel IO"
    entity_up: input_boolean.volet_monter_salon # Required: Entity to trigger 'open'
    entity_down: input_boolean.volet_descendre_salon # Required: Entity to trigger 'close'
    entity_stop: input_boolean.volet_stop_salon # Optional: Entity to trigger 'stop'
    travel_time_up: 25 # Optional, Default: 30 (seconds)
    travel_time_down: 23 # Optional, Default: 30 (seconds)
    initial_position: 50 # Optional, Default: 50 (0-100, position if no state restored and not linked)
    existing_shutter_entity_id: cover.salon_shutter_real # Optional
```

### Configuration Variables:

*   **`platform`**: (Required) Must be `volet_virtuel_io`.
*   **`name`**: (Optional) The name for your virtual shutter. Default: `Volet Virtuel IO`.
*   **`entity_up`**: (Required) The `entity_id` of a sensor, input_boolean, or switch that, when activated (e.g., turned 'on'), will trigger the open command.
*   **`entity_down`**: (Required) The `entity_id` of a sensor, input_boolean, or switch that, when activated, will trigger the close command.
*   **`entity_stop`**: (Optional) The `entity_id` of a sensor, input_boolean, or switch that, when activated, will trigger the stop command.
*   **`travel_time_up`**: (Optional) The time in seconds it takes for the shutter to go from fully closed (0%) to fully open (100%). Default: `30`. Only used in standalone mode.
*   **`travel_time_down`**: (Optional) The time in seconds it takes for the shutter to go from fully open (100%) to fully closed (0%). Default: `30`. Only used in standalone mode.
*   **`initial_position`**: (Optional) The position (0-100) the shutter should assume if no previous state can be restored and it's not linked to an existing shutter. Default: `50` (half open). Only used in standalone mode if no state is restored.
*   **`existing_shutter_entity_id`**: (Optional) The `entity_id` of an existing Home Assistant `cover` entity. If provided, the virtual shutter will operate in "Linked Mode," mirroring and controlling this entity. If omitted, it operates in "Standalone Mode."

### How Linked Mode Works:

When `existing_shutter_entity_id` is configured:

1.  **Initial State**: The virtual shutter will attempt to set its initial position based on the current position of the linked shutter.
2.  **State Mirroring**: Any changes to the linked shutter's position or operational state (e.g., if it's controlled manually or by other automations) will be reflected by the virtual shutter.
3.  **Command Forwarding**:
    *   If you call `cover.open_cover`, `cover.close_cover`, `cover.stop_cover`, or `cover.set_cover_position` on the virtual shutter, the command will be forwarded to the linked shutter entity.
    *   If you activate the `entity_up`, `entity_down`, or `entity_stop` control entities, these will also issue the corresponding commands to the linked shutter.
4.  **Standalone Parameters**: `travel_time_up`, `travel_time_down`, and `initial_position` are ignored when `existing_shutter_entity_id` is set, as the behavior is dictated by the linked entity.

This allows you to, for example, create a virtual shutter that uses different types of input entities (like momentary switches via `input_boolean`s) to control an existing shutter that might not natively support them, or to simply create an alternative representation of an existing shutter.
```
