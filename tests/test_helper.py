"""Test helper functions for Dali Center integration."""
# pylint: disable=protected-access

from custom_components.dali_center.helper import find_set_differences


def test_find_set_differences_empty_lists():
    """Test find_set_differences with empty lists."""
    list1 = []
    list2 = []
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert unique1 == []
    assert unique2 == []


def test_find_set_differences_identical_lists():
    """Test find_set_differences with identical lists."""
    list1 = [{"id": "1", "name": "Device 1"}, {"id": "2", "name": "Device 2"}]
    list2 = [{"id": "1", "name": "Device 1"}, {"id": "2", "name": "Device 2"}]
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert unique1 == []
    assert unique2 == []


def test_find_set_differences_completely_different():
    """Test find_set_differences with completely different lists."""
    list1 = [{"id": "1", "name": "Device 1"}, {"id": "2", "name": "Device 2"}]
    list2 = [{"id": "3", "name": "Device 3"}, {"id": "4", "name": "Device 4"}]
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert len(unique1) == 2
    assert len(unique2) == 2
    assert unique1 == list1
    assert unique2 == list2


def test_find_set_differences_partial_overlap():
    """Test find_set_differences with partial overlap."""
    list1 = [
        {"id": "1", "name": "Device 1"},
        {"id": "2", "name": "Device 2"},
        {"id": "3", "name": "Device 3"},
    ]
    list2 = [
        {"id": "2", "name": "Device 2"},
        {"id": "3", "name": "Device 3"},
        {"id": "4", "name": "Device 4"},
    ]
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert len(unique1) == 1
    assert len(unique2) == 1
    assert unique1[0]["id"] == "1"
    assert unique2[0]["id"] == "4"


def test_find_set_differences_first_empty():
    """Test find_set_differences with first list empty."""
    list1 = []
    list2 = [{"id": "1", "name": "Device 1"}, {"id": "2", "name": "Device 2"}]
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert unique1 == []
    assert unique2 == list2


def test_find_set_differences_second_empty():
    """Test find_set_differences with second list empty."""
    list1 = [{"id": "1", "name": "Device 1"}, {"id": "2", "name": "Device 2"}]
    list2 = []
    unique1, unique2 = find_set_differences(list1, list2, "id")

    assert unique1 == list1
    assert unique2 == []


def test_find_set_differences_different_attribute():
    """Test find_set_differences with different attribute name."""
    list1 = [{"unique_id": "1", "name": "Device 1"}]
    list2 = [{"unique_id": "2", "name": "Device 2"}]
    unique1, unique2 = find_set_differences(list1, list2, "unique_id")

    assert len(unique1) == 1
    assert len(unique2) == 1
    assert unique1[0]["unique_id"] == "1"
    assert unique2[0]["unique_id"] == "2"


def test_find_set_differences_complex_objects():
    """Test find_set_differences with complex objects."""
    list1 = [
        {"unique_id": "light_1", "name": "Living Room Light", "type": "light"},
        {"unique_id": "sensor_1", "name": "Motion Sensor", "type": "sensor"},
    ]
    list2 = [
        {"unique_id": "light_1", "name": "Living Room Light", "type": "light"},
        {"unique_id": "button_1", "name": "Scene Button", "type": "button"},
    ]
    unique1, unique2 = find_set_differences(list1, list2, "unique_id")

    assert len(unique1) == 1
    assert len(unique2) == 1
    assert unique1[0]["unique_id"] == "sensor_1"
    assert unique1[0]["type"] == "sensor"
    assert unique2[0]["unique_id"] == "button_1"
    assert unique2[0]["type"] == "button"
