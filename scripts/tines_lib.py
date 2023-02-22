import requests
from bidict import bidict
from pprint import pprint
import pathlib
import json
import shutil
import copy
import logging
logging.basicConfig(level=logging.INFO)

from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# holds functions and objects shared between larger scripts

DATA_DIR = pathlib.Path('../data').resolve()

CONTENT_MAP = bidict({
    'STORY': 'stories',
    'CREDENTIAL': 'user_credentials',
    'RESOURCE': 'global_resources'
  })

CONTENT_NAMES = ['teams', 'folders', 'users', 'stories', 'global_resources', 'user_credentials']

CREDS_PATH = pathlib.Path("/Users/jonathan.dycaico/_auth/tines/")


class Tenant:
  # Should only hold methods and data relevant to 2x or more scripts 
  def __init__(self, name, api_base, headers):
    self.name = name
    self.api_base = api_base
    self.headers = headers
    self.compare_data = {}

  def create_from_file(path):
    file_data = read_json(path)
    name = file_data['name']
    api_base = file_data['api_base']
    headers = file_data['headers']
    return Tenant(name, api_base, headers)

  def create_by_name(name):
    return Tenant.create_from_file(CREDS_PATH / f'{name}.json')

  def list_all_attributes(self):
    return list(self.__dict__.keys())

  def list_primary_data_attributes(self):
    full_list = self.list_all_attributes()
    irrelevant_attributes = ['name', 'api_base', 'headers', 'compare_data']
    return [x for x in full_list if x not in irrelevant_attributes]

  def get_readonly(self, content_name):
    return copy.deepcopy(getattr(self, content_name))

  def set_compare_data(self, content_name, content_data):
    getattr(self, 'compare_data')[content_name] = content_data

  def load_remote_data(self):
    # shared between tines_compare, tines_export
    
    self.teams = api_list_paginated('teams', self, endpoint_url=f'{self.api_base}/teams')
    self.folders = api_list_paginated('folders', self, endpoint_url=f'{self.api_base}/folders')  
    self.global_resources = api_list_paginated('global_resources', self, endpoint_url=f'{self.api_base}/global_resources')

    self.user_credentials = api_list_paginated('user_credentials', self, endpoint_url=f'{self.api_base}/user_credentials')
    
    users_list = api_list_paginated('admin/users', self, endpoint_url=f'{self.api_base}/admin/users')
    self.users = enrich_user_teams(users_list, self.teams, self)

    stories_list = api_list_paginated('stories', self, endpoint_url=f'{self.api_base}/stories')
    self.stories = enrich_stories(stories_list, self)
    
    #self.actions = api_list_paginated('actions', self, endpoint_url=f'{self.api_base}/actions') #cant get at present

#TODO: add function: read_json into instantiate_tenant

def reset_folder(folder_path):
    if folder_path.exists():
        shutil.rmtree(folder_path)
    folder_path.mkdir()


def is_json_string(input):
  # fails on string hashes, for some reason
  # using json.loads() is kludgy, use sparingly
  if isinstance(input, str):
    if not input.isnumeric():
      try:
        json.loads(input)
      except ValueError as e:
        return False
      return True
    return False
  return False


def read_json(filepath):
  with open(filepath, 'r') as infile:
    file_data = json.load(infile)
    # returns a dict
    #for key, value in file_data.items():
    #  if isinstance(value, str):
    #    if not is_int(value):
    #      if is_json(value):
    #        file_data[key] = json.loads(value)
  return file_data


def save_json(filepath, file_data):
  with open(filepath, 'w') as outfile:
    outfile.write(json.dumps(file_data, indent=4))


#TODO: def export_self.data():
#from tines_compare.py


def api_list_paginated(item_name, tenant, endpoint_url):
  # TODO: fix complete=false when results = 0
  request_count = 0
  resp = requests.get(endpoint_url, headers=tenant.headers, verify=False)
  request_count +=1
  all_data = resp.json()[item_name]
  #pprint(resp.json())
  if 'meta' in resp.json():
    meta = resp.json()['meta']
    while meta['next_page'] is not None:
        new_endpoint = meta['next_page']
        resp = requests.get(new_endpoint, headers=tenant.headers, verify=False)
        request_count +=1
        this_data = resp.json()[item_name]
        meta = resp.json()['meta']
        all_data.extend(this_data)
  
    success = ((meta['pages'] == request_count) and meta['count'] == len(all_data))
  #print(f'Listed:{item_name} => pages:{meta["pages"]}; items:{meta["count"]}; complete:{success}')
  return all_data

def enrich_user_teams(users_list, teams_list, tenant):
  for user in users_list:
    user['teams'] = []

  for team in teams_list:
      team_members = api_list_paginated('members', tenant, endpoint_url=f'{tenant.api_base}/teams/{team["id"]}/members')
      for member in team_members:
          for user in users_list:
              if member['id'] == user['id']:
                  user['teams'].append(team['name'])      
  return users_list


def enrich_stories(stories_list, tenant):
  for story_entry in stories_list:
      endpoint = f'{tenant.api_base}/stories/{story_entry["id"]}/export'
      resp = requests.get(endpoint, headers=tenant.headers, verify=False)
      story_json = resp.json()
      story_entry['file_json'] = story_json
  return stories_list
