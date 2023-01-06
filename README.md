# EC2 Deletion Based on Tags

This Python script is for safely deleting Amazon Elastic Compute Cloud (EC2) instances based on specified tags. It does this by creating a backup of the instances using Amazon Machine Images (AMIs) creation and then terminating the instances.

- The script includes the functionality to check and disable instance protections before terminate the instance.
- The AMIs created by the script will be given names in the format `EC2DeletionScript_<instance_id>_<timestamp>`.
- The script does not clean the AMIs after creating them. You will need to manually delete them if you no longer need.

# Prerequisites
- Python 3
- The boto3 and tabulate modules
- AWS credentials with permissions to create AMIs and terminate EC2 instances

# Installation
1. Install Python 3 if it is not already installed on your system.
2. Install the boto3 and tabulate modules:
```bash
pip install boto3 tabulate
```
3. Set up your AWS credentials as environment variables.
```bash
export AWS_ACCESS_KEY_ID=<ACCESS_KEY_ID>
export AWS_SECRET_ACCESS_KEY=<SECRET_ACCESS_KEY>
export AWS_REGION=<REGION>
```

# Usage
1. Specify tags to filter the instances you want to delete, For example, to delete only instances with the tag `Project` set to `Automation` and the tag `Environment` set to `Test` or `Dev`, you would specify the tags list as follows:
```bash
tags = [
    {'Name': 'tag:Project', 'Values': ['Automation']},
    {'Name': 'tag:Environment', 'Values': ['Test', 'Dev']}
]
```
2. Run the script:
```bash
python ec2_termination.py
```

3. The script will list all of the running instances and ask for confirmation before proceeding any actions.
