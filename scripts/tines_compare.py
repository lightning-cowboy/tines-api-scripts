
from urllib3.exceptions import InsecureRequestWarning
from tines_lib import *
import logging
import re
import requests
import inspect
logging.basicConfig(level=logging.INFO)

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Here we compare the contents of 2x tenants
# ATM `tenant` variables are hashes
# list of size two

TESTING = False

COMPARE_DIR = pathlib.Path('../compare').resolve()
BAD_FIELDS = ['id', 'guid', 'user_id', 'team_id',
              'folder_id', 'created_at', 'updated_at', 'last_seen']

tenants_for_compare = [
    Tenant.create_by_name('tines-prod'),
    Tenant.create_by_name('tines-dev')
]


def get_team_name(team_id, tenant):
    teams_mapper = {x['id']: x['name']
                    for x in tenant.get_readonly('teams')}  # dict comp
    try:
        return teams_mapper[team_id]
    except KeyError:
        return None  # personal team for unpublished stories/resources etc


def get_folder_name(folder_id, tenant):
    if folder_id is not None:
        folder_mapper = {x['id']: x['name']
                         for x in tenant.get_readonly('folders')}
        return folder_mapper[folder_id]
    else:
        return None


def enrich_content(content_data, content_name, tenant):
    #print(f'in enrich_content: content_name={content_name}')
    items_to_drop = []
    for item in content_data:
        if 'team_id' in item:
            team_name = get_team_name(item['team_id'], tenant)
            if not team_name:
                items_to_drop.append(item)
            else:
                item['team_name'] = team_name
        if 'folder_id' in item:
            item['folder_name'] = get_folder_name(item['folder_id'], tenant)
    content_data = [x for x in content_data if x not in items_to_drop]
    return content_data


def clean_content(content_data, content_name):
    for item in content_data:
        for field in BAD_FIELDS:
            item.pop(field, None)
        if TESTING == True:
            if content_name == 'users':
                item.pop('teams')
    return content_data


def sort_content(content_data, content_name):
    if content_name in ['folders', 'teams']:
        sort_field = 'name'
    elif content_name == 'users':
        sort_field = 'email'
    else:
        sort_field = 'slug'
    content_sorted = sorted(content_data, key=lambda x: x[sort_field])
    return content_sorted


# skip enrichment for stories
# instead, recurse thru all levels of hash
# and attempt-pop all BAD_KEYS[]
def drop_badkeys_recursive(container):
    # we drop 'form' becuase it's a duplicate of 'forms' (https://docusign.slack.com/archives/C036Z3P3TS6/p1666221998101539)
    bad_keys = ['agent_guid', 'diagram_layout', 'entry_agent_guid', 'entry_agent_id', 'exit_agent_guid', 'exit_agent_guids', 'exit_agent_id',
                'exit_agents', 'exported_at', 'form', 'guid', 'path', 'published', 'recipients', 'secret', 'story_container', 'tenant_id', 'url', 'width', 'locked']
    print('⤋ down a level ⤋')
    if isinstance(container, dict):
        for key in bad_keys:
            if key in container:
                pprint(container)
        for key, val in list(container.items()):
            print(f'key:{key.upper()} - {type(val)}')
            if key in bad_keys:
                print('🔥')
                container.pop(key, None)
            if isinstance(val, dict) or isinstance(val, list):
                #print(f'entering iterthru for {key}')
                drop_badkeys_recursive(val)

    elif isinstance(container, list):
        for i in list(container):
            if isinstance(i, dict) or isinstance(i, list):
                #print(f'entering iterthru for {i}')
                drop_badkeys_recursive(i)

def sort_any_list(items):
  if len(items) > 0:
    distinct_types = set([type(i) for i in items])
    # check that list is uniformly-typed
    if len(distinct_types) == 1:
      type_of_list = type(items[0])
      if isinstance(items[0], dict):
        items.sort(key=lambda d: d.keys())  # or d.items() or something
      else:
        items.sort()


def deepclean_recursive(container):
    # we drop 'form' becuase it's a duplicate of 'forms' (https://docusign.slack.com/archives/C036Z3P3TS6/p1666221998101539)
    bad_keys = ['agent_guid', 'diagram_layout', 'entry_agent_guid', 'entry_agent_id', 'exit_agent_guid', 'exit_agent_guids', 'exit_agent_id',
                'exit_agents', 'exported_at', 'form', 'guid', 'links', 'path', 'recipients', 'secret', 'send_to_stories', 'story_container', 'tenant_id', 'url'] #'published', 
    print('⤋ down a level ⤋')
    if isinstance(container, dict):
        for key in bad_keys:
            if key in container:
                pprint(container)
        for key, val in list(container.items()):
            print(f'key:{key.upper()} - {type(val)}')
            if key in bad_keys:
                print('🔥')
                container.pop(key, None)
            if isinstance(val, dict) or isinstance(val, list):
                #print(f'entering iterthru for {key}')
                deepclean_recursive(val)

    elif isinstance(container, list):
        #sort_any_list(container)
        for i in list(container):
            if isinstance(i, dict) or isinstance(i, list):
                #print(f'entering iterthru for {i}')
                deepclean_recursive(i)


def enrich_story_containers(stories, tenant):
    # entry_agent_id -> entry_agent_name (enrich)
    # exit_agents = [6] -> replace each with agent_name (enrich)
    for story in stories:
        if 'story_container' in story:
            story_container = story['story_container']
            if 'folder_id' in story_container:
                folder_id = story_container['folder_id']
                story_container['folder_name'] = get_folder_name(
                    folder_id, tenant)
                story_container.pop('folder_id', None)
            story_container.pop('published', None)
    return stories


def get_sorted_dict(fields):
    fields_sorted = sorted(fields, key=lambda x: x['name'])
    fields_dict = dict(enumerate(fields_sorted))
    return fields_dict


def sort_story_forms(stories):
    # I would rly rather not have to track indexes and such
    # However, I believe I cannot modify the object inplace to the right output

    # need to cover this as well:
    # stories[i]['file_json']['send_to_stories'][j]['forms'][k]['fields']

    for i in range(len(stories)):  # list
        if 'forms' in stories[i]['file_json']:
            for j in range(len(stories[i]['file_json']['forms'])):
                if 'fields' in stories[i]['file_json']['forms'][j]:
                    fields = stories[i]['file_json']['forms'][j]['fields']
                    stories[i]['file_json']['forms'][j]['fields'] = get_sorted_dict(
                        fields)

        if 'send_to_stories' in stories[i]['file_json']:
            for j in range(len(stories[i]['file_json']['send_to_stories'])):
                if 'forms' in stories[i]['file_json']['send_to_stories'][j]:
                    for k in range(len(stories[i]['file_json']['send_to_stories'][j]['forms'])):
                        if 'fields' in stories[i]['file_json']['send_to_stories'][j]['forms'][k]:
                            fields = stories[i]['file_json']['send_to_stories'][j]['forms'][k]['fields']
                            stories[i]['file_json']['send_to_stories'][j]['forms'][k]['fields'] = get_sorted_dict(
                                fields)

    return stories


def main():
    # keep the original data attributes on the Tenant
    # use getattr(cls, 'fields')['key'] = 'value' to add dict keys

    # clean includes enrichment, because in order to remove IDs we need their names
    # enrich needs Tenant because get_*_name requires tenant

    reset_folder(COMPARE_DIR)

    for tenant in tenants_for_compare:
        print(tenant.name)
        tenant.load_remote_data()
        print(tenant.list_primary_data_attributes())
        pprint(tenant.get_readonly('teams'))

        for content_name in tenant.list_primary_data_attributes():
            content_data = tenant.get_readonly(content_name)
            content_enriched = enrich_content(
                content_data, content_name, tenant)
            content_enriched_clean = clean_content(
                content_enriched, content_name)
            pprint(content_enriched)
            content_final = sort_content(content_enriched_clean, content_name)

            #save_json((COMPARE_DIR / f'{tenant.name}_stdproc.json'), content_final)
        
            if content_name == 'stories':
                stories_enriched = enrich_story_containers(
                    content_final, tenant)
                deepclean_recursive(stories_enriched)
                stories_enriched_sorted = sort_story_forms(stories_enriched)
                tenant.set_compare_data('stories', stories_enriched_sorted)
            else:
                tenant.set_compare_data(content_name, content_final)

        save_json((COMPARE_DIR / f'{tenant.name}.json'),
                  tenant.get_readonly('compare_data'))

    print('equal?')
    print(tenants_for_compare[0].get_readonly(
        'compare_data') == tenants_for_compare[1].get_readonly('compare_data'))


if __name__ == '__main__':
    main()
