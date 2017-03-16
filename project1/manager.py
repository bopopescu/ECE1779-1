import boto3
import time
import logging
import mysql.connector
from datetime import datetime, timedelta
from operator import itemgetter

'''

database config

'''
db_config = {'user': 'ece1779',
         'password': 'secret',
         'host': '127.0.0.1',
         'database': 'project1_admin'}

'''

Functions for Database

'''

def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])

def get_db():
    db = connect_to_database()
    return db

'''

boto3 config

'''
ami_id = 'ami-811bb297'
ec2 = boto3.setup_default_session(region_name='us-east-1')
client = boto3.client('cloudwatch')
ec2 = boto3.resource('ec2')
metric_name = 'CPUUtilization'
namespace = 'AWS/EC2'
statistic = 'Average'

'''

Create Load Balancer

'''
elb = boto3.client('elb')

lb = elb.create_load_balancer(LoadBalancerName='myelb',
                               Listeners=[
                                       {
                                           'Protocol':'TCP',
                                           'LoadBalancerPort':5000,
                                           'InstanceProtocol':'TCP',
                                           'InstancePort':5000
                                       },
                                   ],
                               AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1e']
                            )

# add worker security groups to load balancer
elb.apply_security_groups_to_load_balancer(LoadBalancerName='myelb',
                                           SecurityGroups=['sg-e05d929f'])

# configure health check
health_check = elb.configure_health_check(LoadBalancerName='myelb',
                                          HealthCheck={
                                              'Target': 'TCP:5000',
                                              'Timeout':5,
                                              'Interval':10,
                                              'UnhealthyThreshold':5,
                                              'HealthyThreshold':5
                                            }
                                          )

# # create the database
# new_instance=ec2.create_instances(ImageId=database_ami_id_pre_created,
#                                   KeyName='ece1779_project1',
#                                   MinCount=1,
#                                   MaxCount=1,
#                                   InstanceType='t2.small',
#                                   Monitoring={'Enabled': True},
#                                   SecurityGroupIds=[
#                                         'sg-705b940f',
#                                     ]
#                                   )
# while list(ec2.instances.filter(InstanceIds=[new_instance[0].id]))[0].state.get('Name') != 'running':
#     i=1
# sql_host = list(ec2.instances.filter(InstanceIds=[new_instance[0].id]))[0].public_dns_name
# userdata = '''#cloud-config
#     runcmd:
#      - cd /home/ubuntu/Desktop/ece1779/
#      - ./venv/bin/python run.py {}
#     '''.format(sql_host)

# create the first worker
new_instance=ec2.create_instances(ImageId=ami_id,
                                  KeyName='ece1779_project1',
                                  MinCount=1,
                                  MaxCount=1,
                                  InstanceType='t2.small',
                                  Monitoring={'Enabled': True},
                                  # UserData =
                                  SecurityGroupIds=[
                                        'sg-e05d929f',
                                    ]
                                  )

# attach the first worker instance to the lb
attachinst = elb.register_instances_with_load_balancer(LoadBalancerName='myelb',
                                                      Instances=[
                                                          {
                                                              'InstanceId':new_instance[0].id
                                                          }
                                                       ])

while(1):
    #wait for instance to boot up
    time.sleep(10)
    instances = ec2.instances.filter(
    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    # compute the average cpu utilization now
    sum = 0.0
    num_of_instance = 0
    num_of_new_instance = 0
    num_of_old_instance = 0
    for instance in instances:
        cpu = client.get_metric_statistics(
            Period=1 * 60,
            StartTime=datetime.utcnow() - timedelta(seconds=60 * 60),
            EndTime=datetime.utcnow() - timedelta(seconds=0 * 60),
            MetricName=metric_name,
            Namespace=namespace,  # Unit='Percent',
            Statistics=[statistic],
            Dimensions=[{'Name': 'InstanceId', 'Value': instance.id}]
        )

        datapoints = cpu['Datapoints']
        if(datapoints!=[]):
            last_datapoint = sorted(datapoints, key=itemgetter('Timestamp'))[-1]
            print (last_datapoint)
            utilization = last_datapoint['Average']
            print (utilization)
            sum = sum + utilization
            num_of_instance = num_of_instance + 1
        else:
            continue
    if(num_of_instance!=0):
        utilization = sum / num_of_instance
    else:
        continue

    # fetch the parameters from the database

    cnx = get_db()
    cursor = cnx.cursor()
    query = '''SELECT * FROM config_parameters WHERE id =1
    '''
    cursor.execute(query)
    parameters=cursor.fetchone()

    if (parameters[3] != 1):
        num_of_new_instance = num_of_instance * (parameters[3]-1)
        # set back the database
        query = '''UPDATE config_parameters
                   SET expandratio = 1
                   WHERE id = 1
                '''
        cursor.execute(query)
        cnx.commit()

    if (parameters[4] != 1):
        num_of_old_instance = num_of_instance * (parameters[4]-1)/(parameters[4])
        # set back the database
        query = '''UPDATE config_parameters
                   SET shrinkratio = 1
                   WHERE id = 1
                '''
        cursor.execute(query)
        cnx.commit()

    if(utilization>parameters[1]):
        num_of_new_instance = num_of_new_instance + 1

    if(utilization<parameters[2]):
        num_of_old_instance = num_of_old_instance + 1

    if (num_of_new_instance!=0):
        for i in range(num_of_new_instance):
            new_instance = ec2.create_instances(ImageId=ami_id,
                                                KeyName='ece1779_project1',
                                                MinCount=1,
                                                MaxCount=1,
                                                InstanceType='t2.small',
                                                Monitoring={'Enabled': True},
                                                SecurityGroupIds=[
                                                    'sg-e05d929f',
                                                ]
                                                )
            attachinst = elb.register_instances_with_load_balancer(LoadBalancerName='myelb',
                                                                   Instances=[
                                                                       {
                                                                           'InstanceId': new_instance[0].id
                                                                       }
                                                                   ])

    if (num_of_old_instance!=0):
        instances = ec2.instances.filter(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

        instances = ec2.instances.filter(
            Filters=[{'Name':'instance.group-name', 'Values':['worker_demo_security_group']}]
        )
        i=0
        for instance in instances:
            elb.deregister_instances_from_load_balancer(LoadBalancerName='myelb',
                                                        Instances=[
                                                            {
                                                                'InstanceId': instance.id
                                                            }
                                                        ])
            instance.terminate()
            if (i >= num_of_old_instance):
                break

# delete load balancer
# elb.delete_load_balancer(LoadBalancerName='myelb')