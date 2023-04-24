"""Test the Main class."""
from unittest.mock import Mock, patch


from kytos.lib.helpers import get_test_client, get_controller_mock
from napps.amlight.coloring.main import Main


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
                'endpoint_b': {'switch': switch2.dpid}
            },
            {
                'endpoint_a': {'switch': switch1.dpid},
                'endpoint_b': {'switch': switch1.dpid}
            }
        ]

        assert not self.napp.switches
        self.napp.update_colors(links)

        # Verify installed flows with colors
        assert len(self.napp.switches) == 2
        dpid1 = '00:00:00:00:00:00:00:01'
        dpid2 = '00:00:00:00:00:00:00:02'
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

        # Next test we verify that the napp will not search
        # switch data again, because it is already cached.
        links = [
            {
                'endpoint_a': {'switch': switch1.dpid},
                'endpoint_b': {'switch': switch1.dpid}
            }
        ]

        req_post_mock.reset_mock()
        self.napp.update_colors(links)
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
