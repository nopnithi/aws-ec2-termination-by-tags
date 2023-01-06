import boto3
from botocore.exceptions import ClientError
import sys
import time
import datetime
import tabulate


def display_data(data):
    """
    Display the data in a tabular format.

    Parameters:
        data (list): A list of dictionaries. The keys of the dictionaries will be used as the headers.
    """
    try:
        # Get the keys from the first dictionary in the list
        headers = data[0].keys()
        # Create a list of lists with the values in the correct order
        rows = [[item[header] for header in headers] for item in data]
        print(tabulate.tabulate(rows, headers=headers))
    except:
        pass


def get_tag_value(tag_key, tags):
    """
    Get the value of a tag with the specified key from a list of tags.
    
    Parameters:
        tag_key (str): The key of the tag to get the value of.
        tags (list): The list of tags to search through.
    
    Returns:
        str: The value of the tag with the specified key, or 'N/A' if the tag is not found.
    """
    if isinstance(tags, list):
        for tag in tags:
            if tag['Key'] == tag_key:
                return tag['Value']
    return 'N/A'


def get_protections_status(ec2_client, instance_id):
    """
    Get the termination protection and stop protection status of an instance.
    
    Parameters:
        ec2_client (boto3.client): The EC2 client to use for the operation.
        instance_id (str): The ID of the instance to get the protection status of.
    
    Returns:
        dict: A dictionary containing the termination protection and stop protection status of the instance.
    """
    # Get the termination protection status of the instance
    response = ec2_client.describe_instance_attribute(
        Attribute='disableApiTermination',
        InstanceId=instance_id
    )
    termination_protection_status = response['DisableApiTermination']['Value']
    # Get the stop protection status of the instance
    response = ec2_client.describe_instance_attribute(
        Attribute='disableApiStop',
        InstanceId=instance_id
    )
    stop_protection_status = response['DisableApiStop']['Value']
    return {
        'termination': termination_protection_status,
        'stop': stop_protection_status
    }


def disable_instance_protections(ec2_client, instance_id, disable_termination=False, disable_stop=False):
    """
    Disable the termination protection and/or stop protection status of an instance.
    
    Parameters:
        ec2_client (boto3.client): The EC2 client to use for the operation.
        instance_id (str): The ID of the instance to disable protections for.
        disable_termination (bool): Set to True to disable termination protection (default: False).
        disable_stop (bool): Set to True to disable stop protection (default: False).
    """
    # Disable the termination protection
    if disable_termination:
        ec2_client.modify_instance_attribute(
            InstanceId=instance_id,
            DisableApiTermination={'Value': False}
        )
    # Disable the stop protection
    if disable_stop:
        ec2_client.modify_instance_attribute(
            InstanceId=instance_id,
            DisableApiStop={'Value': False}
        )


def list_instances(ec2_client, tags):
    """
    Get a list of instances in the specified region with the specified tags.
    
    Parameters:
        ec2_client (boto3.client): The EC2 client to use for the operation.
        tags (list): The list of tags to filter the instances by.
    
    Returns:
        list: A list of dictionaries, each containing the ID, name, and state of an instance.
    """
    response = ec2_client.describe_instances(Filters=tags)
    reservations = response['Reservations']
    while 'NextToken' in response:
        response = ec2_client.describe_instances(NextToken=response['NextToken'])
        reservations.extend(response['Reservations'])
    instances = []
    for reservation in reservations:
        for instance in reservation['Instances']:
            instance_name = get_tag_value('Name', instance.get('Tags', []))
            protections_status = get_protections_status(ec2_client, instance['InstanceId'])
            if instance['State']['Name'] in ['running', 'stopping', 'stopped']:
                instances.append(
                    {
                        'name': instance_name,
                        'id': instance['InstanceId'],
                        'state': instance['State']['Name'],
                        'termination_protection': protections_status['termination'],
                        'stop_protection': protections_status['stop']
                    })
    return instances


def create_ami(ec2_client, instance):
    """
    Create an Amazon Machine Image (AMI) from an instance.

    Parameters:
    ec2_client (boto3.client): The EC2 client to use for the operation.
    instance (dict): A dictionary containing the ID and name of the instance to create the AMI from.

    Returns:
    dict: A dictionary containing the instance information of the created AMI.
    """
    # Generate the AMI name and description
    now = datetime.datetime.now()
    ami_name = f'EC2DeletionScript_{instance["id"]}_{now.strftime("%Y%m%d%H%M%S")}'
    ami_description = f'AMI created on {now.strftime("%Y-%m-%d %H:%M:%S")} by EC2 deletion script.'
    # Creating the AMI
    try:
        print(f'Creating AMI from instance {instance["name"]} ({instance["id"]})...')
        response = ec2_client.create_image(
            InstanceId=instance['id'],
            Name=ami_name,
            Description=ami_description,
            NoReboot=True,
            DryRun=False
        )
    # If fails, retry once
    except ClientError as e:
        print('Creating AMI is failed, retrying...')
        print(e)
        time.sleep(5)
        try:
            print(f'Creating AMI from instance {instance["name"]} ({instance["id"]})...')
            response = ec2_client.create_image(
                InstanceId=instance['id'],
                Name=ami_name,
                Description=ami_description,
                NoReboot=True,
                DryRun=False
            )
        except ClientError as e:
            print('Creating AMI is failed, again...')
            print(e)
            print(f'Skipped this instance {instance["name"]} ({instance["id"]}).')
            return {
                'instance_name': instance['name'],
                'instance_id': instance['id'],
                'ami_id': ami_id,
                'ami_name': ami_name,
                'backup_completed': False
            }

    # Get the AMI ID
    ami_id = response['ImageId']

    # Add a Name tag to the AMI
    ec2_client.create_tags(
        Resources=[ami_id],
        Tags=[{'Key': 'Name', 'Value': ami_name}]
    )
    print(f'AMI creation complete.')
    return {
        'instance_name': instance['name'],
        'instance_id': instance['id'],
        'ami_id': ami_id,
        'ami_name': ami_name,
        'backup_completed': True
    }


def backup_instances(ec2_client, instances):
    """
    Backup instances by creating Amazon Machine Images (AMIs).

    Parameters:
    ec2_client (boto3.client): The EC2 client to use for the operations.
    instances (list): A list of dictionaries, each containing the ID and name of an instance to create an AMI from.

    Returns:
    list: A list of dictionaries, each containing the instance ID, instance name, and status of the AMI creation.
    """
    results = []
    for instance in instances:
        result = create_ami(ec2_client, instance)
        results.append(result)
    return results


def terminate_instances(ec2_client, instances):
    """
    Terminate a list of instances.

    Parameters:
    ec2_client (boto3.client): The EC2 client to use for the operation.
    instances (list): A list of dictionaries, each containing the ID and name of an instance to terminate.

    Returns:
    list: A list of dictionaries, each containing the instance ID, instance name, and status of the termination.
    """
    results = []
    # Terminate the instances
    for instance in instances:
        status = False
        try:
            print(f'Terminating {instance["instance_name"]} ({instance["instance_id"]})...')
            response = ec2_client.terminate_instances(InstanceIds=[instance['instance_id']])
            time.sleep(3)
            result = response['TerminatingInstances'][0]
            # If the instance is successfully shutting down, change the status to True
            if result['CurrentState']['Name'] == 'shutting-down':
                print('EC2 termination complete.')
                status = True
            else:
                print('Failed to terminate.')
            results.append({
                'instance_name': instance["instance_name"],
                'instance_id': instance["instance_id"],
                'terminate_completed': status})
        except Exception as e:
            print('Failed to terminate.')
            results.append({
                'instance_name': instance["instance_name"],
                'instance_id': instance["instance_id"],
                'terminate_completed': status})
    return results


def main():
    print('Starting EC2 deletion script...')
    # Set up the EC2 client
    ec2_client = boto3.client('ec2')

    # Set the tags to filter the instances
    tags = [
        {'Name': 'tag:Project', 'Values': ['Automation']},
        {'Name': 'tag:Environment', 'Values': ['Test', 'Dev']}
    ]

    # Get a list of instances with the specified tags
    print('\nListing instances...\n')
    instances = list_instances(ec2_client, tags)
    display_data(instances)
    print(f'\nTotal: {len(instances)}')

    if instances:
        # Check protections status
        print('\nChecking termination protection...\n')
        protections = False
        for instance in instances:
            if instance['termination_protection'] or instance['stop_protection']:
                protections = True
                break
        if protections:
            print('Found some protections are enabled on some instances.')
            user_input = input('Are you want to disable "all protections" for all instances? (y/n)\n> ')
            if user_input.lower() == 'y':
                for instance in instances:
                    disable_instance_protections(
                        ec2_client, instance['id'],
                        disable_termination=True, disable_stop=True
                    )
                # Get a list of instances to check protections status
                print('\nListing instances (again)...\n')
                instances = list_instances(ec2_client, tags)
                display_data(instances)
            else:
                print('Come back if you already disabled protections on all instances.')
                sys.exit()
        else:
            print('Not found any protections are enabled on all instances.')

        # Wait for the user to confirm before proceeding
        input('\nPress enter to continue to backup the instances...')

        # Create AMIs of the instances
        print('\nBacking up instances...\n')
        backup_results = backup_instances(ec2_client, instances)
        print('')
        display_data(backup_results)

        # Wait for the user to confirm before proceeding
        input('\nPress enter to continue to terminate the instances...')

        # Terminate the instances that have been successfully backed up
        print('\nTerminating instances that have already been backed up...\n')
        terminate_results = terminate_instances(ec2_client, backup_results)
        print('')
        display_data(terminate_results)


if __name__ == "__main__":
    main()
