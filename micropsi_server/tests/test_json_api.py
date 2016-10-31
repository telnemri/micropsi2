
import pytest
import json
import re


def assert_success(response):
    assert response.json_body['status'] == 'success'
    assert 'data' in response.json_body


def assert_failure(response):
    assert response.json_body['status'] == 'error'
    assert 'data' in response.json_body


def test_generate_uid(app):
    response = app.get_json('/rpc/generate_uid()')
    assert_success(response)
    assert re.match('[a-f0-9]+', response.json_body['data']) is not None


def test_create_and_invalidate_auth_token(app):
    response = app.get_json('/rpc/create_auth_token(user="Pytest User",password="test")')
    assert_success(response)
    from micropsi_server.micropsi_app import usermanager
    token = response.json_body['data']
    assert token in usermanager.users['Pytest User']['sessions']
    response = app.get_json('/rpc/invalidate_auth_token(token="%s")' % token)
    assert_success(response)
    assert token not in usermanager.users['Pytest User']['sessions']


def test_get_nodenet_metadata(app, test_nodenet, node):
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    data = response.json_body['data']
    assert 'nodetypes' in data
    assert 'native_modules' in data
    assert 'engine' in data
    assert 'nodespaces' in data
    assert 'nodes' not in data
    assert 'links' not in data
    assert data['current_step'] == 0
    assert data['uid'] == test_nodenet


def test_new_nodenet(app, engine):
    app.set_auth()
    response = app.post_json('/rpc/new_nodenet', params={
        'name': 'FooBarTestNet',
        'engine': engine
    })
    assert_success(response)
    uid = response.json_body['data']
    assert uid is not None
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % uid)
    assert_success(response)
    assert response.json_body['data']['name'] == 'FooBarTestNet'
    assert response.json_body['data']['engine'] == engine


def test_get_available_nodenets(app, test_nodenet):
    response = app.get_json('/rpc/get_available_nodenets(user_id="Pytest User")')
    assert_success(response)
    assert test_nodenet in response.json_body['data']


def test_delete_nodenet(app, test_nodenet):
    response = app.get_json('/rpc/delete_nodenet(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    response = app.get_json('/rpc/get_available_nodenets(user_id="Pytest User")')
    assert test_nodenet not in response.json_body['data']


def test_set_nodenet_properties(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, nodenet_name="new_name", worldadapter="Braitenberg", world_uid=test_world))
    assert_success(response)
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert data['name'] == 'new_name'
    assert data['worldadapter'] == 'Braitenberg'


def test_set_node_state(app, test_nodenet, resourcepath):
    import os
    app.set_auth()
    # create a native module:

    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "gatetypes": ["gen", "foo", "bar"],
            "symbol": "t"}}""")

    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")

    response = app.get_json('/rpc/reload_native_modules()')
    assert_success(response)

    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Testnode',
        'position': [23, 23, 12],
        'nodespace': None,
        'name': 'Testnode'
    })
    assert_success(response)

    uid = response.json_body['data']

    response = app.post_json('/rpc/set_node_state', params={
        'nodenet_uid': test_nodenet,
        'node_uid': uid,
        'state': {'foo': 'bar'}
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    assert response.json_body['data']['nodes'][uid]['state'] == {'foo': 'bar'}


def test_set_node_activation(app, test_nodenet, node):
    response = app.post_json('/rpc/set_node_activation', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'activation': '0.734'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    activation = response.json_body['data']['nodes'][node]['activation']
    assert float("%.3f" % activation) == 0.734


def test_start_calculation(app, default_nodenet):
    app.set_auth()
    response = app.post_json('/rpc/start_calculation', params=dict(nodenet_uid=default_nodenet))
    assert_success(response)
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % default_nodenet)
    assert response.json_body['data']['is_active']


def test_start_calculation_with_condition(app, default_nodenet):
    import time
    app.set_auth()
    app.post_json('/rpc/set_runner_properties', params={
        'timestep': 10,
        'factor': 1
    })
    response = app.post_json('/rpc/set_runner_condition', params={
        'nodenet_uid': default_nodenet,
        'steps': '2'
    })
    assert_success(response)
    assert response.json_body['data']['step'] == 2
    response = app.post_json('/rpc/start_calculation', params=dict(nodenet_uid=default_nodenet))
    assert_success(response)
    time.sleep(1)
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % default_nodenet)
    assert not response.json_body['data']['is_active']
    assert response.json_body['data']['current_step'] == 2
    response = app.post_json('/rpc/remove_runner_condition', params=dict(nodenet_uid=default_nodenet))
    assert_success(response)


def test_get_runner_properties(app):
    app.set_auth()
    response = app.get_json('/rpc/get_runner_properties()')
    assert_success(response)
    assert 'timestep' in response.json_body['data']
    assert 'factor' in response.json_body['data']


def test_set_runner_properties(app):
    app.set_auth()
    response = app.post_json('/rpc/set_runner_properties', params=dict(timestep=123, factor=1))
    assert_success(response)
    response = app.get_json('/rpc/get_runner_properties()')
    assert_success(response)
    assert response.json_body['data']['timestep'] == 123
    assert response.json_body['data']['factor'] == 1


def test_get_is_calculation_running(app, default_nodenet):
    response = app.get_json('/rpc/get_is_calculation_running(nodenet_uid="%s")' % default_nodenet)
    assert_success(response)
    assert not response.json_body['data']


def test_stop_calculation(app, default_nodenet):
    app.set_auth()
    response = app.post_json('/rpc/start_calculation', params=dict(nodenet_uid=default_nodenet))
    assert_success(response)
    response = app.get_json('/rpc/get_is_calculation_running(nodenet_uid="%s")' % default_nodenet)
    assert_success(response)
    assert response.json_body['data']
    response = app.post_json('/rpc/stop_calculation', params=dict(nodenet_uid=default_nodenet))
    assert_success(response)
    response = app.get_json('/rpc/get_is_calculation_running(nodenet_uid="%s")' % default_nodenet)
    assert_success(response)
    assert not response.json_body['data']


def test_step_calculation(app, default_nodenet):
    app.set_auth()
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % default_nodenet)
    assert response.json_body['data']['current_step'] == 0
    response = app.get_json('/rpc/step_calculation(nodenet_uid="%s")' % default_nodenet)
    assert_success(response)
    assert response.json_body['data'] == 1
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % default_nodenet)
    assert response.json_body['data']['current_step'] == 1


def test_get_calculation_state(app, test_nodenet, test_world, node):
    from time import sleep
    app.set_auth()
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    assert response.json_body['data']['current_step'] == 0
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, nodenet_name="new_name", worldadapter="Braitenberg", world_uid=test_world))

    response = app.post_json('/rpc/add_gate_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate': 'sub',
    })
    monitor_uid = response.json_body['data']

    response = app.get_json('/rpc/step_calculation(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)

    response = app.get_json('/rpc/start_calculation(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)

    sleep(1)
    response = app.post_json('/rpc/get_calculation_state', params={
        'nodenet_uid': test_nodenet,
        'nodenet': {
            'nodespaces': [None],
            'step': -1,
        },
        'monitors': {
            'logger': ['system', 'world', 'nodenet'],
            'after': 0,
            'monitor_from': 2,
            'monitor_count': 2
        },
        'world': {
            'step': -1
        }
    })

    data = response.json_body['data']

    assert data['current_nodenet_step'] > 0
    assert data['current_world_step'] > 0
    assert data['calculation_running']

    assert 'servertime' in data['monitors']['logs']
    assert 'logs' in data['monitors']['logs']
    assert len(data['monitors']['monitors'][monitor_uid]['values']) == 2

    assert test_nodenet in data['world']['agents']
    assert data['world']['current_step'] > 0


def test_revert_nodenet(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, nodenet_name="new_name", worldadapter="Braitenberg", world_uid=test_world))
    assert_success(response)
    response = app.get_json('/rpc/revert_nodenet(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert data['name'] == 'Testnet'
    assert data['worldadapter'] is None


def test_revert_both(app, test_nodenet, test_world):
    app.set_auth()
    app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, worldadapter="Braitenberg", world_uid=test_world))
    for i in range(5):
        app.get_json('/rpc/step_calculation(nodenet_uid="%s")' % test_nodenet)
    res = app.get_json('/rpc/get_calculation_state(nodenet_uid="%s")' % test_nodenet)
    assert res.json_body['data']['current_nodenet_step'] > 0
    assert res.json_body['data']['current_world_step'] > 0
    app.get_json('/rpc/revert_calculation(nodenet_uid="%s")' % test_nodenet)
    res = app.get_json('/rpc/get_calculation_state(nodenet_uid="%s")' % test_nodenet)
    assert res.json_body['data']['current_nodenet_step'] == 0
    assert res.json_body['data']['current_world_step'] == 0


def test_save_nodenet(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, nodenet_name="new_name", worldadapter="Braitenberg", world_uid=test_world))
    assert_success(response)
    response = app.get_json('/rpc/save_nodenet(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    response = app.get_json('/rpc/revert_nodenet(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert data['name'] == 'new_name'
    assert data['worldadapter'] == 'Braitenberg'

    # now delete the nodenet, to get default state back.
    app.get_json('/rpc/delete_nodenet(nodenet_uid="%s")' % test_nodenet)


def test_export_nodenet(app, test_nodenet, node):
    response = app.get_json('/rpc/export_nodenet(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    data = json.loads(response.json_body['data'])
    assert data['name'] == 'Testnet'
    assert data['nodes'][node]['type'] == 'Pipe'
    assert 'links' in data


def test_import_nodenet(app, test_nodenet, node):
    app.set_auth()
    response = app.get_json('/rpc/export_nodenet(nodenet_uid="%s")' % test_nodenet)
    data = json.loads(response.json_body['data'])
    del data['uid']
    response = app.post_json('/rpc/import_nodenet', params={
        'nodenet_data': json.dumps(data)
    })
    assert_success(response)
    uid = response.json_body['data']
    assert uid is not None
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % uid)
    assert response.json_body['data']['name'] == data['name']
    assert response.json_body['data']['world'] == data['world']
    assert response.json_body['data']['worldadapter'] == data['worldadapter']
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % uid)
    assert list(response.json_body['data']['nodes'].keys()) == [node]
    response = app.get_json('/rpc/delete_nodenet(nodenet_uid="%s")' % uid)


def test_merge_nodenet(app, test_nodenet, engine, node):
    app.set_auth()
    response = app.get_json('/rpc/export_nodenet(nodenet_uid="%s")' % test_nodenet)
    data = json.loads(response.json_body['data'])
    response = app.post_json('/rpc/new_nodenet', params={
        'name': 'ImporterNet',
        'engine': engine,
        'worldadapter': 'Braitenberg',
        'owner': 'Pytest User'
    })
    uid = response.json_body['data']

    data['uid'] = uid
    response = app.post_json('/rpc/merge_nodenet', params={
        'nodenet_uid': uid,
        'nodenet_data': json.dumps(data)
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % uid)
    assert len(list(response.json_body['data']['nodes'].keys())) == 1
    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % uid)
    assert response.json_body['data']['name'] == 'ImporterNet'
    response = app.get_json('/rpc/delete_nodenet(nodenet_uid="%s")' % uid)


###################################################
##
##
##      WORLD
##
##
###################################################

def test_get_available_worlds(app, test_world):
    response = app.get_json('/rpc/get_available_worlds()')
    assert_success(response)
    assert test_world in response.json_body['data']


def test_get_available_worlds_for_user(app, test_world):
    response = app.get_json('/rpc/get_available_worlds(user_id="Pytest User")')
    assert_success(response)
    assert test_world in response.json_body['data']


# TODO: get_nodenet_properties is missing.
def test_get_world_properties(app, test_world):
    response = app.get_json('/rpc/get_world_properties(world_uid="%s")' % test_world)
    assert_success(response)
    data = response.json_body['data']
    assert data['uid'] == test_world
    assert data['name'] == "World of Pain"
    assert 'available_worldadapters' in data
    assert 'available_worldobjects' in data


def test_get_worldadapters(app, test_world):
    response = app.get_json('/rpc/get_worldadapters(world_uid="%s")' % test_world)
    assert_success(response)
    assert 'Braitenberg' in response.json_body['data']


def test_get_world_objects(app, test_world):
    response = app.get_json('/rpc/get_world_objects(world_uid="%s")' % test_world)
    assert_success(response)
    assert response.json_body['data'] == {}


def test_add_worldobject(app, test_world):
    response = app.post_json('/rpc/add_worldobject', params={
        'world_uid': test_world,
        'type': 'Braintree',
        'position': [10, 10],
        'name': 'Testtree'
    })
    assert_success(response)
    uid = response.json_body['data']
    assert uid is not None
    response = app.get_json('/rpc/get_world_objects(world_uid="%s")' % test_world)
    assert uid in response.json_body['data']


def test_delete_worldobject(app, test_world):
    response = app.post_json('/rpc/add_worldobject', params={
        'world_uid': test_world,
        'type': 'Braintree',
        'position': [10, 10],
        'name': 'Testtree'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/delete_worldobject', params={
        'world_uid': test_world,
        'object_uid': uid
    })
    assert_success(response)
    response = app.get_json('/rpc/get_world_objects(world_uid="%s")' % test_world)
    assert uid not in response.json_body['data']


def test_set_worldobject_properties(app, test_world):
    response = app.post_json('/rpc/add_worldobject', params={
        'world_uid': test_world,
        'type': 'Braintree',
        'position': [10, 10],
        'name': 'Testtree'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/set_worldobject_properties', params={
        'world_uid': test_world,
        'uid': uid,
        'position': [20, 20],
        'orientation': 27,
        'name': 'edited'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_world_objects(world_uid="%s")' % test_world)
    data = response.json_body['data']
    assert data[uid]['position'] == [20, 20]
    assert data[uid]['orientation'] == 27
    assert data[uid]['name'] == 'edited'


def test_get_world_view(app, test_world):
    response = app.get_json('/rpc/get_world_view(world_uid="%s", step=0)' % test_world)
    assert_success(response)
    assert 'agents' in response.json_body['data']
    assert 'objects' in response.json_body['data']
    assert response.json_body['data']['current_step'] == 0
    assert 'step' not in response.json_body['data']


def test_set_worldagent_properties(app, test_world, default_nodenet):
    # create agent.
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=default_nodenet, worldadapter="Braitenberg", world_uid=test_world))
    response = app.post_json('/rpc/set_worldagent_properties', params={
        'world_uid': test_world,
        'uid': default_nodenet,
        'position': [23, 23],
        'orientation': 37,
        'name': 'Sepp'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_world_view(world_uid="%s", step=0)' % test_world)
    data = response.json_body['data']['agents'][default_nodenet]
    assert data['position'] == [23, 23]
    assert data['orientation'] == 37
    assert data['name'] == 'Sepp'


def test_new_world(app):
    app.set_auth()
    response = app.post_json('/rpc/new_world', params={
        'world_name': 'FooBarTestWorld',
        'world_type': 'Island'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.get_json('/rpc/get_available_worlds(user_id="Pytest User")')
    assert uid in response.json_body['data']


def test_get_available_world_types(app):
    response = app.get_json('/rpc/get_available_world_types()')
    assert_success(response)
    data = response.json_body['data']
    assert 'Island' in data
    assert data['Island']['config'] == []


def test_delete_world(app, test_world):
    response = app.get_json('/rpc/delete_world(world_uid="%s")' % test_world)
    assert_success(response)
    response = app.get_json('/rpc/get_available_worlds(user_id="Pytest User")')
    assert test_world not in response.json_body['data']


def test_set_world_properties(app, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_world_properties', params={
        'world_uid': test_world,
        'world_name': 'asdf',
        'owner': 'Pytest User'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_world_properties(world_uid="%s")' % test_world)
    assert response.json_body['data']['name'] == "asdf"


def test_revert_world(app, test_world):
    app.set_auth()
    response = app.post_json('/rpc/add_worldobject', params={
        'world_uid': test_world,
        'type': 'Braintree',
        'position': [10, 10],
        'name': 'Testtree'
    })
    response = app.get_json('/rpc/revert_world(world_uid="%s")' % test_world)
    assert_success(response)
    response = app.get_json('/rpc/get_world_view(world_uid="%s",step=0)' % test_world)
    data = response.json_body['data']
    assert data['objects'] == {}


def test_save_world(app, test_world):
    app.set_auth()
    response = app.post_json('/rpc/add_worldobject', params={
        'world_uid': test_world,
        'type': 'Braintree',
        'position': [10, 10],
        'name': 'Testtree'
    })
    uid = response.json_body['data']
    response = app.get_json('/rpc/save_world(world_uid="%s")' % test_world)
    assert_success(response)
    response = app.get_json('/rpc/revert_world(world_uid="%s")' % test_world)
    response = app.get_json('/rpc/get_world_view(world_uid="%s",step=0)' % test_world)
    data = response.json_body['data']
    assert uid in data['objects']
    # delete the world, to get the default state back
    app.get_json('/rpc/delete_world(world_uid="%s")' % test_world)


def test_export_world(app, test_world):
    response = app.get_json('/rpc/export_world(world_uid="%s")' % test_world)
    assert_success(response)
    export_data = json.loads(response.json_body['data'])
    assert export_data['uid'] == test_world
    assert export_data['name'] == 'World of Pain'
    assert export_data['objects'] == {}
    assert export_data['agents'] == {}
    assert export_data['owner'] == 'Pytest User'
    assert export_data['current_step'] == 0
    assert export_data['world_type'] == 'Island'


def test_import_world(app, test_world):
    response = app.get_json('/rpc/export_world(world_uid="%s")' % test_world)
    data = json.loads(response.json_body['data'])
    del data['uid']
    data['name'] = 'Copied Pain'
    response = app.post_json('/rpc/import_world', params={
        'worlddata': json.dumps(data)
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.get_json('/rpc/export_world(world_uid="%s")' % uid)
    data = json.loads(response.json_body['data'])
    assert data['owner'] == 'Pytest User'
    assert data['name'] == 'Copied Pain'
    assert data['objects'] == {}
    assert data['agents'] == {}
    assert uid != test_world


###################################################
##
##
##      MONITORS
##
##
###################################################

def test_get_monitor_data_all(app, test_nodenet):
    response = app.get_json('/rpc/get_monitor_data(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    assert response.json_body['data']['monitors'] == {}


def test_add_gate_monitor(app, test_nodenet, node):
    response = app.post_json('/rpc/add_gate_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate': 'sub'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][uid]['node_uid'] == node
    assert response.json_body['data']['monitors'][uid]['target'] == 'sub'
    assert response.json_body['data']['monitors'][uid]['type'] == 'gate'
    assert response.json_body['data']['monitors'][uid]['values'] == {}


@pytest.mark.engine("dict_engine")
def test_add_slot_monitor(app, test_nodenet, node):
    response = app.post_json('/rpc/add_slot_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'slot': 'gen',
        'name': 'Foobar'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][uid]['name'] == 'Foobar'
    assert response.json_body['data']['monitors'][uid]['node_uid'] == node
    assert response.json_body['data']['monitors'][uid]['target'] == 'gen'
    assert response.json_body['data']['monitors'][uid]['type'] == 'slot'
    assert response.json_body['data']['monitors'][uid]['values'] == {}


def test_add_link_monitor(app, test_nodenet, node):
    response = app.post_json('/rpc/add_link_monitor', params={
        'nodenet_uid': test_nodenet,
        'source_node_uid': node,
        'gate_type': 'gen',
        'target_node_uid': node,
        'slot_type': 'gen',
        'name': 'LinkWeight'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][uid]['name'] == 'LinkWeight'
    assert response.json_body['data']['monitors'][uid]['source_node_uid'] == node
    assert response.json_body['data']['monitors'][uid]['gate_type'] == 'gen'
    assert response.json_body['data']['monitors'][uid]['target_node_uid'] == node
    assert response.json_body['data']['monitors'][uid]['slot_type'] == 'gen'


def test_add_custom_monitor(app, test_nodenet):
    response = app.post_json('/rpc/add_custom_monitor', params={
        'nodenet_uid': test_nodenet,
        'function': 'return len(netapi.get_nodes())',
        'name': 'nodecount'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][uid]['name'] == 'nodecount'


def test_add_group_monitor_by_name(app, test_nodenet):
    app.set_auth()
    uids = []
    for i in range(3):
        response = app.post_json('/rpc/add_node', params={
            'nodenet_uid': test_nodenet,
            'type': 'Neuron',
            'position': [23, 23, 12],
            'nodespace': None,
            'name': 'Testnode %d' % i
        })
        uids.append(response.json_body['data'])
    response = app.post_json('/rpc/add_group_monitor', {
        'nodenet_uid': test_nodenet,
        'name': 'testmonitor',
        'nodespace': None,
        'node_name_prefix': 'Testnode',
        'gate': 'gen'
    })
    mon_uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][mon_uid]['name'] == 'testmonitor'
    assert response.json_body['data']['monitors'][mon_uid]['node_uids'] == uids


def test_add_group_monitor_by_ids(app, test_nodenet):
    app.set_auth()
    uids = []
    for i in range(3):
        response = app.post_json('/rpc/add_node', params={
            'nodenet_uid': test_nodenet,
            'type': 'Neuron',
            'position': [23, 23, 12],
            'nodespace': None,
            'name': 'Testnode %d' % i
        })
        uids.append(response.json_body['data'])
    response = app.post_json('/rpc/add_group_monitor', {
        'nodenet_uid': test_nodenet,
        'name': 'testmonitor',
        'nodespace': None,
        'node_uids': uids,
        'gate': 'gen'
    })
    mon_uid = response.json_body['data']
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert response.json_body['data']['monitors'][mon_uid]['name'] == 'testmonitor'
    assert response.json_body['data']['monitors'][mon_uid]['node_uids'] == uids


def test_remove_monitor(app, test_nodenet, node):
    response = app.post_json('/rpc/add_gate_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate': 'gen'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/remove_monitor', params={
        'nodenet_uid': test_nodenet,
        'monitor_uid': uid
    })
    assert_success(response)
    response = app.post_json('/rpc/get_monitor_data', params={
        'nodenet_uid': test_nodenet
    })
    assert uid not in response.json_body['data']['monitors']


def test_clear_monitor(app, test_nodenet, node):
    response = app.post_json('/rpc/add_gate_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate': 'gen'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/clear_monitor', params={
        'nodenet_uid': test_nodenet,
        'monitor_uid': uid
    })
    assert_success(response)


###################################################
##
##
##      NODENET
##
##
###################################################

def test_get_nodespace_list(app, test_nodenet, node):
    response = app.get_json('/rpc/get_nodespace_list(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    rootid = list(response.json_body['data'].keys())[0]
    assert response.json_body['data'][rootid]['name'] == 'Root'
    assert response.json_body['data'][rootid]['parent'] is None
    assert node in response.json_body['data'][rootid]['nodes']


def test_get_nodespace_activations(app, test_nodenet, node):
    response = app.post_json('/rpc/get_nodespace_activations', params={
        'nodenet_uid': test_nodenet,
        'nodespaces': [None],
        'last_call_step': -1
    })
    assert_success(response)
    assert node not in response.json_body['data']['activations']
    response = app.post_json('/rpc/set_node_activation', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'activation': -1
    })
    response = app.post_json('/rpc/get_nodespace_activations', params={
        'nodenet_uid': test_nodenet,
        'nodespaces': [None],
        'last_call_step': -1
    })
    assert response.json_body['data']['activations'][node][0] == -1


def test_get_node(app, test_nodenet, node):
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, node))
    assert_success(response)
    assert response.json_body['data']['type'] == 'Pipe'


def test_add_node(app, test_nodenet):
    app.set_auth()
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Pipe',
        'position': [23, 42, 13],
        'nodespace': None,
        'name': 'N2',
        'parameters': {'wait': "3"}
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, uid))
    assert response.json_body['data']['name'] == 'N2'
    assert int(response.json_body['data']['parameters']['wait']) == 3


def test_add_nodespace(app, test_nodenet):
    app.set_auth()
    response = app.post_json('/rpc/add_nodespace', params={
        'nodenet_uid': test_nodenet,
        'nodespace': None,
        'name': 'nodespace'
    })
    assert_success(response)
    uid = response.json_body['data']
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % (test_nodenet))
    assert uid in response.json_body['data']['nodespaces']
    assert uid not in response.json_body['data']['nodes']


def test_clone_nodes(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/clone_nodes', params={
        'nodenet_uid': test_nodenet,
        'node_uids': [node],
        'clone_mode': 'all',
        'nodespace': None,
        'offset': [23, 23, 23]
    })
    assert_success(response)
    node = list(response.json_body['data'].values())[0]
    assert node['name'] == 'N1'
    assert node['position'] == [33, 33, 33]
    assert node['links']['gen'][0]['target_node_uid'] == node['uid']


def test_set_node_positions(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/set_node_positions', params={
        'nodenet_uid': test_nodenet,
        'positions': {node: [42, 23, 11]}
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, node))
    assert response.json_body['data']['position'] == [42, 23, 11]


def test_set_node_name(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/set_node_name', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'name': 'changed'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, node))
    assert response.json_body['data']['name'] == 'changed'


def test_delete_node(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/delete_nodes', params={
        'nodenet_uid': test_nodenet,
        'node_uids': [node]
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    assert response.json_body['data']['nodes'] == {}


def test_delete_nodespace(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/add_nodespace', params={
        'nodenet_uid': test_nodenet,
        'nodespace': None,
        'name': 'nodespace'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/delete_nodespace', params={
        'nodenet_uid': test_nodenet,
        'nodespace': uid
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    assert uid not in response.json_body['data']['nodespaces']


def test_align_nodes(app, test_nodenet):
    app.set_auth()
    # TODO: Why does autoalign only move a node if it has no links?
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Neuron',
        'position': [5, 5, 0],
        'nodespace': None,
        'name': 'N2'
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/align_nodes', params={
        'nodenet_uid': test_nodenet,
        'nodespace': None
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, uid))
    assert response.json_body['data']['position'] != [5, 5]


def test_get_available_node_types(app, test_nodenet):
    response = app.get_json('/rpc/get_available_node_types(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    assert 'Pipe' in response.json_body['data']['nodetypes']
    assert 'Neuron' in response.json_body['data']['nodetypes']
    assert 'Sensor' in response.json_body['data']['nodetypes']


def test_get_available_native_module_types(app, test_nodenet, engine):
    response = app.get_json('/rpc/get_available_native_module_types(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    if engine == 'dict_engine':
        assert response.json_body['data'] == {}
    elif engine == 'theano_engine':
        assert "GradientDescent" in response.json_body['data']


def test_set_node_parameters(app, test_nodenet):
    app.set_auth()
    # add activator
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Activator',
        'nodespace': None,
        'position': [23, 42, 0],
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/set_node_parameters', params={
        'nodenet_uid': test_nodenet,
        'node_uid': uid,
        'parameters': {'type': 'sub'}
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, uid))
    assert response.json_body['data']['parameters']['type'] == 'sub'


def test_set_gate_configuration(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/set_gate_configuration', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate_type': 'gen',
        'gatefunction': 'sigmoid',
        'gatefunction_parameters': {
            'bias': '1'
        }
    })
    assert_success(response)
    response = app.post_json('/rpc/get_node', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
    })
    data = response.json_body['data']
    assert data['gate_configuration']['gen']['gatefunction'] == 'sigmoid'
    assert data['gate_configuration']['gen']['gatefunction_parameters'] == {'bias': 1}
    # setting a non-value leads to using the default
    response = app.post_json('/rpc/set_gate_configuration', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate_type': 'gen',
        'gatefunction': 'sigmoid',
        'gatefunction_parameters': {
            'bias': ''
        }
    })
    response = app.post_json('/rpc/get_node', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
    })
    data = response.json_body['data']
    assert data['gate_configuration']['gen']['gatefunction'] == 'sigmoid'
    assert data['gate_configuration']['gen']['gatefunction_parameters'] == {'bias': 0}


def test_get_available_gatefunctions(app, test_nodenet):
    response = app.post_json('/rpc/get_available_gatefunctions', params={'nodenet_uid': test_nodenet})
    funcs = response.json_body['data']
    assert funcs['identity'] == {}
    assert funcs['absolute'] == {}
    assert funcs['one_over_x'] == {}
    assert funcs['sigmoid'] == {'bias': 0}
    assert funcs['elu'] == {'bias': 0}
    assert funcs['relu'] == {'bias': 0}
    assert funcs['threshold'] == {
        'minimum': 0,
        'maximum': 1,
        'amplification': 1,
        'threshold': 0
    }


def test_get_available_datasources(app, test_nodenet, test_world):
    app.set_auth()
    # set worldadapter
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, world_uid=test_world, worldadapter="Braitenberg"))
    response = app.get_json('/rpc/get_available_datasources(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    assert 'brightness_l' in response.json_body['data']
    assert 'brightness_l' in response.json_body['data']


def test_get_available_datatargets(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, world_uid=test_world, worldadapter="Braitenberg"))
    response = app.get_json('/rpc/get_available_datatargets(nodenet_uid="%s")' % test_nodenet)
    assert_success(response)
    assert 'engine_l' in response.json_body['data']
    assert 'engine_r' in response.json_body['data']


def test_bind_datasource_to_sensor(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, world_uid=test_world, worldadapter="Braitenberg"))
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Sensor',
        'position': [23, 42, 13],
        'nodespace': None,
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/bind_datasource_to_sensor', params={
        'nodenet_uid': test_nodenet,
        'sensor_uid': uid,
        'datasource': 'brightness_l'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, uid))
    assert response.json_body['data']['parameters']['datasource'] == 'brightness_l'


def test_bind_datatarget_to_actuator(app, test_nodenet, test_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, world_uid=test_world, worldadapter="Braitenberg"))
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Actuator',
        'position': [23, 42, 13],
        'nodespace': None,
    })
    uid = response.json_body['data']
    response = app.post_json('/rpc/bind_datatarget_to_actuator', params={
        'nodenet_uid': test_nodenet,
        'actuator_uid': uid,
        'datatarget': 'engine_l'
    })
    assert_success(response)
    response = app.get_json('/rpc/get_node(nodenet_uid="%s",node_uid="%s")' % (test_nodenet, uid))
    assert response.json_body['data']['parameters']['datatarget'] == 'engine_l'


def test_add_link(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/add_link', params={
        'nodenet_uid': test_nodenet,
        'source_node_uid': node,
        'gate_type': 'sub',
        'target_node_uid': node,
        'slot_type': 'gen',
        'weight': 0.7
    })
    assert_success(response)
    uid = response.json_body['data']
    assert uid is not None
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert data['nodes'][node]['links']['sub'][0]['target_node_uid'] == node
    assert round(data['nodes'][node]['links']['sub'][0]['weight'], 3) == 0.7


def test_set_link_weight(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/set_link_weight', params={
        'nodenet_uid': test_nodenet,
        'source_node_uid': node,
        'gate_type': "gen",
        'target_node_uid': node,
        'slot_type': "gen",
        'weight': 0.345
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert float("%.3f" % data['nodes'][node]['links']['gen'][0]['weight']) == 0.345


def test_get_links_for_nodes(app, test_nodenet, node):
    response = app.post_json('/rpc/get_links_for_nodes', params={
        'nodenet_uid': test_nodenet,
        'node_uids': [node]
    })
    assert_success(response)
    link = list(response.json_body['data']['links'])[0]
    assert link['source_node_uid'] == node


def test_delete_link(app, test_nodenet, node):
    app.set_auth()
    response = app.post_json('/rpc/delete_link', params={
        'nodenet_uid': test_nodenet,
        'source_node_uid': node,
        'gate_type': "gen",
        'target_node_uid': node,
        'slot_type': "gen"
    })
    assert_success(response)
    response = app.get_json('/rpc/get_nodes(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    data['nodes'][node]['links'] == {}


def test_reload_native_modules(app, test_nodenet, resourcepath):
    app.set_auth()
    # create a native module:
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "gatetypes": ["gen", "foo", "bar"],
            "symbol": "t"}}""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")
    response = app.get_json('/rpc/reload_native_modules()')
    assert_success(response)
    response = app.get_json('/rpc/get_available_node_types(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']['native_modules']['Testnode']
    assert data['nodefunction_name'] == "testnodefunc"
    assert data['gatetypes'] == ['gen', 'foo', 'bar']
    assert data['slottypes'] == ['gen', 'foo', 'bar']
    assert data['name'] == 'Testnode'


def test_user_prompt_response(app, test_nodenet, resourcepath):
    app.set_auth()
    # create a native module:
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "gatetypes": ["gen", "foo", "bar"],
            "symbol": "t"}}""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")
    response = app.get_json('/rpc/reload_native_modules()')
    assert_success(response)

    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Testnode',
        'position': [23, 23],
        'nodespace': None,
        'name': 'Testnode'
    })
    assert_success(response)

    uid = response.json_body['data']

    response = app.post_json('/rpc/user_prompt_response', {
        'nodenet_uid': test_nodenet,
        'node_uid': uid,
        'values': {'foo': 'bar'},
        'resume_nodenet': True
    })
    assert_success(response)
    response = app.get_json('/rpc/export_nodenet(nodenet_uid="%s")' % test_nodenet)
    data = json.loads(response.json_body['data'])
    assert data['nodes'][uid]['parameters']['foo'] == 'bar'
    assert data['is_active']


def test_set_logging_levels(app):
    response = app.post_json('/rpc/set_logging_levels', params={
        'logging_levels': {
            'system': 'INFO',
            'world': 'DEBUG',
        }
    })
    assert_success(response)
    import logging
    assert logging.getLogger('world').getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger('system').getEffectiveLevel() == logging.INFO


def test_get_logger_messages(app, test_nodenet):
    response = app.get_json('/rpc/get_logger_messages(logger=["system"])')
    assert_success(response)
    assert 'servertime' in response.json_body['data']
    assert response.json_body['data']['logs'] == []


def test_get_nodenet_logger_messages(app, test_nodenet):
    import logging
    logging.getLogger('agent.%s' % test_nodenet).warning('asdf')
    logging.getLogger('system').warning('foobar')
    response = app.get_json('/rpc/get_logger_messages(logger=["system", "agent.%s"])' % test_nodenet)
    assert 'servertime' in response.json_body['data']
    netlog = syslog = None
    for item in response.json_body['data']['logs']:
        if item['logger'] == 'system':
            syslog = item
        elif item['logger'].startswith('agent'):
            netlog = item
    assert netlog['step'] == 0
    assert syslog['step'] is None


def test_get_monitoring_info(app, test_nodenet):
    response = app.get_json('/rpc/get_monitoring_info(nodenet_uid="%s",logger=["system,world"],monitor_from=3,monitor_count=10)' % test_nodenet)
    assert_success(response)
    assert 'logs' in response.json_body['data']
    assert 'current_step' in response.json_body['data']
    assert response.json_body['data']['monitors'] == {}
    assert 'servertime' in response.json_body['data']['logs']
    assert response.json_body['data']['logs']['logs'] == []


def test_400(app):
    app.set_auth()
    response = app.get_json('/rpc/save_nodenet("foobar")', expect_errors=True)
    assert_failure(response)
    assert "Malformed arguments" in response.json_body['data']


def test_401(app, default_nodenet):
    app.unset_auth()
    response = app.get_json('/rpc/delete_nodenet(nodenet_uid="%s")' % default_nodenet, expect_errors=True)
    assert_failure(response)
    assert 'Insufficient permissions' in response.json_body['data']


def test_404(app):
    response = app.get_json('/rpc/notthere(foo="bar")', expect_errors=True)
    assert_failure(response)
    assert response.json_body['data'] == "Function not found"


def test_405(app, default_nodenet):
    response = app.get_json('/rpc/get_available_nodenets', params={'nodenet_uid': default_nodenet}, expect_errors=True)
    assert_failure(response)
    assert response.json_body['data'] == "Method not allowed"


def test_500(app):
    response = app.get_json('/rpc/generate_uid(foo="bar")', expect_errors=True)
    assert_failure(response)
    assert "unexpected keyword argument" in response.json_body['data']
    assert response.json_body['traceback'] is not None


def test_get_recipes(app, default_nodenet, resourcepath):
    app.set_auth()
    import os
    recipe_file = os.path.join(resourcepath, 'Test', 'recipes.py')
    with open(recipe_file, 'w') as fp:
        fp.write("""
def foobar(netapi, quatsch=23):
    return {'quatsch': quatsch}
""")
    response = app.get_json('/rpc/reload_native_modules()')
    response = app.get_json('/rpc/get_available_recipes()')
    data = response.json_body['data']
    assert 'foobar' in data
    assert len(data['foobar']['parameters']) == 1
    assert data['foobar']['parameters'][0]['name'] == 'quatsch'
    assert data['foobar']['parameters'][0]['default'] == 23


def test_run_recipes(app, test_nodenet, resourcepath):
    app.set_auth()
    import os
    recipe_file = os.path.join(resourcepath, 'Test', 'recipes.py')
    with open(recipe_file, 'w') as fp:
        fp.write("""
def foobar(netapi, quatsch=23):
    return {'quatsch': quatsch}
""")
    response = app.get_json('/rpc/reload_native_modules()')
    response = app.post_json('/rpc/run_recipe', {
        'nodenet_uid': test_nodenet,
        'name': 'foobar',
        'parameters': {
            'quatsch': ''
        }
    })
    data = response.json_body['data']
    assert data['quatsch'] == 23


def test_get_agent_dashboard(app, test_nodenet, node, default_world):
    app.set_auth()
    response = app.post_json('/rpc/set_nodenet_properties', params=dict(nodenet_uid=test_nodenet, worldadapter="Default", world_uid=default_world))
    response = app.get_json('/rpc/get_agent_dashboard(nodenet_uid="%s")' % test_nodenet)
    data = response.json_body['data']
    assert data['count_nodes'] == 1


def test_nodenet_data_structure(app, test_nodenet, resourcepath, node):
    app.set_auth()
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "gatetypes": ["gen", "foo", "bar"],
            "symbol": "t"}}""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")
    response = app.get_json('/rpc/reload_native_modules()')
    response = app.post_json('/rpc/add_nodespace', params={
        'nodenet_uid': test_nodenet,
        'nodespace': None,
        'name': 'Test-Node-Space'
    })
    nodespace_uid = response.json_body['data']
    response = app.post_json('/rpc/add_node', params={
        'nodenet_uid': test_nodenet,
        'type': 'Pipe',
        'position': [42, 42, 23],
        'nodespace': nodespace_uid,
        'name': 'N2'
    })
    n2_uid = response.json_body['data']
    response = app.post_json('/rpc/add_gate_monitor', params={
        'nodenet_uid': test_nodenet,
        'node_uid': node,
        'gate': 'gen',
        'name': 'Testmonitor',
        'color': '#332211'
    })
    monitor_uid = response.json_body['data']

    response = app.get_json('/rpc/get_nodenet_metadata(nodenet_uid="%s")' % test_nodenet)
    metadata = response.json_body['data']

    response_1 = app.post_json('/rpc/get_calculation_state', params={'nodenet_uid': test_nodenet, 'nodenet': {'nodespaces': [None]}, 'monitors': True})
    response = app.get_json('/rpc/save_nodenet(nodenet_uid="%s")' % test_nodenet)
    response = app.get_json('/rpc/revert_nodenet(nodenet_uid="%s")' % test_nodenet)
    response_2 = app.post_json('/rpc/get_calculation_state', params={'nodenet_uid': test_nodenet, 'nodenet': {'nodespaces': [None]}, 'monitors': True})

    assert response_1.json_body['data']['nodenet'] == response_2.json_body['data']['nodenet']
    assert response_1.json_body['data']['monitors']['monitors'] == response_2.json_body['data']['monitors']['monitors']

    data = response_2.json_body['data']

    # Monitors
    response = app.get_json('/rpc/get_monitor_data(nodenet_uid="%s")' % test_nodenet)
    monitor_data = response.json_body['data']['monitors'][monitor_uid]

    assert data['monitors']['monitors'][monitor_uid]['name'] == 'Testmonitor'
    assert data['monitors']['monitors'][monitor_uid]['node_uid'] == node
    assert data['monitors']['monitors'][monitor_uid]['target'] == 'gen'
    assert data['monitors']['monitors'][monitor_uid]['type'] == 'gate'
    assert data['monitors']['monitors'][monitor_uid]['uid'] == monitor_uid
    assert data['monitors']['monitors'][monitor_uid]['values'] == {}
    assert data['monitors']['monitors'][monitor_uid]['color'] == '#332211'
    assert data['monitors']['monitors'][monitor_uid] == monitor_data

    # Nodes
    response = app.get_json('/rpc/get_node(nodenet_uid="%s", node_uid="%s")' % (test_nodenet, node))
    node_data = response.json_body['data']

    assert node in data['nodenet']['nodes']
    assert n2_uid not in data['nodenet']['nodes']
    assert nodespace_uid not in data['nodenet']['nodes']

    # gates
    for key in ['gen', 'por', 'ret', 'sub', 'sur', 'cat', 'exp']:
        assert data['nodenet']['nodes'][node]['gate_activations'][key] == 0

    assert data['nodenet']['nodes'][node]['parameters']['expectation'] == 1
    assert data['nodenet']['nodes'][node]['parameters']['wait'] == 10
    assert data['nodenet']['nodes'][node]['position'] == [10, 10, 10]
    assert data['nodenet']['nodes'][node]['type'] == "Pipe"
    assert 'links' not in data

    assert node_data['parameters']['expectation'] == 1
    assert node_data['parameters']['wait'] == 10
    assert node_data['position'] == [10, 10, 10]
    assert node_data['type'] == "Pipe"

    # Links
    for link in data['nodenet']['nodes'][node]['links']['gen']:
        assert link['weight'] == 1
        assert link['target_node_uid'] == node
        assert link['target_slot_name'] == 'gen'

    # Nodespaces
    # assert data['nodenet']['nodespaces'][nodespace_uid]['index'] == 3
    assert data['nodenet']['nodespaces'][nodespace_uid]['name'] == 'Test-Node-Space'
    # assert data['nodenet']['nodespaces'][nodespace_uid]['parent_nodespace'] == 'Root'

    # Nodetypes
    response = app.get_json('/rpc/get_available_node_types(nodenet_uid="%s")' % test_nodenet)
    node_type_data = response.json_body['data']

    assert 'gatetypes' not in metadata['nodetypes']['Comment']
    assert 'slottypes' not in metadata['nodetypes']['Comment']

    for key in ['Pipe', 'Neuron', 'Actuator']:
        assert 'gatetypes' in metadata['nodetypes'][key]
        assert 'slottypes' in metadata['nodetypes'][key]

    assert 'slottypes' in metadata['nodetypes']['Activator']
    assert 'gatetypes' not in metadata['nodetypes']['Activator']

    assert 'slottypes' not in metadata['nodetypes']['Sensor']
    assert 'gatetypes' in metadata['nodetypes']['Sensor']

    assert metadata['nodetypes'] == node_type_data['nodetypes']

    # Native Modules
    response = app.get_json('/rpc/get_available_native_module_types(nodenet_uid="%s")' % test_nodenet)
    native_module_data = response.json_body['data']

    assert metadata['native_modules']['Testnode']['gatetypes'] == ['gen', 'foo', 'bar']
    assert metadata['native_modules']['Testnode']['name'] == 'Testnode'
    assert metadata['native_modules']['Testnode']['nodefunction_name'] == 'testnodefunc'
    assert metadata['native_modules']['Testnode']['slottypes'] == ['gen', 'foo', 'bar']
    assert metadata['native_modules']['Testnode']['symbol'] == 't'

    assert metadata['native_modules'] == native_module_data

    # Nodenet
    assert metadata['current_step'] == 0  # TODO:
    assert 'step' not in data  # current_step && step?
    assert metadata['version'] == 2
    assert metadata['world'] is None
    assert metadata['worldadapter'] is None


def test_get_state_diff(app, test_nodenet, node):
    from micropsi_core import runtime
    nodenet = runtime.nodenets[test_nodenet]
    runtime.step_nodenet(test_nodenet)
    response = app.post_json('/rpc/get_calculation_state', params={
        'nodenet_uid': test_nodenet,
        'nodenet_diff': {
            'nodespaces': [None],
            'step': 0,
        }
    })
    data = response.json_body['data']['nodenet_diff']
    assert 'activations' in data
    assert 'changes' in data
    assert node in data['changes']['nodes_dirty']
    node2 = nodenet.create_node("Neuron", None, [10, 10], name="node2")
    runtime.step_nodenet(test_nodenet)
    response = app.post_json('/rpc/get_calculation_state', params={
        'nodenet_uid': test_nodenet,
        'nodenet_diff': {
            'nodespaces': [None],
            'step': 1,
        }
    })
    data = response.json_body['data']['nodenet_diff']
    assert [node2] == list(data['changes']['nodes_dirty'].keys())


def test_get_nodenet_diff(app, test_nodenet, node):
    from micropsi_core import runtime
    nodenet = runtime.nodenets[test_nodenet]
    runtime.step_nodenet(test_nodenet)
    response = app.post_json('/rpc/get_nodenet_changes', params={
        'nodenet_uid': test_nodenet,
        'nodespaces': [None],
        'since_step': 0
    })
    data = response.json_body['data']
    assert 'activations' in data
    assert 'changes' in data
    assert node in data['changes']['nodes_dirty']
    node2 = nodenet.create_node("Neuron", None, [10, 10], name="node2")
    runtime.step_nodenet(test_nodenet)
    response = app.post_json('/rpc/get_nodenet_changes', params={
        'nodenet_uid': test_nodenet,
        'nodespaces': [None],
        'since_step': 1
    })
    data = response.json_body['data']
    assert [node2] == list(data['changes']['nodes_dirty'].keys())


def test_get_operations(app):
    response = app.get_json('/rpc/get_available_operations()')
    data = response.json_body['data']
    for selectioninfo in data['autoalign']['selection']:
        if selectioninfo['nodetypes'] == ['Nodespace']:
            assert selectioninfo['mincount'] == 1
            assert selectioninfo['maxcount'] == -1
        else:
            assert selectioninfo['mincount'] == 2
            assert selectioninfo['maxcount'] == -1
            assert selectioninfo['nodetypes'] == []


def test_run_operation(app, test_nodenet, node):
    response = app.post_json('/rpc/run_operation', {
        'nodenet_uid': test_nodenet,
        'name': 'autoalign',
        'parameters': {},
        'selection_uids': [None]
    })
    assert response.json_body['status'] == 'success'


@pytest.mark.engine("theano_engine")
def test_add_gate_activation_recorder(app, test_nodenet, resourcepath):
    from micropsi_core import runtime
    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    for i in range(3):
        netapi.create_node('Neuron', None, "testnode_%d" % i)
    response = app.post_json('/rpc/add_gate_activation_recorder', {
        'nodenet_uid': test_nodenet,
        'group_definition': {'nodespace_uid': nodespace.uid, 'node_name_prefix': 'testnode'},
        'name': "recorder",
        'interval': 2
    })
    assert_success(response)
    recorder_uid = response.json_body['data']
    runtime.step_nodenet(test_nodenet)
    runtime.step_nodenet(test_nodenet)
    assert netapi.get_recorder(recorder_uid).name == 'recorder'
    assert 'activations' in netapi.get_recorder(recorder_uid).values


@pytest.mark.engine("theano_engine")
def test_add_node_activation_recorder(app, test_nodenet, resourcepath):
    from micropsi_core import runtime
    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    for i in range(3):
        netapi.create_node('Pipe', None, "testnode_%d" % i)
    response = app.post_json('/rpc/add_node_activation_recorder', {
        'nodenet_uid': test_nodenet,
        'group_definition': {'nodespace_uid': nodespace.uid, 'node_name_prefix': 'testnode'},
        'name': "recorder",
        'interval': 2
    })
    assert_success(response)
    recorder_uid = response.json_body['data']
    runtime.step_nodenet(test_nodenet)
    runtime.step_nodenet(test_nodenet)
    assert netapi.get_recorder(recorder_uid).name == 'recorder'
    assert netapi.get_recorder(recorder_uid).values['activations'][0].shape == (7, 3)


@pytest.mark.engine("theano_engine")
def test_add_linkweight_recorder(app, test_nodenet, resourcepath):
    from micropsi_core import runtime
    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    layer1 = []
    layer2 = []
    for i in range(3):
        layer1.append(netapi.create_node('Neuron', None, "l1_%d" % i))
        layer2.append(netapi.create_node('Neuron', None, "l2_%d" % i))
    for i in range(3):
        for j in range(3):
            netapi.link(layer1[i], 'gen', layer2[j], 'gen', weight=0.89)

    response = app.post_json('/rpc/add_linkweight_recorder', {
        'nodenet_uid': test_nodenet,
        'from_group_definition': {'nodespace_uid': nodespace.uid, 'node_name_prefix': 'l1'},
        'to_group_definition': {'nodespace_uid': nodespace.uid, 'node_name_prefix': 'l2'},
        'name': "recorder",
        'interval': 2
    })
    assert_success(response)
    recorder_uid = response.json_body['data']
    runtime.step_nodenet(test_nodenet)
    runtime.step_nodenet(test_nodenet)
    assert netapi.get_recorder(recorder_uid).name == 'recorder'
    assert 'linkweights' in netapi.get_recorder(recorder_uid).values


@pytest.mark.engine("theano_engine")
def test_clear_recorder(app, test_nodenet, resourcepath):
    from micropsi_core import runtime
    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    for i in range(3):
        netapi.create_node('Neuron', None, "testnode_%d" % i)
    recorder = netapi.add_gate_activation_recorder(group_definition={'nodespace_uid': nodespace.uid, 'node_name_prefix': 'testnode'}, name="recorder")
    for i in range(3):
        runtime.step_nodenet(test_nodenet)

    response = app.post_json('/rpc/clear_recorder', {
        'nodenet_uid': test_nodenet,
        'recorder_uid': recorder.uid,
    })
    assert_success(response)
    assert recorder.values == {}


@pytest.mark.engine("theano_engine")
def test_remove_recorder(app, test_nodenet, resourcepath):
    from micropsi_core import runtime
    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    for i in range(3):
        netapi.create_node('Neuron', None, "testnode_%d" % i)
    recorder = netapi.add_gate_activation_recorder(group_definition={'nodespace_uid': nodespace.uid, 'node_name_prefix': 'testnode'}, name="recorder")
    for i in range(3):
        runtime.step_nodenet(test_nodenet)

    response = app.post_json('/rpc/remove_recorder', {
        'nodenet_uid': test_nodenet,
        'recorder_uid': recorder.uid,
    })
    assert_success(response)
    assert netapi.get_recorder(recorder.uid) is None


@pytest.mark.engine("theano_engine")
def test_get_recorders(app, test_nodenet):
    from micropsi_core import runtime
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    nodespace = netapi.get_nodespace(None)
    for i in range(3):
        netapi.create_node('Neuron', None, "testnode_%d" % i)
    runtime.step_nodenet(test_nodenet)
    recorder = netapi.add_gate_activation_recorder(group_definition={'nodespace_uid': nodespace.uid, 'node_name_prefix': 'testnode'}, name="recorder", interval=3)
    runtime.step_nodenet(test_nodenet)
    runtime.step_nodenet(test_nodenet)
    response = app.post_json('/rpc/get_recorders', {
        'nodenet_uid': test_nodenet
    })
    data = response.json_body['data'][recorder.uid]
    assert data["uid"] == recorder.uid
    assert data["name"] == 'recorder'
    assert data["interval"] == 3
    assert data["filename"] == recorder.filename
    assert data["current_index"] == 0
    assert data["first_step"] == 3
    assert data["classname"] == 'GateActivationRecorder'


@pytest.mark.engine("theano_engine")
def test_flow_modules(app, runtime, test_nodenet, resourcepath, default_world):
    import numpy as np
    from micropsi_core.world.worldadapter import ArrayWorldAdapter

    class SimpleArrayWA(ArrayWorldAdapter):
        def __init__(self, world):
            super().__init__(world)
            self.add_datasources(['a', 'b', 'c', 'd', 'e'])
            self.add_datatargets(['a', 'b', 'c', 'd', 'e'])
            self.update_data_sources_and_targets()

        def update_data_sources_and_targets(self):
            self.datatarget_feedback_values = np.copy(self.datatarget_values)
            self.datasources = np.random.rand(len(self.datasources))

    import os
    with open(os.path.join(resourcepath, 'nodetypes.json'), 'w') as fp:
        fp.write("""
    {"Double": {
        "flow_module": true,
        "name": "Double",
        "flowfunction_name" : "double",
        "inputs": ["inputs"],
        "outputs": ["outputs"]
    }}""")
    with open(os.path.join(resourcepath, 'nodefunctions.py'), 'w') as fp:
        fp.write("""
def double(inputs):
    return inputs * 2
""")

    app.set_auth()
    nodenet = runtime.nodenets[test_nodenet]
    netapi = nodenet.netapi
    worldadapter = SimpleArrayWA(runtime.worlds[default_world])
    nodenet.worldadapter_instance = worldadapter
    runtime.reload_native_modules()

    result = app.post_json('/rpc/add_node', {
        'nodenet_uid': test_nodenet,
        'type': 'Double',
        'position': [200, 200, 0],
        'nodespace': None,
        'name': 'Double'})
    assert_success(result)
    flow_uid = result.json_body['data']

    source = netapi.create_node("Neuron", None, "Source")
    source.activation = 1
    netapi.link(source, 'gen', source, 'gen')
    netapi.link(source, 'gen', netapi.get_node(flow_uid), 'sub')

    connect = {
        'nodenet_uid': test_nodenet,
        'flow_module_uid': flow_uid,
        'gateslot': 'outputs'
    }
    result = app.post_json('/rpc/connect_flow_module_to_worldadapter', connect)
    assert_success(result)
    connect['gateslot'] = 'inputs'
    result = app.post_json('/rpc/connect_flow_module_to_worldadapter', connect)
    assert_success(result)

    sources = np.zeros((5), dtype=nodenet.numpyfloatX)
    sources[:] = np.random.randn(*sources.shape)
    worldadapter.datasource_values = sources

    runtime.step_nodenet(test_nodenet)
    assert np.all(worldadapter.datatarget_values == sources * 2)

    result = app.post_json('/rpc/disconnect_flow_module_from_worldadapter', {
        'nodenet_uid': test_nodenet,
        'flow_module_uid': flow_uid,
        'gateslot': 'outputs'
    })
    assert_success(result)

    double2 = netapi.create_node("Double", None, "double2")
    netapi.link(source, 'gen', double2, 'sub')
    netapi.connect_flow_module_to_worldadapter(double2, 'outputs')
    result = app.post_json('/rpc/connect_flow_modules', {
        'nodenet_uid': test_nodenet,
        'source_node_uid': flow_uid,
        'source_output': 'outputs',
        'target_node_uid': double2.uid,
        'target_input': 'inputs'
    })
    assert_success(result)

    runtime.step_nodenet(test_nodenet)
    assert np.all(worldadapter.datatarget_values == sources * 4)

    result = app.post_json('/rpc/disconnect_flow_modules', {
        'nodenet_uid': test_nodenet,
        'source_node_uid': flow_uid,
        'source_output': 'outputs',
        'target_node_uid': double2.uid,
        'target_input': 'inputs'
    })

    runtime.step_nodenet(test_nodenet)
    assert np.all(worldadapter.datatarget_values == sources)
