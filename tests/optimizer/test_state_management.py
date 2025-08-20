"""Tests for the state_management module."""

from unittest.mock import MagicMock
from uuid import UUID

import pytest

from energy_assistant.devices import StateId, StatesRepository
from energy_assistant.devices.home import Home
from energy_assistant.devices.homeassistant import HOMEASSISTANT_CHANNEL
from energy_assistant.optimizer.config import EmhassConfig
from energy_assistant.optimizer.state_management import StateManager


@pytest.fixture
def mock_config() -> EmhassConfig:
    """Create a mock EmhassConfig for testing."""
    config = MagicMock(spec=EmhassConfig)
    config.power_no_var_loads_id = "sensor.power_no_var_loads"
    config.hass_entity_prefix = "em"
    return config


@pytest.fixture
def state_manager(mock_config: EmhassConfig) -> StateManager:
    """Create a StateManager instance for testing."""
    return StateManager(mock_config)


@pytest.fixture
def mock_home() -> Home:
    """Create a mock Home for testing."""
    home = MagicMock(spec=Home)
    home.home_consumption_power = 1500.0
    home.self_sufficiency = 0.75
    home.self_consumption = 0.65
    
    # Create mock devices
    device1 = MagicMock()
    device1.power_controllable = True
    device1.power = 200.0
    
    device2 = MagicMock()
    device2.power_controllable = False
    device2.power = 100.0
    
    device3 = MagicMock()
    device3.power_controllable = True
    device3.power = 300.0
    
    home.devices = [device1, device2, device3]
    return home


@pytest.fixture
def mock_state_repository() -> StatesRepository:
    """Create a mock StatesRepository for testing."""
    return MagicMock(spec=StatesRepository)


@pytest.fixture
def mock_no_var_loads_buffer() -> MagicMock:
    """Create a mock no var loads buffer for testing."""
    return MagicMock()


@pytest.fixture
def mock_get_forecast_value_func() -> MagicMock:
    """Create a mock forecast value function for testing."""
    mock_func = MagicMock()
    mock_func.side_effect = lambda key: {
        "P_PV": 800.0,
        "P_Load": 1200.0,
    }.get(key, 0.0)
    return mock_func


class TestStateManager:
    """Test the StateManager class."""

    def test_init(self, state_manager: StateManager, mock_config: EmhassConfig) -> None:
        """Test StateManager initialization."""
        assert state_manager._config == mock_config
        assert state_manager._optimzed_devices == []

    def test_set_optimized_devices(self, state_manager: StateManager) -> None:
        """Test setting optimized devices."""
        devices = ["device1", "device2"]
        state_manager.set_optimized_devices(devices)
        assert state_manager._optimzed_devices == devices

    def test_update_repository_states_power_calculation(
        self,
        state_manager: StateManager,
        mock_home: Home,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test power calculation in update_repository_states."""
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Expected power calculation: home_consumption (1500) - controllable devices (200 + 300) = 1000
        expected_power = 1000.0
        mock_no_var_loads_buffer.add_data_point.assert_called_once_with(expected_power)

    def test_update_repository_states_power_minimum_zero(
        self,
        state_manager: StateManager,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test that power calculation doesn't go below zero."""
        # Create a home where controllable devices exceed home consumption
        mock_home = MagicMock(spec=Home)
        mock_home.home_consumption_power = 500.0
        mock_home.self_sufficiency = 0.75
        mock_home.self_consumption = 0.65
        
        device1 = MagicMock()
        device1.power_controllable = True
        device1.power = 400.0
        
        device2 = MagicMock()
        device2.power_controllable = True
        device2.power = 300.0
        
        mock_home.devices = [device1, device2]
        
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Power should be clamped to 0
        mock_no_var_loads_buffer.add_data_point.assert_called_once_with(0.0)

    def test_update_repository_states_sets_all_required_states(
        self,
        state_manager: StateManager,
        mock_home: Home,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
        mock_config: EmhassConfig,
    ) -> None:
        """Test that all required states are set."""
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Verify all expected states are set
        expected_calls = [
            # Power no var loads
            (
                StateId(id="sensor.power_no_var_loads", channel=HOMEASSISTANT_CHANNEL),
                "1000.0",
                {
                    "unit_of_measurement": "W",
                    "state_class": "measurement", 
                    "device_class": "power",
                }
            ),
            # PV forecast
            (
                StateId(id="sensor.em_p_pv", channel=HOMEASSISTANT_CHANNEL),
                "800.0",
                {
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "device_class": "power",
                }
            ),
            # Consumption forecast
            (
                StateId(id="sensor.em_p_consumption", channel=HOMEASSISTANT_CHANNEL),
                "1200.0",
                {
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "device_class": "power",
                }
            ),
            # Home consumption
            (
                StateId(id="sensor.em_home_consumption", channel=HOMEASSISTANT_CHANNEL),
                "1500.0",
                {
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "device_class": "power",
                }
            ),
            # Self sufficiency
            (
                StateId(id="sensor.em_self_sufficiency", channel=HOMEASSISTANT_CHANNEL),
                "75",
                {
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                }
            ),
            # Self consumption
            (
                StateId(id="sensor.em_self_consumption", channel=HOMEASSISTANT_CHANNEL),
                "65",
                {
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                }
            ),
        ]
        
        # Verify the number of calls
        assert mock_state_repository.set_state.call_count == len(expected_calls)
        
        # Verify each call
        for i, expected_call in enumerate(expected_calls):
            actual_call = mock_state_repository.set_state.call_args_list[i]
            state_id, value, attributes = actual_call[0]
            
            expected_state_id, expected_value, expected_attributes = expected_call
            
            assert state_id.id == expected_state_id.id
            assert state_id.channel == expected_state_id.channel
            assert value == expected_value
            assert attributes == expected_attributes

    def test_update_repository_states_with_different_prefix(
        self,
        mock_config: EmhassConfig,
        mock_home: Home,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test state updates with different entity prefix."""
        mock_config.hass_entity_prefix = "custom"
        state_manager = StateManager(mock_config)
        
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Check that custom prefix is used
        call_args_list = mock_state_repository.set_state.call_args_list
        
        # Find calls with the custom prefix
        pv_call = next(call for call in call_args_list if call[0][0].id == "sensor.custom_p_pv")
        consumption_call = next(call for call in call_args_list if call[0][0].id == "sensor.custom_p_consumption")
        home_consumption_call = next(call for call in call_args_list if call[0][0].id == "sensor.custom_home_consumption")
        
        assert pv_call is not None
        assert consumption_call is not None
        assert home_consumption_call is not None

    def test_update_repository_states_only_non_controllable_devices(
        self,
        state_manager: StateManager,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test power calculation when all devices are non-controllable."""
        # Create a home with only non-controllable devices
        mock_home = MagicMock(spec=Home)
        mock_home.home_consumption_power = 1500.0
        mock_home.self_sufficiency = 0.75
        mock_home.self_consumption = 0.65
        
        device1 = MagicMock()
        device1.power_controllable = False
        device1.power = 200.0
        
        device2 = MagicMock()
        device2.power_controllable = False
        device2.power = 300.0
        
        mock_home.devices = [device1, device2]
        
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Power should equal home consumption since no controllable devices to subtract
        mock_no_var_loads_buffer.add_data_point.assert_called_once_with(1500.0)

    def test_update_repository_states_no_devices(
        self,
        state_manager: StateManager,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test power calculation when home has no devices."""
        mock_home = MagicMock(spec=Home)
        mock_home.home_consumption_power = 1500.0
        mock_home.self_sufficiency = 0.75
        mock_home.self_consumption = 0.65
        mock_home.devices = []
        
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Power should equal home consumption since no devices to subtract
        mock_no_var_loads_buffer.add_data_point.assert_called_once_with(1500.0)

    def test_self_sufficiency_and_consumption_rounding(
        self,
        state_manager: StateManager,
        mock_state_repository: StatesRepository,
        mock_no_var_loads_buffer: MagicMock,
        mock_get_forecast_value_func: MagicMock,
    ) -> None:
        """Test that self sufficiency and consumption are properly rounded."""
        mock_home = MagicMock(spec=Home)
        mock_home.home_consumption_power = 1000.0
        mock_home.self_sufficiency = 0.754  # Should round to 75
        mock_home.self_consumption = 0.656  # Should round to 66
        mock_home.devices = []
        
        state_manager.update_repository_states(
            mock_home,
            mock_state_repository,
            mock_no_var_loads_buffer,
            mock_get_forecast_value_func,
        )
        
        # Find the self sufficiency and self consumption calls
        call_args_list = mock_state_repository.set_state.call_args_list
        
        self_sufficiency_call = next(call for call in call_args_list if "self_sufficiency" in call[0][0].id)
        self_consumption_call = next(call for call in call_args_list if "self_consumption" in call[0][0].id)
        
        assert self_sufficiency_call[0][1] == "75"  # 0.754 * 100 rounded = 75
        assert self_consumption_call[0][1] == "66"   # 0.656 * 100 rounded = 66