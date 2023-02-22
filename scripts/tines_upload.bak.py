import requests
import json
import pathlib
import shutil
from pprint import pprint
import random
from tines_lib import *
import uuid
import logging
logging.basicConfig(level=logging.DEBUG)

from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

TESTING = False

# Reflects all Tines tenant data from folder structure into an empty workspace

# Credentials are given random() values because the value is not saved on export.
# Thus, manual filling-in of these values will be necessary after the script is run
# Also, credential upload does not support non-TEXT creds at this time (some bugs exist)

# Because Users cannot be assigned Team Membership from the API, this will have to be done manually after run
# Hold on that - I think can INVITE them, tho it may cause spam

MY_USER = "jonathan.dycaico@docusign.com"

tenant = Tenant.create_by_name('tines-prod')

def delete_all_items(item_name, endpoint):
  endpoint_url = tenant.api_base + f'/{endpoint}'
  items_list = api_list_paginated(item_name, tenant, endpoint_url)
  for item in items_list:
    id = item['id']
    this_endpoint = f'{endpoint_url}/{id}'
    if item_name == "admin/users" and item['email'] == MY_USER:
      print('Skipping delete on MY_USER')
    else:
      #print(f'DELETE {this_endpoint}')
      resp = requests.delete(this_endpoint, headers=tenant.headers, verify=False)
      if not resp.ok:
        print(f'badresp! {resp}\n{resp.text}')


def batch_delete_stories():
  # faster in batch
  print("deleting all stories...")
  list_endpoint = tenant.api_base + '/stories'
  delete_endpoint = list_endpoint + '/batch'
  stories_list = api_list_paginated('stories', tenant, list_endpoint)
  story_ids = [x['id'] for x in stories_list]
  print(story_ids)
  data = {'ids': story_ids}
  resp = requests.delete(delete_endpoint, json=data, headers=tenant.headers, verify=False)
  if not resp.ok:
      print(f'badresp! {resp}\n{resp.text}')


def reset_instance():
  # fails with HTTP 422 because `can't delete a team with contents!`
  # Teams, Folders are likely to exhibit this behavior
  # Thus, first delete_all(resource_type_1, resource_type_2, etc), then delete these containers
  delete_all_items('admin/users', endpoint='admin/users')

  delete_all_items('global_resources', endpoint='global_resources')
  delete_all_items('user_credentials', endpoint='user_credentials')
  batch_delete_stories()
  
  delete_all_items('folders', endpoint='folders')
  delete_all_items('teams', endpoint='teams')


def get_folder_contents(folder_path, type):
  cwd = folder_path.iterdir()
  if type.upper() == 'FILE':
    files = [x for x in cwd if x.is_file()]
    return [x for x in files if x.suffix == ".json"]
  elif type.upper() == 'FOLDER':
    return [x for x in cwd if x.is_dir()]


def make_teams():
  endpoint = tenant.api_base + '/teams/'
  # p = DATA_DIR.glob('**/*') # gets all files/folders recursively (not just cwd)
  teams_dir = DATA_DIR / 'teams'
  subfolders = get_folder_contents(teams_dir, type='FOLDER')
  #pprint(subfolders)
  teams_list = []
  for folder in subfolders:
    data = {'name': folder.name}
    resp = requests.post(endpoint, json=data, headers=tenant.headers, verify=False)
    if not resp.ok:
      print(f'badresp! {resp}\n{resp.text}')
    else:
      teams_list.append(resp.json())
  
  return teams_list


def make_folders(teams_list):
  endpoint = tenant.api_base + '/folders/'
  folders_list = []
  for team in teams_list:
    print(f'making folders for team: {team["name"]}')
    team_path = DATA_DIR / 'teams' / team['name']
    for content_name in CONTENT_MAP.values():
      content_path = team_path / content_name
      subfolders = get_folder_contents(content_path, type='FOLDER')
      content_type = CONTENT_MAP.inverse[content_name]

      for folder in subfolders:
        request_data = {
          'name': folder.name,
          'content_type': content_type,
          'team_id': team['id']
        }
        resp = requests.post(endpoint, json=request_data, headers=tenant.headers, verify=False)
        if not resp.ok:
          print(f'badresp! {resp}\n{resp.text}')
        else:
          folders_list.append(resp.json())

  return folders_list


def upload_story(file_data, team_id, folder_id=None):
  endpoint = tenant.api_base + '/stories/import/'
  story_name = file_data['name']
  request_data = {
    'new_name': story_name,
    'data': file_data,
    'team_id': team_id,
    'folder_id': folder_id
  }
  #pprint(request_data)
  resp = requests.post(endpoint, json=request_data, headers=tenant.headers, verify=False)
  if not resp.ok:
    print(f'badresp! {resp}\n{resp.text}')  


def upload_resource(file_data, team_id, folder_id=None):
  # cannot use the resource file's team_id, folder_id
  endpoint = tenant.api_base + '/global_resources/'

  if is_json_string(file_data['value']):
    value = json.loads(file_data['value'])
  else:
    value = file_data['value']

  request_data = {
    'name': file_data['name'],
    'value': value,
    'description': file_data['description'],
    'read_access': file_data['read_access'],
    'team_id': team_id,
    'folder_id': folder_id
  }
  
  resp = requests.post(endpoint, json=request_data, headers=tenant.headers, verify=False)
  if not resp.ok:
    print(f'badresp! {resp}\n{resp.text}')


def upload_credential(file_data, team_id, folder_id=None):
  # cannot use the credfile's team_id, folder_id
  # we are only using TEXT-type at present, but credential can have a lot of other fields!
  # because of this, will try and just take off team_id, folder_id and pass the rest of the dict direct to API
  endpoint = tenant.api_base + '/user_credentials/'

  request_data = file_data
  request_data['team_id'] = team_id
  request_data['folder_id'] = folder_id
  request_data['value'] = str(uuid.uuid1())  #random value, see notes at top
  
  for bad_key in ['id', 'slug', 'created_at', 'updated_at']:
    request_data.pop(bad_key, None)

  if file_data['mode'] != 'TEXT':
    print('WARNING! NON-TEXT CREDENTIAL DETECTED! skipping...')
  else:
    resp = requests.post(endpoint, json=request_data, headers=tenant.headers, verify=False)
    if not resp.ok:
      print(f'badresp! {resp}\n{resp.text}') 


def manage_file_upload(content_name, file_data, team_id, folder_id=None):
  # directory for functions based on content_name
  # ideally we dont go inside file_data payloads within this function
  if content_name == "user_credentials":
    upload_credential(file_data, team_id, folder_id)
  elif content_name == "stories":
    upload_story(file_data, team_id, folder_id)
  elif content_name == "global_resources":
    upload_resource(file_data, team_id, folder_id)


def get_matching_folder_id(subfolder, folders_list, team):
  for folder in folders_list:
    if folder['name'] == subfolder.name and folder['team_id'] == team['id']:
      return folder['id']
  return None


def upload_all_items(content_name, team, folders_list):
  content_path = DATA_DIR / 'teams' / team['name'] / content_name
  #outer files (no folder id)
  top_level_files = get_folder_contents(content_path, type='FILE')
  for filepath in top_level_files:
    file_data = read_json(filepath)
    manage_file_upload(content_name, file_data, team['id'])

  # nested files (needs folder id)
  subfolders = get_folder_contents(content_path, type='FOLDER')
  for subfolder in subfolders:
    # first map-back the folder id,
    # then read the files and handle the uploads
    #folder_id = [x['id'] for x in folders_list if subfolder.name == x['name']][0]
    # this list comp is returning multiple items
    # I think it's because we're not checking both TEAM and FOLDERNAME
    folder_id = get_matching_folder_id(subfolder, folders_list, team)
    subfolder_files = get_folder_contents(subfolder, type='FILE')
    for filepath in subfolder_files:
      file_data = read_json(filepath)
      manage_file_upload(content_name, file_data, team['id'], folder_id)


def create_user(file_data):
  # NOTE: single User records are duplicated because they can be Members of multiple teams
  #   if possible, avoid the duplication of requests
  # waiting on FR to be able to assign Team membership from /admin/users (not ideal actually)

  # create the user: Once
  # assign ('invite') the user to teams: Multiple

  endpoint = tenant.api_base + '/admin/users'
  request_data = {
    'email': file_data['email'],
    'first_name': file_data['first_name'],
    'last_name': file_data['last_name'],
    'admin': file_data['admin']
  }

  resp = requests.post(endpoint, json=request_data, headers=tenant.headers, verify=False)
  if not resp.ok:
    print(f'badresp! {resp}\n{resp.text}')
  else:
    return resp.json()


def invite_to_teams(new_user_id, user_file_data, teams_list):
  #use user_id - comes from create_user()
  results = []
  new_team_ids = [x['id'] for x in teams_list if x['name'] in user_file_data['teams']]
  for team_id in new_team_ids:
    this_endpoint = tenant.api_base + f'/teams/{team_id}/invite_member'
    request_data = {'user_id': new_user_id}
    resp = requests.post(this_endpoint, json=request_data, headers=tenant.headers, verify=False)
    if not resp.ok:
        print(f'badresp! {resp}\n{resp.text}')
    else: 
      results.append({'user_id': new_user_id, 'team_id': team_id, 'resp': resp.json()})
  return results


def upload_all_users(teams_list):
  user_path = DATA_DIR / 'users'
  user_files = get_folder_contents(user_path, 'FILE')

  for filepath in user_files:
    user_file_data = read_json(filepath)
    if user_file_data['email'] == MY_USER:
      print('skipping upload of MY_USER')
    else:
      create_response = create_user(user_file_data)
      new_user_id = create_response['id']
      if not TESTING:
        results = invite_to_teams(new_user_id, user_file_data, teams_list)
        pprint({'invite_to_team results': results})


def main():
  reset_instance()

  teams_list = make_teams()
  pprint({'TEAMS_LIST': teams_list})
  folders_list = make_folders(teams_list)
  pprint({'FOLDERS_LIST': folders_list})
  
  for team in teams_list:
    for content_name in CONTENT_MAP.values():
      print(f'initiate upload_all_items for team:{team}, content_name:{content_name}')
      upload_all_items(content_name, team, folders_list)

  upload_all_users(teams_list)


if __name__ == '__main__':
    main()





