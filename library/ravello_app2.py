#!/usr/bin/python

# (c) 2015, ravellosystems
# 
# author zoza
#
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

######################################################################

import random, string

try:
    from ravello_sdk import *
    HAS_RAVELLO_SDK = True
except ImportError:
    HAS_RAVELLO_SDK = False

except ImportError:
    print "failed=True msg='ravello sdk required for this module'"
    sys.exit(1)

from ravello_cli import get_diskimage

DOCUMENTATION = '''
---
module: ravello_app
short_description: Create/delete/start/stop an application in ravellosystems
description:
     - Create/delete/start/stop an application in ravellosystems and wait for it (optionally) to be 'running'
     - list state will return a fqdn list of exist application hosts with their external services
     - blueprint state wil create a blueprint from an existing app (must provide blueprint_name)
options:
  state:
    description:
     - Indicate desired state of the target.
    default: present
    choices: ['design', 'present', 'started', 'absent', 'stopped','list','blueprint']
  username:
     description:
      - ravello username
  password:
    description:
     - ravello password
  service_name: 
  	description:
     - Supplied Service name for list state 
    default: ssh
  name:
    description:
     - application name
  description:
    description:
     - application description
  blueprint_id:
    description:
     - create app, based on this blueprint
  #publish options
  cloud:
    description:
     - cloud to publish
  region:
    description:
     - region to publish
  publish_optimization:
    default: cost
    choices: ['cost', 'performance']
  application_ttl:
    description:
     - application autostop in mins
    default: -1 # never
  wait
    description:
     - Wait for the app to be in state 'running' before returning.
    default: True
    choices: [ True, False ]
  wait_timeout:
    description:
     - How long before wait gives up, in seconds.
    default: 600
  blueprint_name:
    description:
     - Specify a name for a new blueprint based on existing app
  blueprint_description:
    description:
     - Description of new blueprint 
  app_template:
    description:
     - Path to a YML file that defines an application infrastructure then creates a blueprint for further processing with follow-on playbooks.  Must use state=design
'''

EXAMPLES = '''
# Create app, based on blueprint, start it and wait for started
- local_action:
    module: ravello_app
    username: user@ravello.com
    password: password
    name: 'my-application-name'
    description: 'app desc'
    blueprint_id: '2452'
    wait: True
    wait_timeout: 600
    state: present
# Create app, based on blueprint
- local_action:
    module: ravello_app
    username: user@ravello.com
    password: password
    name: 'my-application-name'
    description: 'app desc'
    publish_optimization: performance
    cloud:AMAZON
    region: Oregon
    state: present
# List application example
- local_action:
    module: ravello_app
    name: 'my-application-name'
    service_name: 'ssh'
    state: list
# Delete application example
- local_action:
    module: ravello_app
    name: 'my-application-name'
    state: absent
# Create blueprint from existing app
- local_action:
    module: ravello_app
    name: 'my-application-name'
    blueprint_name: 'my-application-bp'
    blueprint_description: 'Blueprint of app xyz'
    state: blueprint
# Create blueprint based on app_template.yml
- local_action:
    module: ravello_app
    name: 'my-new-baseline'
    description: 'My new baseline'
    app_template: 'app_template.yml'
    state: design
  register: design_results
'''

import os
import base64
import getpass
import logging
import logging.handlers

def get_credentials():
        with open(os.path.expanduser("~/.ravello_login"),"r") as pf:
                username = pf.readline().strip()
                encrypted_password = pf.readline().strip()
        password = base64.b64decode(encrypted_password).decode()
        return username,password

def get_user_credentials(username):

        password = None

        if username:
                password = getpass.getpass('Enter a Password: ')
        else:
                #read user credentials from .ravello_login file in user HOMEDIR
                username,password = get_credentials()

        if not username or not password:
                log.error('User credentials are not set')
                print('Error: User credentials are not set')
                return None,None

        return username,password

def initlog(log_file):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logpath=os.path.join(os.getcwd(),log_file)
        handler = logging.handlers.RotatingFileHandler(logpath, maxBytes=1048576, backupCount=10)
        fmt = '%(asctime)s: %(filename)-20s %(levelname)-8s %(message)s'
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

def connect(username, password):
        client = RavelloClient()
        try:
                client.login(username, password)
        except Exception as e:
                sys.stderr.write('Error: {!s}\n'.format(e))
                log.error('Invalid user credentials, username {0}'.format(username))
                print('Error: Invalid user credentials, username {0}'.format(username))
                return None
        return client

def get_app_id(app_name,client):
        app_id=0
        for app in client.get_applications():
                if app['name'].lower() == app_name.lower():
                        app_id = app['id']
                        break
        if app_id == 0:
          module.fail_json(msg = 'ERROR: Cloud not find app: %s' % app_name)
        return app_id

def get_blueprint_id(blueprint_name,client):
        blueprint_id=0
        for blueprint in client.get_blueprints():
                if blueprint['name'].lower() == blueprint_name.lower():
                        blueprint_id = blueprint['id']
                        break
        if blueprint_id == 0:
          module.fail_json(msg = 'ERROR: Cloud not find blueprint: %s' % blueprint_name)
        return blueprint_id

def get_image_id(image_name,client):
        image_id=0
        for image in client.get_images():
                if image['name'].lower() == image_name.lower():
                        image_id = image['id']
                        break
        if image_id == 0:
          module.fail_json(msg = 'ERROR: Cloud not find VM image named: %s' % image_name)
        return image_id

def get_image(image_id,client):
        try:
          image = client.get_image(image_id)
        except Exception as e:
          module.fail_json(msg = 'ERROR: Cloud not find VM image id: %s' % image_id)
        return image

def main():
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    ### Optionally add a formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    ### Add the console handler to the logger
    logger.addHandler(ch)    
    argument_spec=dict(
            # for nested babu only
            url=dict(required=False, type='str'),
            state=dict(default='present', choices=['design', 'present', 'started', 'absent', 'stopped', 'list', 'test', 'blueprint','blueprint_delete','blueprint_location']),
            username=dict(required=False, type='str'),
            password=dict(required=False, type='str'),
            name=dict(required=True, type='str'),
            description=dict(required=False, type='str'),
            blueprint_id=dict(required=False, type='str'),
            app_template=dict(required=False, default=None, type='path'),
            cloud=dict(required=False, type='str'),
            region=dict(required=False, type='str'),
            publish_optimization=dict(default='cost', choices=['cost', 'performance']),
            application_ttl=dict(default='-1', type='int'),
            service_name=dict(default='ssh', type='str'),
            blueprint_description=dict(required=False, type='str'),
            blueprint_name=dict(required=False, type='str'),
            wait=dict(type='bool', default=True ,choices=BOOLEANS),
            wait_timeout=dict(default=1200, type='int')
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=[['blueprint', 'app_template']],
        # We really really should support this...
        # supports_check_mode = True
    )
    if not HAS_RAVELLO_SDK:
        module.fail_json(msg='ravello_sdk required for this module')
    try:
        #username = module.params.get('username', os.environ.get('RAVELLO_USERNAME', None)) 
        #password = module.params.get('password', os.environ.get('RAVELLO_PASSWORD', None))
       # 
       # client = RavelloClient(username, password, module.params.get('url'))

        #Get user credentials
        username, password  = get_user_credentials(None)
        if not username or not password:
                exit(1)

        #Connect to Ravello
        client = connect(username, password)
        if not client:
                exit (1)
        if module.params.get('state') == 'design':
          create_app(client, module)
        elif module.params.get('state') == 'present':
          create_app_and_publish(client, module)
        elif module.params.get('state') == 'absent':
          action_on_app(module, client, client.delete_application, lambda: None, 'Deleted')
        elif module.params.get('state') == 'started':
          action_on_app(module, client, client.start_application, functools.partial(_wait_for_state,client,'STARTED',module), 'Started')
        elif module.params.get('state') == 'stopped':
          action_on_app(module, client, client.stop_application, functools.partial(_wait_for_state,client,'STOPPED',module), 'Stopped')
        elif module.params.get('state') == 'list':
          list_app(client, module)
        elif module.params.get('state') == 'blueprint':
          create_blueprint(module, client, client.create_blueprint)
        elif module.params.get('state') == 'blueprint_delete':
          action_on_blueprint(module, client, client.delete_blueprint)
        elif module.params.get('state') == 'blueprint_location':
          action_on_blueprint(module, client, client.get_blueprint_publish_locations)
        elif module.params.get('state') == 'test':
          module.exit_json(msg = 'Authentication to Ravello successful')
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)

def _wait_for_state(client, state, module):
    if module.params.get('wait') == False:
        return
    wait_timeout = module.params.get('wait_timeout')
    app_id = 0
    wait_till = time.time() + wait_timeout
    while wait_till > time.time():
        if app_id > 0:
            app = client.get_application(app_id)
        else:
            app =  client.get_application_by_name(module.params.get('name'))
            app_id = app['id']
        states = list(set((vm['state'] for vm in app.get('deployment', {}).get('vms', []))))
        if "ERROR" in states:
            log_contents = log_capture_string.getvalue()
            log_capture_string.close()
            module.fail_json(msg = 'Vm got ERROR state',stdout='%s' % log_contents)
        if len(states) == 1 and states[0] == state:
            return
        time.sleep(10)
    log_contents = log_capture_string.getvalue()
    log_capture_string.close()
    module.fail_json(msg = 'Timed out waiting for async operation to complete.',  stdout='%s' % log_contents)

def is_wait_for_external_service(supplied_service,module):
    return supplied_service['name'].lower() == module.params.get('service_name').lower() and supplied_service['external'] == True

def get_list_app_vm_result(app, vm, module):
   
    for supplied_service in vm['suppliedServices']:            
    	if is_wait_for_external_service(supplied_service, module):
            for network_connection in vm['networkConnections']:
                if network_connection['ipConfig']['id'] == supplied_service['ipConfigLuid']:
                    dest = network_connection['ipConfig'].get('fqdn')
                    port = int(supplied_service['externalPort'].split(",")[0].split("-")[0])
                    return (dest,port)
	            
def list_app(client, module):
    try:
        app_name = module.params.get("name")
        app = client.get_application_by_name(app_name)
        
        results = []
        
        for vm in app['deployment']['vms']:
            if vm['state'] != "STARTED":
                continue
            (dest,port) = get_list_app_vm_result(app, vm, module)
            results.append({'host': dest, 'port': port})
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.exit_json(changed=True, name='%s' % app_name, results='%s' % results,stdout='%s' % log_contents)
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)

def create_blueprint(module, client, runner_func):
    app_name = module.params.get("name")
    app = client.get_application_by_name(app_name)
    blueprint_name = module.params.get("blueprint_name")
    blueprint_description = module.params.get("blueprint_description")
    blueprint_dict = {"applicationId":app['id'], "blueprintName":blueprint_name, "offline": True,  "description":blueprint_description }
    try:
        blueprint_id=((runner_func(blueprint_dict))['_href'].split('/'))[2]
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.exit_json(changed=True, name='%s' % app_name, blueprint_id='%s' % blueprint_id)
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)        

def action_on_blueprint(module, client, runner_func):
    if module.params.get("blueprint_id"):
      blueprint_id = module.params.get("blueprint_id")
    elif module.params.get("blueprint_name"):
      blueprint_name = module.params.get("blueprint_name")
      blueprint_id = get_blueprint_id(blueprint_name, client)
    try:
        output = runner_func(blueprint_id)
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.exit_json(changed=True, name='%s' % blueprint_name,stdout='%s' % log_contents, blueprint_id='%s' % blueprint_id, output='%s' % output)
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)        

def create_app(client, module):
    app_name = module.params.get("name")
    app_description = module.params.get("description")
    if not module.params.get("app_template"):
        module.fail_json(msg='Must supply an app_template for design state.', changed=False)
    app_template = module.params.get("app_template")
    with open(app_template, 'r') as data:
      try:
        read_app = yaml.load(data)
      except yaml.YAMLError as exc:
        print(exc)
    rand_str = lambda n: ''.join([random.choice(string.lowercase) for i in xrange(n)])
    app = []
    new_app = app['design']
    new_app['name'] = "tmp-app-build-" + rand_str(10)
    new_app['description'] = app_description
    for vm in read_app['vms']:
      if vm['tag']:
        desc = "tag:" + vm['tag'] + "\n"
        vm['description'] = vm['description'] + "\n" + desc
      new_vm = {'name': vm['name'],
                'description': vm['description'],
                'os': 'linux_manuel',
                'baseVmId': 0,
                'numCpus': vm['numCpus']
               }
      new_vm['memorySize']['unit'] = vm['memorySize']['unit']
      new_vm['memorySize']['value'] = vm['memorySize']['value']
      if vm['keypairName']:
        new_vm['keypairName'] = vm['keypairName']
      if vm['supportsCloudInit']:
        new_vm['supportsCloudInit'] = True
      if vm['allowNested']:
        new_vm['allowNested'] = True
      drives = new_vm['hardDrives'] = []
      for hd in vm['hardDrives']:
        new_drive = { 'index': hd['index'],
                      'type': hd['type'],
                      'boot': hd['boot'],
                      'controller': hd['controller'],
                      'name': hd['name'],
                    }
        new_drive['size']['unit'] = hd['size']['unit']
        new_drive['size']['value'] = hd['size']['value']
        if hd['baseDiskImageId']:
          new_drive['baseDiskImageId'] = hd['baseDiskImageId']
        elif hd['imageName']:
          image_id = get_diskimage(client, hd['imageName'])
          if image_id is None:
            module.fail_json(msg = 'FATAL ERROR no such disk image %s' % hd['imageName'])
          new_drive['baseDiskImageId'] = image_id
        drives.append(new_drive)
      connections = new_vm['networkConnections'] = []
      for nic in vm['networkConnections']:
        supsvc = False
        new_nic = { 'name': nic['name'] }
        new_nic['device'] = { 'index': nic['device']['index'],
                              'deviceType': nic['device']['deviceType']
                            }
        if nic['device']['useAutomicMac']:
          new_nic['device']['useAtomaticMac'] = True
        else:
          new_nic['device']['mac'] = nic['device']['mac']
        if nic['ipConfig']['autoIpConfig']:
          new_nic['ipConfig']['autoIpConfig'] = { 'reservedIp': nic['ipConfig']['autoIpConfig']['reservedIp'] }
        elif nic['ipConfig']['staticIpConfig']:
          new_nic['ipConfig']['staticIpConfig'] = { 'ip': nic['ipConfig']['autoIpConfig']['ip'],
                                                    'mask': nic['ipConfig']['autoIpConfig']['mask']
                                                  }
          if nic['ipConfig']['staticIpConfig']['gateway']:
            new_nic['ipConfig']['staticIpConfig']['gateway'] = nic['ipConfig']['staticIpConfig']['gateway']
          if nic['ipConfig']['staticIpConfig']['dns']:
            new_nic['ipConfig']['staticIpConfig']['dns'] = nic['ipConfig']['staticIpConfig']['dns']
        if nic['ipConfig']['hasPublicIp']:
          new_nic['ipConfig']['hasPublicIp'] = True
          supsvc = True
        connections.append(new_nic)
      if supsvc:
        services = new_vm['suppliedServices'] = []
        for svc in vm['suppliedServices']:
          new_svc = { 'external': True,
                      'name': svc['name'],
                      'ip': svc['ip'],
                      'portRange': svc['portRange']
                    }
          if svc['protocol']:
            new_svc['protocol'] = svc['protocol']
          services.append(new_svc)
      new_app.append(new_vm)
    print "-------------------"
    print(new_app)
    print "-------------------"
    module.exit_json(changed=False, name='DEBUG %s' % app_name)
    try:
        created_app = client.create_application(new_app)
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)
    appID = created_app['id']
    blueprint_name = app_name + "-bp"
    blueprint_dict = {"applicationId":appID, "blueprintName":blueprint_name, "offline": False, "description":app_description }
    try:
        blueprint_id=((client.create_blueprint(blueprint_dict))['_href'].split('/'))[2]
        client.delete_application(created_app)
        module.exit_json(changed=True, name='%s' % app_name, blueprint_id='%s' % blueprint_id)
    except Exception, e:
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        module.fail_json(msg = '%s' % e,stdout='%s' % log_contents)

def create_app_and_publish(client, module):
    #validation
    if not module.params.get("blueprint_id"):
            module.fail_json(msg='Must supply a blueprint_id', changed=False)
    if 'performance' == module.params.get("publish_optimization"):
        if not module.params.get("cloud"):
            module.fail_json(msg='Must supply a cloud when publish optimization is performance', changed=False)
        if not module.params.get("region"):
            module.fail_json(msg='Must supply a region when publish optimization is performance', changed=False)
    app = {'name': module.params.get("name"), 'description': module.params.get("description",''), 'baseBlueprintId': module.params.get("blueprint_id")}    
    app = client.create_application(app)
    req = {}
    if 'performance' == module.params.get("publish_optimization"):
        req = {'id': app['id'] ,'preferredCloud': module.params.get("cloud"),'preferredRegion': module.params.get("region"), 'optimizationLevel': 'PERFORMANCE_OPTIMIZED'}
    ttl=module.params.get("application_ttl")
    if ttl != -1:
        ttl =ttl * 60
        exp_req = {'expirationFromNowSeconds': ttl}
        client.set_application_expiration(app,exp_req)
    client.publish_application(app, req)
    _wait_for_state(client,'STARTED',module)
    log_contents = log_capture_string.getvalue()
    log_capture_string.close()
    module.exit_json(changed=True, name='%s' % module.params.get("name"),stdout='%s' % log_contents, app_id='%s' % app['id'])

# import module snippets
import ansible
import os
import functools
import logging
import io
import datetime
import sys
import yaml
import json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_capture_string = io.BytesIO()

from ansible.module_utils.basic import *

main()
