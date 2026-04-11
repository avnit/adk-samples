import subprocess
import re
import requests
import json
import copy
import dotenv
import os
import platform

# Load environment variables from .env file
dotenv.load_dotenv()

CLOUDFLARE_API_TOKEN = os.getenv("API_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
TUNNEL_ID = os.getenv("TUNNEL_ID")

# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
# REQUIRED: USER CONFIGURATION
#
# 1. Get your Cloudflare API Token:
#    - Go to: https://dash.cloudflare.com/profile/api-tokens
#    - Create a Custom Token
#    - Give it permissions:
#      - Account > Cloudflare Tunnel: Edit
#      - Account > Account Settings: Read
#
# 2. Get your Account ID:
#    - Go to your Cloudflare dashboard, select any domain, and scroll down.
#    - Your Account ID will be on the right-hand side.
#
# 3. Get your Tunnel ID:
#    - Go to Zero Trust > Networks > Tunnels.
#    - Click on your tunnel (e.g., "casaos") and its UUID is the Tunnel ID.
#      (It will be in the URL: .../tunnels/<TUNNEL_ID>/details)
# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---


# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
# REQUIRED: SERVICE MAPPING
#
# Map your public Cloudflare hostnames to their *local* hostnames
# (the name that appears in the `arp -a` command) and the port.
#
# Example from your screenshot:
# Public Hostname: "pi.asblog.com"
# Local Hostname (from arp -a): "pi" or "pi.local"
# Service: "http://192.168.0.74:80" -> port is 80, protocol is http
# Local IP Table: {'avnit-msi-z790': '192.168.96.41',
# 'SYNOLOGYNAS': '192.168.96.54',
# 'DEB-NAS': '192.168.96.39', 
# 'ORANGEPI5-PLUS': '192.168.0.76', 
# 'HOMEASSISTANT': '192.168.68.95', 
# 'DESKTOP-TNNIS50': '192.168.0.77',
# 'magicdns': '100.100.100.100'}
# Add all your services from the screenshot here.
# --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---

SERVICE_MAPPING = {
    # "public_hostname_in_cloudflare": {
    #   "local_hostname": "name_from_arp_a_output",
    #   "port": 80,
    #   "protocol": "http"
    # },
    "homeassistant.asblog.com": {
        "192.168.68.95": "HOMEASSISTANT", # e.g., 'homeassistant' or 'homeassistant.local'
        "port": 8123,
        "protocol": "http"
    },
    "nas.asblog.com": {
        "192.168.96.54": "SYNOLOGYNAS",
        "port": 5000,
        "protocol": "http"
    },
    
    "tools.asblog.com": {
        "192.168.0.74": "orange-pi.local", # e.g., 'ubuntu-server'
        "port": 8081,
        "protocol": "http"
    },
    "pi.asblog.com": {
        "192.168.68.160": "pi.local", # e.g., 'pi' or 'pi.local'
        "port": 80,
        "protocol": "http"
    },
    "casaos.asblog.com": {
        "192.168.0.31": "casaos-server.local",
        "port": 81,
        "protocol": "http"
    },
    "ubuntu2.asblog.com": {
        "192.168.0.31": "ubuntu2.local",
        "port": 31,
        "protocol": "http"
    },
    "jelly.asblog.com": {
        "192.168.68.84": "jellyfin-server.local",
        "port": 8096,
        "protocol": "http"
    },
    "sonarr.asblog.com": {
        "local_hostname": "ORANGEPI5-PLUS",
        "port": 8989,
        "protocol": "http"
    },
    # --- ADD THE REST OF YOUR SERVICES HERE ---
    "homepage.asblog.com": {
        "192.168.0.74": "orange",
        "port": 3000,
        "protocol": "http"
    },
    "pi2.asblog.com": {
        "192.168.0.68": "pi2",
        "port": 80, 
        "protocol": "http"
    },
    "pi.asblog.com": {
        "192.168.0.68": "pi",
        "port": 80,
        "protocol": "http"  
    },
    "unraid.asblog.com": {
        "192.168.68.84": "unraid",
        "port": 80,
        "protocol": "http"
    },
    "immich.asblog.com": {
        "192.168.0.32": "immich",
        "port": 2283,
        "protocol": "http"
    },
}

# --- SCRIPT LOGIC (No edits needed below this line) ---
def get_arp_table_windows():
    """
    Runs ARP scan on Windows.
    1. Runs 'arp -a' to get all IPs.
    2. Runs 'ping -a' on each IP to resolve hostname.
    This is much slower than the Linux version.
    """
    print("Running Windows-specific ARP scan (this may take a moment)...")
    ip_lookup = {}
    try:
        # 1. Get all IPs from arp -a
        arp_result = subprocess.run(
            ['arp', '-a'], 
            capture_output=True, 
            text=True, 
            check=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # Regex for Windows: "  192.168.0.1           00-aa-bb-cc-dd-ee     dynamic"
        ip_regex = re.compile(r"^\s+([\d\.]+)\s+[\w\-]+")
        
        ips_to_check = []
        for line in arp_result.stdout.splitlines():
            match = ip_regex.search(line)
            if match:
                ip = match.group(1)
                # Avoid broadcast/multicast/localhost
                if not ip.endswith('.255') and not ip.startswith('224.') and not ip.startswith('127.'):
                     ips_to_check.append(ip)
        
        print(f"Found {len(ips_to_check)} IPs. Now resolving hostnames...")

        # 2. For each IP, run 'ping -a' to get hostname
        # Regex for ping -a: "Pinging hostname.local [192.168.0.74]..."
        ping_regex = re.compile(r"Pinging\s+([\w\.\-]+)\s+\[([\d\.]+)\]")

        for ip in ips_to_check:
            try:
                # -n 1: 1 ping, -w 1000: 1s timeout
                ping_result = subprocess.run(
                    ['ping', '-a', '-n', '1', '-w', '1000', ip],
                    capture_output=True, 
                    text=True, 
                    timeout=2,
                    encoding='utf-8',
                    errors='ignore'
                )
                ping_match = ping_regex.search(ping_result.stdout)
                
                if ping_match:
                    hostname = ping_match.group(1).split('.')[0] # Get base hostname
                    ip_from_ping = ping_match.group(2)
                    if ip_from_ping == ip: # Make sure it matches
                        ip_lookup[hostname] = ip
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                # Host is down or doesn't respond to ping
                continue 
        
        return ip_lookup

    except Exception as e:
        print(f"Error during Windows ARP scan: {e}")
        return {} # Return empty dict, not None

def get_arp_table_linux():
    """
    Runs 'arp -a' on Linux/macOS, which includes hostnames.
    """
    print("Running Linux/macOS ARP scan with 'arp -a'...")
    try:
        # Run the arp -a command
        result = subprocess.run(
            ['arp', '-a'], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # Regex to find lines like:
        # pi.local (192.168.0.74) at ...
        arp_regex = re.compile(r"^([\w\.\-]+)\s+\(([\d\.]+)\)")
        
        ip_lookup = {}
        for line in result.stdout.splitlines():
            match = arp_regex.search(line)
            if match:
                # Get hostname, remove .local or other domains
                hostname = match.group(1).split('.')[0] 
                ip_address = match.group(2)
                if hostname != '?':
                    ip_lookup[hostname] = ip_address
        
        return ip_lookup

    except FileNotFoundError:
        print("Error: 'arp' command not found. Is it installed and in your PATH?")
        return {}
    except subprocess.CalledProcessError as e:
        print(f"Error running 'arp -a': {e}")
        return {}

def get_arp_table():
    """
    Runs 'arp -a' and parses the output based on the OS.
    On Windows, it must also run 'ping -a' to resolve hostnames,
    which is slower.
    
    Returns a dictionary: {'local_hostname': 'ip_address'}
    e.g., {'pi': '192.168.0.74', 'ubuntu-server': '192.168.0.76'}
    """
    system = platform.system().lower()
    
    print(f"Detected OS: {system.capitalize()}")
    
    if system == "windows":
        ip_lookup = get_arp_table_windows()
    else:
        ip_lookup = get_arp_table_linux()
        
    if ip_lookup:
        print(f"Found {len(ip_lookup)} devices with hostnames in ARP table.")
    else:
        # This is the user's error. Let's make it more helpful.
        print("Found 0 devices with resolvable hostnames in ARP table.")
        print("Troubleshooting:")
        print("1. Ensure this script is run on the same local network as your services.")
        print("2. If on Windows, ensure your devices respond to 'ping -a <ip>' with a hostname.")
        print("3. If on Linux, ensure 'arp -a' shows hostnames (e.g., 'pi.local (192.168.0.74)').")

    return ip_lookup

def get_cloudflare_config(api_token, account_id, tunnel_id):
    """
    Fetches the current configuration for a specific Cloudflare Tunnel.
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    print(f"Fetching current tunnel config for {tunnel_id}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raises an error for 4xx/5xx responses
        
        # The config is nested inside a 'result' object
        return response.json().get('result', {}).get('config')
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Cloudflare config: {e}")
        return None

def update_cloudflare_config(api_token, account_id, tunnel_id, new_config):
    """
    Updates a Cloudflare Tunnel with a new configuration.
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # The API expects the *entire* config object to be PUT
    payload = {"config": new_config}
    
    print("Pushing updated configuration to Cloudflare...")
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        print("Successfully updated Cloudflare tunnel configuration!")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error updating Cloudflare config: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response body: {e.response.text}")
        return None

def main():
    if "YOUR_CLOUDFLARE_API_TOKEN" in CLOUDFLARE_API_TOKEN:
        print("Error: Please fill in your Cloudflare credentials in the script.")
        return

    # 1. Get local network IPs
    ip_lookup = get_arp_table()
    if not ip_lookup:
        print("ARP table scan failed to find mappable devices. Exiting.")
        return
        
    print(f"Local IP Table: {ip_lookup}")

    # 2. Get current Cloudflare config
    current_config = get_cloudflare_config(
        CLOUDFLARE_API_TOKEN, ACCOUNT_ID, TUNNEL_ID
    )
    if not current_config:
        print("Could not get Cloudflare config. Exiting.")
        return

    # Create a deep copy to modify
    new_config = copy.deepcopy(current_config)
    needs_update = False

    # 3. Check for services that need updates
    print("\nChecking for required updates...")
    if 'ingress' not in new_config:
        print("Warning: 'ingress' rules not found in config.")
        return

    for rule in new_config['ingress']:
        # Check if it's a rule we manage (has a hostname and is in our map)
        if 'hostname' in rule and rule['hostname'] in SERVICE_MAPPING:
            public_hostname = rule['hostname']
            service_details = SERVICE_MAPPING[public_hostname]
            local_hostname = service_details['local_hostname']
            
            # Check if we found this local hostname in our ARP scan
            if local_hostname in ip_lookup:
                new_ip = ip_lookup[local_hostname]
                port = service_details['port']
                protocol = service_details['protocol']
                
                new_service_url = f"{protocol}://{new_ip}:{port}"
                current_service_url = rule.get('service', '')
                
                if new_service_url != current_service_url:
                    print(f"  [UPDATE] {public_hostname}")
                    print(f"    - OLD: {current_service_url}")
                    print(f"    - NEW: {new_service_url}")
                    rule['service'] = new_service_url
                    needs_update = True
                else:
                    print(f"  [OK] {public_hostname} is already up-to-date.")
            else:
                print(f"  [WARN] Local hostname '{local_hostname}' for "
                      f"'{public_hostname}' not found in ARP table. Skipping.")

    # 4. Push updates if needed
    if needs_update:
        print("\nChanges detected, updating Cloudflare.")
        update_cloudflare_config(
            CLOUDFLARE_API_TOKEN, ACCOUNT_ID, TUNNEL_ID, new_config
        )
    else:
        print("\nAll configured services are up-to-date. No changes made.")

if __name__ == "__main__":
    main()
