import os


version = '1.1'
default_address = '172.93.103.204'  # FGMEMBERS address
default_port = 16605  # FGMEMBERS port
server_address = server_port = None
scenario_path = os.path.dirname(os.path.abspath(__file__))
scenario_path = os.path.join(scenario_path, 'scenarios')
filename = None
scenario = None
server_address = None
server_port = None
data = {'magvar': None, 
        'navaids': None, 
        'runways': None, 
        'aircraft': None}