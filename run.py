import os
import paramiko
import requests
import json
from datetime import datetime, timezone, timedelta

def ssh_multiple_connections(hosts_info, command):
    results = []  # 存储每个主机的结果信息，包括用户和执行状态
    for host_info in hosts_info:
        hostname = host_info['hostname']
        username = host_info['username']
        password = host_info['password']
        result = {
            'hostname': hostname,
            'user': None,
            'status': '',
            'error': None
        }
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=hostname, port=22, username=username, password=password)
            
            # 执行whoami命令获取用户名
            stdin, stdout, stderr = ssh.exec_command(command)
            user = stdout.read().decode().strip()
            result['user'] = user
            
            # 以后台方式执行当前目录下的monitor脚本
            monitor_command = 'nohup ./monitor > /dev/null 2>&1 &'
            stdin, stdout, stderr = ssh.exec_command(monitor_command)
            
            # 读取可能的错误输出
            error = stderr.read().decode().strip()
            if error:
                result['status'] = 'error'
                result['error'] = error
            else:
                result['status'] = 'success'
            
            ssh.close()
        except Exception as e:
            result['status'] = 'connection_error'
            result['error'] = str(e)
        
        results.append(result)
    return results

# 读取主机信息
hosts_info = []
ssh_info_str = os.getenv('SSH_INFO', '[]')
hosts_info = json.loads(ssh_info_str)

# 执行SSH连接和监控脚本
command = 'whoami'
execution_results = ssh_multiple_connections(hosts_info, command)

# 收集用户列表和执行状态信息
user_list = [r['user'] for r in execution_results if r['user']]
status_details = []

for result in execution_results:
    host = result['hostname']
    if result['status'] == 'success':
        status_details.append(f"{host}: 已成功启动monitor脚本 (用户: {result['user']})")
    elif result['status'] == 'error':
        status_details.append(f"{host}: 执行monitor脚本出错 - {result['error']} (用户: {result['user']})")
    else:
        status_details.append(f"{host}: 连接失败 - {result['error']}")

# 准备通知内容
beijing_timezone = timezone(timedelta(hours=8))
time = datetime.now(beijing_timezone).strftime('%Y-%m-%d %H:%M:%S')
loginip = requests.get('https://api.ipify.org?format=json').json()['ip']

pushplus_token = os.getenv('PUSHPLUS_TOKEN')
title = 'serv00 服务器登录提醒'

# 构建包含详细状态的内容
content = f"登录时间：{time}<br>登录IP：{loginip}<br><br>执行结果：<br>"
content += "<br>".join(status_details)

# 发送通知
url = 'http://www.pushplus.plus/send'
data = {
    "token": pushplus_token,
    "title": title,
    "content": content
}
body = json.dumps(data).encode(encoding='utf-8')
headers = {'Content-Type': 'application/json'}

response = requests.post(url, data=body, headers=headers)
if response.status_code == 200:
    print("推送成功")
else:
    print(f"推送失败，状态码: {response.status_code}")
