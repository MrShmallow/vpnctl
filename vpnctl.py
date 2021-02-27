#!/usr/bin/env python3

import bs4
import requests
import sys
import subprocess
import os
import argparse
import time

# Default values
DEFAULT_SERVER_LIST_URL = "https://privatevpn.com/serverlist"
DEFAULT_CONNECTION_NAME = "PrivateVPN"
DEFAULT_RESTART_DELAY_SECONDS = 1


class VpnConnection(object):
    """Class for performing operations on a VPN connection using nmcli."""

    def __init__(self, name, restart_delay_seconds=DEFAULT_RESTART_DELAY_SECONDS):
        """Create a new connection object.

        Parameters:
            name: vpn connection name
            restart_delay_seconds: seconds to sleep after disconnecting and before connecting again
        """

        self.name = name
        self._restart_delay_seconds = restart_delay_seconds

    def is_connected(self):
        """Check whether the VPN connection is active.

        Returns:
            True if the connection is active, False otherwise
        """

        command_output = subprocess.check_output(["nmcli",
                                                  "-g", "GENERAL.STATE",
                                                  "con",
                                                  "show",
                                                  self.name])
        return len(command_output) > 0

    def connect(self, only_if_disconnected=False):
        """Turn on the VPN connection.

        Parameters:
            only_if_disconnected: if set to True then try to connect only if not already connected
        """

        if not only_if_disconnected or not self.is_connected():
            subprocess.check_output(["nmcli", "con", "up", self.name])

    def disconnect(self, only_if_connected=False):
        """Turn off the VPN connection.

        Parameters:
            only_if_connected: if set to True then try to disconnect only if already connected
        """

        if not only_if_connected or self.is_connected():
            subprocess.check_output(["nmcli", "con", "down", self.name])

    def restart(self):
        """Disconnect, wait a bit and then reconnect."""

        if self.is_connected():
            self.disconnect()
            time.sleep(self._restart_delay_seconds)
        self.connect()

    def get_data_item(self, key):
        """Get a specific item from the VPN data dictionary.

        Parameters:
            key: key of the item to get from the dictionary

        Returns:
            the requested item
        """

        return self._get_data()[item_key]

    def set_data_item(self, key, value):
        """Set a specific item in the VPN data dictionary.

        Parameters:
            key: key of the item to set in the dictionary
        """

        subprocess.check_output(["nmcli", "con", "mod", self.name, "+vpn.data", f"{key}={value}"])

    def get_remote_address(self):
        """Get the remote address associated with the connection.

        Returns:
            the address
        """

        return self.get_data_item("remote")

    def set_remote_address(self, address):
        """Set the remote address associated with the connection.

        Parameters:
            address: the new address
        """

        self.set_data_item("remote", address)

    def _get_data(self):
        """Get the VPN data dictionary for the connection.

        Returns:
            the dictionary
        """

        command_output = subprocess.check_output(["nmcli",
                                                  "-g", "vpn.data",
                                                  "con",
                                                  "show",
                                                  self.name])

        # The data is in the form of "key1 = value1, key2 = value2"
        return dict([entry.split(" = ") for entry in command_output.decode().strip().split(", ")])


def parse_arguments():
    """Parse command-line arguments for the program.

    Returns:
        program arguments as an argparse namespace
    """

    parser = argparse.ArgumentParser(description="Manage VPN connections")

    parser.add_argument("-c",
                        "--connection",
                        type=str,
                        default=DEFAULT_CONNECTION_NAME,
                        help=f"name of the connection (default: {DEFAULT_CONNECTION_NAME})")
    parser.add_argument("-d", "--disconnect", action="store_true", help="turn off the VPN")
    parser.add_argument("-u", "--url", type=str, help="server address to connect to")
    parser.add_argument("-l", "--list", action="store_true", help="only list servers")
    parser.add_argument("-v", "--verbose", action="store_true", help="print verbose messages")
    parser.add_argument("-s",
                        "--server-list-url",
                        type=str,
                        default=DEFAULT_SERVER_LIST_URL,
                        help=f"URL of the server list (default: {DEFAULT_SERVER_LIST_URL})")

    return parser.parse_args()

def get_servers_list(server_list_url):
    """Get a list of available VPN servers from the web.

    Parameters:
        server_list_url: URL of the servers list webpage

    Returns:
        list of dictionaries with information about each available server
    """

    r = requests.get(server_list_url)

    # The first table in the page contains the servers list
    html_doc = r.content
    soup = bs4.BeautifulSoup(html_doc, "html.parser")
    table = soup.find("table")
    tbody = table.find("tbody")
    trs = tbody.find_all("tr")

    servers = []
    for tr in trs:
        server = {}
        tds = tr.find_all("td")
        # Location comes after the flag in the first column
        server["location"] = [child for child in tds[0].children][2].strip()
        server["address"] = tds[1].string.strip()
        servers.append(server)

    return servers

def print_servers_list(servers):
    """Print the VPN servers list as a human-readable table.

    Parameters:
        servers: the list of servers (obtained from get_servers_list())
    """

    first_column_width = len("Number")
    # Width of seconds column is the length of the longest location string
    second_column_width = max(len(server["location"]) for server in servers)

    print("Number".ljust(first_column_width) + "\t" +
          "Location".ljust(second_column_width) + "\t" +
          "Address")

    for i, server in enumerate(servers):
        print(str(i + 1).ljust(first_column_width) + "\t" + 
              server["location"].ljust(second_column_width) + "\t" + 
              server["address"])


def get_chosen_server(servers):
    """Request the user to choose a server from the list, until getting a valid number.

    Parameters:
        servers: the list of servers (obtained from get_servers_list())

    Returns:
        the requested server, as a dictionary from the list
    """

    again = True
    while again:
        try:
            server_number = int(input("Choose server number to connect: ")) - 1
            if not 0 <= server_number < len(servers):
                # If the input is not an integer or not in the range, ValueError is thrown
                raise ValueError()
            again = False
        except ValueError:
            # Just try again if the input was invalid
            print("Invalid server number")

    return servers[server_number]


def main():
    """Manage VPN connections - connect to a specific server, disconnect etc.

    Returns:
        exit status for the program
    """

    try:
        arguments = parse_arguments()

        connection = VpnConnection(arguments.connection)

        # Disconnect
        if arguments.disconnect:
            if arguments.verbose:
                print(f"Turning off {arguments.connection}...")
            connection.disconnect(only_if_connected=True)
            return 0

        # Print servers list
        if arguments.list:
            if arguments.verbose:
                print("Fetching servers list...")
            print_servers_list(get_servers_list(arguments.server_list_url))
            return 0

        if arguments.url is not None:
            server_address = arguments.url
        else:
            # Request server from user
            arguments.verbose = True
            print("Fetching servers list...")
            servers = get_servers_list(arguments.server_list_url)
            print_servers_list(servers)
            server = get_chosen_server(servers)
            server_address = server["address"]

        # Connect
        if arguments.verbose:
            print(f"Connecting {arguments.connection} to {server_address}...")
        connection.set_remote_address(server_address)
        connection.restart()
        if arguments.verbose:
            print("Connected")

    except subprocess.CalledProcessError as e:
        # nmctl failures are raised with the exit status
        return e.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())

