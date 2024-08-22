"""Test the Main class."""
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from kytos.lib.helpers import get_controller_mock, get_test_client

from kytos.core.common import EntityStatus
from kytos.core.events import KytosEvent
from napps.amlight.coloring.main import Main


async def test_on_table_enabled():
    """Test on_table_enabled"""
    # Succesfully setting table groups
    controller = get_controller_mock()
    controller.buffers.app.aput = AsyncMock()
    napp = Main(controller)
    napp.update_switches_table = MagicMock()
    content = {"coloring": {"base": 123}}
    event = KytosEvent(name="kytos/of_multi_table.enable_table",
                       content=content)
    await napp.on_table_enabled(event)
    assert napp.table_group == content["coloring"]
    assert controller.buffers.app.aput.call_count == 1
    napp.update_switches_table.assert_called_once()

    await napp.on_table_enabled(event)
    assert controller.buffers.app.aput.call_count == 2
    napp.update_switches_table.assert_called_once()

    # Failure at setting table groups
    content = {"coloring": {"unknown": 123}}
    event = KytosEvent(name="kytos/of_multi_table.enable_table",
                       content=content)
    await napp.on_table_enabled(event)
    assert controller.buffers.app.aput.call_count == 2


class TestMain:
    """Test the Main class."""

    def setup_method(self):
        """Setup method."""
        controller = get_controller_mock()
        self.napp = Main(controller)
        self.api_client = get_test_client(controller, self.napp)
        self.base_endpoint = "amlight/coloring"

    def test_color_to_field_dl(self):
        """Test method color_to_field.
        Fields dl_src and dl_dst."""

        color = self.napp.color_to_field(300, 'dl_src')
        assert color == 'ee:ee:ee:ee:01:2c'

        color = self.napp.color_to_field(300, 'dl_dst')
        assert color == 'ee:ee:ee:ee:01:2c'

    def test_color_to_field_nw(self):
        """Test method color_to_field.
        Fields nw_src and nw_dst."""

        color = self.napp.color_to_field(300, 'nw_src')
        assert color == '0.0.1.44'

        color = self.napp.color_to_field(300, 'nw_dst')
        assert color == '0.0.1.44'

    def test_color_to_field_others(self):
        """Test method color_to_field.
        Fields in_port, dl_vlan, tp_src and tp_dst."""
        initial_color = 300
        expected_color = initial_color & 0xffff
        color = self.napp.color_to_field(initial_color, 'in_port')
        assert color == expected_color

        color = self.napp.color_to_field(initial_color, 'dl_vlan')
        assert color == expected_color

        color = self.napp.color_to_field(initial_color, 'tp_src')
        assert color == expected_color

        color = self.napp.color_to_field(initial_color, 'tp_dst')
        assert color == expected_color

    def test_color_to_field_nw_tos(self):
        """Test method color_to_field.
        Fields nw_tos and nw_proto."""
        initial_color = 300
        expected_color = initial_color & 0xff
        color = self.napp.color_to_field(initial_color, 'nw_tos')
        assert color == expected_color

        color = self.napp.color_to_field(initial_color, 'nw_proto')
        assert color == expected_color

    def test_color_to_field_fail(self):
        """Test method color_to_field with invalid field name."""
        initial_color = 300
        color = self.napp.color_to_field(300, 'does_not_exit')
        assert color == initial_color & 0xff

    async def test_rest_settings(self):
        """Test method return_settings."""
        endpoint = f"{self.base_endpoint}/settings/"
        response = await self.api_client.get(endpoint)
        assert response.status_code == 200
        json_response = response.json()

        assert json_response['color_field'] == "dl_src"
        assert json_response['coloring_interval'] == 10
        flow_manager_url = "/api/kytos/flow_manager/v2/flows/"
        assert flow_manager_url in json_response['flow_manager_url']
        topology_url = json_response['topology_url']
        assert topology_url.endswith("/api/kytos/topology/v3/links")

    # pylint: disable=too-many-statements
    @patch('requests.post')
    def test_update_colors(self, req_post_mock):
        """Test method update_colors."""
        switch1 = Mock()
        switch1.dpid = '00:00:00:00:00:00:00:01'
        switch1.ofp_version = '0x04'
        switch2 = Mock()
        switch2.dpid = '00:00:00:00:00:00:00:02'
        switch2.ofp_version = '0x04'

        self.napp.controller.switches = {'1': switch1, '2': switch2}

        def switch_by_dpid(dpid):
            if dpid == '00:00:00:00:00:00:00:01':
                return switch1
            if dpid == '00:00:00:00:00:00:00:02':
                return switch2
            return None
        self.napp.controller.get_switch_by_dpid = \
            Mock(side_effect=switch_by_dpid)

        links = [
            {
                'endpoint_a': {'switch': switch1.dpid},
                'endpoint_b': {'switch': switch2.dpid},
                'enabled': True
            },
            {
                'endpoint_a': {'switch': switch1.dpid},
                'endpoint_b': {'switch': switch1.dpid},
                'enabled': True
            }
        ]

        assert not self.napp.switches

        dpid1 = '00:00:00:00:00:00:00:01'
        dpid2 = '00:00:00:00:00:00:00:02'

        # Verify no switches with switches DOWN and disabled
        switch1.status = EntityStatus.DOWN
        switch2.status = EntityStatus.DOWN
        switch1.is_enabled = lambda: False
        switch2.is_enabled = lambda: False
        links[0]['enabled'] = False
        links[1]['enabled'] = False

        self.napp.update_colors(links)
        assert not self.napp.switches

        # Verify installed flows with colors
        switch1.status = EntityStatus.UP
        switch2.status = EntityStatus.UP
        switch1.is_enabled = lambda: True
        switch2.is_enabled = lambda: True
        links[0]['enabled'] = True
        links[1]['enabled'] = True
        self.napp.update_colors(links)
        sw1 = self.napp.switches[dpid1]
        sw2 = self.napp.switches[dpid2]

        assert sw1['color'] == 1
        assert sw1['flows'][dpid2]['match']['dl_src'] == 'ee:ee:ee:ee:ee:02'
        cookie = self.napp.get_cookie(switch1.dpid)
        assert sw1['flows'][dpid2]['cookie'] == cookie

        assert sw2['color'] == 2
        assert sw2['flows'][dpid1]['match']['dl_src'] == 'ee:ee:ee:ee:ee:01'
        cookie = self.napp.get_cookie(switch2.dpid)
        assert sw2['flows'][dpid1]['cookie'] == cookie

        # Tests that the FLOW_MANAGER_URL was called twice to insert flow.
        assert req_post_mock.call_count == 2

        # Verify switches with no neighbors, flows cleanup is performed
        # by handle_link_disabled()
        switch1.status = EntityStatus.DOWN
        switch2.status = EntityStatus.DOWN
        switch1.is_enabled = lambda: False
        switch2.is_enabled = lambda: False
        links[0]['enabled'] = False
        links[1]['enabled'] = False

        self.napp.update_colors(links)

        assert len(self.napp.switches) == 2
        sw1 = self.napp.switches[dpid1]
        sw2 = self.napp.switches[dpid2]
        assert not sw1['neighbors']
        assert not sw2['neighbors']

        # Next test we verify that the napp will not search
        # switch data again, because it is already cached.
        links2 = [
            {
                'endpoint_a': {'switch': switch1.dpid},
                'endpoint_b': {'switch': switch1.dpid}
            }
        ]

        req_post_mock.reset_mock()
        self.napp.update_colors(links2)
        req_post_mock.assert_not_called()

    def test_update_colors_without_links(self):
        """Test method update_colors without links."""
        switch1 = Mock()
        switch1.dpid = '00:00:00:00:00:00:00:01'
        switch1.ofp_version = '0x04'
        switch2 = Mock()
        switch2.dpid = '00:00:00:00:00:00:00:02'
        switch2.ofp_version = '0x04'

        self.napp.controller.switches = {'1': switch1, '2': switch2}

        def switch_by_dpid(dpid):
            if dpid == '00:00:00:00:00:00:00:01':
                return switch1
            if dpid == '00:00:00:00:00:00:00:02':
                return switch2
            return None
        self.napp.controller.get_switch_by_dpid = \
            Mock(side_effect=switch_by_dpid)

        self.napp.update_colors([])

        # Verify installed flows with colors
        assert len(self.napp.switches) == 2

        dpid1 = '00:00:00:00:00:00:00:01'
        dpid2 = '00:00:00:00:00:00:00:02'
        sw1 = self.napp.switches[dpid1]
        sw2 = self.napp.switches[dpid2]

        assert sw1['color'] == 1
        assert sw1['flows'] == {}
        assert sw2['color'] == 2
        assert sw2['flows'] == {}

    async def test_rest_colors(self):
        """ Test rest call to /colors to retrieve all switches color. """
        switch1 = {'dpid': '00:00:00:00:00:00:00:01',
                   'ofp_version': '0x04',
                   'color': 300}
        self.napp.switches = {'1': switch1}

        endpoint = f"{self.base_endpoint}/colors"
        response = await self.api_client.get(endpoint)
        assert response.status_code == 200

        json_response = response.json()
        assert json_response['colors']['1']['color_field'] == 'dl_src'
        color_value = json_response['colors']['1']['color_value']
        assert color_value == 'ee:ee:ee:ee:01:2c'

    async def test_rest_colors_without_switches(self):
        """ Test rest call to /colors without switches. """
        self.napp.switches = {}

        endpoint = f"{self.base_endpoint}/colors"
        response = await self.api_client.get(endpoint)
        assert response.status_code == 200
        assert response.json()['colors'] == {}

    def test_get_cookie(self) -> None:
        """test get_cookie."""
        dpid = "cc4e244b11000000"
        assert Main.get_cookie(dpid) == 0xac4e244b11000000
        dpid = "0000000000000001"
        assert Main.get_cookie(dpid) == 0xac00000000000001

    def test_set_flow_table_group_owner(self):
        """Test set_flow_table_group_owner"""
        self.napp.table_group = {"base": 2}
        flow = {}
        self.napp.set_flow_table_group_owner(flow, "base")
        assert "table_group" in flow
        assert "owner" in flow
        assert flow["table_id"] == 2

    @patch('napps.amlight.coloring.main.log')
    def test_handle_switch_disabled(self, mock_log):
        """Test handle_switch_disabled"""
        dpid = '00:00:00:00:00:00:00:01'
        self.napp.switches = {'00:00:00:00:00:00:00:01': {
            'color': 1,
            'neighbors': set(),
            'flows': {}
        }}
        self.napp.handle_switch_disabled(dpid)
        assert not self.napp.switches

        self.napp.switches = {'00:00:00:00:00:00:00:01': {
            'color': 1,
            'neighbors': {'00:00:00:00:00:00:00:02'},
            'flows': {}
        }}
        self.napp.handle_switch_disabled(dpid)
        assert mock_log.error.call_count == 1

        self.napp.handle_switch_disabled("mock_switch")
        assert mock_log.error.call_count == 2

    @patch('napps.amlight.coloring.main.Main._remove_flow_mods')
    def test_handle_link_disabled(self, mock_remove):
        """Test handle_link_disabled"""
        self.napp.switches = {
            '00:00:00:00:00:00:00:01': {
                'color': 1,
                'neighbords': {'00:00:00:00:00:00:00:02'},
                'flows': {
                    '00:00:00:00:00:00:00:02': {
                        'match': {'dl_src': 'ee:ee:ee:ee:ee:01'},
                        'table_id': 0
                    }
                }
            },
            '00:00:00:00:00:00:00:02': {
                'color': 2,
                'neighbords': {'00:00:00:00:00:00:00:01'},
                'flows': {
                    '00:00:00:00:00:00:00:01': {
                        'match': {'dl_src': 'ee:ee:ee:ee:ee:02'},
                        'table_id': 0
                    }
                }
            }
        }
        link = Mock()
        link.endpoint_a.switch.dpid = '00:00:00:00:00:00:00:01'
        link.endpoint_b.switch.dpid = '00:00:00:00:00:00:00:02'
        self.napp.handle_link_disabled(link)
        assert not self.napp.switches['00:00:00:00:00:00:00:01']['flows']
        assert not self.napp.switches['00:00:00:00:00:00:00:02']['flows']
        assert mock_remove.call_count == 1

        link.endpoint_b.switch.dpid = '00:00:00:00:00:00:00:01'
        self.napp.handle_link_disabled(link)
        assert mock_remove.call_count == 1

    # pylint: disable=protected-access
    def test_remove_flow_mods(self):
        """Test _remove_flow_mods"""
        flows = {
            "00:01": [{
                'match': {'dl_src': 'ee:ee:ee:ee:ee:02'},
                'table_id': 0
            }]
        }
        self.napp._remove_flow_mods(flows)
        args = self.napp.controller.buffers.app.put.call_args[0][0]
        assert args.name == "kytos.flow_manager.flows.delete"
        assert args.content['flow_dict']['flows'] == flows['00:01']
        assert self.napp.controller.buffers.app.put.call_count == 1

    def test_update_switches_table(self):
        """Test update_switches_table"""
        sw1 = '00:00:00:00:00:00:00:01'
        sw2 = '00:00:00:00:00:00:00:02'
        sw3 = '00:00:00:00:00:00:00:03'
        switches = {sw1: {
            'color': 1,
            'neighbors': {sw2, sw3},
            'flows': {
                sw3: {'table_id': 0, 'table_group': 'base'},
                sw2: {'table_id': 0, 'table_group': 'mock'}
            }
        }}
        self.napp.switches = switches
        self.napp.table_group = {'base': 2, 'mock': 5}
        self.napp.update_switches_table()
        flows = switches[sw1]['flows']
        assert flows[sw3]['table_id'] == self.napp.table_group['base']
        assert flows[sw2]['table_id'] == self.napp.table_group['mock']
