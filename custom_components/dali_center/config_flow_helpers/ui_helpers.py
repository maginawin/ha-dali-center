"""UI formatting and display helpers for config flow."""

from typing import Any, Callable

from ..helper import find_set_differences



class UIFormattingHelper:
    """Helper class for UI formatting and display logic."""

    @staticmethod
    def format_discovery_summary(
        discovered_entities: dict[str, Any],
        refresh_devices: bool,
        refresh_groups: bool,
        refresh_scenes: bool
    ) -> str:
        """Format a summary of discovered entities."""
        entity_types = [
            ("devices", refresh_devices),
            ("groups", refresh_groups),
            ("scenes", refresh_scenes)
        ]

        summary: list[str] = []
        for entity_type, should_refresh in entity_types:
            if should_refresh and entity_type in discovered_entities:
                total = len(discovered_entities[entity_type])
                summary.append(f"Discovered {entity_type.title()}: {total}")

        return "\n".join(summary) if summary else "No entities discovered"

    @staticmethod
    def format_refresh_results(refresh_results: dict[str, Any]) -> str:
        """Format refresh results for display."""
        if not refresh_results:
            return "No items refreshed"

        result_parts: list[str] = []

        # Define entity types and their formatters
        def format_group(g: dict[str, Any]) -> str:
            channel = g.get("channel", "N/A")
            group_id = g.get("id", "N/A")
            return f"Channel: {channel}, Group: {group_id}"

        def format_scene(s: dict[str, Any]) -> str:
            channel = s.get("channel", "N/A")
            scene_id = s.get("id", "N/A")
            return f"Channel: {channel}, Scene: {scene_id}"

        entity_configs: list[tuple[
            str, str, str | Callable[[dict[str, Any]], str]
        ]] = [
            ("devices", "name", "unique_id"),
            ("groups", "name", format_group),
            ("scenes", "name", format_scene),
        ]

        for entity_type, name_key, id_formatter in entity_configs:
            count_key = f"{entity_type}_count"
            if count_key in refresh_results:
                result_parts.append(
                    f"Total {entity_type.title()}: {
                        refresh_results[count_key]
                    }"
                )
                details = UIFormattingHelper._format_added_removed(
                    refresh_results, entity_type, name_key, id_formatter
                )
                if details:
                    result_parts.append(details)
                result_parts.append("")  # Empty line

        return "\n".join(result_parts).strip() or "No items refreshed"

    @staticmethod
    def _format_added_removed(
        results: dict[str, Any], prefix: str, name_key: str,
        id_formatter: str | Callable[[dict[str, Any]], str]
    ) -> str:
        """Format added and removed items."""
        def format_items(items: list[Any], action: str) -> list[str]:
            if not items:
                return [f"No {prefix} {action}"]

            lines = [f"{action.title()} {prefix.title()} ({len(items)}):"]
            for item in items:
                id_str = (
                    id_formatter(item) if callable(id_formatter)
                    else f"ID: {item.get(id_formatter, "N/A")}"
                )
                lines.append(f"  - {item.get(name_key, "Unnamed")} ({id_str})")
            lines.append("")
            return lines

        message_parts: list[str] = []
        message_parts.extend(format_items(
            results.get(f"{prefix}_added", []), "added"))
        message_parts.extend(format_items(
            results.get(f"{prefix}_removed", []), "removed"))

        return "\n".join(message_parts)

    @staticmethod
    def calculate_entity_differences(
        selected: dict[str, Any],
        current_data: dict[str, Any],
        refresh_devices: bool,
        refresh_groups: bool,
        refresh_scenes: bool
    ) -> dict[str, Any]:
        """Calculate differences between selected and current entities."""
        refresh_results: dict[str, Any] = {}

        # Process devices
        if refresh_devices and "devices" in selected:
            added, removed = find_set_differences(
                selected["devices"],
                current_data.get("devices", []),
                "unique_id"
            )
            refresh_results["devices_added"] = added
            refresh_results["devices_removed"] = removed
            refresh_results["devices_count"] = len(selected["devices"])

        # Process groups
        if refresh_groups and "groups" in selected:
            added, removed = find_set_differences(
                selected["groups"],
                current_data.get("groups", []),
                "unique_id"
            )
            refresh_results["groups_added"] = added
            refresh_results["groups_removed"] = removed
            refresh_results["groups_count"] = len(selected["groups"])

        # Process scenes
        if refresh_scenes and "scenes" in selected:
            added, removed = find_set_differences(
                selected["scenes"],
                current_data.get("scenes", []),
                "unique_id"
            )
            refresh_results["scenes_added"] = added
            refresh_results["scenes_removed"] = removed
            refresh_results["scenes_count"] = len(selected["scenes"])

        return refresh_results

    @staticmethod
    def get_discovery_instructions() -> str:
        """Get gateway discovery instructions."""
        return (
            "## DALI Gateway Discovery\n\n"
            "**Two-step process:**\n\n"
            "1. **Click SUBMIT** to start discovery "
            "(searches for up to 3 minutes)\n"
            "2. **Short press the RESET button** on your DALI "
            "gateway device **ONCE**\n\n"
            "The gateway will respond immediately "
            "after the button press.\n"
            "Ensure the gateway is powered and on the same network."
        )

    @staticmethod
    def get_discovery_failed_message() -> str:
        """Get discovery failed message."""
        return (
            "## Discovery Failed\n\n"
            "Discovery timed out after **3 minutes**.\n\n"
            "Please ensure:\n"
            "- Gateway is **powered** and on "
            " **same network**\n"
            "- **RESET button was pressed** during "
            "discovery\n\n"
            "Click Submit to **retry**."
        )

    @staticmethod
    def get_no_gateways_message() -> str:
        """Get no gateways found message."""
        return (
            "## No Gateways Found\n\n"
            "Please check:\n"
            "- Gateway is **powered** and on **same network**\n"
            "- **RESET button was pressed** during discovery\n"
            "- Gateway **not already configured** elsewhere\n\n"
            "Click Submit to **retry**."
        )

    @staticmethod
    def get_success_message(gateway_count: int) -> str:
        """Get gateway selection success message."""
        return f"## Success!\n\nFound **{gateway_count} " \
            "gateway(s)**. Select one to configure:"

    @staticmethod
    def format_gateway_options(gateways: list[Any]) -> dict[str, str]:
        """Format gateway selection options."""
        return {
            gateway["gw_sn"]: f"{gateway["name"]} "
            f"({gateway["gw_sn"]})"
            for gateway in gateways
        }
