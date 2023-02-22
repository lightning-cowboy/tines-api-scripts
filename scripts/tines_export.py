import requests
import json
import pathlib
import shutil
from pprint import pprint
from tines_lib import *
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# {item_name}_resp includes `meta` dict, {item_name}_data does not.
# Members should not be folderized!
# Annotations don't live in folders at present (https://docusign.slack.com/archives/C036Z3P3TS6/p1659563043606879) 
# update: Annotations/Notes seem to be part of exported Stories now

#TODO: refactor to use Tenant.load_remote_data()

#API_BASE = "https://wispy-bird-8048.tines.com/api/v1"
#HEADERS = {
#    "x-user-email": "jonathan.dycaico@docusign.com",
#    "x-user-token": "2-P6KcozwEEs82DGzh73"
#}


def create_folders(teams_list, folders_list):
# Folder structure: teams > Team > Content-type > Named-folder; users
    #make main folders
    teams_folder_path = DATA_DIR / 'teams'
    teams_folder_path.mkdir()
    users_folder_path = DATA_DIR / 'users'
    users_folder_path.mkdir()

    paths_map = {}
    paths_map['users'] = users_folder_path
    for team in teams_list:
        team_path = teams_folder_path / team['name']
        team_path.mkdir()
        paths_map[f'{team["id"]}'] = team_path
        for content_name in CONTENT_MAP.values(): #CF_MAP.values(): - do we need a folder for Members?
            content_path = team_path / content_name
            content_path.mkdir()
            paths_map[f'{team["id"]}:{content_name}'] = content_path
            for folder in folders_list:
                if folder['team_id'] == team['id']:
                    if CONTENT_MAP[folder['content_type']] == content_name:
                        folder_path = content_path / folder['name']
                        folder_path.mkdir()
                        paths_map[f'{team["id"]}:{folder["id"]}'] = folder_path
    return paths_map



def save_to_folders(content_type, item_list, paths_map, enriched=False):
    failed_saves = []
    for item in item_list:
        if ('folder_id') in item.keys() and item['folder_id'] is not None:
            path_key = f'{item["team_id"]}:{item["folder_id"]}'
        else: 
            path_key = f'{item["team_id"]}:{content_type}'

        if path_key in paths_map.keys():
            parent_folder = paths_map[path_key]
            stem = item["slug"] if 'slug' in item else str(item['id'])
            filepath = parent_folder / f'{stem}.json'
            file_content = item['file_json'] if enriched==True else item
            save_json(filepath, file_content)
            
        else:
            failed_saves.append({'id': item['id'], 'path_key': path_key})
            # the drafts/samples may show up in Teams in future versions of API
    
    if len(failed_saves) > 0:
        pprint({"failed_saves": {f'{content_type}': failed_saves}})


def save_user_data(enriched_users_list, paths_map):
    users_folder_path = paths_map['users']
    for user_entry in enriched_users_list:
        user_id = user_entry['id']
        filepath = users_folder_path / f'{user_id}.json'
        save_json(filepath, user_entry)

def main():
    reset_folder(DATA_DIR)
    tenant = Tenant.create_by_name('wispy-bird')
    print(tenant)

    tenant.load_remote_data()
    print(tenant.list_all_attributes())

    paths_map = create_folders(tenant.get_readonly('teams'), tenant.get_readonly('folders'))
    pprint(paths_map)
    
    enriched_users_list = enrich_user_teams(tenant.get_readonly('users'), tenant.get_readonly('teams'), tenant)

    pprint(enriched_users_list)
    save_user_data(enriched_users_list, paths_map)

    enriched_stories_list = enrich_stories(tenant.get_readonly('stories'), tenant)
    save_to_folders('stories', enriched_stories_list, paths_map, enriched=True)
    save_to_folders('global_resources', tenant.get_readonly('global_resources'), paths_map)
    save_to_folders('user_credentials', tenant.get_readonly('user_credentials'), paths_map)

if __name__ == '__main__':
    main()
