#!/usr/bin/python

import argparse
import json
import re
import urllib

import requests

# global
jira_epic = 'DO-8612'
api_root = 'https://jira.desk.technology/rest/api/2/'
headers = {'Content-type': 'application/json'}

parser = argparse.ArgumentParser('handle JIRA issues for Puppet alerts')
parser.add_argument('-u', '--user', required=True)
parser.add_argument('-p', '--password', required=True)
parser.add_argument('--dry-run', action='store_true')

args = parser.parse_args()
auth = (args.user, args.password)
dry_run = args.dry_run

def get_status(jira_issue):
    return jira_issue['fields']['status']['name']

def format_hosts(hosts):
    lines = ['Instances:']
    lines.extend('# ' + host for host in hosts)
    return '\n'.join(lines)

def format_summary(alert_name, severity):
    summary = 'Puppet alert:{} severity:{} (auto-generated)'
    return summary.format(alert_name, severity)

def set_field(jira_id, field, value, notify=False):
    params = {'notifyUsers' : notify}
    print('updating issue:{} field:{} value:"{}" notify={}'.format(jira_id, field, value, notify))
    payload = {'fields': {field: value}}
    request = {'url'    : api_root + 'issue/' + jira_id,
               'headers': headers,
               'auth'   : auth,
               'params' : params,
               'data'   : json.dumps(payload)}

    if not dry_run:
        response = requests.put(**request)
        response.raise_for_status()
        print('successfully updated issue')

def add_comment(jira_id, comment):
    uri = '{}issue/{}/comment'.format(api_root, jira_id)

    print('commenting on issue {}: text:{}'.format(jira_id, comment))
    request = {'url'    : uri,
               'headers': headers,
               'auth'   : auth,
               'data'   : json.dumps({'body': comment})}

    if not dry_run:
        response = requests.post(**request)
        response.raise_for_status()
        print('successfully commented')

def create_issue(summary, description):
    payload = {'fields':
               {'project'          : {'id' : '12635'}, # devops
                'issuetype'        : {'id' : '10109'}, # puppet
                'summary'          : summary,
                'description'      : description,
                'reporter'         : {'name' : 'cmcavoy'},
                'customfield_12120': jira_epic,
                'customfield_14120': {'value' : 'Devops'}}} # what field? 
    print('creating issue: ' + json.dumps(payload))
    
    request = {'url'    : api_root + 'issue',
               'headers': headers,
               'auth'   : auth,
               'data'   : json.dumps(payload)}
    
    if not dry_run:
        response = requests.post(**request)
        response.raise_for_status()
        print('successfully created issue')


transition_ids_by_name = {'In Progress': '911',
                          'Complete'   : '831',
                          'In Backlog' : '751'}

def set_status(jira_id, status_name):
    if not transition_ids_by_name.has_key(status_name):
        print('transition: {} not known (look up on JIRA and add to the script)'.format(status_name))
        sys.exit(1)

    transition_id = transition_ids_by_name[status_name]
    payload = {'transition': {'id': transition_id}}
    print('updating status of:{} to:{}'.format(jira_id, status_name))

    request = {'url:'   : api_root + 'issue/' + jira_id  + '/transitions',
               'headers': headers,
               'auth'   : auth,
               'data'   : json.dumps(payload)}
    
    if not dry_run:
        response = requests.post(**request)
        print(response.text)
        print('here')
        response.raise_for_status()
        print('successfully updated status')

def close_issue(jira_id, assignee):
    comment = assignee + 'closing issue {}'.format(jira_id)
    print('closing issue: {}'.format(jira_id))
    add_comment(jira_id, comment)
    set_status(jira_id, 'Complete')

def get_assignee(jira_issue):
    assignee = ''
    if jira_issue['fields']['assignee'] is not None:
        assignee = '@' + jira_issue['fields']['assignee']['key'] + ' '
    return assignee

query = urllib.urlencode({'jql'       : '"Epic Link"=' + jira_epic,
                          'startAt'   : 0,
                          'maxResults': 200})
epic_url = api_root + 'search?' + query
print('fetching epic: ' + epic_url)
epic_response = requests.get(epic_url, auth=auth)
epic_response.raise_for_status()
print('successfully fetched epic')

epic_json = epic_response.json()
epic_all_issues = epic_json['issues']
print('{} issues found in epic {}'.format(len(epic_all_issues), jira_epic))

def is_puppet(issue):
    summary = issue['fields']['summary']
    return summary.startswith('Puppet alert:')\
        and summary.endswith('(auto-generated)')

puppet_issues = [i for i in epic_all_issues if is_puppet(i)]
puppet_issues_by_id = {i['key']: i for i in puppet_issues}

summary_pat = re.compile('^Puppet alert:.* severity:.* \(auto-generated\)$')

#create_issue('Puppet alert:this is a test issue please ignore (auto-generated)', 'Test description, ignore.')
print(puppet_issues)
print(puppet_issues_by_id)
