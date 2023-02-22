import requests
import json
import pathlib
import shutil
from pprint import pprint
from tines_lib import *
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# this is a quickscript for ad-hoc data export from an endpoint

tenant = Tenant.create_by_name('tines-prod')


def main():
    print(tenant)
    action_id = 2893 #read email
    #action_id = 2836 #trigger success
    results = api_list_paginated('events', tenant, endpoint_url=f'{tenant.api_base}/agents/{action_id}/events')
    save_json(f'events_{action_id}.json', results)
    pprint(results)
    
    #stringify_events = read_json('./troy_results_stringify.json')
    #success_events = read_json('./troy_results_success.json')
    #print(stringify_events)
    
    #print(len(stringify_events))
    #list of dicts
    #success_guids = [x['story_run_guid'] for x in success_events]
    #print(success_guids)
    #lost_events = [x for x in stringify_events if x['story_run_guid'] not in success_guids]
    #print(len(lost_events))
    #[x for x in x if not in y]

    #save_json('./lost_events.json', lost_events)



if __name__ == '__main__':
    main()
