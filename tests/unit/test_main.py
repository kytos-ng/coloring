"""Test the Main class."""
import json
from unittest import TestCase
from unittest.mock import Mock, patch


from kytos.lib.helpers import get_test_client, get_controller_mock
from napps.amlight.coloring.main import Main


class TestMain(TestCase):
    """Test the Main class."""

    def setUp(self):
        self.server_name_url = 'http://localhost:8181/api/amlight/coloring'
        self.napp = Main(get_controller_mock())

    def test_color_to_field_dl(self):
        """Test method color_to_field.
        Fields dl_src and dl_dst."""

        color = self.napp.color_to_field(300, 'dl_src')
        self.assertEqual(color, 'ee:ee:ee:ee:01:2c')

        color = self.napp.color_to_field(300, 'dl_dst')
        self.assertEqual(color, 'ee:ee:ee:ee:01:2c')

    def test_color_to_field_nw(self):
        """Test method color_to_field.
        Fields nw_src and nw_dst."""

        color = self.napp.color_to_field(300, 'nw_src')
        self.assertEqual(color, '0.0.1.44')

        color = self.napp.color_to_field(300, 'nw_dst')
        self.assertEqual(color, '0.0.1.44')

    def test_color_to_field_others(self):
        """Test method color_to_field.
        Fields in_port, dl_vlan, tp_src and tp_dst."""
        initial_color = 300
        expected_color = initial_color & 0xffff
        color = self.napp.color_to_field(initial_color, 'in_port')
        self.assertEqual(color, expected_color)

        color = self.napp.color_to_field(initial_color, 'dl_vlan')
        self.assertEqual(color, expected_color)

        color = self.napp.color_to_field(initial_color, 'tp_src')
        self.assertEqual(color, expected_color)

        color = self.napp.color_to_field(initial_color, 'tp_dst')
        self.assertEqual(color, expected_color)

    def test_color_to_field_nw_tos(self):
        """Test method color_to_field.
        Fields nw_tos and nw_proto."""
        initial_color = 300
        expected_color = initial_color & 0xff
        color = self.napp.color_to_field(initial_color, 'nw_tos')
        self.assertEqual(color, expected_color)

        color = self.napp.color_to_field(initial_color, 'nw_proto')
        self.assertEqual(color, expected_color)

    def test_color_to_field_fail(self):
        """Test method color_to_field with invalid field name."""
        initial_color = 300
        color = self.napp.color_to_field(300, 'does_not_exit')
        self.assertEqual(color, initial_color & 0xff)

    def test_rest_settings(self):
        """Test method return_settings."""
        api = get_test_client(self.napp.controller, self.napp)
        url = f'{self.server_name_url}/settings/'
        response = api.get(url)
        json_response = json.loads(response.data)

        self.assertEqual(json_response['color_field'], "dl_src")
        self.assertEqual(json_response['coloring_interval'], 10)
        self.assertTrue("/api/kytos/flow_manager/v2/flows/" in
                        json_response['flow_manager_url'])
        self.assertTrue(json_response['topology_url']
                        .endswith("/api/kytos/topology/v3/links"))

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

        self.assertEqual(self.napp.switches, {})
        self.napp.update_colors(links)

        # Verify installed flows with colors
        self.assertTrue(len(self.napp.switches) == 2)
        self.assertEqual(
            self.napp.switches['00:00:00:00:00:00:00:01']['color'], 1)
        self.assertEqual((self.napp.switches['00:00:00:00:00:00:00:01']
                         ['flows']['00:00:00:00:00:00:00:02']['match']
                         ['dl_src']),
                         'ee:ee:ee:ee:ee:02')
        self.assertEqual((self.napp.switches['00:00:00:00:00:00:00:01']
                         ['flows']['00:00:00:00:00:00:00:02']['cookie']),
                         self.napp.get_cookie(switch1.dpid))

        self.assertEqual(
            self.napp.switches['00:00:00:00:00:00:00:02']['color'], 2)
        self.assertEqual((self.napp.switches['00:00:00:00:00:00:00:02']
                         ['flows']['00:00:00:00:00:00:00:01']['match']
                         ['dl_src']),
                         'ee:ee:ee:ee:ee:01')
        self.assertEqual((self.napp.switches['00:00:00:00:00:00:00:02']
                         ['flows']['00:00:00:00:00:00:00:01']['cookie']),
                         self.napp.get_cookie(switch2.dpid))

        # Tests that the FLOW_MANAGER_URL was called twice to insert flow.
        self.assertEqual(req_post_mock.call_count, 2)

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
        self.assertTrue(len(self.napp.switches) == 2)

        self.assertEqual(
            self.napp.switches['00:00:00:00:00:00:00:01']['color'], 1)
        self.assertEqual((self.napp.switches
                          ['00:00:00:00:00:00:00:01']['flows']), {})
        self.assertEqual(
            self.napp.switches['00:00:00:00:00:00:00:02']['color'], 2)
        self.assertEqual((self.napp.switches
                          ['00:00:00:00:00:00:00:02']['flows']), {})

    def test_rest_colors(self):
        """ Test rest call to /colors to retrieve all switches color. """
        switch1 = {'dpid': '00:00:00:00:00:00:00:01',
                   'ofp_version': '0x04',
                   'color': 300}
        self.napp.switches = {'1': switch1}

        # Call rest /colors
        api = get_test_client(self.napp.controller, self.napp)
        url = f'{self.server_name_url}/colors'
        response = api.get(url)
        json_response = json.loads(response.data)
        self.assertEqual(json_response['colors']['1']['color_field'],
                         'dl_src')
        self.assertEqual(json_response['colors']['1']['color_value'],
                         'ee:ee:ee:ee:01:2c')

    def test_rest_colors_without_switches(self):
        """ Test rest call to /colors without switches. """
        self.napp.switches = {}

        # Call rest /colors
        api = get_test_client(self.napp.controller, self.napp)
        url = f'{self.server_name_url}/colors'
        response = api.get(url)
        json_response = json.loads(response.data)

        self.assertEqual(json_response['colors'], {})

    def test_get_cookie(self) -> None:
        """test get_cookie."""
        dpid = "cc4e244b11000000"
        assert Main.get_cookie(dpid) == 0xac4e244b11000000
        dpid = "0000000000000001"
        assert Main.get_cookie(dpid) == 0xac00000000000001
