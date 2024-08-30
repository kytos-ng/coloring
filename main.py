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

from kytos.core import KytosNApp, log, rest
from kytos.core.common import EntityStatus
from kytos.core.helpers import listen_to, alisten_to
from kytos.core.rest_api import JSONResponse, Request
from kytos.core.events import KytosEvent
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

    @listen_to('kytos/topology.switch.disabled')
    def on_switch_disabled(self, event):
        """Remove switch from self.switches"""
        self.handle_switch_disabled(event.content['dpid'])

    @listen_to('kytos/topology.link.disabled')
    def on_link_disabled(self, event):
        """Remove link from self.switches neighbors"""
        self.handle_link_disabled(event.content['link'])

    @listen_to('kytos/topology.updated')
    def topology_updated(self, event):
        """Update colors on topology update."""
        topology = event.content['topology']
        self.update_colors(
            [link.as_dict() for link in topology.links.values()]
        )

    # pylint: disable=too-many-branches
    def update_colors(self, links):
        """ Color each switch, with the color based on the switch's DPID.
            After that, if not yet installed, installs, for each switch, flows
            with the color of its neighbors, to send probe packets to the
            controller.
        """
        with self._switches_lock:
            for switch in self.controller.switches.copy().values():
                if not switch.is_enabled():
                    if switch.dpid in self.switches:
                        self.switches[switch.dpid]['neighbors'] = set()
                    continue
                if switch.dpid not in self.switches:
                    color = int(switch.dpid.replace(':', '')[4:], 16)
                    self.switches[switch.dpid] = {'color': color,
                                                  'neighbors': set(),
                                                  'flows': {}}
                else:
                    self.switches[switch.dpid]['neighbors'] = set()

            for link in links:
                if link.get('enabled') is not True:
                    continue
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
                if switch.status != EntityStatus.UP:
                    continue
                if switch.ofp_version == '0x04':
                    controller_port = PortNo.OFPP_CONTROLLER
                else:
                    continue
                for neighbor in switch_dict['neighbors']:
                    if neighbor not in switch_dict['flows']:
                        flow_dict = {
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
                        self.set_flow_table_group_owner(flow_dict)

                        switch_dict['flows'][neighbor] = flow_dict
                        dpid_flows[dpid].append(flow_dict)

        self._send_flow_mods(dpid_flows, "install")

    def handle_link_disabled(self, link):
        """Handle link deletion. Deletes only flows from the proper switches.
         The field 'neighbors' is managed by update_colors method."""
        switch_a_id = link.endpoint_a.switch.dpid
        switch_b_id = link.endpoint_b.switch.dpid

        if switch_b_id == switch_a_id:
            return

        with self._switches_lock:
            flow_mods = defaultdict(list)
            flow = self.switches[switch_a_id]['flows'][switch_b_id]
            flow_mods[switch_a_id].append({
                "table_id": flow['table_id'],
                "owner": 'coloring',
                "match": flow['match']
            })
            flow = self.switches[switch_b_id]['flows'][switch_a_id]
            flow_mods[switch_b_id].append({
                "table_id": flow['table_id'],
                "owner": 'coloring',
                "match": flow['match']
            })
            self.switches[switch_a_id]['flows'].pop(switch_b_id)
            self.switches[switch_b_id]['flows'].pop(switch_a_id)
        self._send_flow_mods(flow_mods, "delete")

    def handle_switch_disabled(self, dpid):
        """Handle switch deletion. Links are expected to be disabled first
         therefore the deleted inner dictionary is expected to be empty with
         no flows and neighbors."""
        with self._switches_lock:
            try:
                sw_dct = self.switches[dpid]
                if sw_dct['flows'] or sw_dct['neighbors']:
                    log.error(f"There was an error cleanning up {dpid}. "
                              "The fields 'flows' and 'neighbors' should be"
                              " empty.")
                    return
            except KeyError as err:
                log.error(f"Error while handling disabled switch: "
                          f"Switch {err} not found.")
                return
            self.switches.pop(dpid, None)

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

    def _send_flow_mods(
        self, flows: dict, action: str, force: bool = True
    ) -> None:
        """Remove FlowMods"""
        for dpid, mod_flows in flows.items():
            name = f"kytos.flow_manager.flows.{action}"
            content = {
                'dpid': dpid,
                'flow_dict': {'flows': mod_flows},
                'force': force,
            }
            event = KytosEvent(name=name, content=content)
            self.controller.buffers.app.put(event)

    @rest('colors')
    def rest_colors(self, _request: Request) -> JSONResponse:
        """ List of switch colors."""
        return JSONResponse({'colors': self._switch_colors()})

    @staticmethod
    @rest('/settings', methods=['GET'])
    def return_settings(_request: Request) -> JSONResponse:
        """ List the SDNTrace settings
            Return:
            SETTINGS in JSON format
        """
        settings_dict = {}
        settings_dict['color_field'] = settings.COLOR_FIELD
        settings_dict['coloring_interval'] = settings.COLORING_INTERVAL
        settings_dict['topology_url'] = settings.TOPOLOGY_URL
        settings_dict['flow_manager_url'] = settings.FLOW_MANAGER_URL
        return JSONResponse(settings_dict)

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
        flow["table_id"] = self.table_group[group]
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
        if table_group != self.table_group:
            self.table_group.update(table_group)
            self.update_switches_table()
        content = {"group_table": self.table_group}
        event_out = KytosEvent(name="kytos/coloring.enable_table",
                               content=content)
        await self.controller.buffers.app.aput(event_out)

    def update_switches_table(self):
        """Update switch flow table ids when a pipeline is enabled."""
        with self._switches_lock:
            for _, content in self.switches.items():
                flows = content["flows"]
                for _, flow in flows.items():
                    group = flow['table_group']
                    flow['table_id'] = self.table_group[group]
