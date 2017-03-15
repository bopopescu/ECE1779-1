This is a project for ECE1779 intro to cloud computing in uoft.

# Connect to Database Remotely
Create two new instances using existing ami.

'worker':  
security group configuration:    
worker_demo_security_group   
ssh 22 anywhere  
tcp 5000 anywhere  

external ip: 54.234.250.254  
internal ip: 172.31.54.162

change config.py database host to internal ip of your database if you are using security group. change it to external ip if you are using anywhere.

database:  
security group configuration:   
database_demo_security_group  
ssh 22 anywhere  
tcp 5000 anywhere  
mysql 3306 worker_demo_security_group  

external ip: 54.197.198.118  
internal ip: 172.31.48.24

first do sudo passwd to reset your UNIX password
than do sudo vim mysqld.cnf to
change configuration file in /etc/mysql/mysql.conf.d/mysqld.cnf  
bind-address = 0.0.0.0

restart database  
sudo /etc/init.d/mysql restart
