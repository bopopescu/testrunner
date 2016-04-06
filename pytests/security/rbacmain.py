from membase.api.rest_client import RestConnection
import json
from security.rbacRoles import rbacRoles
import logger
log = logger.Logger.get_logger()
import base64
from security.rbacPermissionList import rbacPermissionList

class rbacmain:

    def __init__(self,
                master_ip=None,
                bucket_name=None,
                servers=None,
                cluster=None
            ):

        self.master_ip = master_ip
        self.bucket_name = bucket_name
        self.servers = servers
        self.cluster = cluster

    roles_admin = {'admin','ro_admin','cluster_admin'}
    roles_bucket = {'bucket_admin','views_admin','replication_admin'}

    def setUp(self):
        super(rbacmain, self).setUp()

    def tearDown(self):
        super(rbacmain, self).tearDown()


    def _retrive_all_user_role(self, user_list=None ):
        server = self.master_ip
        rest = RestConnection(server)
        url = "/settings/rbac/roles"
        api = rest.baseUrl + url
        status, content, header = rest._http_request(api, 'GET')
        print status
        print content
        print header
        return status, content, header

    def _retrieve_user_roles(self):
        rest = RestConnection(self.master_ip)
        url = "/settings/rbac/users"
        api = rest.baseUrl + url
        status, content, header = rest._http_request(api, 'GET')
        print status
        print content
        print header
        return status, content, header

    def _set_user_roles(self,user_name,payload):
        rest = RestConnection(self.master_ip)
        url = "settings/rbac/users/" + user_name
        #param = urllib.urlencode(payload)
        param = payload
        api = rest.baseUrl + url
        status, content, header = rest._http_request(api, 'PUT', param)
        print status
        print content
        print header
        return status, content, header

    def _delete_user(self,user_name):
        rest = RestConnection(self.master_ip)
        url = "/settings/rbac/users/" + user_name
        api = rest.baseUrl + url
        status, content, header = rest._http_request(api, 'DELETE')
        print status
        print content
        print header
        return status, content, header

    def _check_user_permission(self,user_name,password,permission_set):
        rest = RestConnection(self.master_ip)
        url = "pools/default/checkPermissions/"
        param = permission_set
        api = rest.baseUrl + url
        authorization = base64.encodestring('%s:%s' % (user_name, password))
        header =  {'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': 'Basic %s' % authorization,
                'Accept': '*/*'}
        status, content, header = rest._http_request(api, 'POST', params=param,headers=header)
        return status, content, header

    def _return_roles(self,user_role):
        final_roles = ""
        user_role_param = user_role.split(":")
        if len(user_role_param) == 1:
            final_roles = user_role_param[0]
        else:
            for role in user_role_param:
                final_roles = role + "," + final_roles
        return final_roles

    def _delete_user_from_roles(self,server):
        status, content, header = rbacmain(server)._retrieve_user_roles()
        content = json.loads(content)
        for temp in content:
            status, content, header = rbacmain(server)._delete_user(temp['id'])


    def _check_role_permission_validate_multiple(self,user_id,user_role,bucket_name,final_user_role,no_bucket_access=None,no_access_bucket_name=None):
        failure_list = []
        result = True
        user_details = user_id.split(":")
        final_roles = self._return_roles(user_role)
        payload = "name=" + user_details[0] + "&roles=" + final_roles
        status, content, header =  rbacmain(self.master_ip)._set_user_roles(user_name=user_details[0],payload=payload)
        master, expected, expected_neg = rbacRoles()._return_permission_set(final_user_role)

        if no_bucket_access:
            temp_dict =  expected_neg['permissionSet']
            bucket_name = no_access_bucket_name
        else:
            temp_dict =  expected['permissionSet']

        for permission in temp_dict.iterkeys():
            if "[<bucket_name>]" in permission:
                new_key = permission.replace("<bucket_name>",bucket_name)
                temp_dict[new_key] = temp_dict.pop(permission)
        permission_set = master['permissionSet'].split(',')
        for idx, permission in enumerate(permission_set):
            if "[<bucket_name>]" in permission:
                permission = permission.replace("<bucket_name>",bucket_name)
                permission_set[idx] = permission
        permission_str = ','.join(permission_set)
        status, content, header = rbacmain(self.master_ip)._check_user_permission(user_details[0],user_details[1],permission_str)
        content = json.loads(content)
        log.info ("Value of content is {0}".format(content))
        log.info ("Value of expected key is {0}".format(temp_dict))
        for item in temp_dict.iterkeys():
            if temp_dict[item] != content[item]:
                log.info ("Item is {0} -- Expected Value is - {1} and Actual Value is {2}".format(item,temp_dict[item],content[item]))
                result = False
        return result

    def _parse_set_user_respone(self,response):
        id = None
        name = None
        roles = {}
        response = json.loads(response)
        for value in response:
            for item in value:
                if item == 'roles':
                    roles = value[item][0]
                elif item == 'name':
                    name = value[item]
                elif item == 'id':
                    id = value[item]
        return id, name, roles

    def _parse_get_user_response(self,response,user_id,user_name,roles):
        print "Into user response"
        role_return = self._convert_user_roles_format(roles)
        result = False
        for user in response:
            if  user['id'] == user_id:
                if user['name'] == user_name:
                    result = True
                if [item for item in user['roles'] if item in role_return]:
                    result = True
                return result

    def _convert_user_roles_format(self,roles):
        print "convert user roles"
        role_return = []
        temp_roles = roles.split(":")
        for temp in temp_roles:
            if temp in self.roles_admin:
                role_return.append({'role':temp})
            else:
                temp1 = temp.split('[')
                role_return.append({'role':temp1[0],'bucket_name':(temp1[1])[:-1]})
        return role_return

    def returnUserList(self, Admin):
        Admin = (items.split(':') for items in Admin.split("?"))
        return list(Admin)


    def _test_box_statistics(self):
        process_dict = {}
        process_name = "beam.smp"
        process_data_collect = {}
        proc_detail = {}
        pid_detail = {}
        pid_det_list = []
        for server in self.servers:
            shell = RemoteMachineShellConnection(server)
            o,r = shell.execute_command("top -b -n 1 | grep " + process_name + " | cut -d ' ' -f2")
            process_dict[process_name] = o

        print process_dict

        for items in process_dict: # Process Name
            print process_dict[items]
            for item in process_dict[items]: # PID
                print item
                pid_detail[item]={}
            pid_det_list.append(pid_detail)
        proc_detail[items] = pid_det_list
        print proc_detail

        j=1
        for i in range(0,10):
            for items in process_dict: # Process Name
                #for item in process_dict[items]: # PID
                for i in range(0,len(items)):
                    o,r = shell.execute_command("top -b -n 1 -p " + item + " | cut -d ' ' -f3")
                    print proc_detail[items]
                    print proc_detail[items][i]
                    #print proc_detail[items][j][item]
                    #proc_detail[items][j][item].append(o)
                    #j=j+1
                j=0
        print proc_detail



    def get_role_permission(self,permission_set):
        permission_fun_map = {
        'cluster.admin.diag!read':"cluster_admin_diag_read",
        'cluster.admin.diag!write':'cluster_admin_diag_write',
        'cluster.admin.setup!write':'cluster_admin_setup_write',
        'cluster.admin.security!read':'cluster_admin_security_read',
        'cluster.admin.security!write':'cluster_admin_security_write',
        'cluster.admin.logs!read':'cluster_logs_read',
        'cluster.pools!read':"cluster_pools_read",
        'cluster.pools!write':'get_cluster_pools_write',
        'cluster.nodes!read':'cluster_nodes_read',
        'cluster.nodes!write':'cluster_nodes_write',
            'cluster.samples!read':'cluster_samples_read',
            'cluster.settings!read':'cluster_settings_read',
            'cluster.settings!write':'get_cluster_settings_write',
            'cluster.tasks!read':'get_cluster_tasks_read',
            'cluster.stats!read':'cluster_stats_read',
            'cluster.server_groups!read':'cluster_server_groups_read',
            'cluster.server_groups!write':'cluster_server_groups_write',
            'cluster.indexes!read':'cluster_indexes_read',
            'cluster.indexes!write':'cluster_indexes_write',
            'cluster.xdcr.settings!read':'cluster_xdcr_settings_read',
            'cluster.xdcr.settings!write':'cluster_xdcr_settings_write',
            'cluster.xdcr.remote_clusters!read':'cluster_xdcr_remote_clusters_read',
            'cluster.xdcr.remote_clusters!write':'cluster_xdcr_remote_clusters_write',
            'cluster.bucket[<bucket_name>]!create':'cluster_bucket_all_create',
            'cluster.bucket[<bucket_name>]!delete':'cluster_bucket_delete',
            'cluster.bucket[<bucket_name>]!compact':'cluster_bucket_compact',
            'cluster.bucket[<bucket_name>].settings!read':'cluster_bucket_settings_read',
            'cluster.bucket[<bucket_name>].settings!write':'cluster_bucket_settings_write',
            'cluster.bucket[<bucket_name>].password!read':'cluster_bucket_password_read', #Need to fix this"
            'cluster.bucket[<bucket_name>].data!read':'cluster_bucket_data_read', #Need to fix this"
            'cluster.bucket[<bucket_name>].data!write':'cluster_bucket_data_write',
            'cluster.bucket[<bucket_name>].recovery!read':'cluster_bucket_recovery_read',
            'cluster.bucket[<bucket_name>].recovery!write':'cluster_bucket_recovery_write',
            'cluster.bucket[<bucket_name>].views!read':'cluster_bucket_views_read',
            'cluster.bucket[<bucket_name>].views!write':'cluster_bucket_views_write',
            'cluster.bucket[<bucket_name>].xdcr!read':'cluster_bucket_xdcr_read',
            'cluster.bucket[<bucket_name>].xdcr!write':'cluster_bucket_xdcr_write',
            'cluster.bucket[<bucket_name>].xdcr!execute':'cluster_bucket_xdcr_execute',
            'cluster.admin.internal!all':'cluster_admin_internal_all'
        }
        permission = permission_set.split(":")
        perm_fun_map = permission_fun_map[permission[0]]
        print perm_fun_map
        print permission[1]
        print type(permission[1])
        if permission[1] == 'True':
            http_code = [200,201]
        else:
            http_code = [401,403]
        return perm_fun_map, http_code

    def test_perm_rest_api(self,permission,user,password,user_role):
        func_name,http_code = self.get_role_permission(permission)
        rest = RestConnection(self.master_ip)
        try:
            rest.create_bucket(bucket='default',ramQuotaMB=100)
        except:
            log.info("Default Bucket already exists")
        final_func = "rbacPermissionList()."+ func_name + "('" + user + "','" + password + "',host=self.master_ip,servers=self.servers,cluster=self.cluster,httpCode=" + str(http_code) +",user_role="+"'" + str(user_role)+"'" + ")"
        print final_func
        flag = eval(final_func)
        return flag


    def _check_role_permission_validate_multiple_rest_api(self,user_id,user_role,bucket_name,final_user_role,no_bucket_access=None,no_access_bucket_name=None):
        final_result = True
        user_details = user_id.split(":")
        final_roles = self._return_roles(user_role)
        payload = "name=" + user_details[0] + "&roles=" + final_roles
        status, content, header =  rbacmain(self.master_ip)._set_user_roles(user_name=user_details[0],payload=payload)
        master, expected, expected_neg = rbacRoles()._return_permission_set(final_user_role)


        if no_bucket_access:
            temp_dict =  expected_neg['permissionSet']
            bucket_name = no_access_bucket_name
        else:
            temp_dict =  expected['permissionSet']

        f = open(user_role,'w')
        f.close()

        for key,value in temp_dict.iteritems():
            temp_str = str(key) + ":" + str(value)
            result = self.test_perm_rest_api(temp_str,user_details[0],'password',user_role)

        with open(user_role, "r") as ins:
            log.info(" -------- FINAL RESULT for role - {0} ---------".format(user_role))
            array = []
            for line in ins:
                array.append(line)
                log.info(line)
            log.info("----------END FINAL RESULT ------------")

        for item in array:
            json_acceptable_string = item.replace("'", "\"")
            item = json.loads(json_acceptable_string)
            if item['final_result'] == 'False':
                final_result = False

        return final_result


        '''
        f = open(user_role,'r')
        final_output = f.read()
        f.close()
        log.info(" -------- FINAL RESULT for role - {0} ---------".format(user_role))
        log.info(final_output)
        log.info("----------END FINAL RESULT ------------")
        return final_result
        '''''


        '''
        for permission in temp_dict.iterkeys():
            if "[<bucket_name>]" in permission:
                new_key = permission.replace("<bucket_name>",bucket_name)
                temp_dict[new_key] = temp_dict.pop(permission)
        permission_set = master['permissionSet'].split(',')
        for idx, permission in enumerate(permission_set):
            if "[<bucket_name>]" in permission:
                permission = permission.replace("<bucket_name>",bucket_name)
                permission_set[idx] = permission
        permission_str = ','.join(permission_set)
        status, content, header = rbacmain(self.master_ip)._check_user_permission(user_details[0],user_details[1],permission_str)
        content = json.loads(content)
        log.info ("Value of content is {0}".format(content))

        for item in temp_dict.iterkeys():
            if temp_dict[item] != content[item]:

                log.info ("Item is {0} -- Expected Value is - {1} and Actual Value is {2}".format(item,temp_dict[item],content[item]))
                result = False
        return result
        '''