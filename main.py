"""Main module of amlight/coloring Kytos Network Application.

NApp to color a network topology
"""
# Check for import order disabled in pylint due to conflict
# with isort.
# pylint: disable=wrong-import-order
# isort:skip_file
import struct
from threading import Lock
from collections import defaultdict

import requests
from flask import jsonify
from kytos.core import KytosNApp, log, rest
from kytos.core.events import KytosEvent
from kytos.core.helpers import listen_to, alisten_to
from napps.amlight.coloring import settings
from napps.amlight.coloring.utils import make_unicast_local_mac
from pyof.v0x04.common.port import PortNo


class Main(KytosNApp):
    """Main class of amlight/coloring NApp.

    This class is the entry point for this napp.
    """

    def setup(self):
        """Replace the '__init__' method for the KytosNApp subclass.

        The setup method is automatically called by the controller when your
        application is loaded.

        So, if you have any setup routine, insert it here.
        """
        self.switches = {}
        self._switches_lock = Lock()
        self._flow_manager_url = settings.FLOW_MANAGER_URL
        self._color_field = settings.COLOR_FIELD
        self.table_group = {"base": 0}

    def execute(self):
        """ Topology updates are executed through events. """

    @listen_to('kytos/topology.updated')
    def topology_updated(self, event):
        """Update colors on topology update."""
        topology = event.content['topology']
        self.update_colors(
            [link.as_dict() for link in topology.links.values()]
        )

    def update_colors(self, links):
        """ Color each switch, with the color based on the switch's DPID.
            After that, if not yet installed, installs, for each switch, flows
            with the color of its neighbors, to send probe packets to the
            controller.
        """
        with self._switches_lock:
            for switch in self.controller.switches.copy().values():
                if switch.dpid not in self.switches:
                    color = int(switch.dpid.replace(':', '')[4:], 16)
                    self.switches[switch.dpid] = {'color': color,
                                                  'neighbors': set(),
                                                  'flows': {}}
                else:
                    self.switches[switch.dpid]['neighbors'] = set()

            for link in links:
                source = link['endpoint_a']['switch']
                target = link['endpoint_b']['switch']
                if source != target:
                    self.switches[source]['neighbors'].add(target)
                    self.switches[target]['neighbors'].add(source)

        dpid_flows = defaultdict(list)

        # Create the flows for each neighbor of each switch and installs it
        # if not already installed
        with self._switches_lock:
            for dpid, switch_dict in self.switches.items():
                switch = self.controller.get_switch_by_dpid(dpid)
                if switch.ofp_version == '0x04':
                    controller_port = PortNo.OFPP_CONTROLLER
                else:
                    continue
                for neighbor in switch_dict['neighbors']:
                    if neighbor not in switch_dict['flows']:
                        flow_dict = {
                            'table_id': 0,
                            'match': {},
                            'priority': 50000,
                            'actions': [
                                {'action_type': 'output',
                                 'port': controller_port}
                            ],
                            'cookie': self.get_cookie(dpid)}

                        flow_dict['match'][self._color_field] = \
                            self.color_to_field(
                                self.switches[neighbor]['color'],
                                self._color_field
                            )
                        self.set_flow_table_group_owner(flow_dict, "base")

                        switch_dict['flows'][neighbor] = flow_dict
                        dpid_flows[dpid].append(flow_dict)

        self._send_flow_mods(dpid_flows)

    def shutdown(self):
        """This method is executed when your napp is unloaded.

        If you have some cleanup procedure, insert it here.
        """

    @staticmethod
    def color_to_field(color, field='dl_src'):
        """
        Gets the color number and returns it in a format suitable for the field
        :param color: The color of the switch (integer)
        :param field: The field that will be used to create the flow for the
        color
        :return: A representation of the color suitable for the given field
        """
        if field in ('dl_src', 'dl_dst'):
            color_64bits = color & 0xffffffffffffffff
            int_mac_6bytes = struct.pack('!Q', color_64bits)[2:]
            color_value = ':'.join([f'{b:02x}' for b in int_mac_6bytes])
            return make_unicast_local_mac(color_value.replace('00', 'ee'))
        if field in ('nw_src', 'nw_dst'):
            color_32bits = color & 0xffffffff
            int_ip = struct.pack('!L', color_32bits)
            return '.'.join(map(str, int_ip))
        if field in ('in_port', 'dl_vlan', 'tp_src', 'tp_dst'):
            return color & 0xffff
        if field in ('nw_tos', 'nw_proto'):
            return color & 0xff
        return color & 0xff

    def _switch_colors(self) -> dict:
        """Build switch colors dict."""
        with self._switches_lock:
            colors = {}
            for dpid, switch_dict in self.switches.items():
                colors[dpid] = {'color_field': self._color_field,
                                'color_value': self.color_to_field(
                                    switch_dict['color'],
                                    field=self._color_field
                                )}
            return colors

    # pylint: disable=missing-timeout
    def _send_flow_mods(self, dpid_flows: dict) -> None:
        """Send FlowMods."""
        for dpid, flows in dpid_flows.items():
            res = requests.post(
                self._flow_manager_url % dpid,
                json={'flows': flows, 'force': True}
            )
            if res.status_code // 100 != 2:
                log.error(f'Flow manager returned an error inserting '
                          f'flows {flows}. Status code {res.status_code} '
                          f'on dpid {dpid}')

    @rest('colors')
    def rest_colors(self):
        """ List of switch colors."""
        return jsonify({'colors': self._switch_colors()})

    @staticmethod
    @rest('/settings', methods=['GET'])
    def return_settings():
        """ List the SDNTrace settings
            Return:
            SETTINGS in JSON format
        """
        settings_dict = {}
        settings_dict['color_field'] = settings.COLOR_FIELD
        settings_dict['coloring_interval'] = settings.COLORING_INTERVAL
        settings_dict['topology_url'] = settings.TOPOLOGY_URL
        settings_dict['flow_manager_url'] = settings.FLOW_MANAGER_URL
        return jsonify(settings_dict)

    @staticmethod
    def get_cookie(dpid):
        """Get 8-byte integer cookie."""
        int_dpid = int(dpid.replace(":", ""), 16)
        return (0x00FFFFFFFFFFFFFF & int_dpid) | (settings.COOKIE_PREFIX << 56)

    def set_flow_table_group_owner(self,
                                   flow: dict,
                                   group: str = "base") -> dict:
        """Set owner, table_group and table_id
        coloring is only allowing 'base' for now"""
        try:
            flow["table_id"] = self.table_group[group]
        except KeyError as err:
            log.error(f'The table group "{group}" has not been found'
                      f'Table group in settings: {self.table_group}')
            raise err
        flow["owner"] = "coloring"
        flow["table_group"] = group
        return flow

    # pylint: disable=attribute-defined-outside-init
    @alisten_to("kytos/of_multi_table.enable_table")
    async def on_table_enabled(self, event):
        """Handle a recently table enabled.
        Coloring only allows "base" as flow group
        """
        table_group = event.content.get("coloring", None)
        if not table_group:
            return
        for group in table_group:
            if group not in settings.TABLE_GROUP_ALLOWED:
                log.error(f'The table group "{group}" is not allowed for '
                          f'coloring. Allowed table groups are '
                          f'{settings.TABLE_GROUP_ALLOWED}')
                return
        self.table_group = table_group
        content = {"group_table": self.table_group}
        event_out = KytosEvent(name="kytos/coloring.enable_table",
                               content=content)
        await self.controller.buffers.app.aput(event_out)
