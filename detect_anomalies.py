import nfstream
import json
import sys
import getopt   
# from utils import ....

APP_NAME_ERR = "PROTOCOL NEVER USED"
DST_IP_ERR   = "UNKNOWN DESTINATION IP"
SRC_IP_ERR   = "UNKNOWN SOURCE IP"

flows_counter = 0   # number of analyzed flows
report = {"":[], APP_NAME_ERR:[], DST_IP_ERR:[], SRC_IP_ERR:[]}  # dictionary used for the final report

# Load the services map used as a reference to detect anomalies
with open('export.json', 'r') as fd:
    services_map = json.load(fd)

# Parse command-line arguments
def parse_cmdline_args(argv):
    interface = "null"

    # No arguments/flag in input
    if len(argv) == 0:
        print("Usage: detect_anomalies.py -i <interface>")
        sys.exit()

    try:
        opts, args = getopt.getopt(argv, "hi:", ["help=", "interface="])
    except getopt.GetoptError:
        print("Error")
        sys.exit(2)
    
    # Parsing arguments
    for opt, arg in opts:
        if opt in ['-h', '--help']:
            print("Usage: detect_anomalies.py -i <interface>")
            sys.exit()
        elif opt in ['-i', '--interface']:
            interface = arg

    if interface == "null":
        print("Usage: detect_anomalies.py -i <interface>")
        sys.exit()

    return interface

# Check if addr is a local or remote address
def check_address(addr):
    # Split the address and convert it to int
    parts = list(map(int, addr.split(".")))
    
    # local address 10.0.0.0 - 10.255.255.255
    if parts[0] == 10:
        return addr
    # local address 172.16.0.0 - 172.31.255.255
    elif (parts[0] == 172) and (parts[1] >= 16) and (parts[1] <= 31):
        return addr
    # local address 192.168.0.0 - 192.168.255.55
    elif (parts[0] == 192) and (parts[1] == 168):
        return addr
    else:
        return "remote"

# Based on source ip, destination ip and application name of the flow, check if 
# the flow is an anomaly on the network
def check_flow(src_ip, dst_ip, app_name):
    # src_ip already seen in the network
    if src_ip in services_map.keys():
        # src_ip has alreay contacted dst_ip
        if dst_ip in services_map[src_ip].keys():
            # with a different protocol
            if app_name not in services_map[src_ip][dst_ip][1:]:
                return APP_NAME_ERR
        else:
            return DST_IP_ERR
    else:
        return SRC_IP_ERR

    return ""

# Update a data structure dedicated to the final report (after an interruption like SIGINT)
def update_report(err_id, src_ip, dst_ip, app_name, b_bytes, report_dict):
    try:
        dst_list = report_dict[src_ip]
    # "src_ip" key doesn't exists
    except KeyError:
        report_dict[src_ip] = {}
        report_dict[src_ip][dst_ip] = [err_id, b_bytes, app_name]
        dst_list = report_dict[src_ip]
    
    # If "src_ip" is a key, let's see if dst_ip already exists
    if dst_ip not in dst_list.keys():
        dst_list[dst_ip] = [err_id, b_bytes, app_name]
    else:
        dst_list[dst_ip][1] += b_bytes
        dst_list[dst_ip].append(app_name)

    return report_dict


# Unused, take for the report script
def print_report(report):
    # For every source ip
    for i in report.keys():
        dst_list = report[i]
        print("{0:15s} talks to: ".format(i))
        
        # For every destination ip
        for j in dst_list.keys():
            arr = dst_list[j]
            print("\t--> {0:15s}, {1:20s}, Bytes:{2:9d}, {3:22s}".format(
                j,
                arr[2:],
                arr[1],
                arr[0]
            ))
            

if __name__ == "__main__":
    inner_counter = 0

    # Get interface name and activate the metering processes
    interface = parse_cmdline_args(sys.argv[1:])
    my_streamer = nfstream.NFStreamer(source=interface,
        snapshot_length=1600,
        idle_timeout=120,
        active_timeout=1800,
        udps=None)

    for flow in my_streamer:
        # Doesn't count IPv6 addresses (TODO)
        if ":" in flow.src_ip:
            continue

        src_ip   = check_address(flow.src_ip) 
        dst_ip   = check_address(flow.dst_ip)
        app_name = flow.application_name
        b_bytes  = int(flow.bidirectional_bytes)
        resp     = "{0:15s} --> {1:15s} , {2:20s} | ".format(src_ip, dst_ip, app_name)
                
        err = check_flow(src_ip, dst_ip, app_name)
        report = update_report(err, src_ip, dst_ip, app_name, b_bytes, report)
        # report dictionary persistence
        if inner_counter == 5:
            inner_counter = 0
            with open('export_report.json', 'w') as fd:
                json.dump(report, fd)
    
        # Print flow analysis results
        print("{0:2d}. {}".format(flows_counter, resp+err))
        flows_counter += 1
        inner_counter += 1
        

# TODO: Statistiche su numero di anomalie, percentuali ecc..
# TODO: creare utils.py con tutte le classi/funzioni che vengono condivise dai vari script
# TODO: Support IPv6
'''
src_ip: {
    src_error: 1/0
    dst_ip:[err_id, bytes, app_name]
    dst_ip1:[err_id, bytes, app_name1, app_name2]
    ....
}
'''